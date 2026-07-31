import base64
import hashlib
import hmac
import mimetypes
import os
from pathlib import Path
import re
import secrets
import sqlite3
import threading
import time

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

app = FastAPI(title="Resume Portfolio Template")

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
STATIC_DIR = FRONTEND_DIR / "static"
RESUME_ASSETS_DIR = FRONTEND_DIR / "resume-assets"
SCRIPTS_DIR = BASE_DIR / "scripts"
BACKEND_DIR = Path(__file__).resolve().parent
RESUME_HASH_FILE = BACKEND_DIR / ".resume_access_hash"
LEGACY_CODE_FILE = BACKEND_DIR / ".resume_access_code"
SECURITY_DB_FILE = BACKEND_DIR / ".security_state.sqlite3"

RESUME_COOKIE = "resume_access"
PBKDF2_ITERATIONS = 600_000
MAX_FAILURES = 5
FAILURE_WINDOW_SECONDS = 24 * 60 * 60
LOCK_SECONDS = 24 * 60 * 60
SESSION_TTL_SECONDS = 2 * 60
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "0") == "1"
RESUME_SESSIONS: dict[str, tuple[str, float]] = {}
SESSION_LOCK = threading.Lock()

STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class ResumeAccessRequest(BaseModel):
    password: str


def hash_password(password: str, *, iterations: int = PBKDF2_ITERATIONS) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return "pbkdf2_sha256${}${}${}".format(
        iterations,
        base64.urlsafe_b64encode(salt).decode("ascii"),
        base64.urlsafe_b64encode(digest).decode("ascii"),
    )


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations_text, salt_text, digest_text = stored_hash.strip().split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_text)
        salt = base64.urlsafe_b64decode(salt_text.encode("ascii"))
        expected = base64.urlsafe_b64decode(digest_text.encode("ascii"))
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(actual, expected)
    except (TypeError, ValueError):
        return False


def write_password_hash(stored_hash: str) -> None:
    temp_path = RESUME_HASH_FILE.with_suffix(".tmp")
    temp_path.write_text(stored_hash, encoding="utf-8")
    temp_path.replace(RESUME_HASH_FILE)


def migrate_legacy_password() -> None:
    """Convert the former plaintext file once, verify it, then remove it."""
    if RESUME_HASH_FILE.exists() or not LEGACY_CODE_FILE.exists():
        return
    password = LEGACY_CODE_FILE.read_text(encoding="utf-8").strip()
    if not password:
        raise RuntimeError("旧简历密码文件为空")
    stored_hash = hash_password(password)
    write_password_hash(stored_hash)
    if not verify_password(password, RESUME_HASH_FILE.read_text(encoding="utf-8")):
        raise RuntimeError("简历密码哈希迁移校验失败")
    LEGACY_CODE_FILE.unlink()


