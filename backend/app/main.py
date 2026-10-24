from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api import commesse, fonti, generale
from .config import settings
from .db import Base, SessionLocal, engine
from .seed import carica_esempio


@asynccontextmanager
async def avvio(_: FastAPI):
    Base.metadata.create_all(engine)
    if settings.carica_dati_esempio:
        with SessionLocal() as db:
            carica_esempio(db)
    yield


app = FastAPI(title="Registro Commesse", version="1.0.0", lifespan=avvio)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"])
app.include_router(generale.router)
app.include_router(commesse.router)
app.include_router(fonti.router)


@app.get("/api/salute")
def salute():
    return {"ok": True}


# In produzione il backend serve anche il frontend compilato (frontend/dist)
DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = DIST / path
        return FileResponse(f if path and f.is_file() else DIST / "index.html")
