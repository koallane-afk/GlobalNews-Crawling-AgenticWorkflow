# Comprehensive Crawling Methods Encyclopedia

**Purpose**: Exhaustive catalog of every known web crawling/scraping method applicable to news sites.
**Context**: System crawls 116 international news sites. Current implementation uses 12 strategies in a 5-tier DynamicBypassEngine. This document expands the catalog to ensure no method is overlooked -- "3 methods and give up" must never happen.
**Date**: 2026-03-15

---

## System Status: What We Already Have

The existing DynamicBypassEngine (`src/crawling/dynamic_bypass.py`) implements 12 strategies across 5 tiers (T0-T4), with a 4-level retry system (90 attempts) followed by a Never-Abandon persistence loop (10 additional cycles). The current 12 strategies are:

| # | Strategy | Tier | Targets |
|---|----------|------|---------|
| 1 | rotate_user_agent | T0 | UA_FILTER |
| 2 | exponential_backoff | T0 | RATE_LIMIT |
| 3 | rss_feed_fallback | T0 | RATE_LIMIT, IP_BLOCK |
| 4 | google_cache_fallback | T0 | GEO_BLOCK, IP_BLOCK |
| 5 | amp_version_fallback | T0 | GEO_BLOCK |
| 6 | curl_cffi_impersonate | T1 | UA_FILTER, FINGERPRINT, JS_CHALLENGE |
| 7 | fingerprint_rotation | T1 | FINGERPRINT |
| 8 | cloudscraper_solve | T1 | JS_CHALLENGE |
| 9 | patchright_stealth | T2 | JS_CHALLENGE, CAPTCHA, FINGERPRINT |
| 10 | camoufox_stealth | T2 | CAPTCHA, FINGERPRINT |
| 11 | proxy_rotation | T3 | IP_BLOCK, RATE_LIMIT, GEO_BLOCK |
| 12 | wayback_fallback | T4 | IP_BLOCK, GEO_BLOCK |

The 7 block types detected by `block_detector.py`: IP_BLOCK, UA_FILTER, RATE_LIMIT, CAPTCHA, JS_CHALLENGE, FINGERPRINT, GEO_BLOCK.

**The 4 failure patterns we face** (derived from the 116-site deployment):
1. **F1: 403 Forbidden** (biggest problem, ~22 sites) -- server rejects the request outright
2. **F2: Empty/truncated body** (~12 sites) -- request succeeds but content is missing (paywall, JS-rendered)
3. **F3: CAPTCHA/JS challenge** (~10 sites) -- interactive human verification blocks automation
4. **F4: Geo-restriction** (~9 sites) -- content unavailable from non-local IPs

---

## COMPLETE METHOD CATALOG

### Category 1: Feed-Based Methods (Structured Data Extraction)

These methods avoid scraping entirely by consuming structured feeds that the site publishes for syndication.

---

#### 1.1 RSS 2.0 / Atom Feeds (Standard Discovery)

**How it works**: Fetch the site's RSS or Atom feed URL (e.g., `/feed`, `/rss`, `/rss.xml`, `/atom.xml`, `/feeds/all.atom.xml`). Parse the XML for article entries containing title, link, publication date, author, and optionally the full article body in `<content:encoded>` or `<description>`.

**Discovery methods for RSS URLs**:
- Check `<link rel="alternate" type="application/rss+xml">` in HTML `<head>`
- Try common paths: `/feed`, `/rss`, `/rss.xml`, `/feed.xml`, `/atom.xml`, `/index.xml`, `/blog/feed`, `/news/rss`
- Check robots.txt for sitemap references (sitemaps sometimes reference RSS)
- Check the site's footer or dedicated RSS page
- Search third-party RSS directories (Feedspot, Feedly)

**Python libraries**: `feedparser` (2.0.0), `httpx`, `lxml`

**Anti-bot effectiveness**: HIGH -- RSS feeds are designed for machine consumption. They are rarely behind bot protection (though some sites restrict by IP or require authentication).

**Failure patterns addressed**: F1 (RSS endpoints often bypass WAF), F2 (full content in `<content:encoded>`), F4 (RSS subdomains may have different geo-rules than main site)

**Implementation complexity**: EASY

**Current status**: IMPLEMENTED as `rss_feed_fallback` (T0 strategy)

**Enhancement opportunity**: The current implementation only tries a fixed set of RSS paths. Expand to include:
- Per-site RSS URL database (already in `sources.yaml`)
- RSS autodiscovery from HTML `<link>` tags
- Category-specific feeds (e.g., `/rss/politics.xml`, `/rss/economy.xml`)
- Legacy/alternative RSS domains (e.g., `rss.donga.com`, `file.mk.co.kr/news/rss/`)

---

#### 1.2 Google News RSS Proxy

**How it works**: Google News generates RSS feeds for any publication or topic. The URL format is:
```
https://news.google.com/rss/search?q=site:{domain}&hl=en&gl=US&ceid=US:en
```
This returns an RSS feed of recent articles from that site as indexed by Google News. Each entry includes the article title, publication date, and a Google News redirect URL that resolves to the original article.

**Python libraries**: `feedparser`, `httpx`

**Anti-bot effectiveness**: HIGH -- This completely bypasses the target site's bot protection for URL discovery. The article links from Google News often pass through a Google redirect that may circumvent some bot detection.

**Failure patterns addressed**: F1 (completely bypasses target site for discovery), F4 (Google News accessible globally)

**Implementation complexity**: EASY

**Current status**: NOT IMPLEMENTED

**Limitations**: Google may rate-limit aggressive querying of its News RSS. Only returns articles that Google has indexed (usually major publications). The redirect URL must be resolved to get the actual article URL.

**Recommended addition**: Yes -- as a T0 strategy named `google_news_rss`. Effective as a universal URL discovery fallback for any site that Google indexes.

---

#### 1.3 Bing News RSS

**How it works**: Similar to Google News, Bing provides RSS feeds:
```
https://www.bing.com/news/search?q=site:{domain}&format=rss
```

**Python libraries**: `feedparser`, `httpx`

**Anti-bot effectiveness**: HIGH

**Failure patterns addressed**: F1, F4

**Implementation complexity**: EASY

**Current status**: NOT IMPLEMENTED

**Recommended addition**: Yes -- as a T0 strategy named `bing_news_rss`. Provides redundancy when Google News RSS fails.

---

#### 1.4 Sitemap XML Parsing (Standard, News, Index)

**How it works**: Fetch `/sitemap.xml` or sitemap URLs listed in `robots.txt`. Parse for `<loc>` URLs. News sitemaps (`xmlns:news`) include publication date, title, and keywords per URL. Sitemap indexes (`<sitemapindex>`) reference multiple child sitemaps.

**Discovery methods**:
- robots.txt `Sitemap:` directive
- `/sitemap.xml`, `/sitemap_index.xml`, `/sitemap-news.xml`
- `/wp-sitemap.xml` (WordPress), `/yoast-sitemap.xml`
- `/.well-known/sitemap.xml`

**Python libraries**: `lxml`, `httpx`, `xml.etree.ElementTree`

**Anti-bot effectiveness**: MEDIUM -- Sitemaps are designed for search engines and are usually accessible, but some sites return 403 for sitemaps to non-Googlebot UAs.

**Failure patterns addressed**: F1 (sitemaps often less protected than article pages), F2 (news sitemaps provide metadata even when articles are paywalled)

**Implementation complexity**: EASY

**Current status**: IMPLEMENTED as primary/fallback method in `sources.yaml`

**Enhancement opportunity**: Add Googlebot spoofing specifically for sitemap access (many sites allow Googlebot to access sitemaps but block other UAs). Add sitemap URL extraction from robots.txt as a systematic step.

---

#### 1.5 OPML Feed Collections

**How it works**: OPML (Outline Processor Markup Language) files aggregate multiple RSS feed URLs. News organizations sometimes publish OPML files listing all their feeds. Third-party curators maintain OPML collections for news categories.

**Sources**:
- `https://raw.githubusercontent.com/AsamK/newsboat-urls/master/urls` (community lists)
- Feedly OPML exports
- NewsBlur OPML exports

**Python libraries**: `lxml`, `httpx`

**Anti-bot effectiveness**: HIGH (it is just a list of RSS URLs)

**Failure patterns addressed**: F1 (discovers RSS URLs that may not be obvious on the site)

**Implementation complexity**: EASY

**Current status**: NOT IMPLEMENTED

**Recommended addition**: Low priority -- useful for initial RSS URL discovery but not a runtime strategy.

---

#### 1.6 JSON Feed (json-feed.org)

**How it works**: Some modern sites publish feeds in JSON format at `/feed.json` or `/feed/json`. The JSON Feed specification (jsonfeed.org) is an alternative to RSS/Atom with native JSON structure.

**Python libraries**: `httpx`, `json` (standard library)

**Anti-bot effectiveness**: HIGH

**Failure patterns addressed**: F1

**Implementation complexity**: EASY

**Current status**: NOT IMPLEMENTED

**Recommended addition**: Low priority -- few news sites use JSON Feed, but worth checking during RSS autodiscovery.

---

### Category 2: Search Engine Intermediaries

These methods use search engines as intermediaries to discover and/or access content without directly hitting the target site's bot protection.

---

#### 2.1 Google Cache / Webcache

**How it works**: Google caches most web pages it indexes. Access the cached version at:
```
https://webcache.googleusercontent.com/search?q=cache:{url}
```
or (newer format):
```
https://www.google.com/search?q=cache:{url}
```
The cached page is served from Google's servers, completely bypassing the target site's infrastructure.

**Python libraries**: `httpx`, `trafilatura` (for content extraction from cached HTML)

**Anti-bot effectiveness**: HIGH -- Google's cache servers have different bot protection than the target site. However, Google itself may challenge heavy automated access.

**Failure patterns addressed**: F1 (bypasses target site entirely), F2 (cached version often has full content), F3 (no CAPTCHA on cached page), F4 (Google cache is globally accessible)

**Implementation complexity**: MEDIUM -- Need to handle Google's own rate limiting and potential CAPTCHA for automated access. Cache may be stale (hours to days old).

**Current status**: IMPLEMENTED as `google_cache_fallback` (T0)

**Enhancement opportunity**: Google has been deprecating the cache feature. Alternative: use Google's AMP cache or Google Search result snippets. Also consider using the `cache:` operator with curl_cffi to avoid Google's bot detection.

**Important caveat**: As of late 2024, Google has been removing the "Cached" link from search results. The webcache URL may stop working. Plan for alternatives.

---

#### 2.2 Google AMP Cache

**How it works**: For sites that publish AMP (Accelerated Mobile Pages), Google hosts cached AMP versions on its CDN:
```
https://www.google.com/amp/s/{domain}/{path}
https://{domain}.cdn.ampproject.org/v/s/{domain}/{path}
```
AMP pages are typically stripped-down versions with full article text, served from Google/AMP CDN infrastructure.

