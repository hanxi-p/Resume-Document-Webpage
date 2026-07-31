from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

app = FastAPI(title="Resume Portfolio Template")

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
STATIC_DIR = FRONTEND_DIR / "static"
SCRIPTS_DIR = BASE_DIR / "scripts"

# Serve static files
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ─── Front Page ───────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def root():
    html_path = FRONTEND_DIR / "index.html"
    if not html_path.exists():
        return HTMLResponse("<h1>正在建设中...</h1>")
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


# ─── Resume ──────────────────────────────────────────────
@app.get("/jianli.html", response_class=HTMLResponse)
async def jianli():
    html_path = FRONTEND_DIR / "jianli.html"
    if not html_path.exists():
        return HTMLResponse("<h1>简历正在准备中...</h1>")
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


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
