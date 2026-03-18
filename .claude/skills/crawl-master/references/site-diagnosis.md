# Site Diagnosis Reference

Template and patterns for diagnosing why a specific site is failing to crawl.
Use this guide when a site starts returning errors or gets blocked.

---

## Quick Diagnosis Checklist

Run these commands in order to identify the issue:

### 1. Check Recent Error Logs

```bash
# Check if there are Tier 6 escalation reports for the site
ls -la logs/tier6-escalation/ 2>/dev/null | grep SITE_ID

# Check circuit breaker state
.venv/bin/python -c "
from src.crawling.circuit_breaker import CircuitBreakerCoordinator
cb = CircuitBreakerCoordinator()
state = cb.get_site_state('SITE_ID')
print(f'State: {state}')
"

# Check anti-block escalation history
.venv/bin/python -c "
from src.crawling.anti_block import AntiBlockEngine
engine = AntiBlockEngine()
profile = engine.get_site_profile('SITE_ID')
print(f'Current tier: {profile.current_tier}')
print(f'Consecutive failures: {profile.consecutive_failures}')
print(f'Last block type: {profile.last_block_type}')
"
```

### 2. Run Live Diagnosis

```bash
.venv/bin/python -c "
import httpx
from src.crawling.block_detector import BlockDetector, HttpResponse

url = 'SITE_URL'

# Raw request to see what happens
try:
    r = httpx.get(url, follow_redirects=True, timeout=15,
                  headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})

    print(f'Status: {r.status_code}')
    print(f'Final URL: {r.url}')
    print(f'Content-Type: {r.headers.get(\"content-type\", \"?\")}')
    print(f'Body length: {len(r.text)}')

    # Key response headers
    for h in ['cf-ray', 'server', 'x-cache', 'retry-after', 'x-robots-tag']:
        if h in r.headers:
            print(f'{h}: {r.headers[h]}')

    # Run block detector
    resp = HttpResponse(
        status_code=r.status_code,
        headers=dict(r.headers),
        body=r.text[:5000],
        url=str(r.url),
        original_url=url,
    )
    detector = BlockDetector()
    diagnoses = detector.detect(resp)

    print(f'\n--- Block Diagnoses ({len(diagnoses)} found) ---')
    for d in diagnoses:
        print(f'  Type: {d.block_type.value}')
        print(f'  Confidence: {d.confidence:.2f}')
        print(f'  Recommended tier: {d.recommended_tier}')
        for e in d.evidence:
            print(f'    Evidence: {e}')
        print()

    # Body snippet for manual inspection
    print(f'\n--- Body preview (first 500 chars) ---')
    print(r.text[:500])

except httpx.ConnectError as e:
    print(f'Connection failed: {e}')
except httpx.TimeoutException:
    print(f'Request timed out (15s)')
except Exception as e:
    print(f'Error: {e}')
"
```

### 3. Test Alternative Sources

```bash
.venv/bin/python -c "
import httpx

domain = 'SITE_DOMAIN'  # e.g., 'www.chosun.com'

# RSS feed
rss_paths = ['/feed', '/rss', '/rss.xml', '/feed.xml', '/atom.xml']
for path in rss_paths:
    try:
        r = httpx.get(f'https://{domain}{path}', timeout=5,
                      headers={'User-Agent': 'Mozilla/5.0'})
        if r.status_code == 200 and ('<rss' in r.text[:500] or '<feed' in r.text[:500]):
            print(f'RSS found: {path} ({len(r.text)} bytes)')
            break
    except: pass
else:
    print('No RSS feed found')

# AMP version
try:
    r = httpx.get(f'https://{domain}/?amp=1', timeout=5, follow_redirects=True,
                  headers={'User-Agent': 'Mozilla/5.0'})
    print(f'AMP: status={r.status_code}, length={len(r.text)}')
except Exception as e:
    print(f'AMP: {e}')

# Google Cache
try:
    r = httpx.get(f'https://webcache.googleusercontent.com/search?q=cache:https://{domain}/',
                  timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
    print(f'Google Cache: status={r.status_code}, length={len(r.text)}')
except Exception as e:
    print(f'Google Cache: {e}')

# Wayback Machine
try:
    r = httpx.get(f'https://web.archive.org/cdx/search/cdx?url={domain}&output=json&limit=3&sort=reverse',
                  timeout=10)
    if r.status_code == 200:
        rows = r.json()
        if len(rows) > 1:
            print(f'Wayback: {len(rows)-1} snapshots, latest={rows[1][1][:8]}')
        else:
            print('Wayback: No snapshots')
except Exception as e:
    print(f'Wayback: {e}')
"
```

