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

import ipaddress
import socket
from urllib.parse import urlparse


def _validate_public_http_url(url: str) -> None:
    """SSRF koruması: loopback, özel ağ, link-local ve bulut metadata adreslerini engeller."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Desteklenmeyen URL şeması: {parsed.scheme}")
    host = parsed.hostname
    if not host:
        raise ValueError("Geçersiz URL: ana makine adı eksik.")
    if host.lower() in ("localhost", "localhost.localdomain"):
        raise ValueError("Güvenlik Kalkanı (SSRF): Yerel ağ adreslerine erişim engellendi.")
    try:
        infos = socket.getaddrinfo(host, None)
        for info in infos:
            ip_obj = ipaddress.ip_address(info[4][0])
            if (
                ip_obj.is_private
                or ip_obj.is_loopback
                or ip_obj.is_link_local
                or ip_obj.is_multicast
                or ip_obj.is_reserved
                or ip_obj.is_unspecified
            ):
                raise ValueError(f"Güvenlik Kalkanı (SSRF): Özel/yerel IP adresi ({ip_obj}) engellendi.")
    except ValueError:
        raise
    except Exception:
        # DNS çözülemiyorsa httpx kendi bağlantı hatasını verecektir
        pass


def fetch_web_content(url: str, max_chars: int = 4000) -> str:
    """
    Belirtilen web sayfasının içeriğini tamamen doğrudan yerel HTTP istemcisiyle çeker.
    Üçüncü taraf aracı veya bulut gateway kullanılmaz; tüm ağ iletişimi yerel makineden hedefe doğrudur.
    """
    try:
        _validate_public_http_url(url)
    except ValueError as ve:
        return str(ve)

    client_kwargs = {
        "timeout": 15.0,
        "follow_redirects": False,
        "headers": DOCUMENTATION_FETCH_HEADERS
    }
    try:
        import h2
        client_kwargs["http2"] = True
    except ImportError:
        pass

    try:
        with httpx.Client(**client_kwargs) as client:
            current_url = url
            resp = None
            for _ in range(5):
                _validate_public_http_url(current_url)
                resp = client.get(current_url)
                if resp.status_code in (301, 302, 303, 307, 308) and resp.headers.get("location"):
                    current_url = str(resp.url.join(resp.headers["location"]))
                    continue
                break
            if resp is not None and resp.status_code == 200:
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
