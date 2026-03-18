# Escalation Ladder -- 12-Level Implementation Guide

Detailed implementation reference for each of the 12 escalation levels.
All code targets the GlobalNews crawling system under `.venv/bin/python` (Python 3.12-3.13).

---

## Dependencies Matrix

| Level | Package | pip install | Included in project |
|-------|---------|------------|-------------------|
| L1 | httpx | `pip install httpx` | Yes (core) |
| L2-L3 | curl_cffi | `pip install curl_cffi` | Yes (core) |
| L4 | cloudscraper | `pip install cloudscraper` | Yes (core) |
| L5 | feedparser | `pip install feedparser` | Yes (analysis) |
| L6 | httpx (same) | -- | Yes |
| L7 | patchright | `pip install patchright && python -m patchright install chromium` | Yes (stealth_browser.py) |
| L8 | camoufox | `pip install camoufox && python -m camoufox fetch` | Optional |
| L9 | patchright + fingerprint-suite | `pip install patchright browserforge` | Optional |
| L10 | curl_cffi (same) | -- | Yes (proxy config needed) |
| L11 | httpx (same) | -- | Yes (API key needed) |
| L12 | httpx (same) | -- | Yes |

Check what is installed:

```bash
.venv/bin/pip list 2>/dev/null | grep -iE "httpx|curl.cffi|cloudscraper|patchright|camoufox|feedparser|browserforge"
```

---

## Level 1: httpx + UA Rotation

**Cost**: Free | **Latency**: Instant | **Complexity**: Trivial

### What it does

Sends a standard HTTP GET with a rotated User-Agent string. The simplest bypass for sites that only check the UA header.

### When to use

- First attempt on any new failure
- Status 403 with no JS challenge or CAPTCHA
- UA filter evidence from BlockDetector

### Block types addressed

- `UA_FILTER`
- Simple `IP_BLOCK` (some sites only check UA + basic rate)

### Implementation

```python
import httpx
import random

# Production UAs from ua_manager.py -- rotate on each request
USER_AGENTS = [
    # Chrome on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    # Chrome on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    # Safari on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    # Firefox on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    # Chrome on Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    # Edge on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
]


def fetch_l1(url: str, timeout: float = 15.0) -> tuple[bool, str, int]:
    """L1: httpx with rotated UA.

    Returns:
        (success, html_or_error, status_code)
    """
    ua = random.choice(USER_AGENTS)
    headers = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,ko;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
    try:
        r = httpx.get(url, headers=headers, follow_redirects=True, timeout=timeout)
        if r.status_code == 200 and len(r.text) > 500:
            return True, r.text, r.status_code
        return False, f"Status {r.status_code}, body length {len(r.text)}", r.status_code
    except Exception as e:
        return False, str(e), 0
```

---

## Level 2: curl_cffi TLS Impersonation

**Cost**: Free | **Latency**: ~50ms | **Complexity**: Low

### What it does

Uses curl_cffi to perfectly mimic the TLS handshake (JA3/JA4 fingerprint) of real browsers. Many WAFs reject connections that have Python-like TLS fingerprints even if headers look correct.

### When to use

- L1 returns 403 but no JS challenge or CAPTCHA
- BlockDetector reports `FINGERPRINT` with high confidence
- Site uses Akamai, Imperva, or similar TLS-fingerprint-aware WAF

### Block types addressed

- `FINGERPRINT`
- `UA_FILTER`
- Simple `JS_CHALLENGE` (some sites)

### 8 Browser Profiles

```python
PROFILES = [
    "chrome120",    # Chrome 120 on Windows
    "chrome124",    # Chrome 124 on macOS
    "chrome131",    # Chrome 131 latest
    "safari17_5",   # Safari 17.5 on macOS
    "safari16_0",   # Safari 16 on macOS
    "firefox120",   # Firefox 120 on Windows
    "firefox115",   # Firefox 115 ESR
    "edge120",      # Edge 120 on Windows
]
```

### Implementation

```python
from curl_cffi import requests as cffi_requests
import random

PROFILES = ["chrome120", "chrome124", "chrome131", "safari17_5",
            "safari16_0", "firefox120", "firefox115", "edge120"]

# Profile-specific headers to match the TLS fingerprint
PROFILE_HEADERS = {
    "chrome120": {
        "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "none",
        "sec-fetch-user": "?1",
    },
    "chrome124": {
        "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "none",
        "sec-fetch-user": "?1",
    },
    "safari17_5": {
        # Safari does NOT send sec-ch-ua or sec-fetch headers
    },
    "firefox120": {
        # Firefox sends sec-fetch but NOT sec-ch-ua
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "none",
        "sec-fetch-user": "?1",
    },
}


def fetch_l2(url: str, timeout: float = 15.0) -> tuple[bool, str, int]:
    """L2: curl_cffi with TLS impersonation, trying all profiles.

    Returns:
        (success, html_or_error, status_code)
    """
    profiles = list(PROFILES)
    random.shuffle(profiles)

    last_error = ""
    for profile in profiles:
        try:
            extra_headers = PROFILE_HEADERS.get(profile, {})
            headers = {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                **extra_headers,
            }
            r = cffi_requests.get(
                url,
                impersonate=profile,
                headers=headers,
                timeout=timeout,
                allow_redirects=True,
            )
            if r.status_code == 200 and len(r.text) > 500:
                return True, r.text, r.status_code
            last_error = f"Profile {profile}: status {r.status_code}, body {len(r.text)} bytes"
        except Exception as e:
            last_error = f"Profile {profile}: {e}"
            continue

    return False, f"All 8 profiles failed. Last: {last_error}", 0
```

