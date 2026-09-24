from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from orientation.router import router as orientation_router

DEMO_INDEX = Path(__file__).resolve().parent.parent / "demo" / "index.html"
MEDIA_DIR = DEMO_INDEX.parent / "media"
MEDIA_DIR.mkdir(exist_ok=True)

app = FastAPI(
    title="ISO-PULSE HR Internal Channel",
    version="0.1.0",
)
app.include_router(
    orientation_router,
    prefix="/api/v1/hr/orientation",
    tags=["orientation"],
)
app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")


@app.get("/demo", include_in_schema=False)
def demo_page() -> FileResponse:
    return FileResponse(DEMO_INDEX, media_type="text/html; charset=utf-8")