**Python libraries**: `httpx`, `trafilatura`, `lxml`

**Anti-bot effectiveness**: HIGH -- AMP CDN servers are separate from the target site. However, not all sites publish AMP pages.

**Failure patterns addressed**: F1 (bypasses target site), F2 (AMP pages contain full article body), F4 (AMP CDN is globally accessible)

**Implementation complexity**: EASY -- Construct the AMP URL, fetch, extract content.

**Current status**: IMPLEMENTED as `amp_version_fallback` (T0)

**Enhancement opportunity**: Detect AMP availability during site reconnaissance (check for `<link rel="amphtml">` in HTML or `/amp/` path pattern). Some sites use `/amp` suffix, others use `?amp=1`, others use `?outputType=amp`.

---

#### 2.3 Wayback Machine (Internet Archive)

**How it works**: The Wayback Machine at `web.archive.org` stores historical snapshots of web pages. The API provides programmatic access:
```
# Check if URL is archived:
https://archive.org/wayback/available?url={url}

# Fetch latest snapshot:
https://web.archive.org/web/2/{url}

# Fetch specific date:
https://web.archive.org/web/20260315120000*/{url}

# CDX API for bulk URL search:
https://web.archive.org/cdx/search/cdx?url={domain}/*&output=json&limit=100
```

**Python libraries**: `httpx`, `waybackpy` (dedicated library), `trafilatura`

**Anti-bot effectiveness**: HIGH -- Wayback Machine has its own separate infrastructure.

**Failure patterns addressed**: F1 (bypasses target entirely), F2 (archived pages usually have full content from when they were captured), F3 (no CAPTCHA), F4 (globally accessible)

**Implementation complexity**: EASY

**Current status**: IMPLEMENTED as `wayback_fallback` (T4)

**Limitations**: Content may be hours to days old. Some sites block Wayback Machine archiving via robots.txt (`Disallow` for `ia_archiver`). Rate limiting on the API (15 requests/minute for anonymous users).

**Enhancement opportunity**: Use the CDX API for bulk URL discovery. The CDX API can list all URLs archived for a domain, filtered by date range -- this is an excellent URL discovery method when sitemaps are blocked.

---

#### 2.4 Archive.today (archive.ph / archive.is)

**How it works**: Archive.today is an independent web archiving service. Users can create snapshots on demand. The API:
```
# Check for existing snapshot:
https://archive.ph/newest/{url}

# Submit URL for archiving:
POST https://archive.ph/submit/ with url={url}
```

**Python libraries**: `httpx`, custom parsing

**Anti-bot effectiveness**: HIGH

**Failure patterns addressed**: F1, F2, F3, F4

**Implementation complexity**: MEDIUM -- The submit endpoint may require solving a CAPTCHA. The service has rate limits and may block automated access.

**Current status**: NOT IMPLEMENTED

**Recommended addition**: Low priority -- useful as a manual escalation path but difficult to automate reliably due to CAPTCHA requirements on submission.

---

#### 2.5 DuckDuckGo Instant Answers / Lite

**How it works**: DuckDuckGo's lite version (`https://lite.duckduckgo.com/lite?q=site:{domain}`) provides simplified search results that include article titles, URLs, and snippets. DDG does not block bots as aggressively as Google.

**Python libraries**: `httpx`, `lxml` or `beautifulsoup4`

**Anti-bot effectiveness**: MEDIUM-HIGH

**Failure patterns addressed**: F1 (URL discovery), F4 (globally accessible)

**Implementation complexity**: EASY

**Current status**: NOT IMPLEMENTED

**Recommended addition**: Yes -- as a T0 strategy named `duckduckgo_discovery`. Useful for URL discovery when sitemaps and RSS are blocked.

---

#### 2.6 Common Crawl Data

**How it works**: Common Crawl is a nonprofit that crawls the entire web monthly and publishes the data for free. Access via:
```
# Index API:
https://index.commoncrawl.org/CC-MAIN-2026-11-index?url={domain}/*&output=json

# WARC file access for full page content:
https://data.commoncrawl.org/{warc-path}
```

**Python libraries**: `httpx`, `warcio` (WARC file parsing), `cdx_toolkit` (CDX API client)

**Anti-bot effectiveness**: MAX -- No interaction with the target site at all. Data is pre-crawled.

**Failure patterns addressed**: F1, F2, F3, F4 (all bypassed -- data is pre-crawled)

**Implementation complexity**: HARD -- Large dataset, requires understanding WARC format, latency between crawl and availability (1-2 months).

**Current status**: NOT IMPLEMENTED

**Recommended addition**: Medium priority -- as a T4 "archive" strategy named `common_crawl_fallback`. Useful for sites that block all direct access. Stale data is acceptable for trend analysis.

**Limitations**: Data is 1-2 months old. Not all pages are captured. Large WARC files to process.

---

### Category 3: HTTP Client Techniques (Header/TLS Manipulation)

These methods modify the HTTP request characteristics to avoid detection.

---

#### 3.1 User-Agent Rotation

**How it works**: Rotate the `User-Agent` header among a pool of real browser UA strings. Modern detection also checks UA consistency with other headers (Sec-CH-UA, Accept-Language, etc.).

**UA sources**:
- Real browser UA databases (useragentstring.com, whatismybrowser.com)
- `fake-useragent` library (auto-updated database)
- Platform-specific UAs (Windows/macOS/Linux/Android/iOS)
- Googlebot UA (`Googlebot/2.1 (+http://www.google.com/bot.html)`) -- some sites whitelist this

**Python libraries**: `fake-useragent`, manual pool in code

**Anti-bot effectiveness**: LOW-MEDIUM -- Modern sites check more than just UA string.

**Failure patterns addressed**: F1 (if block is purely UA-based)

**Implementation complexity**: EASY

**Current status**: IMPLEMENTED as `rotate_user_agent` (T0) with 61+ UAs in 4 tiers

---

#### 3.2 Full Header Profile Mimicry

**How it works**: Beyond just UA rotation, mimic the complete header profile of a real browser request:
- `Accept`: `text/html,application/xhtml+xml,...`
- `Accept-Language`: matched to target site language (e.g., `ko-KR,ko;q=0.9,en-US;q=0.8`)
- `Accept-Encoding`: `gzip, deflate, br`
- `Sec-CH-UA`: Chrome client hints matching the UA
- `Sec-CH-UA-Mobile`: `?0`
- `Sec-CH-UA-Platform`: `"Windows"` / `"macOS"`
- `Sec-Fetch-Dest`: `document`
- `Sec-Fetch-Mode`: `navigate`
- `Sec-Fetch-Site`: `none` (direct) or `same-origin` (following links)
- `Sec-Fetch-User`: `?1`
- `Referer`: realistic (e.g., from Google search or site homepage)
- `DNT`: `1`
- `Connection`: `keep-alive`
- `Upgrade-Insecure-Requests`: `1`

**Python libraries**: `httpx` (custom headers), `curl_cffi` (automatic with impersonation)

**Anti-bot effectiveness**: MEDIUM -- Defeats simple header-checking bots but not TLS fingerprinting.

**Failure patterns addressed**: F1

**Implementation complexity**: EASY-MEDIUM

**Current status**: PARTIALLY IMPLEMENTED (curl_cffi handles some of this, but explicit header profiling per target site is not systematic)

**Enhancement opportunity**: Create per-site header profiles that match the site's expected visitor profile (language, region, etc.).

---

#### 3.3 TLS Fingerprint Mimicry (JA3/JA4)

**How it works**: TLS fingerprinting identifies clients by the specific parameters of the TLS handshake (cipher suites, extensions, curves, etc.). Each browser has a unique TLS fingerprint (JA3 hash). Anti-bot systems compare the client's TLS fingerprint against known browser fingerprints.

`curl_cffi` can impersonate specific browser TLS fingerprints:
```python
from curl_cffi import requests
resp = requests.get(url, impersonate="chrome124")
```

This sends a TLS handshake identical to Chrome 124, fooling JA3-based detection.

**Python libraries**: `curl_cffi` (primary), `tls-client` (alternative), `requests_go` (Go-based TLS)

**Anti-bot effectiveness**: HIGH -- This is one of the most effective anti-detection techniques. Many sites (especially Cloudflare-protected ones) use TLS fingerprinting as a primary detection method.

**Failure patterns addressed**: F1, F3 (some JS challenges are bypassed when TLS fingerprint matches)

**Implementation complexity**: EASY (with curl_cffi)

**Current status**: IMPLEMENTED as `curl_cffi_impersonate` (T1) with 4 fingerprint profiles

**Enhancement opportunity**: Add more impersonation targets: `chrome131`, `safari18`, `firefox133`, `edge131`. curl_cffi supports many profiles. Rotate profiles per-domain based on success rate.

---

#### 3.4 HTTP/2 and HTTP/3 Protocol Selection

**How it works**: Some anti-bot systems check the HTTP protocol version. Real browsers use HTTP/2 or HTTP/3 (QUIC). Python's `httpx` defaults to HTTP/1.1 in most configurations. `curl_cffi` with impersonation automatically uses HTTP/2.

**Python libraries**: `curl_cffi` (HTTP/2 automatic with impersonation), `httpx` (HTTP/2 with `http2=True`), `hyper` (HTTP/2), `aioquic` (HTTP/3/QUIC)

**Anti-bot effectiveness**: MEDIUM -- Upgrades from "bot-like HTTP/1.1" to "browser-like HTTP/2"

**Failure patterns addressed**: F1 (some 403s are triggered by HTTP/1.1 usage)

**Implementation complexity**: EASY (with curl_cffi impersonation, HTTP/2 is automatic)

**Current status**: PARTIALLY IMPLEMENTED (curl_cffi handles this, but httpx may not be configured for HTTP/2)

**Enhancement opportunity**: Ensure all httpx clients use `http2=True`. Consider HTTP/3 for sites that support it.

---

#### 3.5 Cookie Management and Session Simulation

**How it works**: Maintain persistent sessions with cookies across multiple requests to the same site. This simulates a real browsing session rather than individual stateless requests. Techniques include:
- Accept and send back all cookies (session cookies, tracking cookies, consent cookies)
- Pre-visit the homepage before accessing article pages (establish session)
- Accept GDPR/cookie consent banners programmatically
- Rotate/clear cookies periodically for metered paywalls

**Python libraries**: `httpx` (session with cookie jar), `requests.Session`, `http.cookiejar`

**Anti-bot effectiveness**: MEDIUM -- Many sites require session cookies to serve full content.

**Failure patterns addressed**: F1 (some 403s require cookie consent), F2 (metered paywalls reset with cookie clearing)

**Implementation complexity**: MEDIUM

**Current status**: PARTIALLY IMPLEMENTED (session_manager.py exists, but systematic pre-visit and consent handling may be incomplete)

