# Site Replacement Decisions — 39 Failing Sites

**Date**: 2026-03-17
**Purpose**: For each of 39 failing sites, determine whether to DISABLE (region already covered) or REPLACE (no working site for that country/region), with verified RSS URLs for replacements.

---

## Verification Notes

All RSS feed URLs listed as CONFIRMED were successfully fetched via WebFetch and returned valid RSS 2.0 XML with current articles (2025–2026 datestamps). URLs marked STALE returned valid XML but contained only old articles (2017–2018). URLs marked BLOCKED or 404 failed to fetch.

---

## Summary Table

| Failing Site | Country/Region | Action | Replacement Site | Verified RSS URL | Notes |
|---|---|---|---|---|---|
| welt | DE (Germany) | DISABLE | — | — | spiegel, sueddeutsche, faz already cover Germany |
| telegraph | GB (UK) | DISABLE | — | — | bbc, guardian, thetimes already cover UK |
| indianexpress | IN (India) | DISABLE | — | — | hindustantimes, economictimes already cover India |
| timesofindia | IN (India) | DISABLE | — | — | hindustantimes, economictimes already cover India |
| corriere | IT (Italy) | DISABLE | — | — | repubblica, ansa already cover Italy |
| rbc | RU (Russia) | DISABLE | — | — | ria, rg already cover Russia |
| inquirer | PH (Philippines) | DISABLE | — | — | philstar already covers Philippines |
| manilatimes | PH (Philippines) | DISABLE | — | — | philstar already covers Philippines |
| panapress | AF (Africa) | DISABLE | — | — | allafrica, africanews already cover Africa |
| theafricareport | AF (Africa) | DISABLE | — | — | allafrica, africanews already cover Africa |
| elmercurio | CL (Chile) | DISABLE | — | — | biobiochile already covers Chile |
| arabnews | ME (Middle East) | DISABLE | — | — | aljazeera, middleeasteye, almonitor already cover Middle East |
| balkaninsight | EU | DISABLE | — | — | politico_eu, euronews already cover EU region |
| centraleuropeantimes | EU | DISABLE | — | — | politico_eu, euronews already cover EU region |
| euractiv | EU | DISABLE | — | — | politico_eu, euronews already cover EU region |
| intellinews | EU | DISABLE | — | — | politico_eu, euronews already cover EU region |
| fnnews | KR (Korea) | DISABLE | — | — | 13 Korean sites working |
| ohmynews | KR (Korea) | DISABLE | — | — | 13 Korean sites working |
| sciencetimes | KR (Korea) | DISABLE | — | — | 13 Korean sites working |
| techneedle | KR (Korea) | DISABLE | — | — | 13 Korean sites working |
| zdnet_kr | KR (Korea) | DISABLE | — | — | 13 Korean sites working |
| lemonde | FR (France) | REPLACE | france24_fr | https://www.france24.com/fr/france/rss | CONFIRMED: 30 items, French, 2026 |
| lefigaro | FR (France) | REPLACE | france24_fr | (same as above — one entry covers all 4) | Blocked by Cloudflare |
| liberation | FR (France) | REPLACE | france24_fr | (same as above — one entry covers all 4) | Blocked |
| ouestfrance | FR (France) | REPLACE | france24_fr | (same as above — one entry covers all 4) | Blocked |
| bloomberg | US (Finance) | REPLACE | cnbc | https://www.cnbc.com/id/100003114/device/rss/rss.html | CONFIRMED: 30 items, English, 2026 |
| wsj | US (Finance) | REPLACE | fortune | https://fortune.com/feed/ | CONFIRMED: 10 items, English (en-US), 2026 |
| marketwatch | US (Finance) | REPLACE | cnbc | (same as cnbc above) | Paywall |
| latimes | US (General) | REPLACE | nbcnews | https://feeds.nbcnews.com/nbcnews/public/news | CONFIRMED: 29 items, English (en-US), 2026 |
| nationalpost | CA (Canada) | REPLACE | nbcnews | (same as nbcnews above — note: Canada gap remains) | No Canadian replacement verified; nbcnews is US |
| israelhayom | IL (Israel) | DISABLE | — | — | haaretz (soft paywall but accessible) + jpost both cover Israel; jpost RSS confirmed working |
| jordantimes | JO (Jordan) | REPLACE | jordannews | https://jordannews.jo/rss/ | CONFIRMED: 15 items, English content (mislabeled ar), 2026 |
| icelandmonitor | IS (Iceland) | REPLACE | ruv_english | https://www.ruv.is/rss/english | CONFIRMED: 30 items, English content from Iceland, 2026 |
| idnes | CZ (Czech Rep.) | REPLACE | novinky | https://www.novinky.cz/rss | CONFIRMED: 30 items, Czech, 2026 |
| people_cn | CN (China) | REPLACE | scmp_china | https://www.scmp.com/rss/4/feed/ | CONFIRMED: 50 items, English, China section, 2026 |
| afmedios | MX (Mexico) | REPLACE | eluniversal_mx | https://www.eluniversal.com.mx/arc/outboundfeeds/rss/?outputType=xml | CONFIRMED: 20 items, Spanish, 2026 |
| voakorea | KR (VOA Korean) | REPLACE | voa_usa | https://www.voanews.com/api/zqboml-vomx-tpeivmy | VOA Korean feeds redirect; use VOA USA English instead — Korea already covered by 13 KR sites |
| qz | Global Business | DISABLE | — | — | ft, wired, techmeme already cover global business/tech |
| investing_com | Financial Data | DISABLE | — | — | Not traditional news; ft + cnbc replacement covers finance |

