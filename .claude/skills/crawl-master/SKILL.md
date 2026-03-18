---
name: crawl-master
description: 12-level escalation ladder for diagnosing and bypassing crawl blocks. Use when user says "크롤링 문제 해결", "fix crawling", "사이트 크롤링 안됨", "crawl failed", "site blocked", or any crawling failure scenario.
---

# Crawl Master

GlobalNews 크롤링 시스템의 12단계 에스컬레이션 래더. 사이트가 차단되었을 때 **모든 가용한 방법을 순차적으로 시도**하여 포기 없이 콘텐츠를 수집한다.

> 핵심 원칙: **"3개 방법으로 시도하고 포기하는 일이 절대 없어야 한다."**
> (Never give up after only 3 methods.)

## Absolute Rules

1. **Quality over speed** -- 크롤링 성공률이 유일한 기준. 시도 횟수, 시간, 비용은 부차적이다.
2. **Exhaust all levels** -- 12개 레벨 중 적용 가능한 모든 레벨을 시도한 후에만 실패를 보고한다. 3-4개 방법만 시도하고 포기하는 것은 이 스킬의 존재 이유에 반한다.
3. **Learn and persist** -- 성공한 전략은 `data/config/sources.yaml`과 `DynamicBypassEngine`의 domain stats에 기록하여 다음 실행에서 즉시 활용한다.
4. **Cheapest first** -- 동일 효과의 전략 중 비용이 낮은 것부터 시도한다 (free > RAM > $).

## Prerequisites

스킬 실행 전 확인:

1. **프로젝트 구조**: `src/crawling/` 디렉터리 존재 확인 (block_detector.py, dynamic_bypass.py, anti_block.py)
2. **Python 환경**: `.venv/bin/python` 사용 (spaCy/pydantic v1 호환 -- Python 3.12-3.13)
3. **선택 의존성 확인**: `pip list | grep -E "curl_cffi|cloudscraper|patchright|camoufox"`

## Protocol

### Step 1: Diagnose -- 차단 유형 식별

#### 1a. 에러 로그 확인

```bash
# 최근 크롤링 로그에서 실패 사이트 확인
.venv/bin/python -c "
from src.crawling.block_detector import BlockDetector, HttpResponse
import json, glob

# 최근 Tier 6 에스컬레이션 리포트 확인
reports = sorted(glob.glob('logs/tier6-escalation/*.json'))
for r in reports[-5:]:
    with open(r) as f:
        data = json.load(f)
    print(f'{data.get(\"site_id\", \"?\")} -- blocks: {data.get(\"block_types\", [])}')
"
```

#### 1b. 실시간 진단

```bash
# 특정 사이트 즉석 진단
.venv/bin/python -c "
import httpx
from src.crawling.block_detector import BlockDetector, HttpResponse

url = 'https://TARGET_SITE_URL'
try:
    r = httpx.get(url, follow_redirects=True, timeout=15)
    resp = HttpResponse(
        status_code=r.status_code,
        headers=dict(r.headers),
        body=r.text[:5000],
        url=str(r.url),
        original_url=url,
    )
    detector = BlockDetector()
    diagnoses = detector.detect(resp)
    for d in diagnoses:
        print(f'  [{d.block_type.value}] confidence={d.confidence:.2f} tier={d.recommended_tier}')
        for e in d.evidence:
            print(f'    - {e}')
except Exception as e:
    print(f'Connection error: {e}')
"
```

#### 1c. 차단 유형 분류

| 차단 유형 | 증상 | 적용 레벨 |
|----------|------|----------|
| **403 Forbidden** | Status 403, "Access Denied" 본문 | L1, L2, L3, L7, L8, L10 |
| **404 Not Found** | Status 404, URL 구조 변경 | L5, L6, L12 |
| **Rate Limit (429)** | Status 429, Retry-After 헤더 | L1, L5, L10 |
| **CAPTCHA** | reCAPTCHA/hCaptcha/Turnstile 마커 | L4, L7, L8, L9 |
| **JS Challenge** | Cloudflare JS challenge, 빈 본문 + JS redirect | L4, L7, L8 |
| **Fingerprint** | TLS fingerprint 거부, 403 + 특정 헤더 | L2, L3, L7, L8, L9 |
| **Geo-Block** | 지역 리다이렉트, "not available" 메시지 | L6, L10, L12 |

### Step 2: Escalate -- 12단계 래더에서 적절한 레벨 선택

