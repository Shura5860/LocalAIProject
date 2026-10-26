import random
import httpx
import re
from typing import Dict, Any, List
from api_server.app.tools.base import tool
from api_server.app.core.guardrails import sanitize_web_query

# Bot korumalarını atlatmak için gerçek modern masaüstü tarayıcı User-Agent havuzu
USER_AGENTS = [
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0",
]

def get_stealth_headers() -> Dict[str, str]:
    """Cloudflare ve WAF bot tespit sistemlerini yanıltan tarayıcı başlıkları üretir."""
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }

def fetch_stealth_content(url: str, max_chars: int = 4000) -> str:
    """
    Cloudflare, CAPTCHA ve karmaşık JavaScript korumalarını aşarak
    herhangi bir web sayfasını temiz metin/markdown olarak çeker.
    """
    # 1. Aşama: Jina Reader Gateway (En etkili Cloudflare & JS bypass yöntemi)
    jina_url = f"https://r.jina.ai/{url}"
    try:
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            resp = client.get(
                jina_url,
                headers={"X-Return-Format": "markdown", "User-Agent": random.choice(USER_AGENTS)}
            )
            if resp.status_code == 200 and len(resp.text.strip()) > 50:
                clean_text = resp.text.strip()
                # Gereksiz link ve görsel kalabalığını filtrele
                clean_text = re.sub(r"!\[.*?\]\(.*?\)", "", clean_text)
                return clean_text[:max_chars]
    except Exception:
        pass

    # 2. Aşama: Doğrudan Stealth İsteği (Fallback)
    try:
        # http2 desteği varsa kullan, yoksa standart HTTP/1.1 ile devam et
        client_kwargs = {"timeout": 15.0, "follow_redirects": True, "headers": get_stealth_headers()}
        try:
            import h2
            client_kwargs["http2"] = True
        except ImportError:
            pass

        with httpx.Client(**client_kwargs) as client:
            resp = client.get(url)
            if resp.status_code == 200:
                text = resp.text
                # Basit HTML tag temizliği
                clean = re.sub(r"<script.*?</script>", "", text, flags=re.DOTALL)
                clean = re.sub(r"<style.*?</style>", "", clean, flags=re.DOTALL)
                clean = re.sub(r"<.*?>", " ", clean)
                clean = re.sub(r"\s+", " ", clean).strip()
                return clean[:max_chars]
            else:
                return f"Web sayfası okunamadı (HTTP {resp.status_code})"
    except Exception as e:
        return f"Sayfa getirme hatası: {str(e)}"

@tool(
    name="read_web_page",
    description="Herhangi bir web sitesinin (blog, haber, dokümantasyon, wiki) içeriğini bot korumalarını (Cloudflare vb.) aşarak temiz metin olarak okur. Parametre: 'url', opsiyonel: 'max_chars'."
)
def read_web_page(url: str, max_chars: int = 4000) -> str:
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url
    raw_content = fetch_stealth_content(url, max_chars=max_chars)
    from api_server.app.core.sanitizer import quarantine_untrusted_content
    return quarantine_untrusted_content(raw_content, source_type="web", source_name=url)

