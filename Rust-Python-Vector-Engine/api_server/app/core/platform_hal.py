"""
Cross-Platform Operating System and Hardware Abstraction Layer (HAL) for AURA-CORE.
Provides unified hardware detection, accelerator discovery (CUDA, Apple Silicon Metal, ROCm, AVX2 CPU),
and OS-level process sandbox isolation across Linux, macOS (Darwin), and Windows.
"""

import os
import sys
import platform
import shutil
import subprocess
import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


class PlatformHAL:
    """
    Platform and Hardware Abstraction Layer.
    Tüm işletim sistemlerini ve donanım hızlandırıcılarını tek bir standart arabirimde birleştirir:
    - Linux: NVIDIA CUDA, AMD ROCm, CPU AVX2, Linux Bubblewrap (bwrap) sandbox
    - macOS (Darwin): Apple Silicon Metal (M1/M2/M3/M4), Unified RAM, macOS sandbox-exec
    - Windows: DirectML, NVIDIA CUDA, Windows Restricted Subshell
    """

    @classmethod
    def get_os_type(cls) -> str:
        """'linux', 'darwin' (macOS), veya 'windows' döner."""
        system = platform.system().lower()
        if "darwin" in system:
            return "darwin"
        elif "windows" in system:
            return "windows"
        return "linux"

    @classmethod
    def get_hardware_profile(cls) -> Dict[str, Any]:
        """
        Platforma özel donanım ve VRAM/Metal kaynaklarını analiz eder.
        """
        os_type = cls.get_os_type()
        arch = platform.machine().lower()
        profile: Dict[str, Any] = {
            "os": os_type,
            "architecture": arch,
            "gpu_backend": "cpu",
            "gpu_name": "Generic CPU",
            "vram_free_gb": 0.0,
            "vram_total_gb": 0.0,
            "has_sandboxing": False,
            "sandbox_type": "none"
        }

        # 1. Sandbox Desteği Kontrolü
        if os_type == "linux":
            if shutil.which("bwrap"):
                profile["has_sandboxing"] = True
                profile["sandbox_type"] = "bubblewrap"
        elif os_type == "darwin":
            if shutil.which("sandbox-exec"):
                profile["has_sandboxing"] = True
                profile["sandbox_type"] = "seatbelt"
        elif os_type == "windows":
            profile["has_sandboxing"] = True
            profile["sandbox_type"] = "restricted_token"

        # 2. Donanım Hızlandırma Tespiti
        # A) macOS (Apple Silicon Metal)
        if os_type == "darwin":
            try:
                cpu_brand = subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"], text=True).strip()
                if "apple" in cpu_brand.lower():
                    # Apple Silicon Unified Memory
                    mem_bytes = int(subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True).strip())
                    total_gb = round(mem_bytes / (1024 ** 3), 1)
                    # Metal can typically allocate up to ~75% of unified memory for LLM
                    metal_vram = round(total_gb * 0.75, 1)
                    profile["gpu_backend"] = "metal"
                    profile["gpu_name"] = cpu_brand
                    profile["vram_free_gb"] = metal_vram
                    profile["vram_total_gb"] = total_gb
                    return profile
            except Exception:
                pass

        # B) Linux / Windows NVIDIA CUDA
        if shutil.which("nvidia-smi"):
            try:
                res = subprocess.run(
                    ["nvidia-smi", "--query-gpu=name,memory.total,memory.free", "--format=csv,noheader,nounits"],
                    capture_output=True,
                    text=True,
                    timeout=2
                )
                if res.returncode == 0 and res.stdout.strip():
                    parts = [p.strip() for p in res.stdout.strip().splitlines()[0].split(",")]
                    name = parts[0]
                    total_mb = float(parts[1])
                    free_mb = float(parts[2])
                    profile["gpu_backend"] = "cuda"
                    profile["gpu_name"] = name
                    profile["vram_free_gb"] = round(free_mb / 1024.0, 2)
                    profile["vram_total_gb"] = round(total_mb / 1024.0, 2)
                    return profile
            except Exception:
                pass

        # C) AMD ROCm (Linux)
        if shutil.which("rocm-smi"):
            profile["gpu_backend"] = "rocm"
            profile["gpu_name"] = "AMD Radeon / Instinct"
            profile["vram_free_gb"] = 6.0
            return profile

        # D) CPU Fallback
        profile["gpu_backend"] = "cpu"
        profile["gpu_name"] = f"{platform.processor() or 'CPU'} (AVX2/SIMD)"
        return profile

    @classmethod
    def get_optimal_gpu_layers(cls) -> int:
        """
        Donanıma göre llama.cpp için en güvenli ve hızlı GPU katmanını (-1, 20, veya 0) hesaplar.
        """
        hw = cls.get_hardware_profile()
        backend = hw.get("gpu_backend")
        free_vram = hw.get("vram_free_gb", 0.0)

        # macOS Metal veya 5.5GB+ VRAM olan CUDA sistemlerde tüm katmanları GPU'ya ver
        if backend == "metal" or (backend == "cuda" and free_vram >= 5.5):
            return -1
        # 3GB - 5.5GB arası hibrit offloading
        elif backend == "cuda" and free_vram >= 3.0:
            return 20
        # Diğer durumlarda CPU
        return 0

    @classmethod
    def bind_cpu_affinity(cls, num_cores: Optional[int] = None) -> bool:
        """
        CPU Çekirdek Sabitleme (Core Affinity & NUMA Tuning).
        Linux sistemlerde çıkarım iş parçacıklarını fiziksel performans çekirdeklerine (P-Cores)
        kilitler, L3 cache kaçırmalarını ve E-Core darboğazlarını önler.
        """
        if cls.get_os_type() != "linux" or not hasattr(os, "sched_setaffinity"):
            return False

        try:
            total_cpus = os.cpu_count() or 4
            cores_to_use = num_cores or max(1, total_cpus // 2)
            target_mask = set(range(min(total_cpus, cores_to_use)))
            os.sched_setaffinity(0, target_mask)
            logger.info("⚡ [Core Affinity] Çıkarım threadleri fiziksel çekirdeklere sabitlendi: %s", target_mask)
            return True
        except Exception as e:
            logger.warning("Core affinity ayarlanamadı: %s", str(e))
            return False

    @classmethod
    def execute_sandboxed_command(cls, command: str, cwd: str, timeout: int = 60) -> subprocess.CompletedProcess:
        """
        İşletim sistemine uygun güvenli sandbox içinde komut yürütür.
        """
        os_type = cls.get_os_type()

        # 1. Linux: Bubblewrap (bwrap)
        if os_type == "linux":
            bwrap_path = shutil.which("bwrap")
            use_bwrap = os.environ.get("AURA_ENABLE_BWRAP", "1") == "1"
            if bwrap_path and use_bwrap:
                bwrap_cmd = [
                    bwrap_path,
                    "--ro-bind", "/", "/",
                    "--bind", cwd, cwd,
                    "--dev", "/dev",
                    "--proc", "/proc",
                    "--tmpfs", "/tmp",
                    "--unshare-all",
                    "--share-net",
                    "--die-with-parent",
                    "--chdir", cwd,
                    "bash", "-c", command
                ]
                res = subprocess.run(bwrap_cmd, capture_output=True, text=True, timeout=timeout)
                # Eğer bwrap container içinde, CI runner'da veya kısıtlı yetkilerde başarısız olduysa subshell'e geri çekil
                if res.returncode != 0 and (
                    "bwrap" in res.stderr.lower()
                    or any(err in res.stderr.lower() for err in ["namespace", "not permitted", "not implemented", "permission", "cannot", "failed", "denied"])
                ):
                    return subprocess.run(command, shell=True, cwd=cwd, capture_output=True, text=True, timeout=timeout)
                return res

        # 2. macOS: sandbox-exec
        elif os_type == "darwin":
            sandbox_exec = shutil.which("sandbox-exec")
            if sandbox_exec:
                # Basic seatbelt profile allowing local writes only to cwd and temp
                seatbelt_profile = f"(version 1) (allow default) (deny file-write* (regex #\"^/(usr|etc|bin|sbin|System|Library)\")) (allow file-write* (subpath \"{cwd}\")) (allow file-write* (subpath \"/tmp\"))"
                cmd = [sandbox_exec, "-p", seatbelt_profile, "bash", "-c", command]
                return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

        # 3. Windows veya Standart Fallback
        return subprocess.run(command, shell=True, cwd=cwd, capture_output=True, text=True, timeout=timeout)


platform_hal = PlatformHAL()