---

## Level 3: curl_cffi + Cookie Warm-up + Header Sync

**Cost**: Free | **Latency**: 2x requests | **Complexity**: Medium

### What it does

Creates a curl_cffi session, visits the site homepage first to collect cookies and establish a "session" with the WAF, then navigates to the target URL. Mimics real user navigation flow.

### When to use

- L2 gets 200 on homepage but 403 on article page
- Site sets mandatory cookies on first visit (CF clearance, session tokens)
- BlockDetector reports session-based block patterns

### Block types addressed

- `FINGERPRINT` (session-validated)
- Session-based `IP_BLOCK`

### Implementation

```python
from curl_cffi import requests as cffi_requests
from urllib.parse import urlparse
import time
import random


def fetch_l3(url: str, timeout: float = 15.0) -> tuple[bool, str, int]:
    """L3: curl_cffi session with cookie warm-up.

    Steps:
    1. Create a persistent session with one TLS profile
    2. Visit homepage to collect cookies
    3. Wait 1-3s (human-like)
    4. Visit a section page if identifiable (builds referer chain)
    5. Visit target URL with accumulated cookies
    """
    parsed = urlparse(url)
    domain = parsed.hostname or ""
    base_url = f"{parsed.scheme}://{parsed.netloc}"

    profile = random.choice(["chrome124", "chrome131", "safari17_5"])
    session = cffi_requests.Session(impersonate=profile)

    try:
        # Step 1: Homepage warm-up
        r_home = session.get(base_url + "/", timeout=timeout)
        if r_home.status_code != 200:
            return False, f"Homepage returned {r_home.status_code}", r_home.status_code

        # Step 2: Human-like delay
        time.sleep(random.uniform(1.0, 3.0))

        # Step 3: Section page (optional -- derive from URL path)
        path_parts = parsed.path.strip("/").split("/")
        if len(path_parts) > 1:
            section_url = f"{base_url}/{path_parts[0]}/"
            try:
                session.get(section_url, timeout=timeout)
                time.sleep(random.uniform(0.5, 1.5))
            except Exception:
                pass  # Section visit is best-effort

        # Step 4: Target URL with full cookie jar + referer
        headers = {"Referer": base_url + "/"}
        r = session.get(url, headers=headers, timeout=timeout)

        if r.status_code == 200 and len(r.text) > 500:
            return True, r.text, r.status_code

        return False, f"Status {r.status_code} after warm-up, body {len(r.text)} bytes", r.status_code

    except Exception as e:
        return False, str(e), 0
    finally:
        session.close()
```

---

## Level 4: cloudscraper Cloudflare JS Solver

**Cost**: Free | **Latency**: ~500ms | **Complexity**: Low

### What it does

Uses cloudscraper to automatically solve Cloudflare's JavaScript challenge without a browser. Works for the standard "checking your browser" interstitial.

### When to use

- Response contains Cloudflare challenge markers (cf_clearance, `__cf_bm`)
- BlockDetector reports `JS_CHALLENGE` with Cloudflare evidence
- 5-second delay page observed

### Block types addressed

- `JS_CHALLENGE` (Cloudflare specifically)

### Implementation

```python
import cloudscraper


def fetch_l4(url: str, timeout: float = 20.0) -> tuple[bool, str, int]:
    """L4: cloudscraper for Cloudflare JS challenges.

    Note: cloudscraper works for CF's JavaScript challenge but NOT
    for hCaptcha/Turnstile challenges. For those, use L7-L9 browsers.
    """
    try:
        scraper = cloudscraper.create_scraper(
            browser={
                "browser": "chrome",
                "platform": "windows",
                "mobile": False,
            },
            delay=5,  # Delay for CF challenge
        )
        r = scraper.get(url, timeout=timeout)

        if r.status_code == 200 and len(r.text) > 500:
            # Verify it is not still the challenge page
            if "cf-browser-verification" not in r.text.lower():
                return True, r.text, r.status_code
            return False, "Cloudflare challenge not solved", r.status_code

        return False, f"Status {r.status_code}, body {len(r.text)} bytes", r.status_code
    except cloudscraper.exceptions.CloudflareChallengeError as e:
        return False, f"CF challenge failed: {e}", 0
    except Exception as e:
        return False, str(e), 0
```

---

## Level 5: RSS/Atom + Google News RSS + GDELT API

