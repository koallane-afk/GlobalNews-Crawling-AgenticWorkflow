# GlobalNews Agentic Workflow

> **AI Agentic Workflow Automation System — 뉴스 크롤링 + 빅데이터 분석 자동화**

전 세계 44개 뉴스 사이트에서 기사를 자동 수집하고, 56개 빅데이터 분석 기법으로 처리하여, 5-Layer 신호 계층(Fad → Short → Mid → Long → Singularity)으로 분류하는 **완전 자동화 시스템**을 AI 에이전트 워크플로우로 구축한다.

| 항목 | 내용 |
|------|------|
| **시스템 유형** | AI Agentic Workflow Automation System |
| **부모 프레임워크** | [AgenticWorkflow](AGENTICWORKFLOW-ARCHITECTURE-AND-PHILOSOPHY.md) |
| **산출물** | Parquet/SQLite 구조화된 분석 데이터 |
| **실행 환경** | MacBook M2 Pro 16GB, Claude API $0 |
| **상태** | Step 1/20 — Research Phase |

---

## 핵심 스펙

```
INPUT:  44개 뉴스 사이트 (sources.yaml)
  ↓
[크롤링 엔진] → 모든 섹션 동적 탐색, 차단 시 6-Tier 에스컬레이션
  ↓
[분석 엔진]  → 8-Stage 파이프라인, 56개 기법
  ↓
OUTPUT: Parquet/SQLite (사회 변화 트렌드 연구 기초 자료)
```

### 대상 사이트 (44개)

| 그룹 | 수 | 사이트 |
|------|--:|-------|
| Korean Major Dailies | 5 | chosun.com, joongang.co.kr, donga.com, hani.co.kr, yna.co.kr |
| Korean Economy | 4 | mk.co.kr, hankyung.com, fnnews.com, mt.co.kr |
| Korean Niche | 3 | nocutnews.co.kr, kmib.co.kr, ohmynews.com |
| Korean IT/Science | 7 | 38north.org, bloter.net, etnews.com, sciencetimes.co.kr, zdnet.co.kr, irobotnews.com, techneedle.com |
| US/English Major | 12 | nytimes.com, wsj.com, bloomberg.com, ft.com, cnn.com, marketwatch.com 등 |
| Asia-Pacific | 6 | people.com.cn, scmp.com, yomiuri.co.jp, taiwannews.com 등 |
| Europe/Middle East | 7 | aljazeera.com, bild.de, lemonde.fr, arabnews.com 등 |

### 분석 기법 (56개, 8-Stage Pipeline)

| Stage | 기법 수 | 핵심 기법 |
|-------|------:|---------|
| 1. Preprocessing | 6 | 형태소 분석 (Kiwi/spaCy), 언어 감지, 토큰화 |
| 2. Feature Extraction | 6 | NER, 키워드 추출 (KeyBERT), 임베딩 (SBERT) |
| 3. Sentiment/Tone | 10 | 감정 분석 (KoBERT/VADER), 프레이밍, 가독성 |
| 4. Topic Modeling | 6 | BERTopic, HDBSCAN, NMF/LDA, Louvain |
| 5. Time Series | 7 | STL 분해, Changepoint (PELT), Burst 감지 (Kleinberg) |
| 6. Cross-Analysis | 8 | Granger 인과, PCMCI, 네트워크 분석, 교차 언어 |
| 7. Signal Classification | 2+ | 5-Layer 규칙, 이상 탐지, BERTrend |
| 8. Data Output | — | Parquet ZSTD, SQLite FTS5, sqlite-vec |

### 5-Layer 신호 계층

```
Fad (< 48h) → Short-term (2-14d) → Mid-term (2-12w) → Long-term (3-12m) → Singularity (> 12m)
```

---

## 3대 차별화

| # | 차별화 | 설명 |
|---|--------|------|
| **D1** | **Dynamic-First 전체 사이트 크롤링** | 랜딩페이지가 아닌 모든 섹션을 Playwright/Patchright로 동적 탐색 |
| **D2** | **적응형 차단 돌파 (Never Give Up)** | 7가지 차단 유형 실시간 진단 → 6-Tier 에스컬레이션 → 4-level retry (90회 자동 시도) |
| **D3** | **한국어+글로벌 융합 분석** | Kiwi + KoBERT + 다국어 임베딩으로 교차 언어 분석 |

