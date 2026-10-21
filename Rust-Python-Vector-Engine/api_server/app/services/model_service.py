import os
import psutil
import subprocess
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class ModelService:
    def __init__(self):
        self.base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
        self.models_dir = os.path.join(self.base_dir, "Rust-LLM-Engine/models")
        os.makedirs(self.models_dir, exist_ok=True)

        # Ön Tanımlı Model Profilleri Kataloğu
        self.catalog = {
            "qwen2.5-coder-7b": {
                "id": "qwen2.5-coder-7b",
                "name": "Qwen 2.5 Coder 7B (Derin Mühendis)",
                "filename": "qwen2.5-coder-7b-instruct-q4_k_m.gguf",
                "parameters": "7.0B",
                "quantization": "Q4_K_M",
                "disk_size_gb": 4.68,
                "min_vram_gb": 6.0,
                "recommended_for": "Üst düzey kodlama, derin DevOps, mimari refactoring (8GB VRAM)",
                "hf_repo": "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF",
                "sha256": "509287f78cb4d4cf6b3843734733b914b2c158e43e22a7f4bf5e963800894d3c"
            },
            "qwen2.5-coder-3b": {
                "id": "qwen2.5-coder-3b",
                "name": "Qwen 2.5 Coder 3B (Hızlı & 4GB VRAM)",
                "filename": "qwen2.5-coder-3b-instruct-q4_k_m.gguf",
                "parameters": "3.0B",
                "quantization": "Q4_K_M",
                "disk_size_gb": 1.95,
                "min_vram_gb": 3.0,
                "recommended_for": "Hafif görevler, hızlı yanıt, 4GB GPU'lar & arkada oyun açıkken",
                "hf_repo": "Qwen/Qwen2.5-Coder-3B-Instruct-GGUF",
                "sha256": "724fb256bec1ff062b2f65e4569e871ad2e95ab2a3989723d1769c54294730b7"
            }
        }

        # Varsayılan Aktif Model (Donanıma göre belirlenir)
        self.active_model_id = "qwen2.5-coder-7b"

    def get_hardware_info(self) -> Dict[str, Any]:
        """Sistem RAM ve NVIDIA GPU VRAM bilgilerini tespit eder."""
        ram = psutil.virtual_memory()
        total_ram_gb = round(ram.total / (1024 ** 3), 1)
        avail_ram_gb = round(ram.available / (1024 ** 3), 1)

        vram_info = {"has_gpu": False, "gpu_name": "Yok", "total_vram_gb": 0.0, "free_vram_gb": 0.0}
        try:
            res = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total,memory.free", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=2
            )
            if res.returncode == 0 and res.stdout.strip():
                parts = [p.strip() for p in res.stdout.strip().split(",")]
                if len(parts) >= 3:
                    vram_info = {
                        "has_gpu": True,
                        "gpu_name": parts[0],
                        "total_vram_gb": round(float(parts[1]) / 1024, 1),
                        "free_vram_gb": round(float(parts[2]) / 1024, 1)
                    }
        except Exception:
            pass

        # Akıllı Öneri: Eğer VRAM < 6GB ise 3B modelini öner
        if vram_info["has_gpu"] and vram_info["total_vram_gb"] < 6.0:
            recommended = "qwen2.5-coder-3b"
            reason = f"Ekran kartı ({vram_info['total_vram_gb']}GB VRAM) 4GB profilinde olduğu için 3B modeli önerilir."
        else:
            recommended = "qwen2.5-coder-7b"
            reason = f"Sistem donanımı ({vram_info.get('total_vram_gb', 0)}GB VRAM, {total_ram_gb}GB RAM) 7B derin mühendis modelini rahatlıkla kaldırabilir."

        return {
            "ram": {"total_gb": total_ram_gb, "available_gb": avail_ram_gb},
            "gpu": vram_info,
            "recommended_model_id": recommended,
            "recommendation_reason": reason
        }

    def list_models(self) -> List[Dict[str, Any]]:
        """Katalogdaki tüm modelleri, disk durumlarını ve aktif seçimi listeler."""
        result = []
        for model_id, info in self.catalog.items():
            file_path = os.path.join(self.models_dir, info["filename"])
            is_downloaded = os.path.exists(file_path)
            size_on_disk = round(os.path.getsize(file_path) / (1024 ** 3), 2) if is_downloaded else 0.0

            result.append({
                **info,
                "is_active": (model_id == self.active_model_id),
                "is_downloaded": is_downloaded,
                "file_path": file_path,
                "actual_size_gb": size_on_disk
            })
        return result

    def get_active_model_info(self) -> Dict[str, Any]:
        """Aktif seçili modelin detaylarını döner."""
        info = self.catalog.get(self.active_model_id, self.catalog["qwen2.5-coder-7b"])
        file_path = os.path.join(self.models_dir, info["filename"])
        return {
            **info,
            "is_active": True,
            "is_downloaded": os.path.exists(file_path),
            "file_path": file_path
        }

    def get_active_model_path(self) -> str:
        """Rust LLM Bridge için aktif model dosyasının mutlak yolunu döner."""
        info = self.get_active_model_info()
        return info["file_path"]

    def set_active_model(self, model_id: str) -> Dict[str, Any]:
        """Kullanıcının seçimine göre aktif modeli anında değiştirir."""
        if model_id not in self.catalog:
            raise ValueError(f"Geçersiz model ID: '{model_id}'. Mevcut modeller: {list(self.catalog.keys())}")

        self.active_model_id = model_id
        logger.info(f"🔄 Aktif model değiştirildi: {model_id}")
        return {
            "status": "success",
            "message": f"Aktif model '{self.catalog[model_id]['name']}' olarak güncellendi.",
            "active_model": self.get_active_model_info()
        }

    def verify_model_integrity(self, model_id: str) -> Dict[str, Any]:
        """GGUF model dosyasının SHA-256 bütünlüğünü resmi hash ile doğrular (Tedarik zinciri koruması)."""
        import hashlib
        if model_id not in self.catalog:
            raise ValueError(f"Bilinmeyen model ID: {model_id}")

        info = self.catalog[model_id]
        file_path = os.path.join(self.models_dir, info["filename"])

        if not os.path.exists(file_path):
            return {
                "model_id": model_id,
                "verified": False,
                "error": f"Model dosyası bulunamadı: {file_path}"
            }

        expected_hash = info.get("sha256")
        hasher = hashlib.sha256()
        # Büyük dosyaları parça parça oku (64KB chunks)
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        computed_hash = hasher.hexdigest().lower()

        is_valid = (computed_hash == expected_hash.lower()) if expected_hash else False
        return {
            "model_id": model_id,
            "filename": info["filename"],
            "expected_sha256": expected_hash,
            "computed_sha256": computed_hash,
            "verified": is_valid,
            "status": "SECURE_INTEGRITY_VERIFIED" if is_valid else "CORRUPTED_OR_TAMPERED"
        }

model_service = ModelService()