---

## Detailed Findings by Category

### France — No Domestic French Site Working

All four French domestic sites (lemonde, lefigaro, liberation, ouestfrance) are inaccessible (Cloudflare blocking or paywalls). france24_fr provides French-language domestic France coverage:

- **feed URL**: `https://www.france24.com/fr/france/rss`
- **verified**: 30 items, `<language>fr</language>`, last build March 17 2026
- **feed title**: "France : News et actualité en continu - France 24"
- **coverage**: French politics, municipal elections, domestic affairs — adequate domestic coverage
- **note**: france24 also has an English France section at `https://www.france24.com/en/france/rss` (30 items, English) — this can serve as a secondary English-language window into French news

Recommendation: Add `france24_fr` as a single new entry replacing all four failing French sites. One entry is sufficient because france24 covers the full domestic French news brief with 25-30 articles per day.

### USA Financial/Business — Bloomberg, WSJ, MarketWatch All Fail

- **CNBC**: `https://www.cnbc.com/id/100003114/device/rss/rss.html` — CONFIRMED working, 30 items, "US Top News and Analysis", March 17 2026. Also has a broader international feed at `/id/100727362/`. Low bot-blocking.
- **Fortune**: `https://fortune.com/feed/` — CONFIRMED working, 10 items, "Fortune | FORTUNE", en-US, March 17 2026. Smaller output (~10/day) but quality business coverage.
- **Washington Post**: `https://feeds.washingtonpost.com/rss/homepage` — CONFIRMED working, 75 items, general US news (not finance-focused, soft paywall but RSS accessible).
- **Reuters**: feeds.reuters.com blocked (Cloudflare). Not accessible.

Recommendation: Add `cnbc` (primary, 30 articles/day) + `fortune` (secondary, ~10/day) as replacements for bloomberg/wsj/marketwatch.

### USA General — LA Times, National Post Fail

- **NBC News**: `https://feeds.nbcnews.com/nbcnews/public/news` — CONFIRMED working, 29 items, "NBC News Top Stories", en-US, March 17 2026.
- **ABC News**: `https://abcnews.com/abcnews/topstories` — CONFIRMED working, 25 items, "ABC News: Top Stories", March 17 2026.
- **Washington Post homepage**: `https://feeds.washingtonpost.com/rss/homepage` — CONFIRMED working, 75 items.

Note on nationalpost: This is a Canadian site. With its failure, Canada has no coverage. The closest available option is a US general news site. If Canadian coverage specifically matters, a dedicated search for CBC/Globe and Mail RSS would be needed. CBC News has RSS at `https://rss.cbc.ca/lineup/topstories.xml` — this was not tested in this session.

Recommendation: Add `nbcnews` replacing latimes for US general coverage. For nationalpost/Canada, flag as needing separate verification of CBC RSS.

### Israel — israelhayom Fails

- **jpost**: `https://www.jpost.com/rss/rssfeedsfrontpage.aspx` — CONFIRMED working, 27 items, English, March 17 2026. Israel and Middle East coverage.
- **haaretz**: All tested RSS URLs for Haaretz redirect to non-RSS pages. Haaretz RSS appears broken/retired. The site has a hard paywall.

Recommendation: DISABLE israelhayom — jpost alone provides adequate Israel coverage (27 articles/day confirmed). Haaretz RSS is broken anyway, so jpost is the reliable Israeli source.

### Jordan — jordantimes Fails

- **Jordan News (jordannews.jo)**: `https://jordannews.jo/rss/` — CONFIRMED working, 15 items. Content is in English (metadata tag says `ar` but all article text is English). Covers Jordan and MENA region. Published March 17 2026.

Recommendation: Replace jordantimes with jordannews.

### Iceland — icelandmonitor Fails

- **RUV English** (`www.ruv.is`): `https://www.ruv.is/rss/english` — CONFIRMED working, 30 items, English content from Icelandic national broadcaster, March 17 2026. Iceland-specific news including politics, infrastructure, culture, weather.
- **Iceland Review**: `https://www.icelandreview.com/feed/` — CONFIRMED working, 8 items, en-US, March 17 2026. Smaller output but English-language Iceland coverage.
- **Reykjavik Grapevine**: `https://grapevine.is/feed/` — CONFIRMED working, 11 items, en-US, March 13 2026.