---

## 핵심 제약 조건

| # | 제약 | 설명 |
|---|------|------|
| C1 | **Claude API = $0** | 모든 분석은 로컬 Python 라이브러리. Claude Code 구독만 사용 |
| C2 | **Conductor Pattern** | Claude Code가 스크립트 생성 → Bash 실행 → 결과 판단 |
| C3 | **MacBook M2 Pro 16GB** | 클라우드 GPU 없이 단일 머신 실행 |
| C4 | **Output = Parquet/SQLite** | 대시보드/시각화 없음. 구조화된 데이터만 |
| C5 | **합법적 크롤링** | robots.txt 존중, Rate Limiting, 개인정보 미수집 |

---

## 빠른 시작

### 사전 준비

| 항목 | 필수 여부 | 설명 |
|------|----------|------|
| Claude Code CLI | 필수 | `npm install -g @anthropic-ai/claude-code` |
| Python 3.10+ | 필수 | 크롤링/분석 스크립트 실행 |
| PyYAML | 필수 | SOT 관리 (`pip install pyyaml`) |

### 워크플로우 시작

```bash
cd GlobalNews-Crawling-AgenticWorkflow
claude                  # Claude Code 실행
```

Claude Code 내에서:
```
시작하자              # 자연어 트리거 → /start 자동 실행
```

또는 직접:
```
/start                # 워크플로우 시작 명령
```

Autopilot 모드 (전자동 실행):
```
autopilot으로 시작해줘
```

---

## 프로젝트 구조 (자식 시스템)

```
GlobalNews-Crawling-AgenticWorkflow/
├── prompt/
│   └── workflow.md                    ← 20-step 워크플로우 정의 (설계도)
├── coding-resource/
│   └── PRD.md                         ← 제품 요구사항 정의서 (44사이트, 56기법, 5-Layer)
├── ORCHESTRATOR-PLAYBOOK.md           ← Orchestrator 실행 가이드 (20단계별 상세)
│
├── .claude/
│   ├── state.yaml                     ← SOT (Single Source of Truth)
│   ├── agents/                         ← 35개 에이전트 정의
│   │   ├── [코어 3개]                   translator.md, reviewer.md, fact-checker.md
│   │   ├── [Research 5개]              site-recon, crawl-analyst, dep-validator, nlp-benchmarker, memory-profiler
│   │   ├── [Planning 7개]              system-architect, 4 crawl-strategists, pipeline-designer
│   │   └── [Implementation 20개]       infra-builder, crawler-core-dev, anti-block-dev, ...
│   └── commands/
│       ├── start.md                   ← /start — 워크플로우 시작
│       ├── review-research.md         ← /review-research — Step 4 리서치 리뷰
│       ├── review-architecture.md     ← /review-architecture — Step 8 아키텍처 승인
│       └── review-final.md            ← /review-final — Step 18 최종 리뷰
│
├── scripts/                            ← 22개 Orchestrator 스크립트
│   ├── sot_manager.py                 (SOT 관리 — fcntl 잠금 기반 atomic 조작)
│   ├── workflow_starter.py            (워크플로우 시작 컨텍스트 생성)
│   ├── validate_step_transition.py    (단계 전환 사전 검증 ST1-ST6)
│   ├── validate_site_coverage.py      (44사이트 커버리지 P1 검증)
│   ├── validate_technique_coverage.py (56기법 커버리지 P1 검증)
│   ├── validate_code_structure.py     (코드 구조 검증 CS1-CS5)
│   ├── validate_data_schema.py        (Parquet/SQLite 스키마 검증)
│   ├── validate_team_state.py         (팀 상태 일관성 검증)
│   ├── run_quality_gates.py           (L0→L1→L1.5→L2 품질 게이트 순차 실행)
│   ├── extract_orchestrator_step_guide.py  (Playbook 단계별 가이드 추출)
│   ├── extract_site_urls.py           (PRD에서 사이트 목록 추출)
│   ├── generate_sources_yaml_draft.py (sources.yaml 초안 생성)
│   ├── split_sites_by_group.py        (44사이트 → 4그룹 분배)
│   ├── distribute_sites_to_teams.py   (44사이트 → 4팀 배분)
│   ├── merge_recon_and_deps.py        (Step 1-2 산출물 병합)
│   ├── filter_prd_architecture.py     (PRD §6-8 아키텍처 섹션 추출)
│   ├── filter_prd_analysis.py         (PRD §5.2 분석 기법 추출)
│   ├── extract_architecture_crawling.py    (크롤링 아키텍처 추출)
│   ├── extract_pipeline_design_s1_s4.py    (Stage 1-4 파이프라인 추출)
│   ├── extract_pipeline_design_s5_s8.py    (Stage 5-8 파이프라인 추출)
│   ├── calculate_success_metrics.py   (PRD §9.1 성공 지표 계산)
│   └── verify_adapter_coverage.py     (44사이트 어댑터 완전성 검증)
│
├── tests/                              ← 3계층 테스트 (7개 파일)
│   ├── test_sot_manager.py            (Unit — SOT CRUD)
│   ├── test_distribute_sites.py       (Unit — 사이트 분배)
│   ├── test_generate_sources.py       (Unit — YAML 생성)
│   ├── test_setup_init.py             (Unit — 인프라 검증)
│   ├── test_sot_lifecycle.py          (Integration — SOT 전체 라이프사이클)
│   ├── test_agent_structure.py        (Structural — 35개 에이전트 frontmatter)
│   ├── test_site_consistency.py       (Structural — 44사이트 일관성)
│   └── test_playbook_structure.py     (Structural — Playbook 20단계 완전성)
│
└── pytest.ini                          ← 테스트 설정 (unit/integration/structural 마커)
```

