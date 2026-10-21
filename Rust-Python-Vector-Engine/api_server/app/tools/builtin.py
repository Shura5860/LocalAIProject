import sys
import io
import math
import psutil
from typing import Dict, Any, List
from duckduckgo_search import DDGS
from api_server.app.tools.base import tool

@tool(
    name="calculator",
    description="Matematiksel ifadeleri ve hesaplamaları güvenle çözer. Örn: '125 * 34' veya 'math.sqrt(144) + 10'."
)
def calculator(expression: str) -> str:
    allowed_names = {k: v for k, v in math.__dict__.items() if not k.startswith("__")}
    allowed_names.update({"abs": abs, "round": round, "min": min, "max": max, "sum": sum, "pow": pow})
    try:
        # Güvenli eval
        result = eval(expression, {"__builtins__": None}, allowed_names)
        return str(result)
    except Exception as e:
        return f"Hesaplama hatası: {str(e)}"

@tool(
    name="system_info",
    description="İşletim sistemi, CPU kullanımı, RAM durumu ve disk alanı gibi sistem metriklerini getirir. Parametre: 'all', 'cpu', 'memory', 'disk'."
)
def system_info(metric: str = "all") -> Dict[str, Any]:
    metric = metric.lower()
    info = {}
    
    if metric in ("all", "cpu"):
        info["cpu_percent"] = f"{psutil.cpu_percent(interval=0.1)}%"
        info["cpu_count_logical"] = psutil.cpu_count(logical=True)
        info["cpu_count_physical"] = psutil.cpu_count(logical=False)
        
    if metric in ("all", "memory"):
        mem = psutil.virtual_memory()
        info["ram_total_gb"] = round(mem.total / (1024**3), 2)
        info["ram_used_gb"] = round(mem.used / (1024**3), 2)
        info["ram_percent"] = f"{mem.percent}%"
        
    if metric in ("all", "disk"):
        disk = psutil.disk_usage("/")
        info["disk_total_gb"] = round(disk.total / (1024**3), 2)
        info["disk_free_gb"] = round(disk.free / (1024**3), 2)
        info["disk_percent"] = f"{disk.percent}%"
        
    return info

from api_server.app.core.guardrails import sanitize_web_query

@tool(
    name="web_search",
    description="DuckDuckGo üzerinden internette canlı arama yapar. Güncel olaylar, hava durumu, haberler veya genel web aramaları için kullanılır."
)
def web_search(query: str, max_results: int = 3) -> List[Dict[str, str]]:
    try:
        # Etik & Gizlilik Kalkanı: Sorgudan hassas verileri arındır
        safe_query = sanitize_web_query(query)
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(safe_query, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "snippet": r.get("body", ""),
                    "href": r.get("href", "")
                })
        return results if results else [{"snippet": "Herhangi bir sonuç bulunamadı."}]
    except Exception as e:
        return [{"error": f"Arama servisi hatası: {str(e)}"}]

@tool(
    name="python_interpreter",
    description="Küçük Python kod bloklarını çalıştırıp stdout çıktısını veya dönen sonucu alır. Veri analizi veya algoritma hesaplama için idealdir."
)
def python_interpreter(code: str) -> str:
    old_stdout = sys.stdout
    redirected_output = io.StringIO()
    sys.stdout = redirected_output
    local_vars = {}
    try:
        exec(code, {}, local_vars)
        sys.stdout = old_stdout
        out = redirected_output.getvalue().strip()
        if not out and local_vars:
            last_key = list(local_vars.keys())[-1]
            out = f"{last_key} = {local_vars[last_key]}"
        return out if out else "Kod başarıyla çalıştı (Çıktı yok)."
    except Exception as e:
        sys.stdout = old_stdout
        return f"Python çalıştırma hatası: {str(e)}"