**Enhancement opportunity**: Implement a "warm-up" sequence: visit homepage, accept cookies, wait, then visit article pages. This is a common pattern for bypassing metered paywalls.

---

#### 3.6 Referer Chain Spoofing

**How it works**: Set the `Referer` header to simulate a realistic browsing flow:
- `Referer: https://www.google.com/search?q={article+title}` (coming from Google search)
- `Referer: https://news.google.com/` (coming from Google News)
- `Referer: https://t.co/...` (coming from Twitter/X)
- `Referer: https://{same-site}/` (internal navigation)

Many sites serve full content to users coming from search engines (to be indexed) but block direct access.

**Python libraries**: `httpx` (custom headers)

**Anti-bot effectiveness**: MEDIUM-HIGH -- Very effective for metered paywalls that allow Google search referrals.

**Failure patterns addressed**: F1, F2 (metered paywalls often pass through Google referral traffic)

**Implementation complexity**: EASY

**Current status**: PARTIALLY IMPLEMENTED (referer chains mentioned in strategy docs but may not be systematic)

**Enhancement opportunity**: For every metered paywall site, try Google referrer first. This is the single most effective free technique for soft paywalls.

---

### Category 4: Browser Automation (Full Rendering)

These methods use real browser engines to render pages with full JavaScript execution.

---

#### 4.1 Playwright (Standard)

**How it works**: Launches a real Chromium, Firefox, or WebKit browser in headless mode. Navigates to URLs, waits for JavaScript to render, then extracts the DOM. Supports screenshots, network interception, cookie management, and user interaction simulation.

```python
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(url, wait_until="networkidle")
    html = page.content()
```

**Python libraries**: `playwright` (1.50+)

**Anti-bot effectiveness**: MEDIUM -- Standard Playwright is detectable by anti-bot systems (navigator.webdriver=true, specific Chrome flags, headless indicators).

**Failure patterns addressed**: F2 (renders JS-dependent content), F3 (can interact with some challenges)

**Implementation complexity**: MEDIUM

**Current status**: IMPLEMENTED via `browser_renderer.py` and `stealth_browser.py`

---

#### 4.2 Patchright (Stealth Playwright Fork)

**How it works**: A patched version of Playwright that removes common anti-detection markers. It patches the Chrome DevTools Protocol (CDP) to hide automation signals:
- Removes `navigator.webdriver = true`
- Hides CDP-specific JavaScript properties
- Removes Playwright-specific console messages
- Uses a real Chrome binary rather than a stripped Chromium

```python
from patchright.sync_api import sync_patchright
with sync_patchright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()
    page.goto(url)
```

**Python libraries**: `patchright` (1.58+)

**Anti-bot effectiveness**: HIGH -- Passes most anti-bot tests including Cloudflare, PerimeterX, and DataDome in many cases.

**Failure patterns addressed**: F1, F2, F3 (bypasses JS challenges and fingerprint detection), F4 (can use proxy)

**Implementation complexity**: MEDIUM

**Current status**: IMPLEMENTED as `patchright_stealth` (T2)

---

#### 4.3 Camoufox (Stealth Firefox)

**How it works**: A custom-patched Firefox browser designed specifically for web scraping. It randomizes 300+ fingerprint attributes (canvas, WebGL, audio, fonts, screen, timezone, etc.) and is undetectable by common anti-bot systems.

```python
from camoufox.sync_api import Camoufox
with Camoufox(headless=True) as browser:
    page = browser.new_page()
    page.goto(url)
    html = page.content()
```

**Python libraries**: `camoufox` (0.4+)

**Anti-bot effectiveness**: VERY HIGH -- Firefox fingerprint is less common among bots, and the 300+ randomized attributes make fingerprint-based detection very difficult.

**Failure patterns addressed**: F1, F2, F3, F4

**Implementation complexity**: MEDIUM

**Current status**: IMPLEMENTED as `camoufox_stealth` (T2)

**Enhancement opportunity**: Camoufox supports locale/timezone/language presets that can match the target site's region. Use this for geo-specific sites.

---

#### 4.4 Undetected ChromeDriver (Selenium-based)

**How it works**: A patched version of ChromeDriver that avoids common anti-bot detections. Unlike Playwright-based solutions, it uses Selenium WebDriver protocol.

```python
import undetected_chromedriver as uc
driver = uc.Chrome(headless=True)
driver.get(url)
html = driver.page_source
```

**Python libraries**: `undetected-chromedriver` (3.5+), `selenium`

**Anti-bot effectiveness**: HIGH -- Effective against Cloudflare, PerimeterX, and similar systems.

**Failure patterns addressed**: F1, F2, F3

**Implementation complexity**: MEDIUM

**Current status**: NOT IMPLEMENTED as a strategy (validated as CONDITIONAL in Step 2 -- requires Chrome binary)

**Recommended addition**: Low priority -- Patchright and Camoufox cover this space. Could be added as a redundant T2 strategy.

---

#### 4.5 Puppeteer via Pyppeteer

**How it works**: Node.js-based browser automation ported to Python. Controls Chromium via DevTools Protocol.

```python
import asyncio
from pyppeteer import launch
browser = await launch(headless=True)
page = await browser.newPage()
await page.goto(url)
html = await page.content()
```

**Python libraries**: `pyppeteer` (Python port), or call Node.js Puppeteer via subprocess

**Anti-bot effectiveness**: MEDIUM -- Detectable without stealth plugins.

**Failure patterns addressed**: F2, F3

**Implementation complexity**: MEDIUM

**Current status**: NOT IMPLEMENTED

**Recommended addition**: No -- Playwright/Patchright are superior replacements.

---

#### 4.6 Playwright-Stealth Plugin

**How it works**: A Playwright plugin that applies stealth patches (evasion scripts) to standard Playwright:

```python
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    stealth_sync(page)
    page.goto(url)
```

**Python libraries**: `playwright-stealth`

**Anti-bot effectiveness**: MEDIUM-HIGH -- Less effective than Patchright (which patches at CDP level), but useful as a supplement.

**Failure patterns addressed**: F1, F3

**Implementation complexity**: EASY (add-on to existing Playwright)

**Current status**: NOT IMPLEMENTED as a separate strategy

**Recommended addition**: Low priority -- Patchright subsumes this.

---

#### 4.7 Nodriver (Chrome DevTools Protocol Direct)

**How it works**: A newer library that controls Chrome directly via DevTools Protocol without WebDriver, making it inherently less detectable:

```python
import nodriver
browser = await nodriver.start()
tab = await browser.get(url)
html = await tab.get_content()
```

**Python libraries**: `nodriver` (successor to undetected-chromedriver, by the same author)

**Anti-bot effectiveness**: VERY HIGH -- No WebDriver protocol means no WebDriver-based detection.

**Failure patterns addressed**: F1, F2, F3

**Implementation complexity**: MEDIUM

**Current status**: NOT IMPLEMENTED

**Recommended addition**: Medium priority -- as a T2 alternative named `nodriver_stealth`. Good for sites where Patchright is detected.

---

### Category 5: Network/Transport Level Techniques

These methods operate at the network or transport layer.

---

#### 5.1 Residential Proxy Rotation

**How it works**: Route requests through residential IP addresses (real ISP IPs assigned to home users) rather than datacenter IPs. This makes requests appear to come from real users.

**Providers**: BrightData (formerly Luminati), Oxylabs, Smartproxy, SOAX, IPRoyal, PacketStream

**Python libraries**: `httpx` with proxy parameter, `curl_cffi` with proxy

**Anti-bot effectiveness**: VERY HIGH -- Residential IPs are virtually indistinguishable from real users.

**Failure patterns addressed**: F1, F4 (geo-targeted residential IPs solve geo-restriction)

**Implementation complexity**: EASY (technical), requires subscription (cost)

**Current status**: IMPLEMENTED as `proxy_rotation` (T3) -- infrastructure ready, requires proxy pool

**Cost**: $5-15/GB depending on provider and region. For 116 sites with ~6,500 articles/day, estimated 1-2 GB/day = $5-30/day.

---

#### 5.2 Mobile Proxy Rotation

**How it works**: Similar to residential proxies but uses mobile carrier IPs (3G/4G/5G). Mobile IPs are shared among many users (CGNAT), so they are rarely blocked. Rotating mobile IPs is the most effective proxy type.

**Providers**: BrightData, Oxylabs (with mobile IP selection)

**Python libraries**: Same as residential proxy

**Anti-bot effectiveness**: MAXIMUM -- Mobile IPs are almost never blocked.

**Failure patterns addressed**: F1, F4

**Implementation complexity**: EASY (technical), HIGH cost

**Current status**: NOT IMPLEMENTED as a distinct strategy

**Recommended addition**: Medium priority -- as a T3+ strategy for the most aggressive sites (Bloomberg, NYT, WSJ).

**Cost**: $15-40/GB -- significantly more expensive than residential.

---

#### 5.3 ISP Proxy / Static Residential

**How it works**: Uses datacenter IPs registered to ISPs (appearing as residential to IP databases like MaxMind). Cheaper than rotating residential but equally legitimate-looking.

**Providers**: BrightData (ISP proxies), Oxylabs (Dedicated Datacenter)

**Anti-bot effectiveness**: HIGH

**Failure patterns addressed**: F1, F4

**Implementation complexity**: EASY

**Current status**: NOT IMPLEMENTED as a distinct strategy

**Recommended addition**: Low priority -- covered by residential proxy category.

---

#### 5.4 Tor Network

**How it works**: Route requests through the Tor anonymity network. Each request can use a different exit node IP.

```python
import httpx
proxies = {"all://": "socks5://127.0.0.1:9050"}
resp = httpx.get(url, proxy=proxies["all://"])
```

**Python libraries**: `httpx` with SOCKS5 proxy, `stem` (Tor controller), `PySocks`

**Anti-bot effectiveness**: LOW-MEDIUM -- Many sites block known Tor exit nodes. Very slow (~2-10 seconds per request).

**Failure patterns addressed**: F4 (different IP), but creates F1 (many sites block Tor)

**Implementation complexity**: MEDIUM (requires Tor service running)

**Current status**: NOT IMPLEMENTED

**Recommended addition**: No -- Tor exit nodes are widely blocked and too slow. Residential proxies are superior.

---

#### 5.5 VPN Rotation

**How it works**: Route traffic through VPN servers in the target country. Unlike proxies, VPN encrypts all traffic and changes the apparent IP address.

**Providers**: NordVPN, ExpressVPN, Surfshark (all have CLI tools and API access)

**Python libraries**: Subprocess calls to VPN CLI, or direct WireGuard configuration

**Anti-bot effectiveness**: MEDIUM -- VPN IPs are known datacenter IPs, often in VPN blocklists.

**Failure patterns addressed**: F4 (geo-restriction bypass)

**Implementation complexity**: MEDIUM

**Current status**: NOT IMPLEMENTED