### 4. Test curl_cffi Profiles

```bash
.venv/bin/python -c "
from curl_cffi import requests as cffi_requests

url = 'SITE_URL'
profiles = ['chrome120', 'chrome124', 'safari17_5', 'firefox120',
            'chrome131', 'edge120', 'safari16_0', 'firefox115']

for p in profiles:
    try:
        r = cffi_requests.get(url, impersonate=p, timeout=10, allow_redirects=True)
        status = '  OK' if r.status_code == 200 and len(r.text) > 500 else 'FAIL'
        print(f'  {status}  {p:15s}  status={r.status_code}  body={len(r.text):>7,} bytes')
    except Exception as e:
        print(f'  ERR   {p:15s}  {e}')
"
```

### 5. Test Browser Rendering

```bash
.venv/bin/python -c "
from src.crawling.browser_renderer import render_page

url = 'SITE_URL'
try:
    html = render_page(url, timeout_seconds=30)
    if html and len(html) > 500:
        print(f'Browser render: SUCCESS ({len(html)} bytes)')
    else:
        print(f'Browser render: FAIL (content too short: {len(html) if html else 0} bytes)')
except Exception as e:
    print(f'Browser render: ERROR ({e})')
"
```

---

## Block Type Identification Patterns

### 403 Forbidden

**Symptoms:**
- HTTP status code 403
- Body contains "Access Denied", "Forbidden", "Error 403"
- May include WAF vendor signature

**Sub-classification:**

| Pattern | Sub-type | Evidence |
|---------|----------|---------|
| Body contains "Attention Required" + "cf-" headers | Cloudflare WAF | `cf-ray` header present |
| Body contains "Reference #" + Akamai patterns | Akamai WAF | `akamai-x-cache` header |
| Body contains "Imperva" or "Incapsula" | Imperva/Incapsula | `_incap_ses_` cookie |
| TLS handshake succeeds but 403 immediately | TLS fingerprint block | No JS challenge, no CAPTCHA |
| 403 only on specific paths, homepage OK | Path-based block | Selective enforcement |
| 403 with valid browser but not with httpx | UA/TLS mismatch | Compare httpx vs curl_cffi |

**Recommended levels:** L1 -> L2 -> L3 -> L7 -> L8 -> L9 -> L10

### Rate Limit (429)

**Symptoms:**
- HTTP status code 429
- `Retry-After` header (value in seconds or HTTP date)
- Degraded responses (200 but minimal content)

**Sub-classification:**

| Pattern | Sub-type | Action |
|---------|----------|--------|
| `Retry-After: 30` | Short cooldown | Wait and retry (L1 with backoff) |
| `Retry-After: 3600` | Long cooldown | Switch to RSS/GDELT (L5) |
| 429 on every request | IP-level rate limit | Proxy rotation (L10) |
| 200 but truncated body | Soft rate limit | Slow down + session cycling (L3) |

**Recommended levels:** L1 (backoff) -> L5 -> L10 -> L11

### CAPTCHA

**Symptoms:**
- Body contains reCAPTCHA, hCaptcha, or Turnstile markers
- `cf-mitigated: challenge` header
- Form with CAPTCHA challenge

**Detection patterns:**
```python
CAPTCHA_PATTERNS = [
    r"google\.com/recaptcha",
    r"g-recaptcha",
    r"hcaptcha\.com",
    r"h-captcha",
    r"challenges\.cloudflare\.com/turnstile",
    r"cf-turnstile",
    r"captcha-delivery\.com",
    r"funcaptcha\.com",
]
```

