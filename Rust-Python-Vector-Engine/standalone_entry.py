import os
import sys
import uvicorn

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, ".."))
workspace_root = os.path.abspath(os.path.join(current_dir, "../.."))

if current_dir not in sys.path:
    sys.path.insert(0, current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)

from api_server.app.main import app

def main():
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "127.0.0.1")
    print(f"🚀 [Standalone Production Engine] Sunucu {host}:{port} üzerinde başlatılıyor...")
    uvicorn.run(app, host=host, port=port, log_level="info")

if __name__ == "__main__":
    main()