**Cost**: Free | **Latency**: ~1s | **Complexity**: Medium

### What it does

Completely bypasses the site's web server by fetching article metadata and sometimes full text from alternative sources: the site's own RSS feed, Google News RSS, and GDELT's DOC API.

### When to use

- Direct access consistently fails regardless of method (hard IP block, aggressive WAF)
- Need article URLs/titles even if full text is not available
- Rate limited and need to reduce direct requests

### Block types addressed

- `RATE_LIMIT`
- `IP_BLOCK`
- `404` (URL structure changed)

### Implementation

```python
import httpx
from datetime import datetime, timedelta

# Common RSS feed paths (from dynamic_bypass.py)
RSS_PATHS = ["/feed", "/rss", "/rss.xml", "/feed.xml", "/atom.xml",
             "/feeds/all.atom.xml", "/index.xml", "/blog/feed"]


def fetch_l5_rss(domain: str, timeout: float = 10.0) -> list[dict]:
    """L5a: Try site's native RSS/Atom feed.

    Returns list of {title, url, published, summary} dicts.
    """
    import feedparser

    articles = []
    for path in RSS_PATHS:
        try:
            r = httpx.get(f"https://{domain}{path}",
                          headers={"User-Agent": "Mozilla/5.0"},
                          timeout=timeout, follow_redirects=True)
            if r.status_code == 200 and ("<rss" in r.text[:500] or "<feed" in r.text[:500]):
                feed = feedparser.parse(r.text)
                for entry in feed.entries[:50]:
                    articles.append({
                        "title": entry.get("title", ""),
                        "url": entry.get("link", ""),
                        "published": entry.get("published", ""),
                        "summary": entry.get("summary", "")[:500],
                    })
                if articles:
                    return articles
        except Exception:
            continue
    return articles


def fetch_l5_google_news(domain: str, timeout: float = 10.0) -> list[dict]:
    """L5b: Google News RSS for a domain.

    Returns list of {title, url, published, source} dicts.
    Google News RSS provides article URLs from the original site.
    """
    import feedparser

    gnews_url = f"https://news.google.com/rss/search?q=site:{domain}&hl=en&gl=US&ceid=US:en"
    articles = []
    try:
        r = httpx.get(gnews_url, headers={"User-Agent": "Mozilla/5.0"},
                      timeout=timeout, follow_redirects=True)
        if r.status_code == 200:
            feed = feedparser.parse(r.text)
            for entry in feed.entries[:30]:
                articles.append({
                    "title": entry.get("title", ""),
                    "url": entry.get("link", ""),
                    "published": entry.get("published", ""),
                    "source": entry.get("source", {}).get("title", domain),
                })
    except Exception:
        pass
    return articles


def fetch_l5_gdelt(domain: str, timeout: float = 15.0) -> list[dict]:
    """L5c: GDELT DOC API for a domain.

    Returns list of {title, url, date, language, domain} dicts.
    GDELT indexes news articles globally with ~15min delay.
    """
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d%H%M%S")
    now = datetime.now().strftime("%Y%m%d%H%M%S")

    gdelt_url = (
        f"https://api.gdeltproject.org/api/v2/doc/doc?"
        f"query=domain:{domain}&mode=artlist&format=json"
        f"&startdatetime={yesterday}&enddatetime={now}"
        f"&maxrecords=50"
    )
    articles = []
    try:
        r = httpx.get(gdelt_url, timeout=timeout)
        if r.status_code == 200:
            data = r.json()
            for art in data.get("articles", []):
                articles.append({
                    "title": art.get("title", ""),
                    "url": art.get("url", ""),
                    "date": art.get("seendate", ""),
                    "language": art.get("language", ""),
                    "domain": art.get("domain", domain),
                })
    except Exception:
        pass
    return articles
```

---

## Level 6: AMP + Google Cache + Archive.today

**Cost**: Free | **Latency**: ~2s | **Complexity**: Low

### What it does

Fetches cached or alternative versions of the page that may bypass geo-restrictions or soft blocks. AMP versions are served from CDN, Google Cache from Google's servers, and Archive.today from its own archive.

### When to use

- Content was recently available but now blocked
- Geo-block or soft paywall
- URL returns 404 but content existed recently

### Block types addressed

- `GEO_BLOCK`
- `404` (recent content)
- Soft paywalls and metering

### Implementation