**Recommended addition**: No -- Residential proxies are more effective and more granular.

---

#### 5.6 DNS-over-HTTPS (DoH) for DNS-level Blocks

**How it works**: Some sites use DNS-level blocking. Using DoH bypasses DNS-based content filtering:
```python
import httpx
# Use Cloudflare DoH
resp = httpx.get("https://cloudflare-dns.com/dns-query",
                 params={"name": domain, "type": "A"},
                 headers={"Accept": "application/dns-json"})
```

**Python libraries**: `httpx`, `dnspython` (with DoH support)

**Anti-bot effectiveness**: LOW -- Only addresses DNS-level blocks, not HTTP-level.

**Failure patterns addressed**: F4 (DNS-based geo-blocks)

**Implementation complexity**: EASY

**Current status**: NOT IMPLEMENTED

**Recommended addition**: No -- DNS-level blocking is rare for news sites. Our F4 issues are HTTP-level geo-blocks.

---

### Category 6: JavaScript Rendering Services (Cloud)

These methods use third-party cloud services to render JavaScript and return the HTML.

---

#### 6.1 ScrapingBee

**How it works**: Cloud API that renders pages with real browsers and returns HTML:
```python
import httpx
resp = httpx.get("https://app.scrapingbee.com/api/v1/",
    params={"api_key": KEY, "url": url, "render_js": "true",
            "premium_proxy": "true", "country_code": "kr"})
```

**Python libraries**: `scrapingbee` (official SDK), or plain `httpx`

**Anti-bot effectiveness**: VERY HIGH -- Uses residential proxies + real browsers + anti-detection.

**Failure patterns addressed**: F1, F2, F3, F4

**Implementation complexity**: EASY

**Current status**: NOT IMPLEMENTED

**Cost**: $49/month for 1,000 credits (1 credit = 1 JS render with proxy). 6,500 articles/day = ~195,000/month. Expensive.

**Recommended addition**: Low priority -- cost prohibitive for 116 sites at scale. Useful for Extreme-tier sites only (5 sites = ~1,000 articles/day = 30,000/month = feasible).

---

#### 6.2 ScraperAPI

**How it works**: Similar to ScrapingBee. Cloud proxy + rendering service:
```python
import httpx
resp = httpx.get("http://api.scraperapi.com",
    params={"api_key": KEY, "url": url, "render": "true"})
```

**Python libraries**: `httpx`

**Anti-bot effectiveness**: VERY HIGH

**Failure patterns addressed**: F1, F2, F3, F4

**Implementation complexity**: EASY

**Current status**: NOT IMPLEMENTED

**Cost**: $49/month for 100,000 API calls. More cost-effective than ScrapingBee for high volume.

**Recommended addition**: Medium priority -- cost-effective for a subset of hard sites.

---

#### 6.3 Browserless.io

**How it works**: Self-hosted or cloud Playwright-as-a-Service. Connect to a remote Playwright browser:
```python
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect("wss://chrome.browserless.io?token=KEY")
    page = browser.new_page()
    page.goto(url)
```

**Python libraries**: `playwright` (connect to remote browser)

**Anti-bot effectiveness**: HIGH (uses real browser instances)

**Failure patterns addressed**: F2, F3

**Implementation complexity**: EASY-MEDIUM

**Current status**: NOT IMPLEMENTED

**Cost**: $200/month for cloud; self-hosted is free (Docker container).

**Recommended addition**: Medium priority -- the self-hosted Docker option is attractive for maintaining browser capacity without managing browser binaries locally.

---

#### 6.4 Splash (Scrapinghub)

**How it works**: Open-source JS rendering service. Runs as a Docker container with HTTP API:
```python
import httpx
resp = httpx.get("http://localhost:8050/render.html",
    params={"url": url, "wait": 2})
```

**Python libraries**: `httpx`, `scrapy-splash` (Scrapy integration)

**Anti-bot effectiveness**: LOW-MEDIUM -- Does not include anti-detection features.

**Failure patterns addressed**: F2 (JS rendering)

**Implementation complexity**: EASY (Docker-based)

**Current status**: NOT IMPLEMENTED

**Recommended addition**: No -- Patchright/Camoufox are superior for rendering with anti-detection.

---

#### 6.5 Zenrows

**How it works**: Cloud API with AI-based anti-bot bypass:
```python
import httpx
resp = httpx.get("https://api.zenrows.com/v1/",
    params={"apikey": KEY, "url": url, "js_render": "true",
            "antibot": "true", "premium_proxy": "true"})
```

**Python libraries**: `httpx`

**Anti-bot effectiveness**: VERY HIGH -- Claims to bypass Cloudflare, PerimeterX, DataDome, etc.

**Failure patterns addressed**: F1, F2, F3, F4

**Implementation complexity**: EASY

**Current status**: NOT IMPLEMENTED

**Cost**: $69/month for 250,000 API credits.

**Recommended addition**: Low priority -- another managed scraping service. Consider only if self-hosted solutions fail on Extreme-tier sites.

---

### Category 7: API-Based Extraction

These methods use official or unofficial APIs to get content.

---

#### 7.1 Official News APIs

**How it works**: Some news organizations provide official APIs for content access:
- **NYT API**: `https://api.nytimes.com/svc/` -- Article Search, Most Popular, Top Stories (requires API key, free tier available)
- **Guardian API**: `https://content.guardianapis.com/` (not in our list but shows the pattern)
- **Reuters/AP**: Wire service APIs

**Python libraries**: `httpx`, site-specific SDK

**Anti-bot effectiveness**: MAX -- Official authorized access.

**Failure patterns addressed**: F1, F2, F3, F4 (all bypassed with authorized API access)

**Implementation complexity**: EASY-MEDIUM (registration, API key management)

**Current status**: NOT IMPLEMENTED systematically (VOA uses API-style feeds)

**Recommended addition**: HIGH priority for sites that offer APIs. NYT Article Search API returns full metadata and article snippets (not full body without subscription, but excellent for URL discovery and metadata).

**Known available APIs**:
- NYT: Article Search API (free, 500 req/day)
- Al Jazeera: RSS-based, no formal API
- CNN: No public API (use sitemaps)
- Bloomberg: Terminal API only (subscription)

---

#### 7.2 Undocumented/Internal APIs (Next.js __NEXT_DATA__)

**How it works**: Many modern sites built with Next.js, Nuxt.js, or similar frameworks embed article data in a `<script id="__NEXT_DATA__">` tag containing JSON with all the page's data. This JSON often includes the full article text, metadata, and related articles.

Similarly, React/Angular apps often fetch data from internal REST or GraphQL APIs visible in the browser's Network tab.

**Discovery methods**:
- View page source, search for `__NEXT_DATA__`, `window.__INITIAL_STATE__`, `__INITIAL_DATA__`
- Monitor network requests in browser DevTools for XHR/Fetch calls
- Look for `/api/`, `/v1/`, `/graphql` endpoints
- Check `/_next/data/` paths (Next.js data routes)

**Python libraries**: `httpx`, `json`, `lxml` (for extracting `<script>` tags)

**Anti-bot effectiveness**: HIGH -- Internal APIs often have less protection than the HTML page. The `__NEXT_DATA__` JSON is embedded in the initial HTML response.

**Failure patterns addressed**: F2 (full content in JSON even when HTML rendering is incomplete)

**Implementation complexity**: MEDIUM -- Requires per-site analysis to find the data endpoint/structure.

**Current status**: NOT IMPLEMENTED as a systematic strategy

**Recommended addition**: HIGH priority as a T0 strategy named `nextdata_extraction`. Known Next.js sites in our corpus: scmp.com, taiwannews.com.tw, nytimes.com. The `__NEXT_DATA__` JSON often contains the FULL article body.

**Implementation approach**:
```python
import json
from lxml import html as lxml_html

tree = lxml_html.fromstring(response_text)
script = tree.xpath('//script[@id="__NEXT_DATA__"]/text()')
if script:
    data = json.loads(script[0])
    # Navigate the JSON structure to find article content
    # Structure varies per site -- requires per-site mapping
```

---

#### 7.3 GraphQL API Discovery

**How it works**: Some sites use GraphQL APIs for content delivery. These APIs accept structured queries and return precisely the data requested. GraphQL endpoints are typically at `/graphql`, `/api/graphql`, or `/gql`.

**Discovery**: Monitor network requests or look for GraphQL schema introspection:
```python
import httpx
resp = httpx.post(f"{base_url}/graphql", json={
    "query": "{ __schema { types { name } } }"
})
```

**Python libraries**: `httpx`, `gql` (GraphQL client)

**Anti-bot effectiveness**: HIGH -- GraphQL APIs often have less bot protection than web pages.

**Failure patterns addressed**: F2 (full structured content)

**Implementation complexity**: MEDIUM-HARD (requires schema discovery per site)

**Current status**: NOT IMPLEMENTED

**Recommended addition**: Medium priority -- only relevant for sites with GraphQL backends. Worth investigating for CNN (known to have internal GraphQL).

---

#### 7.4 WordPress REST API (wp-json)

**How it works**: WordPress sites expose a REST API at `/wp-json/wp/v2/posts` that returns articles in JSON format with full content:

```python
import httpx
resp = httpx.get(f"{base_url}/wp-json/wp/v2/posts", params={
    "per_page": 100, "page": 1, "orderby": "date",
    "_fields": "id,title,content,date,link,author,categories"
})
articles = resp.json()
```

**Python libraries**: `httpx`, `json`

**Anti-bot effectiveness**: HIGH -- The wp-json API is designed for programmatic access and often bypasses WAF rules that block normal page requests.

**Failure patterns addressed**: F1 (API endpoint may bypass WAF), F2 (full content in JSON)

**Implementation complexity**: EASY

**Current status**: NOT IMPLEMENTED as a systematic strategy

**Recommended addition**: HIGH priority as a T0 strategy named `wordpress_api`. Many sites in our corpus are WordPress-based: 38north.org, afmedios.com, nationalpost.com (WP VIP), bloter.net, irobotnews.com, techneedle.com, israelhayom.com. The wp-json API returns FULL article content even when the HTML page is behind bot protection.

**Known WordPress sites in corpus**: At least 7 sites (38north.org, afmedios.com, nationalpost.com, bloter.net, irobotnews.com, techneedle.com, israelhayom.com)

---

#### 7.5 Drupal JSON:API

**How it works**: Drupal 8+ sites expose a JSON:API at `/jsonapi/node/article`:
```python
resp = httpx.get(f"{base_url}/jsonapi/node/article",
    params={"sort": "-created", "page[limit]": 50})
```

**Python libraries**: `httpx`, `json`

**Anti-bot effectiveness**: HIGH

**Failure patterns addressed**: F1, F2

**Implementation complexity**: EASY

**Current status**: NOT IMPLEMENTED

**Recommended addition**: Low priority -- few sites in our corpus use Drupal.