> **자동 선택 원칙**: 차단 유형에 매핑된 레벨 중 가장 저비용부터 시작하여 순차적으로 올린다.
> 이미 시도한 레벨은 건너뛴다.

#### The 12-Level Escalation Ladder

```
Cost: Free ─────────────────────────────────────────────────────── Paid
      L1    L2    L3    L4    L5    L6    L7    L8    L9    L10    L11   L12
      httpx curl  curl+ cloud RSS   AMP/  Patch Camo  FP-   Proxy  Cloud WBM
      +UA   cffi  cookie scrp /GDELT Cache right fux   suite  rotate  brw  +meta
```

| Level | Method | Cost | Latency | Addresses |
|-------|--------|------|---------|-----------|
| **L1** | httpx + UA rotation | Free | Instant | UA Filter, simple 403 |
| **L2** | curl_cffi TLS impersonation (8 profiles) | Free | ~50ms | Fingerprint, UA Filter |
| **L3** | curl_cffi + cookie warm-up + header sync | Free | 2x requests | Fingerprint, session-based blocks |
| **L4** | cloudscraper Cloudflare JS solver | Free | ~500ms | JS Challenge, Cloudflare |
| **L5** | RSS/Atom + Google News RSS + GDELT API | Free | ~1s | Rate Limit, IP Block, 404 |
| **L6** | AMP + Google Cache + Archive.today | Free | ~2s | Geo-Block, 404, soft blocks |
| **L7** | Patchright stealth Chromium | 100-500MB RAM, 3-8s | Hard blocks | JS Challenge, CAPTCHA, Fingerprint |
| **L8** | Camoufox stealth Firefox | 200-600MB RAM, 4-10s | Hard blocks | CAPTCHA, Fingerprint |
| **L9** | Browser + fingerprint-suite randomization | 200-600MB RAM | Hard blocks | Advanced fingerprint detection |
| **L10** | Proxy rotation (residential/datacenter) | $0.001-0.01/req | ~1-3s | IP Block, Rate Limit, Geo-Block |
| **L11** | Cloud browser (ScrapingBee/Zyte) | $0.001-0.01/req | ~5-15s | All block types |
| **L12** | Wayback Machine + metadata-only | Free | ~3-10s | Everything (stale, last resort) |

#### Block-to-Level Mapping (Quick Reference)

```
403 Forbidden  -> L1 -> L2 -> L3 -> L7 -> L8 -> L9 -> L10 -> L11
Rate Limit     -> L1 (backoff) -> L5 -> L10 -> L11
CAPTCHA        -> L4 -> L7 -> L8 -> L9 -> L11
JS Challenge   -> L4 -> L7 -> L8 -> L11
Fingerprint    -> L2 -> L3 -> L7 -> L8 -> L9 -> L10 -> L11
Geo-Block      -> L6 -> L10 -> L11 -> L12
404 / URL Change -> L5 -> L6 -> L12
```

### Step 3: Execute -- 적용 가능한 레벨 순차 실행

각 레벨의 실행 코드는 `references/escalation-ladder.md`에 상세 기술. 아래는 실행 프로토콜:

```
for level in applicable_levels(block_type):
    if level.requires_dependency_not_installed:
        log(f"Skipping {level}: dependency missing")
        continue

    result = try_level(url, level)

    if result.success:
        record_success(site_id, level, block_type)
        return result

    log(f"Level {level} failed: {result.error}")
    # Continue to next level -- NEVER stop early

report_exhaustion(site_id, tried_levels, block_type)
```

#### Integration with Existing Codebase

이 스킬은 기존 크롤링 인프라 위에서 동작한다:

| 기존 모듈 | 역할 | 이 스킬과의 관계 |
|----------|------|---------------|
| `block_detector.py` | 7개 차단 유형 진단 | Step 1의 진단 엔진 |
| `dynamic_bypass.py` | 전략 디스패치 + 도메인 학습 | Step 3의 L2-L10 실행 엔진 |
| `anti_block.py` | 6-tier 에스컬레이션 | 기존 T1-T6을 L1-L12로 세분화 |
| `retry_manager.py` | 4-level 재시도 아키텍처 | Never-Abandon 루프에서 이 스킬 호출 |
| `stealth_browser.py` | Patchright/Playwright 래핑 | L7-L9의 브라우저 실행 |
| `session_manager.py` | 세션/쿠키/헤더 관리 | L3의 쿠키 워밍업 |
| `browser_renderer.py` | 서브프로세스 브라우저 렌더링 | L7-L8의 격리 실행 |

