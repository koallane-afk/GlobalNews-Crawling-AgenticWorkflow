# Strategy Cookbook

Copy-paste code snippets for each crawling bypass method.
All code is designed for the GlobalNews crawling system under `.venv/bin/python`.

---

## 1. curl_cffi with TLS Impersonation

The most effective free method for bypassing TLS fingerprint detection.
curl_cffi uses the real browser TLS stack (via libcurl) to produce
authentic JA3/JA4 fingerprints.

### Basic Usage

```python
from curl_cffi import requests as cffi_requests

# Simple impersonation -- one profile
r = cffi_requests.get(
    "https://example.com/article/123",
    impersonate="chrome124",
    timeout=15,
    allow_redirects=True,
)
print(f"Status: {r.status_code}, Body: {len(r.text)} bytes")
```

### All 8 Profiles with Profile-Matched Headers

```python
from curl_cffi import requests as cffi_requests
import random

PROFILES = {
    "chrome120": {
        "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "headers": {
            "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "none",
            "sec-fetch-user": "?1",
        },
    },
    "chrome124": {
        "ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "headers": {
            "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"',
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "none",
            "sec-fetch-user": "?1",
        },
    },
    "chrome131": {
        "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "headers": {
            "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "none",
            "sec-fetch-user": "?1",
        },
    },
    "safari17_5": {
        "ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
        "headers": {
            # Safari does NOT send sec-ch-ua or sec-fetch headers
        },
    },
    "safari16_0": {
        "ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15",
        "headers": {},
    },
    "firefox120": {
        "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
        "headers": {
            # Firefox sends sec-fetch but NOT sec-ch-ua
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "none",
            "sec-fetch-user": "?1",
        },
    },
    "firefox115": {
        "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:115.0) Gecko/20100101 Firefox/115.0",
        "headers": {
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "none",
            "sec-fetch-user": "?1",
        },
    },
    "edge120": {
        "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
        "headers": {
            "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Microsoft Edge";v="120"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "none",
            "sec-fetch-user": "?1",
        },
    },
}


def fetch_with_all_profiles(url: str) -> tuple[bool, str, str]:
    """Try all 8 TLS profiles.

    Returns: (success, html, winning_profile)
    """
    profiles = list(PROFILES.items())
    random.shuffle(profiles)

    for profile_name, config in profiles:
        try:
            headers = {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "User-Agent": config["ua"],
                **config["headers"],
            }
            r = cffi_requests.get(
                url, impersonate=profile_name, headers=headers,
                timeout=15, allow_redirects=True,
            )
            if r.status_code == 200 and len(r.text) > 500:
                return True, r.text, profile_name
        except Exception:
            continue

    return False, "", ""
```

---

## 2. Google News RSS Proxy

Completely bypasses the target site's WAF by fetching article URLs
from Google News. Google caches and re-serves article metadata.

### Fetch Latest Articles for a Domain

```python
import httpx
import feedparser
from datetime import datetime


def fetch_google_news_rss(
    domain: str,
    language: str = "en",
    country: str = "US",
    max_articles: int = 30,
) -> list[dict]:
    """Fetch articles from Google News RSS for a domain.

    Args:
        domain: Target domain (e.g., "www.chosun.com")
        language: 2-letter language code
        country: 2-letter country code
        max_articles: Maximum articles to return

    Returns:
        List of {title, url, published, source} dicts.
        URL points to the original article on the target site.
    """
    # Google News RSS search query
    gnews_url = (
        f"https://news.google.com/rss/search?"
        f"q=site:{domain}&hl={language}&gl={country}&ceid={country}:{language}"
    )

    try:
        r = httpx.get(
            gnews_url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15,
            follow_redirects=True,
        )
        if r.status_code != 200:
            return []

        feed = feedparser.parse(r.text)
        articles = []
        for entry in feed.entries[:max_articles]:
            articles.append({
                "title": entry.get("title", ""),
                "url": entry.get("link", ""),  # Original article URL
                "published": entry.get("published", ""),
                "source": entry.get("source", {}).get("title", domain),
            })
        return articles

    except Exception:
        return []


# Usage:
# articles = fetch_google_news_rss("www.chosun.com", language="ko", country="KR")
# for a in articles[:5]:
#     print(f"  {a['title'][:60]} -> {a['url']}")
```