---

#### 7.6 Mobile App API Reverse Engineering

**How it works**: News organizations' mobile apps often use REST/GraphQL APIs that are less protected than the web version. By intercepting the app's network traffic (using mitmproxy, Charles Proxy, or Frida), the API endpoints and authentication scheme can be discovered and replicated.

**Tools for discovery**: `mitmproxy`, Charles Proxy, Frida, HTTP Toolkit

**Python libraries**: `httpx` (to call discovered endpoints)

**Anti-bot effectiveness**: VERY HIGH -- Mobile APIs are designed for automated consumption and rarely have sophisticated bot detection.

**Failure patterns addressed**: F1 (mobile API may bypass web WAF), F2 (full content), F3 (no CAPTCHA on mobile API)

**Implementation complexity**: HARD (requires reverse engineering per site)

**Current status**: NOT IMPLEMENTED

**Recommended addition**: Medium priority for Extreme-tier sites -- NYT, Bloomberg, FT, and WSJ all have mobile apps with APIs. The NYT app API, for example, is known to expose full article text with proper authentication headers.

**Legal consideration**: May violate terms of service. Use only for personal/research purposes.

---

### Category 8: Content Extraction Enhancement

These methods improve content extraction from already-fetched HTML.

---

#### 8.1 Trafilatura (Intelligent Content Extraction)

**How it works**: A Python library that extracts the main content from HTML pages, removing boilerplate (navigation, ads, footers). Uses a combination of heuristics, XPath, and fallback strategies.

```python
import trafilatura
result = trafilatura.extract(html, include_comments=False,
                             include_tables=True, favor_recall=True)
```

**Python libraries**: `trafilatura` (2.0+)

**Anti-bot effectiveness**: N/A (post-fetch extraction)

**Failure patterns addressed**: F2 (extracts clean content from noisy HTML)

**Implementation complexity**: EASY

**Current status**: IMPLEMENTED as primary content extractor

---

#### 8.2 Newspaper4k

**How it works**: Extract and curate articles from news sites. Handles article download, parsing, content extraction, and metadata extraction:

```python
from newspaper import Article
article = Article(url)
article.download()
article.parse()
print(article.title, article.text, article.publish_date)
```

**Python libraries**: `newspaper4k` (0.9+)

**Anti-bot effectiveness**: N/A (post-fetch)

**Failure patterns addressed**: F2

**Implementation complexity**: EASY

**Current status**: IMPLEMENTED as fallback extractor

---

#### 8.3 Readability (Mozilla Algorithm)

**How it works**: Python port of Mozilla's Readability algorithm (used in Firefox Reader View):

```python
from readability import Document
doc = Document(html)
print(doc.title())
print(doc.summary())  # Clean HTML of main content
```

**Python libraries**: `readability-lxml`

**Anti-bot effectiveness**: N/A

**Failure patterns addressed**: F2

**Implementation complexity**: EASY

**Current status**: NOT IMPLEMENTED as a separate extractor

**Recommended addition**: Medium priority -- good as a third fallback after trafilatura and newspaper4k.

---

#### 8.4 Goose3 (Content Extraction)

**How it works**: Another article extraction library focused on news content:

```python
from goose3 import Goose
g = Goose()
article = g.extract(raw_html=html)
print(article.title, article.cleaned_text, article.publish_date)
```

**Python libraries**: `goose3`

**Anti-bot effectiveness**: N/A

**Failure patterns addressed**: F2

**Implementation complexity**: EASY

**Current status**: NOT IMPLEMENTED

**Recommended addition**: Low priority -- trafilatura is generally superior.

---

### Category 9: Third-Party News Aggregators/APIs

These services aggregate news content and provide programmatic access.

---

#### 9.1 NewsAPI.org

**How it works**: A commercial API aggregating headlines and articles from 80,000+ sources:
```python
import httpx
resp = httpx.get("https://newsapi.org/v2/everything",
    params={"apiKey": KEY, "domains": "nytimes.com",
            "from": "2026-03-14", "sortBy": "publishedAt"})
```

**Python libraries**: `httpx`, `newsapi-python` (official SDK)

**Anti-bot effectiveness**: MAX (authorized API access)

**Failure patterns addressed**: F1, F2 (provides title, description, URL, source -- not full body), F3, F4

**Implementation complexity**: EASY

**Current status**: NOT IMPLEMENTED

**Cost**: Free tier: 100 req/day, no commercial use. Business: $449/month.

**Limitations**: Returns title, description (first ~200 chars), URL, and metadata -- NOT full article body. Useful for URL discovery and metadata, not content extraction.

**Recommended addition**: Medium priority -- excellent for URL discovery as a universal fallback. The free tier (100 req/day) covers discovery for the 5 Extreme-tier sites.

---

#### 9.2 GDELT Project

**How it works**: The GDELT project monitors global news media in 100+ languages, processing every article from 65,000+ sources. The GDELT DOC 2.0 API provides full-text search and article metadata:
```
https://api.gdeltproject.org/api/v2/doc/doc?query=domain:nytimes.com&mode=artlist&maxrecords=250&format=json
```

**Python libraries**: `httpx`, `gdeltdoc` (community library)

**Anti-bot effectiveness**: MAX (separate data source)

**Failure patterns addressed**: F1, F2 (provides URL, title, language, source country, tone -- not full body), F4

**Implementation complexity**: EASY-MEDIUM

**Current status**: NOT IMPLEMENTED

**Cost**: Free and unlimited

**Limitations**: Returns metadata and URLs, not full article body. Excellent for URL discovery. Updates every 15 minutes.

**Recommended addition**: HIGH priority as a T0 URL discovery strategy named `gdelt_discovery`. Free, comprehensive, covers virtually all news sites worldwide. Perfect fallback for URL discovery when RSS/sitemap fail.

---

#### 9.3 Media Cloud

**How it works**: Open-source research platform that tracks global media. API provides story search and word counts:
```
https://api.mediacloud.org/api/v2/stories_public/list?q=media_id:{id}&rows=100
```

**Python libraries**: `mediacloud` (official SDK)

**Anti-bot effectiveness**: MAX

**Failure patterns addressed**: F1, F4

**Implementation complexity**: MEDIUM

**Current status**: NOT IMPLEMENTED

**Recommended addition**: Low priority -- GDELT is more comprehensive and easier to use.

---

#### 9.4 Event Registry

**How it works**: Commercial news intelligence API covering 200,000+ sources:
```python
from eventregistry import EventRegistry, QueryArticlesIter
er = EventRegistry(apiKey=KEY)
q = QueryArticlesIter(sourceUri="nytimes.com", dateStart="2026-03-14")
for article in q.execQuery(er, sortBy="date"):
    print(article["title"], article["body"][:500])
```

**Python libraries**: `eventregistry` (official SDK)

**Anti-bot effectiveness**: MAX

**Failure patterns addressed**: F1, F2 (provides full article body for many sources), F3, F4

**Implementation complexity**: EASY

**Current status**: NOT IMPLEMENTED

**Cost**: $99/month for 200 articles/day, $499/month for 10,000 articles/day

**Recommended addition**: Medium priority -- provides full article body, which GDELT and NewsAPI do not. For 5 Extreme-tier sites, this could be the only way to get full body content.

---

### Category 10: Social Media and Platform-Specific Channels

---

#### 10.1 Twitter/X Links Scraping

**How it works**: News organizations post article links on Twitter/X. Scrape the organization's tweet timeline to discover article URLs:
```
# Using official API (v2):
GET https://api.twitter.com/2/users/{id}/tweets?tweet.fields=entities

# Entities include expanded URLs to articles
```

**Python libraries**: `tweepy` (official SDK), `httpx` + API v2

**Anti-bot effectiveness**: MEDIUM (Twitter API requires OAuth)

**Failure patterns addressed**: F1 (URL discovery bypass)

**Implementation complexity**: MEDIUM (API registration, OAuth)

**Current status**: NOT IMPLEMENTED

**Cost**: Free tier: 1,500 tweets/month (very limited). Basic: $100/month.

**Recommended addition**: Low priority -- too limited and expensive for URL discovery when GDELT/Google News RSS are free.

---

#### 10.2 Facebook Graph API

**How it works**: Access a news page's posts via Facebook Graph API:
```
GET https://graph.facebook.com/{page-id}/posts?fields=link,message,created_time
```

**Python libraries**: `httpx`, `facebook-sdk`

**Anti-bot effectiveness**: MEDIUM

**Failure patterns addressed**: F1 (URL discovery)

**Implementation complexity**: MEDIUM (requires Facebook App registration)

**Current status**: NOT IMPLEMENTED

**Recommended addition**: No -- too complex for URL discovery. GDELT is superior.

---

#### 10.3 Telegram Channel Scraping

**How it works**: Some news organizations operate Telegram channels. The web preview at `https://t.me/s/{channel_name}` is publicly accessible and scrapeable:

```python
resp = httpx.get(f"https://t.me/s/{channel}")
# Parse HTML for article links
```

**Python libraries**: `httpx`, `lxml`, `telethon` (full Telegram API)

**Anti-bot effectiveness**: HIGH (t.me web preview is accessible)

**Failure patterns addressed**: F1 (URL discovery)

**Implementation complexity**: EASY (web preview) / HARD (full API)

**Current status**: NOT IMPLEMENTED

**Recommended addition**: Low priority -- limited to sites with Telegram channels.

---

### Category 11: CDN and Alternative Content Formats

---

#### 11.1 AMP Pages (Multiple Discovery Methods)

**How it works** (expanded from 2.2): AMP pages can be discovered and accessed via multiple methods:
1. `<link rel="amphtml" href="...">` in the original page
2. `/amp/` suffix on the URL path
3. `?amp=1` or `?outputType=amp` query parameter
4. Google AMP Cache: `https://{domain}.cdn.ampproject.org/v/s/{url}`
5. Bing AMP Cache: `https://www.bing.com/amp/s/{url}`

**Python libraries**: `httpx`, `trafilatura`

**Anti-bot effectiveness**: HIGH (CDN-served, often less protected)

**Failure patterns addressed**: F1, F2, F4

**Current status**: IMPLEMENTED as `amp_version_fallback` (T0)

**Enhancement opportunity**: Try ALL five AMP discovery methods, not just one.

---

#### 11.2 Facebook Instant Articles

**How it works**: Some publishers opt into Facebook Instant Articles, which are cached on Facebook's CDN. These can sometimes be accessed via:
```
https://www.facebook.com/instant_articles/preview/{article_url}
```
Or via the Instant Articles API.

**Python libraries**: `httpx`

**Anti-bot effectiveness**: MEDIUM-HIGH

**Failure patterns addressed**: F1, F2

**Implementation complexity**: MEDIUM

**Current status**: NOT IMPLEMENTED

**Recommended addition**: Low priority -- Instant Articles is declining in usage.

---

#### 11.3 Apple News Format

