import sys
import io
import ast
import math
import operator
import threading
import psutil
from typing import Dict, Any, List
from duckduckgo_search import DDGS
from api_server.app.tools.base import tool

_STDOUT_LOCK = threading.Lock()

_SAFE_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
}
_SAFE_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}
_SAFE_MATH_FUNCS = {
    "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "log": math.log, "log10": math.log10, "exp": math.exp, "floor": math.floor,
    "ceil": math.ceil, "fabs": math.fabs, "abs": abs, "round": round,
    "min": min, "max": max, "sum": sum,
}
_SAFE_CONSTS = {"pi": math.pi, "e": math.e, "tau": math.tau}


def _safe_eval_ast(node: ast.AST) -> Any:
    if isinstance(node, ast.Expression):
        return _safe_eval_ast(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.Name) and node.id in _SAFE_CONSTS:
        return _SAFE_CONSTS[node.id]
    if isinstance(node, ast.UnaryOp) and type(node.op) in _SAFE_UNARY_OPS:
        return _SAFE_UNARY_OPS[type(node.op)](_safe_eval_ast(node.operand))
    if isinstance(node, ast.BinOp):
        left = _safe_eval_ast(node.left)
        right = _safe_eval_ast(node.right)
        if isinstance(node.op, ast.Pow):
            if abs(right) > 1000:
                raise ValueError("Üs değeri güvenlik sınırını (1000) aşıyor.")
            return operator.pow(left, right)
        if type(node.op) in _SAFE_BIN_OPS:
            return _SAFE_BIN_OPS[type(node.op)](left, right)
    if isinstance(node, ast.Call):
        func_name = None
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == "math":
            func_name = node.func.attr
        if func_name in _SAFE_MATH_FUNCS:
            args = [_safe_eval_ast(a) for a in node.args]
            return _SAFE_MATH_FUNCS[func_name](*args)
    if isinstance(node, (ast.List, ast.Tuple)):
        return [_safe_eval_ast(elt) for elt in node.elts]
    raise ValueError(f"İzin verilmeyen ifade öğesi: {type(node).__name__}")


@tool(
    name="calculator",
    description="Matematiksel ifadeleri ve hesaplamaları güvenle çözer. Örn: '125 * 34' veya 'math.sqrt(144) + 10'."
)
def calculator(expression: str) -> str:
    if not expression or len(expression) > 500:
        return "Hesaplama hatası: İfade boş veya çok uzun."
    try:
        tree = ast.parse(expression.strip(), mode="eval")
        result = _safe_eval_ast(tree)
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
    description="DuckDuckGo üzerinden internette canlı arama yapar. Güncel olaylar, hava durumu veya genel web aramaları için kullanılır. ENABLE_WEB_SEARCH=false ile tamamen devre dışı bırakılabilir."
)
def web_search(query: str, max_results: int = 3) -> List[Dict[str, str]]:
    import os
    if os.getenv("ENABLE_WEB_SEARCH", "true").lower() in ("false", "0", "no"):
        return [{"snippet": "Canlı web araması kullanıcı yapılandırması tarafından devre dışı bırakıldı (Tamamen Yerel / Air-Gapped Mod)."}]

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
    redirected_output = io.StringIO()
    local_vars = {}
    with _STDOUT_LOCK:
        old_stdout = sys.stdout
        sys.stdout = redirected_output
        try:
            exec(code, {}, local_vars)
            out = redirected_output.getvalue().strip()
            if not out and local_vars:
                last_key = list(local_vars.keys())[-1]
                out = f"{last_key} = {local_vars[last_key]}"
            return out if out else "Kod başarıyla çalıştı (Çıktı yok)."
        except Exception as e:
            return f"Python çalıştırma hatası: {str(e)}"
        finally:
            sys.stdout = old_stdout