```python
import httpx
from urllib.parse import quote


def fetch_l6_amp(url: str, timeout: float = 10.0) -> tuple[bool, str]:
    """L6a: Try AMP version of the page.

    AMP pages are often served from Google's AMP cache CDN,
    bypassing the origin server's geo-restrictions.
    """
    amp_variations = [
        f"{url}/amp",
        f"{url}?amp=1",
        f"{url}?outputType=amp",
        url.replace("://www.", "://amp."),
        url.replace("://www.", "://m."),  # Mobile version as bonus
    ]

    for amp_url in amp_variations:
        try:
            r = httpx.get(amp_url, headers={"User-Agent": "Mozilla/5.0"},
                          follow_redirects=True, timeout=timeout)
            if r.status_code == 200 and len(r.text) > 500:
                # Verify it has actual content, not just a redirect stub
                if "<article" in r.text.lower() or "<p>" in r.text.lower():
                    return True, r.text
        except Exception:
            continue
    return False, "No AMP version found"


def fetch_l6_google_cache(url: str, timeout: float = 15.0) -> tuple[bool, str]:
    """L6b: Fetch Google's cached version.

    Google Cache stores the last time Googlebot crawled the page.
    Bypasses geo-restrictions since content is served from Google.
    """
    cache_url = f"https://webcache.googleusercontent.com/search?q=cache:{quote(url)}&hl=en"
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "text/html",
        }
        r = httpx.get(cache_url, headers=headers, follow_redirects=True, timeout=timeout)
        if r.status_code == 200 and len(r.text) > 500:
            return True, r.text
        return False, f"Google Cache: status {r.status_code}"
    except Exception as e:
        return False, f"Google Cache: {e}"


def fetch_l6_archive_today(url: str, timeout: float = 20.0) -> tuple[bool, str]:
    """L6c: Fetch from Archive.today (archive.ph).

    Archive.today stores full page snapshots. Unlike Wayback Machine,
    it often captures JS-rendered content and bypasses paywalls.
    """
    archive_url = f"https://archive.ph/newest/{url}"
    try:
        r = httpx.get(archive_url, headers={"User-Agent": "Mozilla/5.0"},
                      follow_redirects=True, timeout=timeout)
        if r.status_code == 200 and len(r.text) > 1000:
            return True, r.text
        return False, f"Archive.today: status {r.status_code}"
    except Exception as e:
        return False, f"Archive.today: {e}"
```

---

## Level 7: Patchright Stealth Chromium

**Cost**: 100-500MB RAM, 3-8s/page | **Latency**: 3-8s | **Complexity**: High

### What it does

Launches a full stealth Chromium browser via Patchright (a Playwright fork that patches automation detection at the C++ level). Executes JavaScript, solves some CAPTCHAs via stealth, and renders the full page.

### When to use

- JS Challenge that cloudscraper cannot solve
- Advanced anti-bot (PerimeterX, DataDome, Akamai Bot Manager)
- CAPTCHA that auto-passes with realistic browser fingerprint

### Block types addressed

- `JS_CHALLENGE`
- `CAPTCHA` (some)
- `FINGERPRINT`

### Implementation

```python
import subprocess
import sys
import json
import textwrap


def fetch_l7(url: str, timeout_seconds: int = 30) -> tuple[bool, str]:
    """L7: Patchright stealth browser via subprocess.

    Uses subprocess isolation (same pattern as browser_renderer.py)
    to avoid sync/async conflicts with the main pipeline.
    """
    script = textwrap.dedent(f"""\
        import asyncio
        import json
        import sys

        async def render():
            try:
                from patchright.async_api import async_playwright
                engine = "patchright"
            except ImportError:
                from playwright.async_api import async_playwright
                engine = "playwright"

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    viewport={{"width": 1920, "height": 1080}},
                    locale="en-US",
                    timezone_id="America/New_York",
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/131.0.0.0 Safari/537.36"
                    ),
                )
                page = await context.new_page()

                try:
                    await page.goto("{url}",
                                    wait_until="networkidle",
                                    timeout={timeout_seconds * 1000})
                    # Wait for content to settle
                    await page.wait_for_timeout(2000)
                    html = await page.content()
                    print(json.dumps({{"success": True, "html": html, "engine": engine}}))
                except Exception as e:
                    print(json.dumps({{"success": False, "error": str(e)}}))
                finally:
                    await browser.close()

        asyncio.run(render())
    """)

    try:
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True,
            timeout=timeout_seconds + 10,
        )
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout.strip().split("\n")[-1])
            if data.get("success") and len(data.get("html", "")) > 500:
                return True, data["html"]
            return False, data.get("error", "Empty content")
        return False, f"Process error: {result.stderr[:500]}"
    except subprocess.TimeoutExpired:
        return False, "Browser timeout"
    except Exception as e:
        return False, str(e)
```

---

## Level 8: Camoufox Stealth Firefox

**Cost**: 200-600MB RAM, 4-10s/page | **Latency**: 4-10s | **Complexity**: High

### What it does

Uses Camoufox, a modified Firefox build with 300+ anti-fingerprinting patches. Provides a different browser engine fingerprint from Patchright's Chromium, which is critical when sites specifically detect and block Chromium-based automation.

### When to use

- L7 Patchright is detected (site specifically blocks Chromium automation)
- Need Firefox-based TLS/browser fingerprint diversity
- Advanced CAPTCHA that passes better with Firefox

### Block types addressed

- `CAPTCHA`
- `FINGERPRINT`
- `JS_CHALLENGE`

### Implementation

