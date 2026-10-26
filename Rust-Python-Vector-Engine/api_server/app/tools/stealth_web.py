import httpx
import re
from typing import Dict, Any, List
from api_server.app.tools.base import tool
from api_server.app.core.guardrails import sanitize_web_query

# Halka açık teknik dokümantasyon ve metinleri çekmek için standart başlıklar
DOCUMENTATION_FETCH_HEADERS = {
    "User-Agent": "AURA-CORE-DocumentFetcher/1.0 (Local-OnPremise-Research; +https://github.com/Shura5860/LocalAIProject)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.7",
    "Accept-Language": "en-US,en;q=0.9,tr;q=0.8",
}

def fetch_web_content(url: str, max_chars: int = 4000) -> str:
    """
    Belirtilen web sayfasının içeriğini tamamen doğrudan yerel HTTP istemcisiyle çeker.
    Üçüncü taraf aracı veya bulut gateway kullanılmaz; tüm ağ iletişimi yerel makineden hedefe doğrudur.
    """
    client_kwargs = {
        "timeout": 15.0,
        "follow_redirects": True,
        "headers": DOCUMENTATION_FETCH_HEADERS
    }
    try:
        import h2
        client_kwargs["http2"] = True
    except ImportError:
        pass

    try:
        with httpx.Client(**client_kwargs) as client:
            resp = client.get(url)
            if resp.status_code == 200:
                text = resp.text
                # Script ve style etiketlerini temizle
                clean = re.sub(r"<script.*?</script>", "", text, flags=re.DOTALL)
                clean = re.sub(r"<style.*?</style>", "", clean, flags=re.DOTALL)
                clean = re.sub(r"<.*?>", " ", clean)
                clean = re.sub(r"\s+", " ", clean).strip()
                return clean[:max_chars]
            else:
                return f"Web sayfası okunamadı (HTTP {resp.status_code})"
    except Exception as e:
        return f"Sayfa getirme hatası: {str(e)}"

# Geriye dönük uyumluluk ve testler için alias fonksiyon
def get_stealth_headers() -> Dict[str, str]:
    return dict(DOCUMENTATION_FETCH_HEADERS)

def fetch_stealth_content(url: str, max_chars: int = 4000) -> str:
    return fetch_web_content(url, max_chars=max_chars)

@tool(
    name="read_web_page",
    description="Halka açık teknik dokümantasyon, blog ve wiki sayfalarının içeriğini yerel istemciyle okur. Parametre: 'url', opsiyonel: 'max_chars'."
)
def read_web_page(url: str, max_chars: int = 4000) -> str:
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url
    raw_content = fetch_web_content(url, max_chars=max_chars)
    from api_server.app.core.sanitizer import quarantine_untrusted_content
    return quarantine_untrusted_content(raw_content, source_type="web", source_name=url)