### Korean News Sites Shortcut

```python
# Common Korean news domains and their Google News settings
KR_NEWS_SITES = {
    "chosun": {"domain": "www.chosun.com", "lang": "ko", "country": "KR"},
    "donga": {"domain": "www.donga.com", "lang": "ko", "country": "KR"},
    "joongang": {"domain": "www.joongang.co.kr", "lang": "ko", "country": "KR"},
    "hani": {"domain": "www.hani.co.kr", "lang": "ko", "country": "KR"},
    "khan": {"domain": "www.khan.co.kr", "lang": "ko", "country": "KR"},
    "hankyung": {"domain": "www.hankyung.com", "lang": "ko", "country": "KR"},
    "mk": {"domain": "www.mk.co.kr", "lang": "ko", "country": "KR"},
}


def fetch_kr_news(site_id: str, max_articles: int = 20) -> list[dict]:
    """Convenience wrapper for Korean news sites."""
    config = KR_NEWS_SITES.get(site_id)
    if not config:
        return []
    return fetch_google_news_rss(
        config["domain"], config["lang"], config["country"], max_articles,
    )
```

---

## 3. GDELT DOC API

GDELT monitors global news and indexes articles with ~15 minute delay.
Provides article URLs, titles, and metadata without touching the origin site.

### Basic Query

```python
import httpx
from datetime import datetime, timedelta


def fetch_gdelt_articles(
    domain: str,
    hours_back: int = 24,
    max_records: int = 50,
    language: str = "",
) -> list[dict]:
    """Fetch articles from GDELT DOC API.

    Args:
        domain: Target domain (e.g., "chosun.com")
        hours_back: How many hours to look back
        max_records: Maximum records to return
        language: Optional language filter (e.g., "Korean", "English")

    Returns:
        List of {title, url, date, language, domain, tone} dicts.
    """
    start = (datetime.now() - timedelta(hours=hours_back)).strftime("%Y%m%d%H%M%S")
    end = datetime.now().strftime("%Y%m%d%H%M%S")

    query = f"domain:{domain}"
    if language:
        query += f" sourcelang:{language}"

    gdelt_url = (
        f"https://api.gdeltproject.org/api/v2/doc/doc?"
        f"query={query}&mode=artlist&format=json"
        f"&startdatetime={start}&enddatetime={end}"
        f"&maxrecords={max_records}&sort=datedesc"
    )

    try:
        r = httpx.get(gdelt_url, timeout=20)
        if r.status_code != 200:
            return []

        data = r.json()
        articles = []
        for art in data.get("articles", []):
            articles.append({
                "title": art.get("title", ""),
                "url": art.get("url", ""),
                "date": art.get("seendate", ""),
                "language": art.get("language", ""),
                "domain": art.get("domain", domain),
                "tone": art.get("tone", 0),  # Sentiment score
            })
        return articles

    except Exception:
        return []


# Usage:
# articles = fetch_gdelt_articles("chosun.com", hours_back=48, language="Korean")
```

### GDELT Timeline API (Volume Monitoring)

```python
def check_site_activity(domain: str, days_back: int = 7) -> dict:
    """Check if a site is actively publishing (or down).

    Uses GDELT's timeline API to see article volume over time.
    If volume drops to zero, the site may be down or blocking.
    """
    start = (datetime.now() - timedelta(days=days_back)).strftime("%Y%m%d%H%M%S")
    end = datetime.now().strftime("%Y%m%d%H%M%S")

    timeline_url = (
        f"https://api.gdeltproject.org/api/v2/doc/doc?"
        f"query=domain:{domain}&mode=timelinevolinfo&format=json"
        f"&startdatetime={start}&enddatetime={end}"
    )

    try:
        r = httpx.get(timeline_url, timeout=15)
        data = r.json()
        timeline = data.get("timeline", [{}])[0].get("data", [])

        total_volume = sum(point.get("value", 0) for point in timeline)
        recent_volume = sum(
            point.get("value", 0)
            for point in timeline[-24:]  # Last 24 data points
        )

        return {
            "domain": domain,
            "total_articles_7d": total_volume,
            "recent_articles_24h": recent_volume,
            "is_active": recent_volume > 0,
            "data_points": len(timeline),
        }
    except Exception as e:
        return {"domain": domain, "error": str(e)}
```

---

