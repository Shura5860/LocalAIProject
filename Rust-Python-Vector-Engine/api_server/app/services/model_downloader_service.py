"""
High-Speed Streaming Model Downloader & Hugging Face Hub Registry Service.
Supports multi-chunk, resumable (HTTP Range) downloads, live SSE speed/ETA metrics,
automatic SHA-256 integrity verification, and dynamic catalog registration.
"""

import os
import time
import hashlib
import logging
import threading
from typing import Generator, Dict, Any, Optional, List, Set
import httpx

from api_server.app.services.model_service import model_service

logger = logging.getLogger(__name__)


class ModelDownloaderService:
    def __init__(self):
        self.client_timeout = httpx.Timeout(connect=15.0, read=60.0, write=60.0, pool=30.0)
        self._lock = threading.Lock()
        self._active_downloads: Set[str] = set()

    def search_hub(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Hugging Face Hub API üzerinden GGUF formatındaki popüler modelleri arar.
        """
        if os.environ.get("TESTING", "0") == "1":
            return [
                {
                    "id": "Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF",
                    "author": "Qwen",
                    "downloads": 125000,
                    "likes": 420,
                    "recommended_quant": "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"
                },
                {
                    "id": "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B-GGUF",
                    "author": "deepseek-ai",
                    "downloads": 890000,
                    "likes": 3200,
                    "recommended_quant": "DeepSeek-R1-Distill-Qwen-7B-Q4_K_M.gguf"
                }
            ]

        from urllib.parse import quote
        url = f"https://huggingface.co/api/models?search={quote(query)}&filter=gguf&limit={int(limit)}&full=true"
        try:
            with httpx.Client(timeout=self.client_timeout) as client:
                res = client.get(url)
                if res.status_code == 200:
                    data = res.json()
                    results = []
                    for item in data:
                        results.append({
                            "id": item.get("id"),
                            "author": item.get("author", "Community"),
                            "downloads": item.get("downloads", 0),
                            "likes": item.get("likes", 0),
                            "last_modified": item.get("lastModified")
                        })
                    return results
        except Exception as e:
            logger.warning(f"HuggingFace Hub arama hatası: {e}")

        return []

    def pull_model_stream(
        self,
        repo: str,
        filename: str,
        model_id: Optional[str] = None,
        expected_sha256: Optional[str] = None
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Hugging Face üzerinden GGUF modelini canlı SSE akışıyla indirir.
        Kesintiye dayanıklıdır (Resume destekler) ve tamamlandığında kataloğa ekler.
        """
        import re
        from urllib.parse import quote

        safe_filename = os.path.basename(filename or "")
        if not safe_filename or safe_filename != filename or ".." in safe_filename:
            yield {"status": "error", "message": "Geçersiz veya güvensiz model dosya adı."}
            return
        if not re.match(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$", repo or ""):
            yield {"status": "error", "message": "Geçersiz Hugging Face repo formatı."}
            return

        target_id = model_id or safe_filename.lower().replace(".gguf", "").replace("-instruct", "")
        models_dir_real = os.path.realpath(model_service.models_dir)
        dest_path = os.path.realpath(os.path.join(models_dir_real, safe_filename))
        if os.path.commonpath([models_dir_real, dest_path]) != models_dir_real:
            yield {"status": "error", "message": "Güvenlik İhlali: Hedef yol model dizini dışındadır."}
            return
        part_path = dest_path + ".part"

        # 1. Eğer model zaten tam olarak inmişse
        if os.path.exists(dest_path) and os.path.getsize(dest_path) > 1024 * 1024:
            self._register_in_catalog(target_id, filename, repo, expected_sha256)
            yield {
                "status": "completed",
                "progress": 100.0,
                "model_id": target_id,
                "message": "Model zaten yerel diskte mevcut, kataloğa bağlandı.",
                "path": dest_path
            }
            return

        # Test Modu Simülasyonu
        if os.environ.get("TESTING", "0") == "1":
            for p in [25.0, 50.0, 75.0, 100.0]:
                yield {
                    "status": "downloading" if p < 100 else "completed",
                    "progress": p,
                    "speed_mb": 35.4,
                    "downloaded_gb": round(p * 0.02, 2),
                    "total_gb": 2.0,
                    "model_id": target_id
                }
            self._register_in_catalog(target_id, filename, repo, expected_sha256)
            return

        url = f"https://huggingface.co/{repo}/resolve/main/{filename}"
        with self._lock:
            if filename in self._active_downloads:
                yield {
                    "status": "error",
                    "message": f"'{filename}' şu anda başka bir istemcide indiriliyor. Lütfen tamamlanmasını bekleyin."
                }
                return
            self._active_downloads.add(filename)

        downloaded_bytes = os.path.getsize(part_path) if os.path.exists(part_path) else 0

        headers = {}
        if downloaded_bytes > 0:
            headers["Range"] = f"bytes={downloaded_bytes}-"
            logger.info(f"Yeniden başlatılıyor: {downloaded_bytes} bayttan devam edilecek.")

        try:
            with httpx.Client(timeout=self.client_timeout, follow_redirects=True) as client:
                with client.stream("GET", url, headers=headers) as response:
                    if response.status_code not in (200, 206):
                        yield {
                            "status": "error",
                            "message": f"HuggingFace HTTP {response.status_code}: Model bulunamadı veya erişilemedi."
                        }
                        return

                    content_length = response.headers.get("Content-Length")
                    is_resumed = response.status_code == 206 and downloaded_bytes > 0
                    if not is_resumed:
                        downloaded_bytes = 0
                    total_bytes = (int(content_length) + downloaded_bytes) if content_length else 0
                    total_gb = round(total_bytes / (1024 ** 3), 2) if total_bytes else 0.0

                    start_time = time.time()
                    last_emit_time = start_time
                    bytes_since_last = 0
                    mode = "ab" if is_resumed else "wb"

                    with open(part_path, mode) as f:
                        for chunk in response.iter_bytes(chunk_size=1024 * 1024):  # 1MB Chunks
                            if not chunk:
                                continue
                            f.write(chunk)
                            downloaded_bytes += len(chunk)
                            bytes_since_last += len(chunk)

                            now = time.time()
                            # Her 0.5 saniyede bir SSE ilerleme durumu bildir
                            if now - last_emit_time >= 0.5:
                                elapsed = now - last_emit_time
                                speed_mb = round((bytes_since_last / (1024 * 1024)) / elapsed, 1)
                                pct = round((downloaded_bytes / total_bytes) * 100, 1) if total_bytes else 0.0
                                downloaded_gb = round(downloaded_bytes / (1024 ** 3), 2)
                                remaining_bytes = max(0, total_bytes - downloaded_bytes)
                                eta_sec = int(remaining_bytes / (speed_mb * 1024 * 1024)) if speed_mb > 0 else 0

                                yield {
                                    "status": "downloading",
                                    "progress": pct,
                                    "speed_mb": speed_mb,
                                    "downloaded_gb": downloaded_gb,
                                    "total_gb": total_gb,
                                    "eta_seconds": eta_sec,
                                    "model_id": target_id
                                }

                                last_emit_time = now
                                bytes_since_last = 0

            # İndirme başarıyla bitti, .part dosyasını atomik olarak nihai .gguf dosyasına taşı
            os.replace(part_path, dest_path)

            # Opsiyonel SHA-256 doğrulama
            if expected_sha256:
                yield {"status": "verifying", "message": "SHA-256 bütünlüğü hesaplanıyor..."}
                sha = self._compute_sha256(dest_path)
                if sha.lower() != expected_sha256.lower():
                    os.remove(dest_path)
                    yield {
                        "status": "error",
                        "message": f"SHA-256 bütünlük hatası! Beklenen: {expected_sha256}, Hesaplanan: {sha}"
                    }
                    return

            self._register_in_catalog(target_id, filename, repo, expected_sha256)

            yield {
                "status": "completed",
                "progress": 100.0,
                "model_id": target_id,
                "message": f"'{target_id}' modeli başarıyla indirildi ve kataloğa eklendi.",
                "path": dest_path
            }

        except Exception as e:
            logger.error(f"Model indirme hatası: {e}")
            yield {
                "status": "error",
                "message": f"İndirme kesintiye uğradı: {str(e)}"
            }
        finally:
            with self._lock:
                self._active_downloads.discard(filename)

    def _register_in_catalog(
        self,
        model_id: str,
        filename: str,
        repo: str,
        sha256: Optional[str] = None
    ):
        """İndirilen modeli canlı çalışma zamanı kataloğuna kaydeder."""
        dest_path = os.path.join(model_service.models_dir, filename)
        size_gb = round(os.path.getsize(dest_path) / (1024 ** 3), 2) if os.path.exists(dest_path) else 0.0

        model_service.catalog[model_id] = {
            "id": model_id,
            "name": f"{model_id.upper()} (HuggingFace Hub)",
            "filename": filename,
            "parameters": "Bilinmiyor",
            "quantization": filename.split(".")[-2] if "." in filename else "GGUF",
            "disk_size_gb": size_gb,
            "min_vram_gb": max(3.0, size_gb * 1.2),
            "recommended_for": f"HuggingFace: {repo}",
            "hf_repo": repo,
            "sha256": sha256 or ""
        }
        logger.info(f"Model kataloğa kaydedildi: {model_id} ({size_gb} GB)")

    def _compute_sha256(self, filepath: str) -> str:
        hasher = hashlib.sha256()
        with open(filepath, "rb") as f:
            while chunk := f.read(4 * 1024 * 1024):
                hasher.update(chunk)
        return hasher.hexdigest()


model_downloader = ModelDownloaderService()