---

## 20-Step 워크플로우

### Research Phase (Steps 1-4)

| Step | Type | Agent/Team | 산출물 |
|------|------|-----------|--------|
| 1 | Agent | `@site-recon` (sonnet) | `research/site-reconnaissance.md` |
| 2 | Team | `tech-validation-team` (3명) | `research/tech-validation.md` |
| 3 | Agent | `@crawl-analyst` (opus) | `research/crawling-feasibility.md` |
| 4 | Human | `/review-research` | 리서치 승인/반려 |

### Planning Phase (Steps 5-8)

| Step | Type | Agent/Team | 산출물 |
|------|------|-----------|--------|
| 5 | Agent | `@system-architect` (opus) | `planning/architecture-blueprint.md` |
| 6 | Team | `crawl-strategy-team` (4명) | `planning/crawling-strategies.md` |
| 7 | Agent | `@pipeline-designer` (opus) | `planning/analysis-pipeline-design.md` |
| 8 | Human | `/review-architecture` | 아키텍처 승인/반려 |

### Implementation Phase (Steps 9-20)

| Step | Type | Agent/Team | 산출물 |
|------|------|-----------|--------|
| 9 | Agent | `@infra-builder` (opus) | 프로젝트 인프라 (코드) |
| 10 | Team | `crawl-engine-team` (4명) | `src/crawling/` 코어 모듈 |
| 11 | Team | `site-adapters-team` (4명) | `src/crawling/adapters/` (44개 어댑터) |
| 12 | Agent | `@integration-engineer` (opus) | 크롤링 파이프라인 통합 |
| 13 | Team | `analysis-foundation-team` (4명) | `src/analysis/` Stage 1-4 |
| 14 | Team | `analysis-signal-team` (4명) | `src/analysis/` Stage 5-8 + `src/storage/` |
| 15 | Agent | `@integration-engineer` (opus) | 분석 파이프라인 통합 |
| 16 | Agent | `@test-engineer` (opus) | E2E 테스트 리포트 |
| 17 | Agent | `@devops-engineer` (opus) | cron 자동화 + 운영 스크립트 |
| 18 | Human | `/review-final` | 최종 시스템 리뷰 |
| 19 | Agent | `@doc-writer` (opus) | README + 운영 가이드 |
| 20 | Agent | `@reviewer` (opus) | 최종 코드 리뷰 |