## 4. Archive.today Fetch

Archive.today (archive.ph) stores full page snapshots, often including
JS-rendered content. Unlike Wayback Machine, it captures the page as
seen by a browser (with CSS, JS execution, etc.).

### Fetch Latest Snapshot

```python
import httpx


def fetch_archive_today(url: str, timeout: float = 20.0) -> tuple[bool, str, str]:
    """Fetch from Archive.today.

    Returns: (success, html_or_error, archive_url)
    """
    # /newest/ redirects to the most recent snapshot
    archive_url = f"https://archive.ph/newest/{url}"

    try:
        r = httpx.get(
            archive_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/131.0.0.0 Safari/537.36",
            },
            follow_redirects=True,
            timeout=timeout,
        )

        if r.status_code == 200 and len(r.text) > 1000:
            # The final URL after redirect is the actual archive URL
            final_url = str(r.url)
            return True, r.text, final_url

        return False, f"Status {r.status_code}, body {len(r.text)} bytes", ""

    except Exception as e:
        return False, str(e), ""


def submit_to_archive_today(url: str) -> str:
    """Submit a URL to Archive.today for archiving.

    Returns the archive URL where the snapshot will be available.
    Note: This triggers a new snapshot, which takes 10-30 seconds.
    """
    try:
        r = httpx.post(
            "https://archive.ph/submit/",
            data={"url": url},
            headers={"User-Agent": "Mozilla/5.0"},
            follow_redirects=True,
            timeout=60,
        )
        # After submission, the response usually redirects to the new snapshot
        return str(r.url)
    except Exception as e:
        return f"Error: {e}"
```

---

## 5. AMP Page Access

AMP (Accelerated Mobile Pages) versions are often served from CDN caches
(Google AMP Cache, Cloudflare AMP, Bing AMP) and bypass origin server
restrictions.

### Try All AMP Variants

```python
import httpx
from urllib.parse import urlparse, quote


def fetch_amp_version(url: str, timeout: float = 10.0) -> tuple[bool, str, str]:
    """Try multiple AMP URL patterns.

    Returns: (success, html, working_url)
    """
    parsed = urlparse(url)
    domain = parsed.hostname or ""

    amp_urls = [
        # Site's own AMP path
        f"{url}/amp",
        f"{url}?amp=1",
        f"{url}?outputType=amp",
        # Common AMP subdomain patterns
        url.replace("://www.", "://amp."),
        url.replace("://www.", "://m."),
        # Google AMP Cache (serves cached AMP version)
        f"https://{domain.replace('.', '-')}.cdn.ampproject.org/c/s/{domain}{parsed.path}",
        # Bing AMP viewer
        f"https://www.bing.com/amp/s/{domain}{parsed.path}",
    ]

    for amp_url in amp_urls:
        try:
            r = httpx.get(
                amp_url,
                headers={"User-Agent": "Mozilla/5.0"},
                follow_redirects=True,
                timeout=timeout,
            )
            if r.status_code == 200 and len(r.text) > 500:
                # Verify it has actual article content
                text_lower = r.text.lower()
                if any(tag in text_lower for tag in ["<article", "<p>", "amp-"]):
                    return True, r.text, amp_url
        except Exception:
            continue

    return False, "No AMP version found", ""
```

---

## 6. Patchright Stealth Browser

Patchright is a Playwright fork that patches automation detection at the
C++ level. It passes most anti-bot checks that standard Playwright fails.

### Basic Page Fetch (Subprocess)

```python
import subprocess
import sys
import json
import textwrap


def patchright_fetch(url: str, timeout_s: int = 30) -> tuple[bool, str]:
    """Fetch a page using Patchright stealth browser.

    Uses subprocess isolation to avoid async/sync conflicts.
    """
    script = textwrap.dedent(f"""\
        import asyncio, json, sys

        async def main():
            try:
                from patchright.async_api import async_playwright
            except ImportError:
                print(json.dumps({{"ok": False, "err": "patchright not installed"}}))
                return

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                ctx = await browser.new_context(
                    viewport={{"width": 1920, "height": 1080}},
                    locale="en-US",
                    timezone_id="America/New_York",
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/131.0.0.0 Safari/537.36"
                    ),
                )
                page = await ctx.new_page()
                try:
                    await page.goto("{url}", wait_until="networkidle", timeout={timeout_s * 1000})
                    await page.wait_for_timeout(2000)
                    html = await page.content()
                    print(json.dumps({{"ok": True, "html": html}}))
                except Exception as e:
                    print(json.dumps({{"ok": False, "err": str(e)}}))
                finally:
                    await browser.close()

        asyncio.run(main())
    """)

    try:
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, timeout=timeout_s + 10,
        )
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout.strip().split("\n")[-1])
            if data.get("ok"):
                return True, data["html"]
            return False, data.get("err", "Unknown")
        return False, result.stderr[:300]
    except subprocess.TimeoutExpired:
        return False, "Timeout"
    except Exception as e:
        return False, str(e)
```