**How it works**: Publishers that support Apple News publish articles in Apple News Format (ANF). These are typically accessible through Apple News aggregation but not through a public API.

**Anti-bot effectiveness**: N/A (no public access mechanism)

**Current status**: NOT IMPLEMENTED

**Recommended addition**: No -- no public API for scraping Apple News content.

---

#### 11.4 Google News Article Scraping

**How it works**: Google News aggregates and links to articles. The Google News page for a publisher can be scraped for URLs:
```
https://news.google.com/search?q=site:{domain}&hl=en
```
Or navigate directly to a publisher's Google News page.

**Python libraries**: `httpx`, `lxml`, or Playwright (Google News uses JS rendering)

**Anti-bot effectiveness**: MEDIUM (Google may challenge automated access)

**Failure patterns addressed**: F1 (URL discovery)

**Implementation complexity**: MEDIUM

**Current status**: NOT IMPLEMENTED (Google News RSS is a simpler version)

**Recommended addition**: Low priority -- Google News RSS (1.2) covers this use case.

---

### Category 12: Email/Newsletter-Based Methods

---

#### 12.1 Newsletter Archives

**How it works**: Many news sites maintain archives of their email newsletters on their website (e.g., `/newsletters/`, `/archive/`). These archives contain links to articles and are often less protected than the main site.

**Python libraries**: `httpx`, `lxml`

**Anti-bot effectiveness**: MEDIUM-HIGH (newsletter archives are often public and less protected)

**Failure patterns addressed**: F1 (archive pages may bypass main site WAF)

**Implementation complexity**: EASY-MEDIUM (requires per-site archive URL discovery)

**Current status**: NOT IMPLEMENTED

**Recommended addition**: Low priority -- useful for specific sites but not a general strategy.

---

#### 12.2 RSS-to-Email Services (Reverse)

**How it works**: Services like Feedbin, Feedly, and Inoreader consume RSS feeds and provide web interfaces and APIs to access the content. These services have their own crawling infrastructure that may succeed where ours fails.

```python
# Feedly API
resp = httpx.get(f"https://cloud.feedly.com/v3/streams/contents",
    params={"streamId": f"feed/{rss_url}", "count": 20},
    headers={"Authorization": f"Bearer {token}"})
```

**Python libraries**: `httpx`

**Anti-bot effectiveness**: HIGH (third-party crawling infrastructure)