```python
import subprocess
import sys
import json
import textwrap


def fetch_l8(url: str, timeout_seconds: int = 40) -> tuple[bool, str]:
    """L8: Camoufox stealth Firefox via subprocess.

    Camoufox provides a separate browser engine (Gecko/Firefox) with
    extensive anti-fingerprinting patches. Some sites specifically
    detect Chromium automation but not Firefox-based tools.
    """
    script = textwrap.dedent(f"""\
        import json
        try:
            from camoufox.sync_api import Camoufox

            with Camoufox(headless=True) as browser:
                page = browser.new_page()
                page.goto("{url}", wait_until="networkidle", timeout={timeout_seconds * 1000})
                page.wait_for_timeout(2000)
                html = page.content()

                if len(html) > 500:
                    print(json.dumps({{"success": True, "html": html}}))
                else:
                    print(json.dumps({{"success": False, "error": "Content too short"}}))
        except ImportError:
            print(json.dumps({{"success": False, "error": "camoufox not installed"}}))
        except Exception as e:
            print(json.dumps({{"success": False, "error": str(e)}}))
    """)

    try:
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True,
            timeout=timeout_seconds + 15,
        )
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout.strip().split("\n")[-1])
            if data.get("success"):
                return True, data["html"]
            return False, data.get("error", "Unknown error")
        return False, f"Process error: {result.stderr[:500]}"
    except subprocess.TimeoutExpired:
        return False, "Camoufox timeout"
    except Exception as e:
        return False, str(e)
```

---

## Level 9: Browser + Fingerprint-Suite Randomization

**Cost**: 200-600MB RAM | **Latency**: 5-12s | **Complexity**: Very High

### What it does

Combines Patchright with comprehensive fingerprint randomization: canvas noise injection, WebGL parameter randomization, font enumeration spoofing, and randomized viewport/locale/timezone combinations. Each page load presents a unique, realistic browser fingerprint.

### When to use

- L7 and L8 are detected by sophisticated anti-bot (PerimeterX, DataDome, Kasada)
- Site uses canvas/WebGL fingerprinting to identify automation
- Need maximum fingerprint entropy

### Block types addressed

- `FINGERPRINT` (advanced)
- `CAPTCHA` (behavioral)

### Implementation

```python
import subprocess
import sys
import json
import textwrap
import random


def fetch_l9(url: str, timeout_seconds: int = 40) -> tuple[bool, str]:
    """L9: Patchright with full fingerprint randomization."""

    viewport_w = random.choice([1366, 1440, 1536, 1920, 2560])
    viewport_h = random.choice([768, 900, 864, 1080, 1440])
    locale = random.choice(["en-US", "en-GB", "ko-KR", "ja-JP", "de-DE"])
    tz = random.choice([
        "America/New_York", "America/Chicago", "America/Los_Angeles",
        "Europe/London", "Europe/Berlin", "Asia/Seoul", "Asia/Tokyo",
    ])
    color = random.choice(["light", "dark"])
    scale = random.choice([1.0, 1.25, 1.5, 2.0])

    script = textwrap.dedent(f"""\
        import asyncio
        import json
        import sys

        CANVAS_NOISE_SCRIPT = '''
        // Canvas fingerprint noise
        const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
        HTMLCanvasElement.prototype.toDataURL = function(type) {{
            const ctx = this.getContext('2d');
            if (ctx) {{
                try {{
                    const img = ctx.getImageData(0, 0, this.width, this.height);
                    for (let i = 0; i < img.data.length; i += 4) {{
                        img.data[i] = Math.max(0, Math.min(255, img.data[i] + Math.floor(Math.random() * 3) - 1));
                    }}
                    ctx.putImageData(img, 0, 0);
                }} catch(e) {{}}
            }}
            return origToDataURL.apply(this, arguments);
        }};

        // WebGL parameter noise
        const origGetParameter = WebGLRenderingContext.prototype.getParameter;
        WebGLRenderingContext.prototype.getParameter = function(param) {{
            // UNMASKED_VENDOR_WEBGL
            if (param === 37445) return 'Google Inc. (NVIDIA)';
            // UNMASKED_RENDERER_WEBGL
            if (param === 37446) return 'ANGLE (NVIDIA, NVIDIA GeForce GTX 1080 Direct3D11 vs_5_0 ps_5_0)';
            return origGetParameter.apply(this, arguments);
        }};

        // Navigator properties
        Object.defineProperty(navigator, 'hardwareConcurrency', {{get: () => {random.choice([4, 8, 12, 16])}}});
        Object.defineProperty(navigator, 'deviceMemory', {{get: () => {random.choice([4, 8, 16])}}});
        '''

        async def render():
            try:
                from patchright.async_api import async_playwright
            except ImportError:
                from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    viewport={{"width": {viewport_w}, "height": {viewport_h}}},
                    locale="{locale}",
                    timezone_id="{tz}",
                    color_scheme="{color}",
                    device_scale_factor={scale},
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/131.0.0.0 Safari/537.36"
                    ),
                )
                page = await context.new_page()
                await page.add_init_script(CANVAS_NOISE_SCRIPT)

                try:
                    await page.goto("{url}",
                                    wait_until="networkidle",
                                    timeout={timeout_seconds * 1000})
                    await page.wait_for_timeout(3000)
                    html = await page.content()
                    print(json.dumps({{"success": True, "html": html}}))
                except Exception as e:
                    print(json.dumps({{"success": False, "error": str(e)}}))
                finally:
                    await browser.close()

        asyncio.run(render())
    """)

    try:
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True,
            timeout=timeout_seconds + 15,
        )
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout.strip().split("\n")[-1])
            if data.get("success") and len(data.get("html", "")) > 500:
                return True, data["html"]
            return False, data.get("error", "Empty content")
        return False, f"Process error: {result.stderr[:500]}"
    except subprocess.TimeoutExpired:
        return False, "Browser timeout"
    except Exception as e:
        return False, str(e)
```