### With Human-Like Behavior

```python
def patchright_fetch_human(url: str, timeout_s: int = 45) -> tuple[bool, str]:
    """Patchright with scroll, mouse movement, and random delays."""

    script = textwrap.dedent(f"""\
        import asyncio, json, random

        async def main():
            from patchright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                ctx = await browser.new_context(
                    viewport={{"width": 1920, "height": 1080}},
                    locale="en-US",
                    timezone_id="America/New_York",
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                )
                page = await ctx.new_page()

                try:
                    # Navigate
                    await page.goto("{url}", wait_until="domcontentloaded", timeout={timeout_s * 1000})
                    await page.wait_for_timeout(random.randint(1000, 2000))

                    # Human-like scroll
                    for _ in range(random.randint(2, 5)):
                        await page.mouse.wheel(0, random.randint(200, 600))
                        await page.wait_for_timeout(random.randint(300, 800))

                    # Random mouse movement
                    for _ in range(random.randint(1, 3)):
                        x = random.randint(100, 1800)
                        y = random.randint(100, 900)
                        await page.mouse.move(x, y)
                        await page.wait_for_timeout(random.randint(100, 300))

                    # Wait for lazy-loaded content
                    await page.wait_for_timeout(2000)
                    html = await page.content()
                    print(json.dumps({{"ok": True, "html": html}}))
                except Exception as e:
                    print(json.dumps({{"ok": False, "err": str(e)}}))
                finally:
                    await browser.close()

        asyncio.run(main())
    """)

    try:
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, timeout=timeout_s + 15,
        )
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout.strip().split("\n")[-1])
            if data.get("ok"):
                return True, data["html"]
            return False, data.get("err", "Unknown")
        return False, result.stderr[:300]
    except subprocess.TimeoutExpired:
        return False, "Timeout"
    except Exception as e:
        return False, str(e)
```

---

## 7. Cookie Warm-Up Pattern

Many sites require valid cookies before serving content. This pattern
visits the homepage first to collect cookies, then navigates to the
target URL with the established session.

### curl_cffi Session with Warm-Up

```python
from curl_cffi import requests as cffi_requests
from urllib.parse import urlparse
import time
import random


def cookie_warmup_fetch(url: str, profile: str = "chrome124") -> tuple[bool, str]:
    """Fetch with cookie warm-up using curl_cffi session.

    Flow: homepage -> optional section -> target URL
    Each step accumulates cookies in the session.
    """
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"

    session = cffi_requests.Session(impersonate=profile)

    try:
        # 1. Visit homepage -- get cookies, CF clearance, etc.
        r1 = session.get(f"{base}/", timeout=15)
        if r1.status_code not in (200, 301, 302):
            return False, f"Homepage: {r1.status_code}"

        time.sleep(random.uniform(1.0, 2.5))

        # 2. Visit section page (extract from URL path)
        path_parts = [p for p in parsed.path.split("/") if p]
        if len(path_parts) >= 2:
            section = f"{base}/{path_parts[0]}/"
            try:
                session.get(section, timeout=10)
                time.sleep(random.uniform(0.5, 1.5))
            except Exception:
                pass

        # 3. Fetch target with cookies + referer
        r = session.get(url, headers={"Referer": f"{base}/"}, timeout=15)

        if r.status_code == 200 and len(r.text) > 500:
            return True, r.text
        return False, f"Target: {r.status_code}, {len(r.text)} bytes"

    except Exception as e:
        return False, str(e)
    finally:
        session.close()
```

### httpx Session with Warm-Up

