import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from api_server.app.api.v1.vectors import router as vectors_router
from api_server.app.api.v1.database import router as database_router
from api_server.app.api.v1.rag import router as rag_router
from api_server.app.api.v1.agent import router as agent_router
from api_server.app.api.v1.memory import router as memory_router
from api_server.app.api.v1.workspace import router as workspace_router
from api_server.app.api.v1.models import router as models_router
from api_server.app.api.v1.license import router as license_router
from api_server.app.core.config import init_database, db, DB_FILE

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 [1/2] Veritabanı başlatılıyor...")
    init_database()
    yield
    print("🛑 [2/2] Sunucu kapatılıyor, veritabanı diske kaydediliyor...")
    db.save_to_disk(DB_FILE)

app = FastAPI(
    title="Unified Rust-AI Engine (Vector DB, LLM RAG, Autonomous Agent & Memory API)",
    description="Rust (PyO3 + HNSW + WAL) Vektör Veritabanı, Rust-LLM-Engine (SIMD Inference), ReAct Ajan ve Kişiselleştirilmiş Hafıza Platformu",
    version="1.0.0",
    lifespan=lifespan
)

import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

STATIC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../static"))
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

DESKTOP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../desktop_app/src"))
if os.path.exists(DESKTOP_DIR):
    app.mount("/desktop", StaticFiles(directory=DESKTOP_DIR, html=True), name="desktop")
    styles_dir = os.path.join(DESKTOP_DIR, "styles")
    js_dir = os.path.join(DESKTOP_DIR, "js")
    if os.path.exists(styles_dir):
        app.mount("/styles", StaticFiles(directory=styles_dir), name="desktop_styles")
    if os.path.exists(js_dir):
        app.mount("/js", StaticFiles(directory=js_dir), name="desktop_js")


app.include_router(vectors_router)
app.include_router(database_router)
app.include_router(rag_router)
app.include_router(agent_router)
app.include_router(memory_router)
app.include_router(workspace_router)
app.include_router(models_router)
app.include_router(license_router)

@app.get("/")
def read_root():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {
        "status": "online",
        "engine": "VectorIndex Rust HNSW Modular Engine",
        "total_documents": db.len()
    }

@app.get("/app")
def read_desktop_view():
    desktop_index = os.path.join(DESKTOP_DIR, "index.html")
    if os.path.exists(desktop_index):
        return FileResponse(desktop_index)
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


if __name__ == "__main__":
    print("🚀 Rust Vektör Veritabanı Clean Architecture REST API Başlatılıyor...")
    uvicorn.run("api_server.app.main:app", host="127.0.0.1", port=8000, reload=True)