#### Level-by-Level Execution

**L1: httpx + UA rotation**
```python
import httpx
from src.crawling.ua_manager import UAManager

ua_mgr = UAManager()
ua = ua_mgr.get_random_ua()
headers = {"User-Agent": ua, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}
r = httpx.get(url, headers=headers, follow_redirects=True, timeout=15)
```
- Addresses: UA Filter, simple 403
- When to use: First attempt on any failure. Near-zero overhead.

**L2: curl_cffi TLS impersonation**
```python
from curl_cffi import requests as cffi_requests

# 8 browser profiles: chrome120, chrome124, safari17_5, firefox120, edge120, chrome116, safari16_0, firefox115
for profile in ["chrome120", "chrome124", "safari17_5", "firefox120"]:
    r = cffi_requests.get(url, impersonate=profile, timeout=15)
    if r.status_code == 200 and len(r.text) > 500:
        break
```
- Addresses: TLS fingerprint detection (JA3/JA4 mismatch)
- When to use: Site rejects httpx due to TLS fingerprint analysis

**L3: curl_cffi + cookie warm-up + header sync**
```python
# Visit homepage first to get cookies, then target URL
session = cffi_requests.Session(impersonate="chrome124")
session.get(f"https://{domain}/", timeout=10)  # Cookie warm-up
import time; time.sleep(1)  # Human-like pause
r = session.get(url, timeout=15)  # Now with cookies
```
- Addresses: Session validation, cookie-required sites
- When to use: L2 gets 403 but homepage loads fine

**L4: cloudscraper JS solver**
```python
import cloudscraper
scraper = cloudscraper.create_scraper(browser={"browser": "chrome", "platform": "windows", "mobile": False})
r = scraper.get(url, timeout=20)
```
- Addresses: Cloudflare JS challenge (5-second delay page)
- When to use: Response body contains Cloudflare challenge markers

**L5: RSS/Atom + Google News RSS + GDELT API**
```python
import httpx, feedparser
# Try site RSS
for path in ["/feed", "/rss", "/rss.xml", "/feed.xml", "/atom.xml"]:
    try:
        r = httpx.get(f"https://{domain}{path}", timeout=10)
        if r.status_code == 200 and ("<rss" in r.text or "<feed" in r.text):
            feed = feedparser.parse(r.text)
            # Extract articles from feed entries
            break
    except: pass

# Google News RSS fallback
gnews_url = f"https://news.google.com/rss/search?q=site:{domain}&hl=en"
r = httpx.get(gnews_url, timeout=10)

# GDELT DOC API
gdelt_url = f"https://api.gdeltproject.org/api/v2/doc/doc?query=domain:{domain}&mode=artlist&format=json"
```
- Addresses: Rate Limit, IP Block (bypass WAF entirely)
- When to use: Direct access consistently fails; need article URLs from alternative sources

**L6: AMP + Google Cache + Archive.today**
```python
# AMP version
amp_urls = [f"{url}/amp", f"{url}?amp=1", url.replace("www.", "amp.")]
for amp_url in amp_urls:
    r = httpx.get(amp_url, timeout=10)
    if r.status_code == 200: break

# Google Cache
cache_url = f"https://webcache.googleusercontent.com/search?q=cache:{url}"
r = httpx.get(cache_url, timeout=10)

# Archive.today
archive_url = f"https://archive.ph/newest/{url}"
r = httpx.get(archive_url, follow_redirects=True, timeout=15)
```
- Addresses: Geo-Block, soft blocks, recent 404s
- When to use: Content was available recently but direct access now blocked

**L7: Patchright stealth Chromium**
```python
# Uses browser_renderer.py subprocess isolation
from src.crawling.browser_renderer import render_page
html = render_page(url, timeout_seconds=30)
```
- Addresses: JS Challenge, CAPTCHA, advanced fingerprint detection
- When to use: Free methods all fail; site requires full browser execution
- Cost: 100-500MB RAM, 3-8 seconds per page

**L8: Camoufox stealth Firefox**
```python
from camoufox.sync_api import Camoufox
with Camoufox(headless=True) as browser:
    page = browser.new_page()
    page.goto(url, wait_until="networkidle", timeout=30000)
    html = page.content()
```
- Addresses: CAPTCHA, sites that detect Chromium-based automation
- When to use: L7 Patchright detected; site specifically blocks Chromium
- Cost: 200-600MB RAM, 4-10 seconds per page