```python
import httpx
import time
import random
from urllib.parse import urlparse


def httpx_warmup_fetch(url: str) -> tuple[bool, str]:
    """httpx version of cookie warm-up (for sites without TLS fingerprinting)."""
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    with httpx.Client(follow_redirects=True, timeout=15, headers=headers) as client:
        # 1. Homepage
        r1 = client.get(f"{base}/")
        time.sleep(random.uniform(1.0, 2.0))

        # 2. Target (cookies carried by httpx.Client)
        r = client.get(url, headers={"Referer": f"{base}/"})

        if r.status_code == 200 and len(r.text) > 500:
            return True, r.text
        return False, f"Status {r.status_code}, body {len(r.text)} bytes"
```

---

## 8. Proxy Rotation with curl_cffi

Combines TLS impersonation with proxy rotation for maximum bypass capability.
Effective against IP blocks and geo-restrictions.

### Basic Proxy Rotation

```python
from curl_cffi import requests as cffi_requests
import random


def proxy_fetch(
    url: str,
    proxies: list[str],
    profile: str = "chrome124",
    max_tries: int = 5,
) -> tuple[bool, str, str]:
    """Fetch through rotating proxies with TLS impersonation.

    Args:
        url: Target URL
        proxies: List of proxy URLs (http://user:pass@host:port)
        profile: curl_cffi impersonation profile
        max_tries: Max proxies to try

    Returns: (success, html, used_proxy)
    """
    random.shuffle(proxies)

    for proxy in proxies[:max_tries]:
        proxy_dict = {"http": proxy, "https": proxy}
        try:
            r = cffi_requests.get(
                url,
                impersonate=profile,
                proxies=proxy_dict,
                timeout=20,
                allow_redirects=True,
            )
            if r.status_code == 200 and len(r.text) > 500:
                return True, r.text, proxy
        except Exception:
            continue

    return False, "All proxies failed", ""
```

### Geo-Targeted Proxy Rotation

```python
def geo_proxy_fetch(
    url: str,
    proxy_endpoint: str,
    target_countries: list[str],
    profile: str = "chrome124",
) -> tuple[bool, str, str]:
    """Fetch using geo-targeted proxy (for geo-blocked content).

    Most proxy providers support country targeting via URL parameters
    or username modifications.

    Args:
        url: Target URL
        proxy_endpoint: Base proxy URL (e.g., "http://user:pass@proxy.example.com:22225")
        target_countries: Country codes to try (e.g., ["kr", "us", "jp"])
        profile: curl_cffi profile

    Returns: (success, html, country_used)

    Example proxy formats by provider:
        BrightData:  http://USERNAME-country-kr:PASSWORD@brd.superproxy.io:22225
        SmartProxy:  http://USERNAME:PASSWORD@gate.smartproxy.com:7000  (session targeting)
        Oxylabs:     http://USERNAME:PASSWORD@pr.oxylabs.io:7777
    """
    for country in target_countries:
        # Modify proxy URL for country targeting
        # This example uses BrightData format -- adapt for your provider
        country_proxy = proxy_endpoint.replace("USERNAME", f"USERNAME-country-{country}")
        proxy_dict = {"http": country_proxy, "https": country_proxy}

        try:
            r = cffi_requests.get(
                url,
                impersonate=profile,
                proxies=proxy_dict,
                timeout=25,
                allow_redirects=True,
            )
            if r.status_code == 200 and len(r.text) > 500:
                return True, r.text, country
        except Exception:
            continue

    return False, "All countries failed", ""
```

### Free Proxy Discovery (Last Resort)

```python
import httpx


def fetch_free_proxies() -> list[str]:
    """Fetch free proxy list from public sources.

    WARNING: Free proxies are unreliable, slow, and potentially dangerous.
    Use only for testing or as an absolute last resort.
    """
    proxies = []

    # ProxyScrape API
    try:
        r = httpx.get(
            "https://api.proxyscrape.com/v3/free-proxy-list/get?"
            "request=displayproxies&protocol=http&timeout=5000&country=all&ssl=yes&anonymity=elite",
            timeout=10,
        )
        if r.status_code == 200:
            for line in r.text.strip().split("\n"):
                line = line.strip()
                if line and ":" in line:
                    proxies.append(f"http://{line}")
    except Exception:
        pass

    return proxies[:20]  # Limit to 20 for sanity
```

---