**Recommended levels:** L4 (if CF only) -> L7 -> L8 -> L9 -> L11

### JS Challenge

**Symptoms:**
- Body has Cloudflare's "checking your browser" page
- Empty or minimal body with `<script>` redirect
- `cf-mitigated: challenge` header (without CAPTCHA)
- Response body < 5KB with JavaScript-heavy content

**Detection patterns:**
```python
JS_CHALLENGE_PATTERNS = [
    r"Checking your browser",
    r"cf-browser-verification",
    r"_cf_chl_opt",
    r"jschl_vc",
    r"jschl_answer",
    r"window\._cf_chl",
    r"managed_checking_msg",
]
```

**Recommended levels:** L4 -> L7 -> L8 -> L11

### TLS Fingerprint Block

**Symptoms:**
- httpx returns 403 but browser works fine
- curl_cffi with wrong profile returns 403, correct profile returns 200
- No JS challenge, no CAPTCHA, just instant 403
- Server header suggests Akamai/Cloudflare/Imperva

**How to confirm:**
```bash
# If this works but httpx does not, it is a TLS fingerprint block
curl -s -o /dev/null -w "%{http_code}" -H "User-Agent: Mozilla/5.0" "SITE_URL"
# If curl also fails, the block is not TLS-based
```

**Recommended levels:** L2 -> L3 -> L7 -> L8 -> L9 -> L10

### Geo-Block

**Symptoms:**
- Redirect to regional site (e.g., `.kr` to `.com` or vice versa)
- Body contains "not available in your region/country"
- 200 but content is localized error page
- Works from one country but not another

**How to confirm:**
```bash
# Check if AMP version (served from CDN) works
.venv/bin/python -c "
import httpx
r = httpx.get('SITE_URL?amp=1', follow_redirects=True, timeout=10,
              headers={'User-Agent': 'Mozilla/5.0'})
print(f'AMP: {r.status_code}, {len(r.text)} bytes')
# If AMP works but direct URL does not, it is a geo-block
"
```

**Recommended levels:** L6 -> L10 (with geo-targeted proxy) -> L11 -> L12

### 404 / URL Structure Change

**Symptoms:**
- Previously working URLs now return 404
- Site redesign changed URL patterns
- Batch of URLs all returning 404 simultaneously

**How to confirm:**
```bash
# Check if the domain itself is accessible
.venv/bin/python -c "
import httpx
r = httpx.get('https://DOMAIN/', timeout=10, follow_redirects=True,
              headers={'User-Agent': 'Mozilla/5.0'})
print(f'Homepage: {r.status_code}')
# If homepage works, the URL structure has changed
"
```

**Recommended levels:** L5 (re-discover URLs) -> L6 -> L12

---

## Common Site-Specific Patterns

### Korean News Sites

| Site | Typical Block | Best Level | Notes |
|------|--------------|------------|-------|
| chosun.com | Fingerprint | L2 (chrome124) | TLS fingerprint check, curl_cffi works |
| donga.com | Rate Limit | L1 (backoff) | Aggressive rate limiting, slow down to 1req/5s |
| joongang.co.kr | JS Challenge | L4 or L7 | Cloudflare protected |
| hani.co.kr | None (open) | L1 | Generally open access |
| khan.co.kr | UA Filter | L1 | Simple UA check |
| hankyung.com | Soft paywall | L7 (fresh context) | Metered -- fresh browser context bypasses |
| mk.co.kr | Rate Limit | L3 (session) | Cookie-based metering |
| yonhapnews.co.kr | None (open) | L1 | Government agency, open access |
| yna.co.kr | None (open) | L1 | Wire service, open access |
| kbs.co.kr | Fingerprint | L2 | Light fingerprint check |

### International News Sites

