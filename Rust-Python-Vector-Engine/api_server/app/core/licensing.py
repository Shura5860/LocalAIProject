import os
import json
import hashlib
import platform
import subprocess
import datetime
import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

TIER_CONFIG = {
    "TRIAL": {"name": "7 Günlük Deneme Sürümü", "days": 7},
    "MONTH": {"name": "1 Aylık Standart Lisans", "days": 30},
    "YEAR1": {"name": "1 Yıllık Kurumsal Lisans", "days": 365},
    "LIFET": {"name": "Sınırsız Ömür Boyu Lisans", "days": 99999}
}

class MachineLicenseManager:
    """
    Kriptografik Zaman Damgalı ve Donanım Kilitli Çok Kademeli Lisans Yöneticisi.
    Desteklenen Kademeler:
      - TRIAL: 7 Günlük Deneme
      - MONTH: 1 Aylık Lisans
      - YEAR1: 1 Yıllık Lisans
      - LIFET: Sınırsız / Ömür Boyu Lisans
    """
    def __init__(self, salt: str = "AIAssistant_Commercial_MultiTier_v1_SecretSalt"):
        self.salt = salt
        self.base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
        self.license_file = os.path.join(self.base_dir, "license.json")

    def get_hardware_fingerprint(self) -> str:
        """İşletim sistemine göre anakart/CPU/UUID kimliğini okur."""
        system = platform.system()
        raw_id = ""

        try:
            if system == "Linux":
                if os.path.exists("/etc/machine-id"):
                    with open("/etc/machine-id", "r") as f:
                        raw_id = f.read().strip()
                elif os.path.exists("/var/lib/dbus/machine-id"):
                    with open("/var/lib/dbus/machine-id", "r") as f:
                        raw_id = f.read().strip()
            elif system == "Windows":
                res = subprocess.run(["wmic", "csproduct", "get", "UUID"], capture_output=True, text=True, timeout=2)
                lines = [l.strip() for l in res.stdout.splitlines() if l.strip()]
                if len(lines) > 1:
                    raw_id = lines[1]
            elif system == "Darwin":
                res = subprocess.run(["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"], capture_output=True, text=True, timeout=2)
                for line in res.stdout.splitlines():
                    if "IOPlatformUUID" in line:
                        raw_id = line.split("=")[-1].replace('"', '').strip()
                        break
        except Exception as e:
            logger.warning(f"Donanım kimliği okunurken hata: {e}")

        if not raw_id:
            raw_id = platform.node() + "_" + platform.machine()

        hasher = hashlib.sha256((raw_id + self.salt).encode("utf-8"))
        fingerprint = hasher.hexdigest()[:16].upper()
        return "-".join([fingerprint[i:i+4] for i in range(0, 16, 4)])

    def _generate_signature(self, tier: str, hw_prefix: str, exp_str: str) -> str:
        payload = f"{tier}:{hw_prefix}:{exp_str}:{self.salt}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:8].upper()

    def generate_license_key(self, hardware_fingerprint: str, tier: str = "TRIAL", custom_days: Optional[int] = None) -> str:
        tier = tier.upper()
        if tier not in TIER_CONFIG:
            raise ValueError(f"Geçersiz lisans kademesi: {tier}. Seçenekler: {list(TIER_CONFIG.keys())}")

        hw_clean = hardware_fingerprint.replace("-", "").strip()[:8]

        days = custom_days if custom_days is not None else TIER_CONFIG[tier]["days"]

        if tier == "LIFET":
            exp_str = "PERPETUA"
        else:
            exp_date = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=days)
            exp_str = exp_date.strftime("%Y%m%d")

        sig = self._generate_signature(tier, hw_clean, exp_str)
        # Format: TIER-HW1-HW2-EXPDATE-SIG
        # Örnek: YEAR1-68EC-55C5-20270923-8B3E6A1C
        return f"{tier}-{hw_clean[:4]}-{hw_clean[4:8]}-{exp_str}-{sig}"

    def verify_license(self, license_key: str, hardware_fingerprint: Optional[str] = None) -> Tuple[bool, str, Dict[str, Any]]:
        if not license_key:
            return False, "Lisans anahtarı boş bırakılamaz.", {}

        parts = license_key.strip().upper().split("-")
        if len(parts) != 5:
            return False, "Geçersiz lisans anahtarı formatı. (Örn: YEAR1-XXXX-XXXX-YYYYMMDD-ZZZZZZZZ)", {}

        tier, hw1, hw2, exp_str, sig = parts
        if tier not in TIER_CONFIG:
            return False, f"Bilinmeyen lisans kademesi: {tier}", {}

        current_hw = (hardware_fingerprint or self.get_hardware_fingerprint()).replace("-", "").strip()[:8]
        expected_hw = f"{hw1}{hw2}"

        if current_hw != expected_hw:
            return False, "Bu lisans anahtarı bu bilgisayara ait değil (Donanım Uyuşmazlığı)!", {}

        expected_sig = self._generate_signature(tier, expected_hw, exp_str)
        if sig != expected_sig:
            return False, "Lisans anahtarı güvenlik imzası doğrulanmadı (Tahrif Edilmiş Anahtar)!", {}

        # Tarih Denetimi
        now = datetime.datetime.now(datetime.timezone.utc)
        if exp_str == "PERPETUA":
            days_left = 99999
            exp_human = "Sınırsız (Ömür Boyu)"
        else:
            try:
                exp_date = datetime.datetime.strptime(exp_str, "%Y%m%d").replace(tzinfo=datetime.timezone.utc)
                exp_date = exp_date.replace(hour=23, minute=59, second=59)
                delta = exp_date - now
                days_left = delta.days
                if delta.total_seconds() <= 0:
                    return False, f"Lisans süreniz dolmuştur! (Son geçerlilik: {exp_str})", {"expired": True, "tier": tier}
                exp_human = exp_date.strftime("%d.%m.%Y")
            except Exception:
                return False, "Lisans bitiş tarihi çözümlenemedi.", {}

        license_info = {
            "valid": True,
            "tier": tier,
            "tier_name": TIER_CONFIG[tier]["name"],
            "hardware_id": hardware_fingerprint or self.get_hardware_fingerprint(),
            "expires_at": exp_human,
            "days_left": days_left,
            "is_lifetime": (tier == "LIFET")
        }
        return True, "Lisans başarıyla doğrulandı.", license_info

    def get_saved_license(self) -> Optional[str]:
        if os.path.exists(self.license_file):
            try:
                with open(self.license_file, "r") as f:
                    data = json.load(f)
                    return data.get("license_key")
            except Exception:
                return None
        return None

    def save_license(self, license_key: str) -> Tuple[bool, str, Dict[str, Any]]:
        is_valid, msg, info = self.verify_license(license_key)
        if not is_valid:
            return False, msg, info

        try:
            with open(self.license_file, "w") as f:
                json.dump({"license_key": license_key.strip().upper(), "activated_at": datetime.datetime.now().isoformat(), "info": info}, f, indent=2)
            return True, "Lisans başarıyla etkinleştirildi ve kaydedildi.", info
        except Exception as e:
            return False, f"Lisans dosyası kaydedilemedi: {e}", {}

    def get_current_status(self) -> Dict[str, Any]:
        hw_id = self.get_hardware_fingerprint()
        saved_key = self.get_saved_license()

        if not saved_key:
            return {
                "is_licensed": False,
                "hardware_id": hw_id,
                "message": "Lisans bulunamadı. Lütfen bir lisans anahtarı giriniz.",
                "details": None
            }

        is_valid, msg, info = self.verify_license(saved_key, hw_id)
        return {
            "is_licensed": is_valid,
            "hardware_id": hw_id,
            "license_key": saved_key,
            "message": msg,
            "details": info if is_valid else None
        }

license_manager = MachineLicenseManager()
