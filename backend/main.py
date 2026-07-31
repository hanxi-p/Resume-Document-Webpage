from pathlib import Path
import hmac
import os
import secrets

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
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
RESUME_CODE_FILE = Path(__file__).resolve().parent / ".resume_access_code"
RESUME_COOKIE = "resume_access"
RESUME_SESSION_TOKEN = secrets.token_urlsafe(32)

# Serve static files
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class ResumeAccessRequest(BaseModel):
    password: str


def get_resume_access_code() -> str:
    """Read the private resume password without storing it in source control."""
    code = os.getenv("RESUME_ACCESS_CODE", "").strip()
    if code:
        return code
    if RESUME_CODE_FILE.exists():
        return RESUME_CODE_FILE.read_text(encoding="utf-8").strip()
    return ""


def has_resume_access(request: Request) -> bool:
    supplied = request.cookies.get(RESUME_COOKIE, "")
    return bool(supplied) and hmac.compare_digest(supplied, RESUME_SESSION_TOKEN)


# ─── Front Page ───────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def root():
    html_path = FRONTEND_DIR / "index.html"
    if not html_path.exists():
        return HTMLResponse("<h1>正在建设中...</h1>")
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


# ─── Resume ──────────────────────────────────────────────
@app.get("/api/resume-auth")
async def resume_auth_status(request: Request):
    if not has_resume_access(request):
        raise HTTPException(status_code=401, detail="需要验证")
    return {"ok": True}


@app.post("/api/resume-auth")
async def resume_auth(payload: ResumeAccessRequest):
    expected = get_resume_access_code()
    if not expected:
        raise HTTPException(status_code=503, detail="简历访问密码尚未配置")
    if not hmac.compare_digest(payload.password.strip(), expected):
        raise HTTPException(status_code=401, detail="密码错误")

    response = JSONResponse({"ok": True})
    response.set_cookie(
        key=RESUME_COOKIE,
        value=RESUME_SESSION_TOKEN,
        max_age=8 * 60 * 60,
        httponly=True,
        samesite="strict",
        secure=False,
    )
    return response


@app.get("/jianli.html", response_class=HTMLResponse)
async def jianli(request: Request):
    if not has_resume_access(request):
        raise HTTPException(status_code=401, detail="请先验证简历访问密码")
    html_path = FRONTEND_DIR / "jianli.html"
    if not html_path.exists():
        return HTMLResponse("<h1>简历正在准备中...</h1>")
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.get("/resume-assets/{filename:path}")
async def resume_asset(filename: str, request: Request):
    if not has_resume_access(request):
        raise HTTPException(status_code=401, detail="请先验证简历访问密码")
    root = RESUME_ASSETS_DIR.resolve()
    asset_path = (root / filename).resolve()
    if root not in asset_path.parents or not asset_path.is_file():
        raise HTTPException(status_code=404, detail="资源不存在")
    return FileResponse(asset_path)


# ─── 技术专题页 (通配路由) ────────────────────────────
@app.get("/{name}.html", response_class=HTMLResponse)
async def tech_page(name: str):
    html_path = FRONTEND_DIR / f"{name}.html"
    if not html_path.exists():
        return HTMLResponse("<h1>页面不存在</h1>", status_code=404)
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


# ─── API Health ───────────────────────────────────────────
@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "resume-portfolio"}


# ─── Demo: 运行计算脚本 ──────────────────────────────────
@app.post("/api/demo/run")
async def run_demo(name: str = ""):
    if not name:
        return {"error": "请指定演示名称"}
    return {"status": "running", "demo": name, "result": "脚本执行中..."}


# ─── List Demos ──────────────────────────────────────────
@app.get("/api/demos")
async def list_demos():
    scripts = []
    if SCRIPTS_DIR.exists():
        for f in SCRIPTS_DIR.glob("*.py"):
            scripts.append({"name": f.stem, "file": f.name})
    return {"demos": scripts}


# ─── 启动 ────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
