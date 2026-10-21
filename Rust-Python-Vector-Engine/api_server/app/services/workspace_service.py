import os
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

class WorkspaceService:
    def __init__(self):
        self.active_workspace_path: Optional[str] = None
        # Varsayılan çalışma alanı kökü
        self.default_base = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "../../../..")
        )

    def get_effective_workspace(self) -> str:
        """Aktif bir proje bağlıysa onun yolunu, değilse varsayılan kökü döner."""
        return self.active_workspace_path or self.default_base

    def bind_workspace(self, path: str) -> Dict[str, Any]:
        """Kullanıcının seçtiği bir proje klasörünü aktif çalışma alanına bağlar."""
        abs_path = os.path.abspath(path) if os.path.isabs(path) else os.path.abspath(os.path.join(self.default_base, path))

        if not os.path.exists(abs_path):
            raise FileNotFoundError(f"Belirtilen proje dizini bulunamadı: {path}")

        if not os.path.isdir(abs_path):
            raise NotADirectoryError(f"Belirtilen yol bir klasör değil: {path}")

        self.active_workspace_path = abs_path
        logger.info(f"📁 Proje çalışma alanı bağlandı: {abs_path}")

        # Basit özet istatistik
        stats = self._inspect_directory(abs_path)
        return {
            "status": "connected",
            "project_name": os.path.basename(abs_path),
            "workspace_path": abs_path,
            "stats": stats
        }

    def unbind_workspace(self) -> Dict[str, Any]:
        """Proje bağlantısını kaldırır ve genel amaçlı moda geri döner."""
        old = self.active_workspace_path
        self.active_workspace_path = None
        logger.info(f"✕ Proje bağlantısı kesildi: {old}")
        return {
            "status": "disconnected",
            "message": "Proje bağlantısı kesildi. Sistem genel amaçlı kişisel AI moduna döndü.",
            "default_workspace": self.default_base
        }

    def get_status(self) -> Dict[str, Any]:
        """Mevcut çalışma alanı durumunu döner."""
        if self.active_workspace_path:
            stats = self._inspect_directory(self.active_workspace_path)
            return {
                "is_project_bound": True,
                "project_name": os.path.basename(self.active_workspace_path),
                "workspace_path": self.active_workspace_path,
                "stats": stats
            }
        return {
            "is_project_bound": False,
            "project_name": None,
            "workspace_path": self.default_base,
            "message": "Genel amaçlı mod aktif (Herhangi bir proje bağlı değil)."
        }

    def get_file_tree(self, max_depth: int = 3) -> Dict[str, Any]:
        """Bağlı projenin dosya ve klasör ağacını döner."""
        root_dir = self.get_effective_workspace()

        def build_tree(current_path: str, depth: int) -> Dict[str, Any]:
            name = os.path.basename(current_path) or current_path
            is_dir = os.path.isdir(current_path)
            node = {
                "name": name,
                "path": os.path.relpath(current_path, root_dir),
                "is_dir": is_dir
            }

            if is_dir and depth < max_depth:
                children = []
                try:
                    entries = sorted(os.listdir(current_path))
                    for entry in entries:
                        # Gizli veya gereksiz devasa klasörleri atla
                        if entry in [".git", ".venv", "target", "node_modules", "__pycache__", ".idea", ".vscode"]:
                            continue
                        sub_path = os.path.join(current_path, entry)
                        children.append(build_tree(sub_path, depth + 1))
                except Exception:
                    pass
                node["children"] = children
            return node

        return {
            "root_name": os.path.basename(root_dir),
            "root_path": root_dir,
            "tree": build_tree(root_dir, 0)
        }

    def index_project_to_rag(self) -> Dict[str, Any]:
        """Proje içerisindeki kaynak kodları HNSW vektör veritabanına indeksler."""
        from api_server.app.services.rag_service import rag_service
        root_dir = self.get_effective_workspace()
        valid_exts = {".rs", ".py", ".toml", ".json", ".md", ".js", ".html", ".css", ".sh"}

        indexed_files = []
        for dirpath, dirnames, filenames in os.walk(root_dir):
            # Filtrele
            dirnames[:] = [d for d in dirnames if d not in [".git", ".venv", "target", "node_modules", "__pycache__"]]
            for f in filenames:
                ext = os.path.splitext(f)[1].lower()
                if ext in valid_exts:
                    full_p = os.path.join(dirpath, f)
                    try:
                        with open(full_p, "r", encoding="utf-8", errors="replace") as file_obj:
                            content = file_obj.read(8000) # İlk 8000 karakter
                            if len(content.strip()) > 20:
                                rel_p = os.path.relpath(full_p, root_dir)
                                doc_text = f"[DOSYA: {rel_p}]\n{content}"
                                rag_service.ingest_document(
                                    content=doc_text,
                                    category="project_code"
                                )
                                indexed_files.append(rel_p)
                    except Exception:
                        pass

        return {
            "status": "success",
            "project_name": os.path.basename(root_dir),
            "indexed_files_count": len(indexed_files),
            "files": indexed_files[:10]  # İlk 10 dosya örneği
        }

    def _inspect_directory(self, path: str) -> Dict[str, Any]:
        total_files = 0
        exts: Dict[str, int] = {}
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d not in [".git", ".venv", "target", "node_modules", "__pycache__"]]
            for f in files:
                total_files += 1
                ext = os.path.splitext(f)[1].lower() or "other"
                exts[ext] = exts.get(ext, 0) + 1
        return {
            "total_files": total_files,
            "extensions": dict(sorted(exts.items(), key=lambda x: x[1], reverse=True)[:5])
        }

workspace_service = WorkspaceService()