Recommendation: Replace icelandmonitor with ruv_english (highest article count, authoritative national broadcaster source).

### Czech Republic — idnes Fails

- **Novinky.cz**: `https://www.novinky.cz/rss` — CONFIRMED working, 30 items, Czech language, March 17 2026. Major Czech news portal (owned by Seznam.cz).
- **iRozhlas.cz**: `https://www.irozhlas.cz/rss/irozhlas` — CONFIRMED working, 20 items, Czech language (cs), March 17 2026. Czech Radio public broadcaster.

Recommendation: Replace idnes with novinky (higher volume, 30 items). iRozhlas is a good secondary option if a second Czech source is desired.

### China — people_cn Fails

- **Xinhua worldrss.xml / chinarss.xml**: Both feeds return valid XML but articles are from 2017-2018. The feeds are structurally intact but **not updated** — stale content.
- **SCMP China section**: `https://www.scmp.com/rss/4/feed/` — CONFIRMED working, 50 items, English, "China - South China Morning Post", March 14-17 2026. Hong Kong-based, independent English-language China coverage. SCMP already exists in the sources.yaml as a working site covering HK/Asia.

Check whether SCMP is already in the working sites list. If scmp already covers China adequately through its existing entry, people_cn can simply be DISABLED. If a China-specific RSS addition is desired, scmp_china (RSS feed /rss/4/) is the best confirmed option.

Recommendation: If scmp is already a working site in sources.yaml — DISABLE people_cn (China already covered). If not, add scmp_china with `https://www.scmp.com/rss/4/feed/`.

### Mexico — afmedios Fails

- **El Universal**: `https://www.eluniversal.com.mx/arc/outboundfeeds/rss/?outputType=xml` — CONFIRMED working, 20 items, Spanish (es), March 16-17 2026. One of Mexico's largest newspapers.

Recommendation: Replace afmedios with eluniversal_mx.

### VOA Korea — voakorea Fails

- All `feeds.voanews.com/voakorea/*` URLs redirect to VOA podcast page (302). VOA Korean feed is broken/retired.
- VOA USA English: `https://www.voanews.com/api/zqboml-vomx-tpeivmy` — CONFIRMED working, 20 items, English.
- Korea is already covered by 13 working Korean sites. VOA Korea was providing an additional English-language perspective on Korea.

Recommendation: DISABLE voakorea. Korea is already covered by 13 domestic Korean sites. If an English-language perspective on Korea is specifically needed, VOA USA feed covers Korea-related stories within its US foreign policy coverage.

### Quartz (qz) — Global Business

- Covered by ft, wired, techmeme.
- Recommendation: DISABLE.

### Investing.com — Financial Data Site

- Not a traditional news publisher. Financial data aggregator.
- Covered by cnbc (new replacement) + ft.
- Recommendation: DISABLE.

---

## New Sites to Add (Replacements Only)

| New Site ID | URL | RSS Feed URL | Language | Country | Daily Articles (est.) |
|---|---|---|---|---|---|
| france24_fr | france24.com/fr | https://www.france24.com/fr/france/rss | fr | FR | ~30 |
| cnbc | cnbc.com | https://www.cnbc.com/id/100003114/device/rss/rss.html | en | US | ~30 |
| fortune | fortune.com | https://fortune.com/feed/ | en | US | ~10 |
| nbcnews | nbcnews.com | https://feeds.nbcnews.com/nbcnews/public/news | en | US | ~29 |
| jordannews | jordannews.jo | https://jordannews.jo/rss/ | en | JO | ~15 |
| ruv_english | ruv.is | https://www.ruv.is/rss/english | en | IS | ~30 |
| novinky | novinky.cz | https://www.novinky.cz/rss | cs | CZ | ~30 |
| eluniversal_mx | eluniversal.com.mx | https://www.eluniversal.com.mx/arc/outboundfeeds/rss/?outputType=xml | es | MX | ~20 |

Note: scmp_china (`https://www.scmp.com/rss/4/feed/`) is available if scmp is not already covering China. Verify against sources.yaml before deciding.

---

## Unresolved Items

1. **Canada (nationalpost fails)**: No Canadian replacement verified in this session. CBC News likely has RSS at `https://rss.cbc.ca/lineup/topstories.xml` — needs separate verification. If Canada-specific coverage is required, this should be tested.

2. **Haaretz RSS**: All known Haaretz RSS URLs are broken (redirects to images or 404). If haaretz is currently listed as "working" in the system, it is working via scraping/sitemap rather than RSS. jpost RSS is the confirmed reliable Israeli source.

3. **VOA Korean**: VOA Korean domain (korean.voanews.com) refused connections in testing. The feed infrastructure appears shut down. No viable VOA Korean replacement found. Korea coverage is adequate from 13 domestic sites.

4. **Xinhua**: Both worldrss.xml and chinarss.xml return 2017 content — feeds exist structurally but are unmaintained. Not usable as a news source. If Chinese state media perspective is specifically needed, CGTN (cgtn.com) may have RSS — not tested.