---

## Level 10: Proxy Rotation (Residential/Datacenter)

**Cost**: $0.001-0.01/req | **Latency**: 1-3s | **Complexity**: Medium

### What it does

Routes requests through a pool of residential or datacenter proxies, presenting different IP addresses to bypass IP-based blocks and geo-restrictions.

### When to use

- Site blocks by IP address regardless of other measures
- Geo-restricted content (need specific country IP)
- Rate limiting that cannot be avoided by other means

### Block types addressed

- `IP_BLOCK`
- `RATE_LIMIT`
- `GEO_BLOCK`

### Implementation

```python
from curl_cffi import requests as cffi_requests
import random


def fetch_l10(
    url: str,
    proxies: list[str],
    target_country: str = "",
    timeout: float = 20.0,
) -> tuple[bool, str, int]:
    """L10: curl_cffi through proxy pool.

    Args:
        url: Target URL.
        proxies: List of proxy URLs (http://user:pass@host:port).
                 For geo-targeting, use country-specific proxy endpoints.
        target_country: ISO country code for geo-targeted proxies.
        timeout: Request timeout.
    """
    if not proxies:
        return False, "No proxies configured", 0

    # Filter proxies by country if needed
    if target_country:
        country_proxies = [p for p in proxies if target_country.lower() in p.lower()]
        if country_proxies:
            proxies = country_proxies

    random.shuffle(proxies)

    last_error = ""
    for proxy in proxies[:5]:  # Try up to 5 proxies
        proxy_dict = {"http": proxy, "https": proxy}
        try:
            r = cffi_requests.get(
                url,
                impersonate="chrome124",
                proxies=proxy_dict,
                timeout=timeout,
                allow_redirects=True,
            )
            if r.status_code == 200 and len(r.text) > 500:
                return True, r.text, r.status_code
            last_error = f"Proxy {proxy[:30]}...: status {r.status_code}"
        except Exception as e:
            last_error = f"Proxy {proxy[:30]}...: {e}"
            continue

    return False, f"All proxies failed. Last: {last_error}", 0


# --- Proxy providers configuration examples ---

# BrightData (Residential)
# proxy = "http://USERNAME:PASSWORD@brd.superproxy.io:22225"
# With country targeting:
# proxy = "http://USERNAME-country-kr:PASSWORD@brd.superproxy.io:22225"

# SmartProxy (Residential)
# proxy = "http://USERNAME:PASSWORD@gate.smartproxy.com:7000"

# Oxylabs (Datacenter)
# proxy = "http://USERNAME:PASSWORD@pr.oxylabs.io:7777"

# ScraperAPI as proxy
# proxy = "http://scraperapi:API_KEY@proxy-server.scraperapi.com:8001"
```

---

## Level 11: Cloud Browser (ScrapingBee / Zyte)

**Cost**: $0.001-0.01/req | **Latency**: 5-15s | **Complexity**: Low (API call)

### What it does

Delegates rendering and anti-bot bypass to a managed cloud service. These services maintain large browser farms with residential IPs, CAPTCHA solving, and JavaScript rendering.

### When to use

- All local methods fail
- Enterprise-grade anti-bot (Akamai, PerimeterX, DataDome, Kasada)
- Need guaranteed high success rate

### Block types addressed

- All block types (managed bypass)

### Implementation