## 9. Wayback Machine CDX API

The Wayback Machine's CDX API provides programmatic access to archived
web pages. Useful as a last resort for retrieving content that is no
longer accessible.

### Find Snapshots

```python
import httpx
import json
from datetime import datetime


def find_wayback_snapshots(
    url: str,
    limit: int = 10,
    status_filter: int = 200,
) -> list[dict]:
    """Find Wayback Machine snapshots for a URL.

    Returns list of {timestamp, url, status, length, archive_url} dicts,
    sorted by most recent first.
    """
    cdx_url = (
        f"https://web.archive.org/cdx/search/cdx?"
        f"url={url}&output=json&limit={limit}&sort=reverse"
    )
    if status_filter:
        cdx_url += f"&filter=statuscode:{status_filter}"

    try:
        r = httpx.get(cdx_url, timeout=15,
                      headers={"User-Agent": "GlobalNews-Crawler/1.0"})
        if r.status_code != 200:
            return []

        rows = r.json()
        if len(rows) < 2:
            return []

        # rows[0] = header: [urlkey, timestamp, original, mimetype, statuscode, digest, length]
        snapshots = []
        for row in rows[1:]:
            ts = row[1]
            snapshots.append({
                "timestamp": ts,
                "date": datetime.strptime(ts[:8], "%Y%m%d").strftime("%Y-%m-%d"),
                "url": row[2],
                "mimetype": row[3],
                "status": int(row[4]),
                "length": int(row[6]) if row[6] != "-" else 0,
                "archive_url": f"https://web.archive.org/web/{ts}id_/{row[2]}",
            })
        return snapshots

    except Exception:
        return []


def fetch_wayback_content(archive_url: str, timeout: float = 20.0) -> tuple[bool, str]:
    """Fetch actual content from a Wayback Machine snapshot URL.

    Use the `id_` variant (no Wayback toolbar) for clean HTML.
    """
    try:
        r = httpx.get(
            archive_url,
            headers={"User-Agent": "GlobalNews-Crawler/1.0"},
            follow_redirects=True,
            timeout=timeout,
        )
        if r.status_code == 200 and len(r.text) > 500:
            return True, r.text
        return False, f"Status {r.status_code}, body {len(r.text)} bytes"
    except Exception as e:
        return False, str(e)
```

### Batch Wayback Check

```python
def batch_wayback_check(urls: list[str]) -> dict[str, dict]:
    """Check Wayback Machine availability for multiple URLs.

    Returns: {url: {available: bool, latest_date: str, archive_url: str}}
    """
    results = {}
    for url in urls:
        snapshots = find_wayback_snapshots(url, limit=1)
        if snapshots:
            s = snapshots[0]
            results[url] = {
                "available": True,
                "latest_date": s["date"],
                "archive_url": s["archive_url"],
            }
        else:
            results[url] = {"available": False, "latest_date": "", "archive_url": ""}
    return results
```

---

## 10. Camoufox Stealth Firefox

Camoufox is a modified Firefox build with 300+ anti-fingerprinting patches.
Provides a different browser engine from Patchright's Chromium, which is
critical when sites detect and block Chromium-based automation specifically.

### Basic Fetch

```python
import subprocess
import sys
import json
import textwrap


def camoufox_fetch(url: str, timeout_s: int = 40) -> tuple[bool, str]:
    """Fetch using Camoufox stealth Firefox."""
    script = textwrap.dedent(f"""\
        import json
        try:
            from camoufox.sync_api import Camoufox

            with Camoufox(headless=True) as browser:
                page = browser.new_page()
                page.goto("{url}", wait_until="networkidle", timeout={timeout_s * 1000})
                page.wait_for_timeout(2000)
                html = page.content()
                print(json.dumps({{"ok": True, "html": html}}))
        except ImportError:
            print(json.dumps({{"ok": False, "err": "camoufox not installed. Run: pip install camoufox && python -m camoufox fetch"}}))
        except Exception as e:
            print(json.dumps({{"ok": False, "err": str(e)}}))
    """)

    try:
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, timeout=timeout_s + 15,
        )
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout.strip().split("\n")[-1])
            if data.get("ok"):
                return True, data["html"]
            return False, data.get("err", "Unknown")
        return False, result.stderr[:300]
    except subprocess.TimeoutExpired:
        return False, "Timeout"
    except Exception as e:
        return False, str(e)
```