**L9: Browser + fingerprint-suite randomization**
```python
from patchright.sync_api import sync_playwright
import random

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        viewport={"width": random.choice([1366,1440,1536,1920]),
                  "height": random.choice([768,900,864,1080])},
        locale=random.choice(["en-US","en-GB","ko-KR"]),
        timezone_id=random.choice(["America/New_York","Europe/London","Asia/Seoul"]),
        color_scheme=random.choice(["light","dark"]),
        user_agent="...",  # Match viewport/locale
    )
    page = context.new_page()
    # Inject canvas/WebGL noise
    page.add_init_script("""
        const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
        HTMLCanvasElement.prototype.toDataURL = function(type) {
            const ctx = this.getContext('2d');
            if (ctx) {
                const img = ctx.getImageData(0, 0, this.width, this.height);
                for (let i = 0; i < img.data.length; i += 4) {
                    img.data[i] += Math.floor(Math.random() * 2);
                }
                ctx.putImageData(img, 0, 0);
            }
            return origToDataURL.apply(this, arguments);
        };
    """)
    page.goto(url, wait_until="networkidle", timeout=30000)
    html = page.content()
```
- Addresses: Advanced fingerprint detection (canvas, WebGL, font enumeration)
- When to use: L7/L8 detected by advanced anti-bot (PerimeterX, DataDome)
- Cost: 200-600MB RAM per page

**L10: Proxy rotation**
```python
from curl_cffi import requests as cffi_requests

proxies = ["http://user:pass@proxy1:8080", "http://user:pass@proxy2:8080"]
for proxy in proxies:
    r = cffi_requests.get(url, impersonate="chrome124",
                          proxies={"https": proxy, "http": proxy}, timeout=20)
    if r.status_code == 200 and len(r.text) > 500:
        break
```
- Addresses: IP Block, Rate Limit, Geo-Block
- When to use: All free methods fail; site blocks by IP/geo
- Cost: $0.001-0.01 per request

**L11: Cloud browser (ScrapingBee/Zyte)**
```python
import httpx

# ScrapingBee
api_url = "https://app.scrapingbee.com/api/v1/"
params = {
    "api_key": "YOUR_API_KEY",
    "url": url,
    "render_js": "true",
    "premium_proxy": "true",
    "country_code": "us",
}
r = httpx.get(api_url, params=params, timeout=60)

# Zyte API alternative
zyte_r = httpx.post("https://api.zyte.com/v1/extract", json={
    "url": url, "httpResponseBody": True, "browserHtml": True,
}, auth=("YOUR_API_KEY", ""), timeout=60)
```
- Addresses: All block types (managed browser + proxy + CAPTCHA solving)
- When to use: Everything else fails; site has enterprise-grade anti-bot
- Cost: $0.001-0.01 per request

**L12: Wayback Machine + metadata-only**
```python
import httpx

# Wayback Machine CDX API -- find recent snapshots
cdx_url = f"https://web.archive.org/cdx/search/cdx?url={url}&output=json&limit=5&sort=reverse"
r = httpx.get(cdx_url, timeout=15)
snapshots = r.json()
if snapshots and len(snapshots) > 1:
    timestamp, original = snapshots[1][1], snapshots[1][2]
    wb_url = f"https://web.archive.org/web/{timestamp}/{original}"
    content = httpx.get(wb_url, timeout=20)

# Metadata-only fallback (title, date, description from CDX)
# Use when even Wayback content is blocked
```
- Addresses: Everything (stale data, last resort)
- When to use: Absolute last resort. Content may be days/weeks old.
- Cost: Free

### Step 4: Learn -- 성공 전략 기록

성공한 전략은 두 곳에 기록한다:

#### 4a. DynamicBypassEngine domain stats (런타임)

```python
engine = DynamicBypassEngine()
# execute_strategy 내부에서 자동으로 domain_stats 업데이트
# 다음 실행 시 성공률 높은 전략이 우선 선택됨
```

#### 4b. sources.yaml 어노테이션 (영구)

```yaml
# data/config/sources.yaml
chosun:
  url: https://www.chosun.com
  bypass_notes: "L2 curl_cffi chrome124 works. L1 httpx blocked since 2025-03."
  preferred_strategy: curl_cffi_impersonate
  preferred_profile: chrome124
  last_block_type: fingerprint
  last_success_date: "2026-03-15"
```