```python
import httpx
import json
import base64


def fetch_l11_scrapingbee(url: str, api_key: str, timeout: float = 60.0) -> tuple[bool, str]:
    """L11a: ScrapingBee cloud browser API.

    Premium proxy + JS rendering + stealth mode.
    Pricing: ~$0.005 per credit (1 credit = 1 simple request, 5 = JS render).
    """
    params = {
        "api_key": api_key,
        "url": url,
        "render_js": "true",
        "premium_proxy": "true",
        "country_code": "us",
        "block_ads": "true",
        "block_resources": "false",
        "wait": "5000",
    }
    try:
        r = httpx.get("https://app.scrapingbee.com/api/v1/",
                      params=params, timeout=timeout)
        if r.status_code == 200 and len(r.text) > 500:
            return True, r.text
        return False, f"ScrapingBee: status {r.status_code}, body {len(r.text)} bytes"
    except Exception as e:
        return False, f"ScrapingBee: {e}"


def fetch_l11_zyte(url: str, api_key: str, timeout: float = 60.0) -> tuple[bool, str]:
    """L11b: Zyte API (formerly ScrapyCloud) with browser rendering.

    Automatic anti-bot bypass + CAPTCHA solving.
    Pricing: ~$0.001-0.01 per request depending on features.
    """
    try:
        r = httpx.post(
            "https://api.zyte.com/v1/extract",
            json={
                "url": url,
                "browserHtml": True,
                "javascript": True,
                "geolocation": "US",
            },
            auth=(api_key, ""),
            timeout=timeout,
        )
        if r.status_code == 200:
            data = r.json()
            html = data.get("browserHtml", "")
            if len(html) > 500:
                return True, html
            return False, "Zyte: empty browserHtml"
        return False, f"Zyte: status {r.status_code}"
    except Exception as e:
        return False, f"Zyte: {e}"


def fetch_l11_scraperapi(url: str, api_key: str, timeout: float = 60.0) -> tuple[bool, str]:
    """L11c: ScraperAPI with auto-parsing.

    Simple API with automatic proxy rotation + CAPTCHA bypass.
    Pricing: $0.001-0.004 per request.
    """
    params = {
        "api_key": api_key,
        "url": url,
        "render": "true",
        "country_code": "us",
    }
    try:
        r = httpx.get("https://api.scraperapi.com/", params=params, timeout=timeout)
        if r.status_code == 200 and len(r.text) > 500:
            return True, r.text
        return False, f"ScraperAPI: status {r.status_code}"
    except Exception as e:
        return False, f"ScraperAPI: {e}"
```

---

## Level 12: Wayback Machine + Metadata-Only

**Cost**: Free | **Latency**: 3-10s | **Complexity**: Low

### What it does

Fetches the most recent snapshot from the Internet Archive's Wayback Machine. As a last resort, if even Wayback content is unavailable, extracts metadata only (title, date, URL) for the record.

### When to use

- Absolute last resort after all other methods fail
- Content is stale but better than nothing
- Site is completely unreachable (DNS failure, shutdown)

### Block types addressed

- All (content may be stale)

### Implementation

```python
import httpx
import json
from datetime import datetime


def fetch_l12_wayback(url: str, timeout: float = 20.0) -> tuple[bool, str, dict]:
    """L12a: Wayback Machine -- most recent snapshot.

    Returns:
        (success, html_or_error, metadata)
        metadata includes: snapshot_date, original_url, archive_url
    """
    # CDX API -- find most recent snapshot
    cdx_url = (
        f"https://web.archive.org/cdx/search/cdx?"
        f"url={url}&output=json&limit=5&sort=reverse"
        f"&filter=statuscode:200"
    )
    try:
        r = httpx.get(cdx_url, timeout=timeout,
                      headers={"User-Agent": "GlobalNews-Crawler/1.0"})
        if r.status_code != 200:
            return False, f"CDX API: status {r.status_code}", {}

        rows = r.json()
        if len(rows) < 2:  # First row is header
            return False, "No Wayback snapshots found", {}

        # rows[0] is header: [urlkey, timestamp, original, mimetype, statuscode, digest, length]
        timestamp = rows[1][1]
        original = rows[1][2]
        snapshot_date = datetime.strptime(timestamp[:8], "%Y%m%d").strftime("%Y-%m-%d")

        archive_url = f"https://web.archive.org/web/{timestamp}id_/{original}"
        metadata = {
            "snapshot_date": snapshot_date,
            "original_url": original,
            "archive_url": archive_url,
            "timestamp": timestamp,
        }

        # Fetch the actual snapshot
        content_r = httpx.get(archive_url, timeout=timeout, follow_redirects=True,
                              headers={"User-Agent": "GlobalNews-Crawler/1.0"})
        if content_r.status_code == 200 and len(content_r.text) > 500:
            return True, content_r.text, metadata

        return False, f"Snapshot fetch failed: {content_r.status_code}", metadata

    except Exception as e:
        return False, f"Wayback: {e}", {}


def fetch_l12_metadata_only(url: str, timeout: float = 10.0) -> dict:
    """L12b: Metadata-only fallback.

    When even Wayback Machine content is unavailable, extract
    minimal metadata (title, date, domain) for the record.
    This ensures the URL is not silently lost.
    """
    from urllib.parse import urlparse
    parsed = urlparse(url)
    domain = parsed.hostname or ""

    metadata = {
        "url": url,
        "domain": domain,
        "status": "metadata_only",
        "reason": "All 12 levels exhausted",
        "title": None,
        "date": None,
    }

    # Try to get title from Google search cache
    try:
        google_url = f"https://www.google.com/search?q=cache:{url}"
        r = httpx.get(google_url, timeout=timeout,
                      headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200:
            import re
            title_match = re.search(r"<title>(.*?)</title>", r.text, re.IGNORECASE)
            if title_match:
                metadata["title"] = title_match.group(1)
    except Exception:
        pass

    return metadata
```