def init_security_db() -> None:
    with sqlite3.connect(SECURITY_DB_FILE, timeout=5) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS auth_failures (
                ip TEXT PRIMARY KEY,
                failures INTEGER NOT NULL,
                first_failure REAL NOT NULL,
                locked_until REAL NOT NULL DEFAULT 0
            )
            """
        )


def get_client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def get_locked_until(ip: str, now: float | None = None) -> float:
    current_time = now if now is not None else time.time()
    with sqlite3.connect(SECURITY_DB_FILE, timeout=5) as connection:
        row = connection.execute(
            "SELECT failures, first_failure, locked_until FROM auth_failures WHERE ip = ?",
            (ip,),
        ).fetchone()
        if not row:
            return 0
        _, first_failure, locked_until = row
        if locked_until > current_time:
            return float(locked_until)
        if locked_until or current_time - first_failure >= FAILURE_WINDOW_SECONDS:
            connection.execute("DELETE FROM auth_failures WHERE ip = ?", (ip,))
        return 0


def record_failed_attempt(ip: str, now: float | None = None) -> tuple[int, float]:
    current_time = now if now is not None else time.time()
    with sqlite3.connect(SECURITY_DB_FILE, timeout=5) as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT failures, first_failure, locked_until FROM auth_failures WHERE ip = ?",
            (ip,),
        ).fetchone()
        if not row or row[2] or current_time - row[1] >= FAILURE_WINDOW_SECONDS:
            failures = 1
            first_failure = current_time
        else:
            failures = int(row[0]) + 1
            first_failure = float(row[1])
        locked_until = current_time + LOCK_SECONDS if failures >= MAX_FAILURES else 0
        connection.execute(
            """
            INSERT INTO auth_failures (ip, failures, first_failure, locked_until)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(ip) DO UPDATE SET
                failures = excluded.failures,
                first_failure = excluded.first_failure,
                locked_until = excluded.locked_until
            """,
            (ip, failures, first_failure, locked_until),
        )
    return failures, locked_until


def clear_failed_attempts(ip: str) -> None:
    with sqlite3.connect(SECURITY_DB_FILE, timeout=5) as connection:
        connection.execute("DELETE FROM auth_failures WHERE ip = ?", (ip,))


def create_resume_session(ip: str) -> str:
    token = secrets.token_urlsafe(32)
    now = time.time()
    with SESSION_LOCK:
        expired_tokens = [
            key for key, (_, expires_at) in RESUME_SESSIONS.items() if expires_at <= now
        ]
        for key in expired_tokens:
            RESUME_SESSIONS.pop(key, None)
        RESUME_SESSIONS[token] = (ip, now + SESSION_TTL_SECONDS)
    return token


def consume_resume_session(request: Request) -> bool:
    token = request.cookies.get(RESUME_COOKIE, "")
    if not token:
        return False
    with SESSION_LOCK:
        session = RESUME_SESSIONS.pop(token, None)
    if not session:
        return False
    session_ip, expires_at = session
    return expires_at > time.time() and hmac.compare_digest(session_ip, get_client_ip(request))


def embed_resume_assets(html: str) -> str:
    root = RESUME_ASSETS_DIR.resolve()
    attribute_pattern = re.compile(
        r'(?P<attr>src|href)=["\'](?P<path>/?resume-assets/[^"\']+)["\']'
    )
    css_url_pattern = re.compile(
        r'url\((?P<quote>["\']?)(?P<path>/?resume-assets/[^\)"\']+)(?P=quote)\)'
    )

    def build_data_url(path: str) -> str | None:
        relative_path = path.removeprefix("/").removeprefix("resume-assets/")
        asset_path = (root / relative_path).resolve()
        if root not in asset_path.parents or not asset_path.is_file():
            return None
        mime_type = mimetypes.guess_type(asset_path.name)[0] or "application/octet-stream"
        encoded = base64.b64encode(asset_path.read_bytes()).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"

    def replace_attribute(match: re.Match[str]) -> str:
        data_url = build_data_url(match.group("path"))
        return f'{match.group("attr")}="{data_url}"' if data_url else match.group(0)

    def replace_css_url(match: re.Match[str]) -> str:
        data_url = build_data_url(match.group("path"))
        return f'url("{data_url}")' if data_url else match.group(0)

    return css_url_pattern.sub(replace_css_url, attribute_pattern.sub(replace_attribute, html))


migrate_legacy_password()
init_security_db()


@app.middleware("http")
async def enforce_ip_lock(request: Request, call_next):
    locked_until = get_locked_until(get_client_ip(request))
    if not locked_until:
        return await call_next(request)

    retry_after = max(1, int(locked_until - time.time()))
    detail = "该IP因连续5次密码错误已被禁止访问24小时"
    if request.url.path.startswith("/api/"):
        response = JSONResponse({"detail": detail}, status_code=429)
    else:
        response = HTMLResponse(
            "<!doctype html><html lang='zh-CN'><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>访问已锁定</title><body style='margin:0;min-height:100vh;display:grid;place-items:center;"
            "font-family:system-ui;background:#102238;color:#fff;text-align:center'>"
            "<main><h1>访问已锁定</h1><p>该IP连续5次输入错误，24小时内无法访问本站。</p></main></body></html>",
            status_code=429,
        )
    response.headers["Retry-After"] = str(retry_after)
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/", response_class=HTMLResponse)
async def root():
    html_path = FRONTEND_DIR / "index.html"
    if not html_path.exists():
        return HTMLResponse("<h1>正在建设中...</h1>")
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.post("/api/resume-auth")
async def resume_auth(payload: ResumeAccessRequest, request: Request):
    if not RESUME_HASH_FILE.exists():
        raise HTTPException(status_code=503, detail="简历访问密码尚未配置")

    ip = get_client_ip(request)
    stored_hash = RESUME_HASH_FILE.read_text(encoding="utf-8").strip()
    if not verify_password(payload.password.strip(), stored_hash):
        failures, locked_until = record_failed_attempt(ip)
        if locked_until:
            response = JSONResponse(
                {"detail": "密码错误次数已达5次，该IP将在24小时内无法访问整个网站"},
                status_code=429,
            )
            response.headers["Retry-After"] = str(LOCK_SECONDS)
            return response
        remaining = MAX_FAILURES - failures
        raise HTTPException(status_code=401, detail=f"密码错误，还可尝试{remaining}次")

    clear_failed_attempts(ip)
    session_token = create_resume_session(ip)
    response = JSONResponse({"ok": True})
    response.set_cookie(
        key=RESUME_COOKIE,
        value=session_token,
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        samesite="strict",
        secure=COOKIE_SECURE,
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/jianli.html", response_class=HTMLResponse)
async def jianli(request: Request):
    if not consume_resume_session(request):
        raise HTTPException(status_code=401, detail="请重新输入简历访问密码")
    html_path = FRONTEND_DIR / "jianli.html"
    if not html_path.exists():
        return HTMLResponse("<h1>简历正在准备中...</h1>")
    response = HTMLResponse(embed_resume_assets(html_path.read_text(encoding="utf-8")))
    response.delete_cookie(RESUME_COOKIE)
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/{name}.html", response_class=HTMLResponse)
async def tech_page(name: str):
    html_path = FRONTEND_DIR / f"{name}.html"
    if not html_path.exists():
        return HTMLResponse("<h1>页面不存在</h1>", status_code=404)
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "resume-portfolio"}


@app.post("/api/demo/run")
async def run_demo(name: str = ""):
    if not name:
        return {"error": "请指定演示名称"}
    return {"status": "running", "demo": name, "result": "脚本执行中..."}


@app.get("/api/demos")
async def list_demos():
    scripts = []
    if SCRIPTS_DIR.exists():
        for script_path in SCRIPTS_DIR.glob("*.py"):
            scripts.append({"name": script_path.stem, "file": script_path.name})
    return {"demos": scripts}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