| Site | Typical Block | Best Level | Notes |
|------|--------------|------------|-------|
| nytimes.com | Hard paywall | L7 + L12 | Paywall, Wayback for older content |
| reuters.com | Fingerprint | L2 | Akamai WAF |
| bbc.com | None (open) | L1 | Open access |
| theguardian.com | None (open) | L1 | Open access with metering |
| bloomberg.com | Hard paywall | L5 + L7 | RSS has summaries, browser for full |
| wsj.com | Hard paywall | L5 + L12 | Very aggressive paywall |
| ft.com | Hard paywall | L6 (Google Cache) | Google-first-click-free sometimes works |

---

## Diagnosis Report Template

After completing diagnosis, fill out this template:

```markdown
## Site Diagnosis Report

**Site**: [site_id] ([URL])
**Date**: YYYY-MM-DD
**Diagnosed by**: crawl-master skill

### Block Analysis

| Check | Result |
|-------|--------|
| HTTP Status | [200/403/404/429/5xx] |
| Block Type | [UA_FILTER/FINGERPRINT/JS_CHALLENGE/CAPTCHA/RATE_LIMIT/IP_BLOCK/GEO_BLOCK] |
| Confidence | [0.0-1.0] |
| WAF Vendor | [Cloudflare/Akamai/Imperva/DataDome/None detected] |
| Evidence | [list of evidence strings] |

### Level Test Results

| Level | Method | Result | Details |
|-------|--------|--------|---------|
| L1 | httpx+UA | PASS/FAIL | [status, body size] |
| L2 | curl_cffi | PASS/FAIL | [working profile if any] |
| L3 | curl_cffi+cookie | PASS/FAIL | |
| L4 | cloudscraper | PASS/FAIL | |
| L5 | RSS/GDELT | PASS/FAIL | [feed URL if found] |
| L6 | AMP/Cache | PASS/FAIL | [which source worked] |
| L7 | Patchright | PASS/FAIL | |
| L8 | Camoufox | PASS/FAIL | |
| L9 | FP-suite | PASS/FAIL | |
| L10 | Proxy | PASS/FAIL/SKIP | [if proxy available] |
| L11 | Cloud browser | PASS/FAIL/SKIP | [if API key available] |
| L12 | Wayback | PASS/FAIL | [snapshot date if found] |

### Recommendation

**Best working level**: L[N] -- [method name]
**Action items**:
1. Update sources.yaml with preferred_strategy
2. [Any site-specific configuration needed]
3. [If all levels fail: escalation path]
```

---

## Automated Batch Diagnosis

For diagnosing multiple failing sites at once:

```bash
.venv/bin/python -c "
import yaml
import httpx
from src.crawling.block_detector import BlockDetector, HttpResponse

# Load all sites from sources.yaml
with open('data/config/sources.yaml') as f:
    sites = yaml.safe_load(f)

detector = BlockDetector()
results = []

for site_id, config in sites.items():
    url = config.get('url', '')
    if not url:
        continue
    try:
        r = httpx.get(url, timeout=10, follow_redirects=True,
                      headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        resp = HttpResponse(status_code=r.status_code, headers=dict(r.headers),
                           body=r.text[:3000], url=str(r.url), original_url=url)
        diagnoses = detector.detect(resp)
        status = 'BLOCKED' if diagnoses else ('OK' if r.status_code == 200 else f'HTTP-{r.status_code}')
        block_types = [d.block_type.value for d in diagnoses]
        results.append((site_id, status, block_types, r.status_code))
    except Exception as e:
        results.append((site_id, 'ERROR', [str(e)[:50]], 0))

# Report
blocked = [r for r in results if r[1] == 'BLOCKED']
errors = [r for r in results if r[1] == 'ERROR']
ok = [r for r in results if r[1] == 'OK']

print(f'=== Batch Diagnosis: {len(results)} sites ===')
print(f'OK: {len(ok)} | Blocked: {len(blocked)} | Errors: {len(errors)}')
print()
if blocked:
    print('--- Blocked Sites ---')
    for site_id, _, blocks, status in blocked:
        print(f'  {site_id:20s}  HTTP {status}  blocks={blocks}')
if errors:
    print('--- Error Sites ---')
    for site_id, _, errs, _ in errors:
        print(f'  {site_id:20s}  {errs}')
"
```