---

## Block Type to Level Mapping (Complete Matrix)

```
                L1   L2   L3   L4   L5   L6   L7   L8   L9   L10  L11  L12
UA_FILTER      [X]  [X]  [ ]  [ ]  [ ]  [ ]  [X]  [ ]  [ ]  [ ]  [X]  [ ]
FINGERPRINT    [ ]  [X]  [X]  [ ]  [ ]  [ ]  [X]  [X]  [X]  [X]  [X]  [ ]
JS_CHALLENGE   [ ]  [ ]  [ ]  [X]  [ ]  [ ]  [X]  [X]  [ ]  [ ]  [X]  [ ]
CAPTCHA        [ ]  [ ]  [ ]  [ ]  [ ]  [ ]  [X]  [X]  [X]  [ ]  [X]  [ ]
RATE_LIMIT     [X]  [ ]  [ ]  [ ]  [X]  [ ]  [ ]  [ ]  [ ]  [X]  [X]  [ ]
IP_BLOCK       [ ]  [ ]  [ ]  [ ]  [X]  [X]  [ ]  [ ]  [ ]  [X]  [X]  [X]
GEO_BLOCK      [ ]  [ ]  [ ]  [ ]  [ ]  [X]  [ ]  [ ]  [ ]  [X]  [X]  [X]
404/URL_CHANGE [ ]  [ ]  [ ]  [ ]  [X]  [X]  [ ]  [ ]  [ ]  [ ]  [ ]  [X]
UNKNOWN        [X]  [X]  [X]  [X]  [X]  [X]  [X]  [X]  [X]  [X]  [X]  [X]
```

---

## Unified Executor

```python
def run_escalation_ladder(
    url: str,
    block_type: str = "unknown",
    proxies: list[str] | None = None,
    cloud_api_keys: dict[str, str] | None = None,
    max_level: int = 12,
) -> dict:
    """Run the full 12-level escalation ladder for a URL.

    Returns dict with: success, html, level_used, attempts_log
    """
    cloud_api_keys = cloud_api_keys or {}
    proxies = proxies or []

    # Map block type to ordered level list
    BLOCK_TO_LEVELS = {
        "ua_filter":     [1, 2, 7, 11],
        "fingerprint":   [2, 3, 7, 8, 9, 10, 11],
        "js_challenge":  [4, 7, 8, 11],
        "captcha":       [7, 8, 9, 11],
        "rate_limit":    [1, 5, 10, 11],
        "ip_block":      [5, 6, 10, 11, 12],
        "geo_block":     [6, 10, 11, 12],
        "404":           [5, 6, 12],
        "unknown":       [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    }

    levels = BLOCK_TO_LEVELS.get(block_type, BLOCK_TO_LEVELS["unknown"])
    levels = [l for l in levels if l <= max_level]

    attempts_log = []
    for level in levels:
        success, content, *extra = _try_level(level, url, proxies, cloud_api_keys)
        attempts_log.append({"level": level, "success": success, "detail": content[:200] if not success else f"{len(content)} bytes"})

        if success:
            return {
                "success": True,
                "html": content,
                "level_used": level,
                "attempts_log": attempts_log,
            }

    return {
        "success": False,
        "html": "",
        "level_used": None,
        "attempts_log": attempts_log,
    }


def _try_level(level, url, proxies, cloud_api_keys):
    """Dispatch to the appropriate level function."""
    if level == 1:  return fetch_l1(url)
    if level == 2:  return fetch_l2(url)
    if level == 3:  return fetch_l3(url)
    if level == 4:  return fetch_l4(url)
    if level == 5:  return (bool(fetch_l5_rss(url.split("/")[2])), str(fetch_l5_rss(url.split("/")[2])))
    if level == 6:
        for fn in [fetch_l6_amp, fetch_l6_google_cache, fetch_l6_archive_today]:
            ok, html = fn(url)
            if ok: return (True, html)
        return (False, "All L6 sources failed")
    if level == 7:  return fetch_l7(url)
    if level == 8:  return fetch_l8(url)
    if level == 9:  return fetch_l9(url)
    if level == 10: return fetch_l10(url, proxies)
    if level == 11:
        for provider, fn in [("scrapingbee", fetch_l11_scrapingbee),
                             ("zyte", fetch_l11_zyte),
                             ("scraperapi", fetch_l11_scraperapi)]:
            key = cloud_api_keys.get(provider, "")
            if key:
                ok, html = fn(url, key)
                if ok: return (True, html)
        return (False, "No cloud API keys or all failed")
    if level == 12:
        ok, html, meta = fetch_l12_wayback(url)
        return (ok, html if ok else str(meta))
    return (False, f"Unknown level {level}")
```