**Failure patterns addressed**: F1 (Feedly's crawlers may succeed), F4 (Feedly crawls from multiple locations)

**Implementation complexity**: MEDIUM

**Current status**: NOT IMPLEMENTED

**Cost**: Feedly Pro: $6/month (includes API access)

**Recommended addition**: Medium priority -- low cost, potentially effective for sites that block us but not Feedly.

---

### Category 13: Specialized Anti-Detection Techniques

---

#### 13.1 CAPTCHA Solving Services

**How it works**: When a CAPTCHA is encountered, send it to a solving service that uses human workers or AI to solve it:

```python
import httpx
# 2Captcha API
task = httpx.post("https://2captcha.com/in.php",
    data={"key": KEY, "method": "userrecaptcha",
          "googlekey": sitekey, "pageurl": url})
# ... poll for solution ...
```

**Services**: 2Captcha, Anti-Captcha, CapSolver, DeathByCaptcha

**Python libraries**: `2captcha-python`, `anticaptcha-client`, `capsolver`

**Anti-bot effectiveness**: HIGH (solves CAPTCHAs directly)

**Failure patterns addressed**: F3 (directly solves CAPTCHAs)

**Implementation complexity**: MEDIUM

**Current status**: NOT IMPLEMENTED (T3 placeholder exists but no integration)

**Cost**: $1-3 per 1,000 CAPTCHAs (reCAPTCHA v2). hCaptcha: $2-5/1,000. Turnstile: varies.

**Recommended addition**: HIGH priority for F3 failures -- as a T3 strategy named `captcha_solve_service`. For ~10 CAPTCHA-affected sites with ~1,000 articles/day, cost is ~$1-3/day.

---

#### 13.2 Cloudflare Turnstile Bypass

**How it works**: Cloudflare Turnstile is a CAPTCHA replacement that runs in the background. It can be bypassed by:
1. `cloudscraper` library (solves Cloudflare challenges without browser)
2. `curl_cffi` with proper TLS fingerprint (bypasses simple Turnstile)
3. CAPTCHA solving services that support Turnstile
4. Patchright/Camoufox with proper stealth (auto-passes Turnstile)

**Python libraries**: `cloudscraper`, `curl_cffi`, `patchright`

**Anti-bot effectiveness**: Varies by approach

**Failure patterns addressed**: F3

**Implementation complexity**: MEDIUM

**Current status**: PARTIALLY IMPLEMENTED (`cloudscraper_solve` strategy exists)

---

#### 13.3 PerimeterX/HUMAN Bot Defender Bypass

**How it works**: PerimeterX (now HUMAN) uses advanced behavioral analysis and device fingerprinting. Bypass requires:
1. Full browser with stealth patches (Patchright/Camoufox)
2. Realistic mouse movement and scrolling patterns
3. Proper TLS fingerprint
4. Cookie persistence across sessions

**Python libraries**: `patchright`, `camoufox` (with human behavior simulation)

**Anti-bot effectiveness**: Requires T2+ strategies

**Failure patterns addressed**: F1, F3

**Implementation complexity**: HARD

**Current status**: PARTIALLY IMPLEMENTED (stealth_browser.py has human behavior simulation)

---

#### 13.4 DataDome Bypass

**How it works**: DataDome is an anti-bot service used by some news sites. It uses device fingerprinting, behavioral analysis, and server-side detection. Bypass requires:
1. Stealth browser with full fingerprint randomization
2. Solving DataDome's challenge (similar to CAPTCHA but harder)
3. Maintaining valid DataDome cookies

**Python libraries**: `patchright`, `camoufox`, CAPTCHA solving services

**Anti-bot effectiveness**: Requires T2-T3 strategies

**Failure patterns addressed**: F1, F3

**Implementation complexity**: HARD

**Current status**: NOT EXPLICITLY HANDLED

**Recommended addition**: Medium priority -- identify which sites use DataDome and add specific handling.

---

#### 13.5 Request Timing Randomization (Human-like Patterns)

**How it works**: Instead of fixed delays, use human-like timing patterns:
- Reading time simulation: delay proportional to article length
- Poisson-distributed inter-request intervals
- Browsing session patterns (burst of requests, then long pause)
- Time-of-day variation (less activity at night)
- Weekend/weekday patterns

```python
import random
import numpy as np

def human_delay(min_s=2.0, max_s=10.0):
    """Generate a human-like delay using log-normal distribution."""
    mean = np.log((min_s + max_s) / 2)
    return max(min_s, min(max_s, np.random.lognormal(mean, 0.5)))
```

**Python libraries**: `numpy`, `random` (standard library)

**Anti-bot effectiveness**: MEDIUM-HIGH (behavioral analysis systems look for timing patterns)

**Failure patterns addressed**: F1 (avoids rate-limit triggers), F3 (behavioral analysis)

**Implementation complexity**: EASY

**Current status**: PARTIALLY IMPLEMENTED (random jitter exists but not sophisticated timing patterns)

**Enhancement opportunity**: Replace fixed `delay + random(0, jitter)` with log-normal distribution and session-level patterns.

---

#### 13.6 Browser Fingerprint Randomization (Canvas, WebGL, Audio)

**How it works**: Anti-bot systems collect browser fingerprints beyond TLS. Key fingerprint surfaces:
- **Canvas**: Drawing a hidden canvas and hashing the result
- **WebGL**: GPU renderer/vendor strings and WebGL parameters
- **Audio**: AudioContext fingerprinting
- **Fonts**: Enumeration of installed fonts
- **Screen**: Resolution, color depth, pixel ratio
- **Navigator**: platform, languages, plugins, hardwareConcurrency, deviceMemory

Camoufox randomizes all 300+ of these. Patchright patches some. Manual fingerprint spoofing requires injecting JavaScript to override these APIs.

**Python libraries**: `camoufox` (comprehensive), `patchright` (partial), custom JS injection via Playwright

**Anti-bot effectiveness**: VERY HIGH

**Failure patterns addressed**: F1, F3

**Implementation complexity**: HARD (manual) / EASY (with Camoufox)

**Current status**: IMPLEMENTED via `camoufox_stealth` and `stealth_browser.py`

---

### Category 14: Paywall-Specific Bypass Methods

---

#### 14.1 Metered Paywall Cookie Reset

**How it works**: Metered paywalls track free article count via cookies, localStorage, or IP-based counters. Bypass by:
1. Clear cookies between crawl sessions
2. Use incognito/private browsing context
3. Rotate IP addresses
4. Clear localStorage entries that track article count

```python
# With Playwright:
context = browser.new_context()  # Fresh context = no cookies
page = context.new_page()
page.goto(url)
html = page.content()
context.close()  # Discard all cookies/storage
```

**Python libraries**: `playwright`/`patchright` (context management), `httpx` (no cookie jar)

**Anti-bot effectiveness**: HIGH (for metered paywalls)

**Failure patterns addressed**: F2 (full content when meter is reset)

**Implementation complexity**: EASY

**Current status**: PARTIALLY IMPLEMENTED (mentioned in strategy docs, fresh contexts used)

**Sites affected**: joongang.co.kr, hankyung.com, scmp.com, latimes.com, nationalpost.com, yomiuri.co.jp, thehindu.com (all soft-metered)

---

#### 14.2 Google/Facebook Referrer Bypass

**How it works**: Many paywalled sites allow full content access for users coming from Google Search or Facebook, to ensure their content is indexed and shared. Setting the Referer header to Google/Facebook bypasses the paywall:

```python
headers = {
    "Referer": "https://www.google.com/",
    # or "https://t.co/", "https://www.facebook.com/"
}
resp = httpx.get(article_url, headers=headers)
```

**Python libraries**: `httpx`

**Anti-bot effectiveness**: MEDIUM-HIGH (very effective for soft paywalls)

**Failure patterns addressed**: F2 (full content with Google referrer)

**Implementation complexity**: EASY

**Current status**: PARTIALLY IMPLEMENTED (referer spoofing mentioned but may not be systematic)

**Sites affected**: All soft-metered sites. Some hard-paywalled sites also allow Google referrer access (NYT used to, but has tightened this).

**Recommended enhancement**: Make this a STANDARD first-attempt for all paywalled sites. Try `Referer: https://www.google.com/` before any other bypass method.

---

#### 14.3 Googlebot User-Agent Spoofing

**How it works**: Set the User-Agent to Googlebot. Some sites serve full content to Googlebot even when they paywall normal users:
```python
headers = {
    "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
}
```

**Python libraries**: `httpx`

**Anti-bot effectiveness**: MEDIUM -- Works on sites that trust the UA header. More sophisticated sites verify Googlebot IPs via reverse DNS.

**Failure patterns addressed**: F1, F2

**Implementation complexity**: EASY

**Current status**: NOT IMPLEMENTED as a systematic strategy

**Recommended addition**: Medium priority as a T0 strategy -- very effective for sitemap access and some paywalls. Use Googlebot UA specifically for sitemap and robots.txt fetching.

**Ethical note**: Impersonating Googlebot may violate site ToS. Use judiciously.

---

#### 14.4 AMP/Lite/Reader Mode Pages

**How it works**: Many paywalled sites offer stripped-down versions for different contexts:
- AMP pages (`/amp/`, `?amp=1`)
- Lite/mobile versions (`lite.{domain}`, `m.{domain}`)
- Google Reader compatibility mode
- Pocket/Instapaper save functionality

These alternative versions sometimes contain full article text without paywall enforcement.

**Python libraries**: `httpx`, `trafilatura`

**Anti-bot effectiveness**: MEDIUM-HIGH

**Failure patterns addressed**: F2

**Implementation complexity**: EASY

**Current status**: PARTIALLY IMPLEMENTED (AMP fallback exists)

**Enhancement opportunity**: Systematically check for `/lite/`, `m.`, `mobile.` subdomains/paths.

---

#### 14.5 Structured Data Extraction (JSON-LD, Schema.org)

**How it works**: Even paywalled pages often include article metadata in structured data formats for SEO:
```html
<script type="application/ld+json">
{
  "@type": "NewsArticle",
  "headline": "...",
  "datePublished": "...",
  "author": {...},
  "articleBody": "..."  // Sometimes includes full text!
}
</script>
```

Many sites include `articleBody` in their JSON-LD even when the visible HTML is paywalled.

**Python libraries**: `lxml`, `json`, `extruct` (structured data extraction)

**Anti-bot effectiveness**: N/A (data is in the HTML source)

**Failure patterns addressed**: F2 (structured data may contain full content)

**Implementation complexity**: EASY

**Current status**: NOT IMPLEMENTED as a systematic extraction method

**Recommended addition**: HIGH priority -- as a content extraction enhancement. Check for JSON-LD `articleBody` before declaring a page as paywall-blocked. The `extruct` library can extract all structured data from a page.

---

### Category 15: Miscellaneous/Advanced Methods

---

#### 15.1 Website Change Detection (for Minimal Crawling)

**How it works**: Instead of crawling full pages, monitor RSS/sitemaps for new URLs only, then fetch only new articles. Tools like `changedetection.io` can monitor pages for changes.

**Python libraries**: `httpx` + URL dedup (already implemented)

**Anti-bot effectiveness**: N/A (reduces request volume, reducing detection risk)

**Failure patterns addressed**: F1 (fewer requests = less likely to be rate-limited/blocked)

**Implementation complexity**: EASY

**Current status**: IMPLEMENTED (dedup system prevents re-fetching)

---

#### 15.2 Headless Chrome via DevTools Port

**How it works**: Launch Chrome with remote debugging enabled and connect to it programmatically:
```bash
google-chrome --headless --remote-debugging-port=9222
```
```python
import httpx
# Chrome DevTools Protocol
resp = httpx.get("http://localhost:9222/json/new?about:blank")
```

**Python libraries**: `httpx`, `websockets` (for CDP), or `playwright` connect

**Anti-bot effectiveness**: HIGH (real Chrome, not automated)

**Implementation complexity**: MEDIUM

**Current status**: NOT IMPLEMENTED as a separate strategy

**Recommended addition**: No -- Patchright and nodriver cover this.

---

#### 15.3 Screenshot-to-Text (OCR Fallback)

**How it works**: As a last resort, take a screenshot of the article page and use OCR to extract text:
```python
from playwright.sync_api import sync_playwright
import pytesseract
from PIL import Image

# Screenshot
page.screenshot(path="article.png", full_page=True)

# OCR
text = pytesseract.image_to_string(Image.open("article.png"))
```

**Python libraries**: `playwright`, `pytesseract`, `Pillow`, `easyocr` (for CJK text)

**Anti-bot effectiveness**: HIGH (screenshots are always available if the page renders)

**Failure patterns addressed**: F2 (extracts text from any rendered page)

**Implementation complexity**: MEDIUM-HARD (OCR quality varies, especially for CJK text)

**Current status**: NOT IMPLEMENTED

**Recommended addition**: Low priority as a T4 strategy named `ocr_screenshot_fallback`. Only for sites where ALL other methods fail to extract body text. easyOCR handles Korean, Chinese, Japanese, Arabic text.

---

#### 15.4 Print/PDF Version Extraction

**How it works**: Many news sites offer print-friendly or PDF versions of articles:
- `/print/` path suffix
- `?print=true` query parameter
- Print stylesheet rendering
- PDF download link

Print versions often contain the full article without ads, navigation, or paywall interstitials.

```python
# Try print version
resp = httpx.get(f"{article_url}?print=true")
# or
resp = httpx.get(f"{article_url}/print")
```

**Python libraries**: `httpx`, `trafilatura`

**Anti-bot effectiveness**: MEDIUM (print URLs often bypass WAF)

**Failure patterns addressed**: F2 (full content in print version)

**Implementation complexity**: EASY

**Current status**: NOT IMPLEMENTED

**Recommended addition**: Yes -- as a T0 strategy named `print_version_fallback`. Very easy to implement and effective for many sites.

---

#### 15.5 Email-Article Feature Exploitation

**How it works**: Some sites have "Email this article" or "Share via email" features that generate a version of the article suitable for email, often containing the full text. The endpoint that generates this content may be less protected.

**Python libraries**: `httpx`

**Anti-bot effectiveness**: MEDIUM

**Failure patterns addressed**: F2

**Implementation complexity**: MEDIUM (requires per-site endpoint discovery)

**Current status**: NOT IMPLEMENTED

**Recommended addition**: Low priority -- too site-specific.

---

#### 15.6 Embedded Content / iFrame Extraction

**How it works**: Some sites embed their content in iframes (especially for syndicated content or partnership arrangements). The iframe source URL may be accessible even when the main page is paywalled.

**Python libraries**: `lxml`, `httpx`

**Anti-bot effectiveness**: MEDIUM

**Failure patterns addressed**: F2

**Implementation complexity**: MEDIUM

**Current status**: NOT IMPLEMENTED

**Recommended addition**: Low priority -- niche use case.

---

#### 15.7 HTTP Range Requests / Partial Content

**How it works**: Some servers support HTTP Range requests, which can be used to fetch specific byte ranges of a page. This is primarily useful for large files but can sometimes help with timeout issues on slow connections.

```python
headers = {"Range": "bytes=0-50000"}
resp = httpx.get(url, headers=headers)
```

**Python libraries**: `httpx`

**Anti-bot effectiveness**: LOW

**Failure patterns addressed**: None directly

**Implementation complexity**: EASY

**Current status**: NOT IMPLEMENTED

**Recommended addition**: No -- not useful for news article scraping.

---

## CONSOLIDATED RECOMMENDATIONS

### Priority 1: Must Implement (HIGH impact, addresses core F1/F2 failures)

| # | New Strategy | Tier | Targets | Why |
|---|-------------|------|---------|-----|
| 1 | `google_news_rss` | T0 | F1, F4 | Universal URL discovery bypass for any Google-indexed site |
| 2 | `wordpress_api` | T0 | F1, F2 | Full content JSON for 7+ WordPress sites in corpus |
| 3 | `nextdata_extraction` | T0 | F2 | Full content from __NEXT_DATA__ for Next.js sites (scmp, taiwannews, nytimes) |
| 4 | `gdelt_discovery` | T0 | F1, F4 | Free, unlimited URL discovery for all 116 sites |
| 5 | `captcha_solve_service` | T3 | F3 | Direct CAPTCHA solving for ~10 affected sites ($1-3/day) |
| 6 | `structured_data_extraction` | T0 | F2 | JSON-LD articleBody from paywalled pages |
| 7 | `google_referrer_bypass` | T0 | F2 | Free paywall bypass for metered sites |
| 8 | `print_version_fallback` | T0 | F2 | Print-friendly URLs often bypass paywall |

### Priority 2: Should Implement (MEDIUM impact)

| # | New Strategy | Tier | Targets | Why |
|---|-------------|------|---------|-----|
| 9 | `bing_news_rss` | T0 | F1, F4 | Redundancy for Google News RSS |
| 10 | `duckduckgo_discovery` | T0 | F1, F4 | URL discovery with minimal bot detection |
| 11 | `nodriver_stealth` | T2 | F1, F3 | CDP-direct browser control, harder to detect than Playwright |
| 12 | `common_crawl_fallback` | T4 | F1, F2 | Pre-crawled data for completely blocked sites |
| 13 | `nyt_api` | T0 | F1 (NYT specific) | Official API for NYT URL discovery (free tier) |
| 14 | `googlebot_ua_spoof` | T0 | F1, F2 | Googlebot impersonation for sitemap/paywall access |
| 15 | `feedly_api` | T0 | F1 | Third-party crawling infrastructure ($6/mo) |

### Priority 3: Nice to Have (LOW impact or HIGH cost)

| # | New Strategy | Tier | Targets | Why |
|---|-------------|------|---------|-----|
| 16 | `scraperapi_service` | T3 | F1-F4 | Managed scraping for Extreme sites ($49/mo) |
| 17 | `readability_extract` | N/A | F2 | Third extraction algorithm after trafilatura/newspaper4k |
| 18 | `ocr_screenshot_fallback` | T4 | F2 | OCR from screenshot as absolute last resort |
| 19 | `mobile_proxy` | T3+ | F1, F4 | Mobile carrier IPs for most aggressive sites |
| 20 | `archive_today` | T4 | F1, F2 | Alternative archive service |

### Not Recommended

| Strategy | Why Not |
|---------|---------|
| Tor network | Tor exit nodes widely blocked, too slow |
| VPN rotation | Residential proxies superior |
| Facebook Graph API | Too complex for URL discovery |
| Twitter/X API | Too expensive, rate-limited |
| Apple News | No public API |
| Puppeteer/Pyppeteer | Playwright is superior |
| Splash | Patchright/Camoufox are superior |
| DNS-over-HTTPS | DNS-level blocking is not our issue |

---

## REVISED STRATEGY TIER ARCHITECTURE

After incorporating all recommended additions, the expanded tier system would be:

### Tier 0 -- Free, No External Dependencies (13 strategies)
1. `rotate_user_agent` (existing)
2. `exponential_backoff` (existing)
3. `rss_feed_fallback` (existing)
4. `google_cache_fallback` (existing)
5. `amp_version_fallback` (existing)
6. `google_news_rss` (NEW)
7. `bing_news_rss` (NEW)
8. `wordpress_api` (NEW)
9. `nextdata_extraction` (NEW)
10. `gdelt_discovery` (NEW)
11. `structured_data_extraction` (NEW)
12. `google_referrer_bypass` (NEW)
13. `print_version_fallback` (NEW)

### Tier 1 -- TLS/Protocol Mimicry (3 strategies)
14. `curl_cffi_impersonate` (existing)
15. `fingerprint_rotation` (existing)
16. `cloudscraper_solve` (existing)

### Tier 2 -- Browser Automation (4 strategies)
17. `patchright_stealth` (existing)
18. `camoufox_stealth` (existing)
19. `nodriver_stealth` (NEW)
20. `googlebot_ua_spoof` (moved from conceptual to explicit T0-T2)

### Tier 3 -- External Services (3 strategies)
21. `proxy_rotation` (existing)
22. `captcha_solve_service` (NEW)
23. `scraperapi_service` (NEW -- Extreme sites only)

### Tier 4 -- Archive/Stale Sources (3 strategies)
24. `wayback_fallback` (existing)
25. `common_crawl_fallback` (NEW)
26. `ocr_screenshot_fallback` (NEW)

**Total: 26 strategies** (up from 12), organized in cost-ascending order.

---

## FAILURE PATTERN TO STRATEGY MAPPING

### F1: 403 Forbidden (22 sites)

**Root causes**: IP blocking, UA filtering, TLS fingerprint rejection, WAF rules

**Recommended strategy sequence** (cheapest first):
1. `google_referrer_bypass` (T0) -- set Referer: google.com
2. `rotate_user_agent` + full header profile (T0)
3. `wordpress_api` (T0) -- if WordPress site
4. `google_news_rss` / `gdelt_discovery` (T0) -- URL discovery bypass
5. `curl_cffi_impersonate` (T1) -- TLS fingerprint mimicry
6. `cloudscraper_solve` (T1) -- Cloudflare JS challenge
7. `patchright_stealth` (T2) -- full stealth browser
8. `camoufox_stealth` (T2) -- Firefox stealth
9. `nodriver_stealth` (T2) -- CDP direct
10. `proxy_rotation` (T3) -- residential IP
11. `captcha_solve_service` (T3) -- if CAPTCHA detected
12. `google_cache_fallback` (T0) -- Google's cached version
13. `wayback_fallback` (T4) -- archive
14. `common_crawl_fallback` (T4) -- pre-crawled data

### F2: Empty/Truncated Body (12 sites)

**Root causes**: JavaScript rendering required, paywall, content loaded via AJAX

**Recommended strategy sequence**:
1. `structured_data_extraction` (T0) -- JSON-LD articleBody
2. `nextdata_extraction` (T0) -- __NEXT_DATA__ JSON
3. `wordpress_api` (T0) -- wp-json full content
4. `google_referrer_bypass` (T0) -- metered paywall bypass
5. `print_version_fallback` (T0) -- print URL
6. `amp_version_fallback` (T0) -- AMP full content
7. `rss_feed_fallback` (T0) -- RSS content:encoded
8. `patchright_stealth` (T2) -- render JavaScript
9. `camoufox_stealth` (T2) -- render + anti-detection
10. `google_cache_fallback` (T0) -- cached full version
11. `ocr_screenshot_fallback` (T4) -- OCR from screenshot

### F3: CAPTCHA/JS Challenge (10 sites)

**Root causes**: Cloudflare, PerimeterX/HUMAN, DataDome, reCAPTCHA

**Recommended strategy sequence**:
1. `curl_cffi_impersonate` (T1) -- bypasses simple JS challenges
2. `cloudscraper_solve` (T1) -- Cloudflare-specific solver
3. `patchright_stealth` (T2) -- auto-passes Turnstile
4. `camoufox_stealth` (T2) -- auto-passes with fingerprint diversity
5. `nodriver_stealth` (T2) -- CDP bypass
6. `captcha_solve_service` (T3) -- human/AI solving
7. `google_news_rss` / `gdelt_discovery` (T0) -- avoid the challenge entirely

### F4: Geo-Restriction (9 sites)

**Root causes**: IP geolocation filtering, region-locked content

**Recommended strategy sequence**:
1. `google_news_rss` (T0) -- globally accessible
2. `gdelt_discovery` (T0) -- globally accessible
3. `amp_version_fallback` (T0) -- AMP CDN serves globally
4. `google_cache_fallback` (T0) -- Google cache serves globally
5. `proxy_rotation` (T3) -- geo-targeted residential IP
6. `wayback_fallback` (T4) -- archive
7. `common_crawl_fallback` (T4) -- pre-crawled data

---

## IMPLEMENTATION PRIORITY MATRIX

| Strategy | Impact | Effort | Cost | Priority Score |
|----------|--------|--------|------|---------------|
| `google_news_rss` | 22 sites (F1+F4) | 2 hours | Free | **10/10** |
| `structured_data_extraction` | 12 sites (F2) | 3 hours | Free | **9/10** |
| `google_referrer_bypass` | 19 sites (F1+F2) | 1 hour | Free | **9/10** |
| `wordpress_api` | 7 sites (F1+F2) | 3 hours | Free | **8/10** |
| `gdelt_discovery` | 22 sites (F1+F4) | 4 hours | Free | **8/10** |
| `print_version_fallback` | 12 sites (F2) | 2 hours | Free | **8/10** |
| `nextdata_extraction` | 3+ sites (F2) | 4 hours | Free | **7/10** |
| `captcha_solve_service` | 10 sites (F3) | 4 hours | $1-3/day | **7/10** |
| `bing_news_rss` | 22 sites (F1+F4) | 2 hours | Free | **6/10** |
| `nodriver_stealth` | 10 sites (F1+F3) | 6 hours | Free | **6/10** |
| `common_crawl_fallback` | 5 sites (all F) | 8 hours | Free | **5/10** |
| `googlebot_ua_spoof` | 10 sites (F1+F2) | 2 hours | Free | **5/10** |
| `feedly_api` | 12 sites (F1) | 3 hours | $6/mo | **4/10** |

---

## UPDATED BLOCK-TYPE-TO-STRATEGY MAPPING

```python
STRATEGY_MAP = {
    BlockType.UA_FILTER: [
        "rotate_user_agent",           # T0
        "google_referrer_bypass",      # T0 (NEW)
        "curl_cffi_impersonate",       # T1
        "googlebot_ua_spoof",          # T0 (NEW)
    ],
    BlockType.FINGERPRINT: [
        "curl_cffi_impersonate",       # T1
        "fingerprint_rotation",        # T1
        "patchright_stealth",          # T2
        "camoufox_stealth",            # T2
        "nodriver_stealth",            # T2 (NEW)
    ],
    BlockType.JS_CHALLENGE: [
        "cloudscraper_solve",          # T1
        "curl_cffi_impersonate",       # T1
        "patchright_stealth",          # T2
        "camoufox_stealth",            # T2
        "nodriver_stealth",            # T2 (NEW)
        "captcha_solve_service",       # T3 (NEW)
    ],
    BlockType.CAPTCHA: [
        "patchright_stealth",          # T2
        "camoufox_stealth",            # T2
        "captcha_solve_service",       # T3 (NEW)
    ],
    BlockType.RATE_LIMIT: [
        "exponential_backoff",         # T0
        "rss_feed_fallback",           # T0
        "google_news_rss",             # T0 (NEW)
        "gdelt_discovery",             # T0 (NEW)
        "proxy_rotation",             # T3
    ],
    BlockType.IP_BLOCK: [
        "google_referrer_bypass",      # T0 (NEW)
        "google_news_rss",             # T0 (NEW)
        "wordpress_api",               # T0 (NEW)
        "rss_feed_fallback",           # T0
        "google_cache_fallback",       # T0
        "proxy_rotation",             # T3
        "wayback_fallback",           # T4
        "common_crawl_fallback",       # T4 (NEW)
    ],
    BlockType.GEO_BLOCK: [
        "google_news_rss",             # T0 (NEW)
        "gdelt_discovery",             # T0 (NEW)
        "amp_version_fallback",        # T0
        "google_cache_fallback",       # T0
        "proxy_rotation",             # T3
        "wayback_fallback",           # T4
        "common_crawl_fallback",       # T4 (NEW)
    ],
}
```

---

## NEVER-ABANDON LOOP: EXPANDED ALTERNATIVE_STRATEGIES

```python
ALTERNATIVE_STRATEGIES = [
    # --- Tier 0: Free, no external deps ---
    "rotate_user_agent",
    "exponential_backoff",
    "rss_feed_fallback",
    "google_cache_fallback",
    "amp_version_fallback",
    "google_news_rss",             # NEW
    "bing_news_rss",               # NEW
    "wordpress_api",               # NEW
    "nextdata_extraction",         # NEW
    "gdelt_discovery",             # NEW
    "structured_data_extraction",  # NEW
    "google_referrer_bypass",      # NEW
    "print_version_fallback",      # NEW
    # --- Tier 1: TLS mimicry ---
    "curl_cffi_impersonate",
    "fingerprint_rotation",
    "cloudscraper_solve",
    # --- Tier 2: Browser automation ---
    "patchright_stealth",
    "camoufox_stealth",
    "nodriver_stealth",            # NEW
    # --- Tier 3: External services ---
    "proxy_rotation",
    "captcha_solve_service",       # NEW
    # --- Tier 4: Archive sources ---
    "wayback_fallback",
    "common_crawl_fallback",       # NEW
    "ocr_screenshot_fallback",     # NEW
]
# Total: 25 strategies (up from 12)
```

With 25 strategies in the Never-Abandon loop, each with multiple attempts, and a 4-level retry system (90 base attempts) plus 10 Never-Abandon cycles, the maximum attempts per URL is:

**90 (standard) + 10 cycles x 25 strategies = 90 + 250 = 340 maximum attempts per URL**

This ensures the system will NEVER give up after only 3 methods. It will exhaust 25 different approaches across network, protocol, rendering, proxy, cache, archive, and third-party dimensions before reporting failure.

---

## COST SUMMARY

| Item | Monthly Cost | Notes |
|------|-------------|-------|
| All T0-T2 strategies | $0 | Free, self-hosted |
| Residential proxy pool (T3) | $150-450 | 10-30 GB/month |
| CAPTCHA solving service (T3) | $30-90 | 10K-30K CAPTCHAs/month |
| Feedly Pro API (optional) | $6 | RSS aggregation backup |
| ScraperAPI (optional, Extreme sites) | $49 | 100K API calls/month |
| **Total (base)** | **$150-450** | Proxy + CAPTCHA only |
| **Total (comprehensive)** | **$235-595** | Including optional services |

The base configuration (free T0-T2 strategies + residential proxy + CAPTCHA solver) costs $150-450/month and covers the vast majority of use cases. The optional services are only needed for the 5 Extreme-tier sites (NYT, FT, WSJ, Bloomberg, Le Monde).