---

## 성공 지표 (PRD §9)

| 지표 | 기준 | 설명 |
|------|------|------|
| 사이트 성공률 | ≥ 80% (35/44) | 44개 중 35개 이상 정상 수집 |
| 일일 기사 수 | ≥ 500건 | 24시간 내 수집된 기사 |
| 중복 제거율 | ≥ 90% | URL + 콘텐츠 해시 기반 |
| E2E 소요 시간 | ≤ 3시간 | 크롤링 + 분석 전체 |
| 피크 메모리 | < 10GB | M2 Pro 16GB 제약 |

---

## DNA 유전 (부모 프레임워크로부터)

이 시스템은 [AgenticWorkflow](AGENTICWORKFLOW-ARCHITECTURE-AND-PHILOSOPHY.md) 부모 프레임워크의 전체 게놈을 구조적으로 내장합니다:

| DNA | 이 시스템에서의 발현 |
|-----|-------------------|
| 절대 기준 (품질 절대주의) | 44개 사이트 전부 수집 = 품질. 1개라도 실패하면 품질 실패 |
| SOT 패턴 | `.claude/state.yaml` — `sot_manager.py`로 atomic 조작 |
| 3단계 구조 | Research(1-4) → Planning(5-8) → Implementation(9-20) |
| 4계층 QA | L0 Anti-Skip → L1 Verification → L1.5 pACS → L2 Review |
| P1 봉쇄 | 6개 P1 검증 스크립트 (site_coverage, technique_coverage, code_structure, data_schema, team_state, step_transition) |
| Safety Hooks | 위험 명령 차단 + TDD Guard + Predictive Debugging |
| Adversarial Review | `@reviewer` (Steps 5, 7, 16, 19, 20) + `@fact-checker` (Steps 1, 3) |
| Context Preservation | 스냅샷 + Knowledge Archive + RLM 복원 |

> **도메인 고유 변이**: D2 "Never Give Up" 유전자 — 4-level retry (90회 자동 시도) + 6-Tier 에스컬레이션 + 자기 수정 코드. 부모 게놈에 없는 이 도메인 고유 변이가 가장 강하게 발현된다.

---

## 문서 가이드

| 문서 | 대상 | 설명 |
|------|------|------|
| **이 문서** (`GLOBALNEWS-README.md`) | 첫 방문자 | 시스템 개요, 빠른 시작 |
| [`GLOBALNEWS-ARCHITECTURE.md`](GLOBALNEWS-ARCHITECTURE.md) | 설계자, 개발자 | 시스템 아키텍처, 데이터 흐름, 에이전트 구조 |
| [`GLOBALNEWS-USER-MANUAL.md`](GLOBALNEWS-USER-MANUAL.md) | 운영자 | 워크플로우 실행, 모니터링, 트러블슈팅 |
| [`coding-resource/PRD.md`](coding-resource/PRD.md) | 기획자 | 제품 요구사항 정의서 (상세 스펙) |
| [`prompt/workflow.md`](prompt/workflow.md) | Orchestrator | 20-step 워크플로우 설계도 |
| [`ORCHESTRATOR-PLAYBOOK.md`](ORCHESTRATOR-PLAYBOOK.md) | Orchestrator | 단계별 실행 가이드 |

### 부모 프레임워크 문서

| 문서 | 설명 |
|------|------|
| [`AGENTICWORKFLOW-ARCHITECTURE-AND-PHILOSOPHY.md`](AGENTICWORKFLOW-ARCHITECTURE-AND-PHILOSOPHY.md) | 부모 프레임워크 설계 철학 |
| [`AGENTICWORKFLOW-USER-MANUAL.md`](AGENTICWORKFLOW-USER-MANUAL.md) | 부모 프레임워크 사용법 |
| [`AGENTS.md`](AGENTS.md) | 모든 AI 에이전트 공통 규칙 (Hub) |
| [`soul.md`](soul.md) | DNA 유전 정의서 |
