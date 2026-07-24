from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware

from app.main import app


DIST_DIR = Path(__file__).resolve().parents[2] / "web" / "dist"
ASSETS_DIR = DIST_DIR / "assets"

app.add_middleware(GZipMiddleware, minimum_size=1024, compresslevel=6)
app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="production-assets")


@app.get("/{resource_path:path}", include_in_schema=False)
def production_frontend(resource_path: str):
    requested_file = (DIST_DIR / resource_path).resolve()
    if requested_file.is_relative_to(DIST_DIR) and requested_file.is_file():
        return FileResponse(requested_file)
    index_file = DIST_DIR / "index.html"
    if index_file.is_file():
        return FileResponse(index_file, headers={"Cache-Control": "no-cache"})
    raise HTTPException(status_code=503, detail="前端生产文件尚未构建")