#### 4c. Knowledge Archive 연동

Hook 시스템이 자동으로 Knowledge Archive(`knowledge-index.jsonl`)에 크롤링 세션 팩트를 기록한다. 다음 세션에서 `Grep "bypass" knowledge-index.jsonl`로 이전 성공 패턴을 검색할 수 있다.

### Step 5: Report -- 상세 리포트 생성

모든 시도 결과를 구조화된 리포트로 출력:

```
=== Crawl Master Report ===
Site: chosun (https://www.chosun.com)
Block Type: FINGERPRINT (confidence: 0.92)
Date: 2026-03-15

Attempts:
  L1 httpx+UA      -> FAIL (403, body="Access Denied", 120ms)
  L2 curl_cffi      -> SUCCESS (200, body=45KB, profile=chrome124, 85ms)

Resolution: L2 curl_cffi with chrome124 profile
Recommendation: Set preferred_strategy=curl_cffi_impersonate in sources.yaml

Learning Applied:
  - DynamicBypassEngine: chosun.com curl_cffi_impersonate success_rate=1.0
  - sources.yaml: Updated bypass_notes
```

## Decision Flowchart

```
START: Site crawl failed
  |
  v
[1] Run BlockDetector on last response
  |
  +-- No response (connection error) --> L1 -> L2 -> L5 -> L10 -> L12
  |
  +-- 403 Forbidden
  |     +-- TLS fingerprint evidence --> L2 -> L3 -> L7 -> L8 -> L9 -> L10
  |     +-- UA filter evidence -------> L1 -> L2 -> L7
  |     +-- Generic 403 --------------> L1 -> L2 -> L3 -> L7 -> L10
  |
  +-- 429 Rate Limit -----------------> L1(backoff) -> L5 -> L10
  |
  +-- CAPTCHA detected ---------------> L4 -> L7 -> L8 -> L9 -> L11
  |
  +-- JS Challenge detected ----------> L4 -> L7 -> L8 -> L11
  |
  +-- Geo-Block detected -------------> L6 -> L10 -> L11 -> L12
  |
  +-- 404 Not Found ------------------> L5 -> L6 -> L12
  |
  +-- Unknown block ------------------> L1 -> L2 -> L3 -> L4 -> L5 -> L6
                                         -> L7 -> L8 -> L9 -> L10 -> L11 -> L12
```

## Quality Checklist

스킬 실행 완료 전 확인:

- [ ] **진단 완료**: 차단 유형이 7개 중 하나로 분류되었는가
- [ ] **래더 소진**: 해당 차단 유형에 매핑된 모든 레벨을 시도했는가
- [ ] **학습 기록**: 성공한 전략이 domain stats와 sources.yaml에 기록되었는가
- [ ] **리포트 생성**: 모든 시도 결과가 구조화된 리포트로 출력되었는가
- [ ] **3개 미만 시도 방지**: 최소 5개 이상의 레벨을 시도했는가 (해당 차단 유형에 적용 가능한 레벨이 5개 미만이면 전부 시도)

## Anti-Patterns

| 금지 사항 | 흔한 합리화 | 왜 안 되는가 |
|----------|-----------|-------------|
| 3개 레벨만 시도하고 포기 | "충분히 시도했다" | 이 스킬의 존재 이유에 반함. 12개 전부 시도 |
| L7-L9 건너뛰기 | "브라우저 무거움" | RAM은 일시적. 크롤링 실패는 영구적 데이터 손실 |
| L10-L11 건너뛰기 | "비용 발생" | 데이터 없는 것이 $0.01보다 비싸다 |
| 진단 없이 L7부터 시작 | "브라우저면 다 됨" | 낭비. L1-L4로 해결 가능한 문제일 수 있음 |
| 성공 전략 미기록 | "다음에 또 하면 됨" | 동일 실패 반복. 학습이 핵심 |
| 레벨 순서 무시 | "L10이 확실함" | 비용 없이 해결 가능한 방법이 있을 수 있음 |

## References

- `references/escalation-ladder.md` -- 12단계 상세 구현 가이드 + 코드 + 의존성
- `references/site-diagnosis.md` -- 사이트 진단 템플릿 + 패턴 사전
- `references/strategy-cookbook.md` -- 복사-붙여넣기용 코드 스니펫 모음