### With Custom Config

```python
def camoufox_fetch_custom(
    url: str,
    locale: str = "en-US",
    screen_width: int = 1920,
    screen_height: int = 1080,
    timeout_s: int = 40,
) -> tuple[bool, str]:
    """Camoufox with custom viewport and locale."""
    script = textwrap.dedent(f"""\
        import json
        try:
            from camoufox.sync_api import Camoufox

            with Camoufox(
                headless=True,
                screen=({screen_width}, {screen_height}),
                locale="{locale}",
            ) as browser:
                page = browser.new_page()
                page.goto("{url}", wait_until="networkidle", timeout={timeout_s * 1000})
                page.wait_for_timeout(3000)

                # Scroll to trigger lazy loading
                page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
                page.wait_for_timeout(1000)

                html = page.content()
                print(json.dumps({{"ok": True, "html": html}}))
        except ImportError:
            print(json.dumps({{"ok": False, "err": "camoufox not installed"}}))
        except Exception as e:
            print(json.dumps({{"ok": False, "err": str(e)}}))
    """)

    try:
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, timeout=timeout_s + 15,
        )
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout.strip().split("\n")[-1])
            if data.get("ok"):
                return True, data["html"]
            return False, data.get("err", "Unknown")
        return False, result.stderr[:300]
    except subprocess.TimeoutExpired:
        return False, "Timeout"
    except Exception as e:
        return False, str(e)
```

---

## 11. Cloud Browser APIs (Quick Reference)

### ScrapingBee

```python
import httpx


def scrapingbee_fetch(url: str, api_key: str) -> tuple[bool, str]:
    """ScrapingBee: managed browser + proxy + anti-bot bypass."""
    r = httpx.get(
        "https://app.scrapingbee.com/api/v1/",
        params={
            "api_key": api_key,
            "url": url,
            "render_js": "true",
            "premium_proxy": "true",
            "country_code": "us",
            "block_ads": "true",
            "wait": "5000",
        },
        timeout=60,
    )
    if r.status_code == 200 and len(r.text) > 500:
        return True, r.text
    return False, f"Status {r.status_code}"
```

### Zyte API

```python
def zyte_fetch(url: str, api_key: str) -> tuple[bool, str]:
    """Zyte API: automatic anti-bot bypass with browser rendering."""
    r = httpx.post(
        "https://api.zyte.com/v1/extract",
        json={"url": url, "browserHtml": True, "javascript": True},
        auth=(api_key, ""),
        timeout=60,
    )
    if r.status_code == 200:
        html = r.json().get("browserHtml", "")
        if len(html) > 500:
            return True, html
    return False, f"Status {r.status_code}"
```

### ScraperAPI

```python
def scraperapi_fetch(url: str, api_key: str) -> tuple[bool, str]:
    """ScraperAPI: simple proxy API with JS rendering."""
    r = httpx.get(
        "https://api.scraperapi.com/",
        params={"api_key": api_key, "url": url, "render": "true"},
        timeout=60,
    )
    if r.status_code == 200 and len(r.text) > 500:
        return True, r.text
    return False, f"Status {r.status_code}"
```

---

## Quick Selection Guide

```
"Site returns 403 with httpx"
  -> Try curl_cffi (Recipe #1) first
  -> If still 403, try cookie warm-up (Recipe #7)
  -> If still 403, try Patchright (Recipe #6)

"Cloudflare challenge page"
  -> Try cloudscraper (SKILL.md L4)
  -> If fails, try Patchright (Recipe #6)

"Rate limited (429)"
  -> Switch to Google News RSS (Recipe #2) or GDELT (Recipe #3)
  -> If need direct access, use proxy rotation (Recipe #8)

"Content is geo-blocked"
  -> Try AMP version (Recipe #5)
  -> Try Google Cache or Archive.today (Recipe #4)
  -> Use geo-targeted proxy (Recipe #8)

"Site completely unreachable"
  -> Wayback Machine (Recipe #9) for old content
  -> Google News RSS (Recipe #2) for recent article URLs
  -> GDELT (Recipe #3) for article metadata

"Everything fails"
  -> Cloud browser API (Recipe #11) -- costs money but works
  -> Wayback Machine + metadata-only (Recipe #9) as absolute last resort
```
