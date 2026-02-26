# GlobalNews User Manual

> **GlobalNews Crawling & Analysis Auto-Build System — 워크플로우 실행 가이드**

이 문서는 GlobalNews 자식 시스템의 워크플로우를 실행하는 방법을 안내한다.
부모 프레임워크(AgenticWorkflow)의 사용법은 [`AGENTICWORKFLOW-USER-MANUAL.md`](AGENTICWORKFLOW-USER-MANUAL.md)를 참조한다.

| 항목 | 내용 |
|------|------|
| **대상** | 이 워크플로우를 실행하는 사용자 (연구자, 운영자) |
| **워크플로우** | 20-step (Research → Planning → Implementation) |
| **실행 도구** | Claude Code CLI |
| **소요 시간** | 워크플로우 전체 구축 후, 일일 자동 운영 |

---

## 1. 사전 준비

### 1.1 필수 환경

| 항목 | 요구 사항 | 확인 방법 |
|------|----------|----------|
| 하드웨어 | MacBook M2 Pro 16GB+ | `sysctl hw.memsize` |
| Python | 3.10 이상 | `python3 --version` |
| Claude Code | 최신 버전 | `claude --version` |
| PyYAML | 설치 필요 | `pip install pyyaml` |
| 디스크 공간 | 20GB+ 여유 | 크롤링 데이터 + NLP 모델 |

### 1.2 초기 설정

```bash
# 1. 프로젝트 클론
git clone <repo-url> GlobalNews-Crawling-AgenticWorkflow
cd GlobalNews-Crawling-AgenticWorkflow

# 2. Claude Code 인프라 검증
claude --init

# 3. 테스트 실행 (선택)
python3 -m pytest tests/ -v
```

### 1.3 인프라 검증 (`/install`)

Claude Code 내에서 `/install`을 실행하면 Hook 인프라의 건강 상태를 분석한다:

- Python 버전 확인
- 19개 Hook 스크립트 구문 검증
- PyYAML 설치 확인
- SOT 쓰기 패턴 안전성 검증
- 런타임 디렉터리 자동 생성

---

## 2. 워크플로우 시작

### 2.1 시작 방법

Claude Code를 실행한 후, 아래 중 하나를 입력:

| 입력 | 동작 |
|------|------|
| `시작하자` | 자연어 트리거 → `/start` 자동 실행 |
| `크롤링 시작` | 동일 |
| `워크플로우 시작` | 동일 |
| `/start` | 직접 슬래시 명령 실행 |

### 2.2 Autopilot 모드 (전자동)

`(human)` 체크포인트(Steps 4, 8, 18)를 자동 승인하는 모드:

| 입력 | 동작 |
|------|------|
| `autopilot으로 시작해줘` | Autopilot ON + 워크플로우 시작 |
| `전자동으로 실행` | 동일 |
| `autopilot 해제` | 수동 모드 전환 |

> **주의**: Autopilot에서도 `(hook)` exit code 2 차단은 무시되지 않는다. Safety Hook은 항상 존중된다.

### 2.3 ULW (Ultrawork) 모드

프롬프트에 `ulw`를 포함하면 최대 철저함 모드가 활성화된다:

```
ulw 시작하자        # ULW + 수동 모드
ulw autopilot으로    # ULW + Autopilot (최대 조합)
```

ULW 강화 규칙:
- **I-1 Sisyphus Persistence**: 최대 3회 재시도, 각 시도는 다른 접근법
- **I-2 Mandatory Task Decomposition**: 비-trivial 작업 시 태스크 분해 강제
- **I-3 Bounded Retry Escalation**: 동일 대상 3회 초과 재시도 금지

### 2.4 시작 시 발생하는 일

`/start` 실행 시 자동으로:

1. `scripts/workflow_starter.py`가 SOT + workflow.md를 파싱
2. 현재 단계(`current_step`)와 상태를 확인
3. 구조화된 시작 컨텍스트 생성
4. 해당 단계의 실행 가이드를 로드

---

## 3. Research Phase (Steps 1-4)

### Step 1: 대상 사이트 정찰 및 분류

| 항목 | 내용 |
|------|------|
| **에이전트** | `@site-recon` (sonnet) |
| **산출물** | `research/site-reconnaissance.md` |
| **Review** | `@fact-checker` |
| **Translation** | `@translator` → `research/site-reconnaissance.ko.md` |

**사용자 행동**: 없음 (자동 실행). 에이전트가 44개 사이트를 방문하여 구조를 분석한다.

**완료 기준**:
- 44개 사이트 전수 분석 (P1: `validate_site_coverage.py`)
- 각 사이트의 크롤링 난이도, 구조, 섹션 수 기록
- `@fact-checker`가 정보 정확성 검증

### Step 2: 기술 스택 검증 (팀)

| 항목 | 내용 |
|------|------|
| **팀** | `tech-validation-team` (3명) |
| **멤버** | `@dep-validator`, `@nlp-benchmarker`, `@memory-profiler` |
| **산출물** | `research/tech-validation.md` |

**사용자 행동**: 없음. 3명의 전문 에이전트가 병렬로:
- 의존성 패키지 설치/검증
- 한국어 NLP 모델 벤치마크
- 메모리 사용 시나리오 프로파일링

### Step 3: 크롤링 실현성 분석

| 항목 | 내용 |
|------|------|
| **에이전트** | `@crawl-analyst` (opus) |
| **산출물** | `research/crawling-feasibility.md` |
| **Review** | `@fact-checker` |
| **Translation** | `@translator` |

**사용자 행동**: 없음. 44개 사이트별 크롤링 전략과 4-level retry 아키텍처를 설계한다.

### Step 4: (human) 리서치 리뷰 및 우선순위 결정

| 항목 | 내용 |
|------|------|
| **유형** | 사용자 체크포인트 |
| **명령** | `/review-research` |

**사용자 행동**:
1. Steps 1-3의 산출물을 검토한다
2. `/review-research` 명령을 실행한다
3. 옵션 선택:
   - **proceed** — 다음 Phase로 진행
   - **rework [step]** — 특정 단계 재작업 지시
   - **modify** — 요구사항 수정

> Autopilot 모드에서는 자동 승인된다 (품질 극대화 기본값).

---

## 4. Planning Phase (Steps 5-8)

### Step 5: 시스템 아키텍처 설계도

| 항목 | 내용 |
|------|------|
| **에이전트** | `@system-architect` (opus) |
| **산출물** | `planning/architecture-blueprint.md` |
| **Review** | `@reviewer` |
| **Translation** | `@translator` |

**사용자 행동**: 없음. 4-Layer 아키텍처, Parquet/SQLite 스키마, 모듈 인터페이스를 설계한다.

### Step 6: 사이트별 크롤링 전략 설계 (팀)

| 항목 | 내용 |
|------|------|
| **팀** | `crawl-strategy-team` (4명) |
| **멤버** | `@crawl-strategist-{kr,en,asia,global}` |
| **산출물** | `planning/crawling-strategies.md` |

**사용자 행동**: 없음. 44개 사이트를 4개 언어/지역 그룹으로 나누어 병렬로 전략을 수립한다.

### Step 7: 분석 파이프라인 상세 설계

| 항목 | 내용 |
|------|------|
| **에이전트** | `@pipeline-designer` (opus) |
| **산출물** | `planning/analysis-pipeline-design.md` |
| **Review** | `@reviewer` |
| **Translation** | `@translator` |

**사용자 행동**: 없음. 8-Stage 파이프라인의 입출력 형식, 56개 기법 매핑, 5-Layer 분류 규칙을 설계한다.

**핵심 검증**: `validate_technique_coverage.py`로 56개 기법 전수 매핑 확인.

### Step 8: (human) 아키텍처 승인

| 항목 | 내용 |
|------|------|
| **유형** | 사용자 체크포인트 |
| **명령** | `/review-architecture` |

**사용자 행동**:
1. Steps 5-7의 설계를 검토한다
2. `/review-architecture` 명령을 실행한다
3. 옵션 선택: proceed / rework / modify

> 이 체크포인트 이후 Implementation Phase에 진입한다. 아키텍처 변경은 이후 비용이 매우 높다.

---

## 5. Implementation Phase (Steps 9-20)

### Step 9: 프로젝트 인프라 구축

| 항목 | 내용 |
|------|------|
| **에이전트** | `@infra-builder` (opus) |
| **산출물** | 프로젝트 디렉터리 구조, `sources.yaml`, `pipeline.yaml`, `requirements.txt`, `main.py` |

**사용자 행동**: 없음. 전체 프로젝트 스캐폴딩을 생성한다.

### Step 10: 크롤링 코어 엔진 구현 (팀)

| 항목 | 내용 |
|------|------|
| **팀** | `crawl-engine-team` (4명) |
| **멤버** | `@crawler-core-dev`, `@anti-block-dev`, `@dedup-dev`, `@ua-rotation-dev` |
| **산출물** | `src/crawling/` 코어 모듈 |

**사용자 행동**: 없음. Dense Checkpoint 패턴으로 4명이 병렬 구현:
- **crawler-core-dev**: NetworkGuard, URL 발견, 기사 추출
- **anti-block-dev**: 7가지 차단 진단, 6-Tier 에스컬레이션, Circuit Breaker
- **dedup-dev**: URL 정규화, SimHash, 제목 유사도
- **ua-rotation-dev**: User-Agent 회전, 세션 관리

### Step 11: 사이트별 어댑터 구현 (팀)

| 항목 | 내용 |
|------|------|
| **팀** | `site-adapters-team` (4명) |
| **멤버** | 4x `@adapter-dev-*` |
| **산출물** | `src/crawling/adapters/` (44개 어댑터) |

**사용자 행동**: 없음. 44개 사이트를 4개 그룹으로 나누어 병렬 구현:
- Korean Major/Economy/Niche (12): `@adapter-dev-kr-major`
- Korean IT/Science (7): `@adapter-dev-kr-tech`
- US/English (12): `@adapter-dev-english`
- Asia-Pacific + Europe/ME (13): `@adapter-dev-multilingual`

**핵심 검증**: `verify_adapter_coverage.py`로 44개 어댑터 완전성 확인.

### Step 12: 크롤링 파이프라인 통합

| 항목 | 내용 |
|------|------|
| **에이전트** | `@integration-engineer` (opus) |
| **산출물** | `src/crawling/pipeline.py`, `retry_manager.py`, `crawl_report.py` |

**사용자 행동**: 없음. 4-Level Retry System (90회 자동 시도)을 포함한 통합 파이프라인을 구현한다.

### Steps 13-14: 분석 파이프라인 구현 (팀 × 2)

| Step | 팀 | Stage | 핵심 기법 |
|------|-----|-------|----------|
| 13 | `analysis-foundation-team` (4명) | 1-4 | Kiwi/spaCy, SBERT, KoBERT, BERTopic |
| 14 | `analysis-signal-team` (4명) | 5-8 | STL, PELT, Granger, 5-Layer, Parquet/SQLite |

**사용자 행동**: 없음. 8명의 전문 에이전트가 8-Stage 파이프라인의 각 Stage를 병렬 구현한다.

### Step 15: 분석 파이프라인 통합

| 항목 | 내용 |
|------|------|
| **에이전트** | `@integration-engineer` (opus) |
| **산출물** | `src/analysis/pipeline.py` |

**사용자 행동**: 없음. 8개 Stage를 직렬 연결하고, Stage 간 메모리 관리(모델 로드 → 처리 → 저장 → 해제)를 구현한다.

### Step 16: E2E 테스트 (44사이트 전체 크롤+분석)

| 항목 | 내용 |
|------|------|
| **에이전트** | `@test-engineer` (opus) |
| **산출물** | `testing/e2e-test-report.md`, `testing/per-site-results.json` |
| **Review** | `@reviewer` |
| **Translation** | `@translator` |

**사용자 행동**: 없음. 전체 시스템을 실제로 실행하여 검증한다:
- 44개 사이트 실제 크롤링
- 8-Stage 분석 파이프라인 실행
- 성공률 ≥ 80%, 일일 기사 ≥ 500건, E2E ≤ 3시간 확인

### Step 17: 자동화 및 스케줄링

| 항목 | 내용 |
|------|------|
| **에이전트** | `@devops-engineer` (opus) |
| **산출물** | `scripts/run_daily.sh`, `scripts/run_weekly_rescan.sh`, `src/utils/self_recovery.py` |

**사용자 행동**: 없음. cron 설정, 자기 복구, 로그 관리를 구현한다.

### Step 18: (human) 최종 시스템 리뷰

| 항목 | 내용 |
|------|------|
| **유형** | 사용자 체크포인트 |
| **명령** | `/review-final` |

**사용자 행동**:
1. E2E 테스트 보고서 (Step 16) 검토
2. 자동화 설정 (Step 17) 확인
3. `/review-final` 실행
4. 옵션:
   - **approve** — 운영 배포 승인
   - **fix [issue]** — 특정 이슈 수정 지시
   - **disable [sites]** — 특정 사이트 비활성화

### Step 19: 문서화

| 항목 | 내용 |
|------|------|
| **에이전트** | `@doc-writer` (opus) |
| **산출물** | `README.md`, `docs/operations-guide.md`, `docs/architecture-guide.md` |
| **Translation** | `@translator` |

**사용자 행동**: 없음. 구축된 시스템의 운영 문서를 생성한다.

### Step 20: 최종 코드 리뷰

| 항목 | 내용 |
|------|------|
| **에이전트** | `@reviewer` (opus) |
| **산출물** | `review-logs/step-20-review.md` |
| **Translation** | `@translator` |

**사용자 행동**: 없음. 전체 코드베이스에 대한 적대적 리뷰:
- 보안 (SQL injection, credential 노출)
- 정확성 (PRD 스키마 일치, 44사이트+56기법 완전성)
- 신뢰성 (retry, Circuit Breaker, 자기 복구)
- 합법성 (robots.txt, Rate Limiting)

---

## 6. 진행 모니터링

### 6.1 SOT 상태 확인

```bash
# Claude Code 외부에서
python3 scripts/sot_manager.py --read --project-dir .

# Claude Code 내부에서
현재 상태 알려줘
```

SOT 출력 예시:

```yaml
workflow:
  current_step: 5
  status: in_progress
  outputs:
    step-1: research/site-reconnaissance.md
    step-2: research/tech-validation.md
    step-3: research/crawling-feasibility.md
    step-4: autopilot-logs/step-4-decision.md
  pacs:
    current_step_score: 78
    dimensions: {F: 82, C: 78, L: 80}
```

### 6.2 단계별 산출물 확인

| Phase | 산출물 경로 |
|-------|-----------|
| Research (1-3) | `research/` |
| Planning (5-7) | `planning/` |
| Implementation (9-17) | `src/`, `testing/`, `scripts/` |
| Human Decisions (4, 8, 18) | `autopilot-logs/` |
| Reviews | `review-logs/` |
| pACS | `pacs-logs/` |
| Verification | `verification-logs/` |
| Translations | 원본 경로에 `.ko.md` 확장자 |

### 6.3 품질 로그 확인

```bash
# pACS 점수 확인
cat pacs-logs/step-N-pacs.md

# 리뷰 결과 확인
cat review-logs/step-N-review.md

# 검증 결과 확인
cat verification-logs/step-N-verify.md
```

---

## 7. 사용자 개입 체크포인트 상세

### 7.1 `/review-research` (Step 4)

검토 대상:
- [ ] 44개 사이트 정찰 보고서가 충분히 상세한가?
- [ ] 기술 스택 검증에서 NO-GO 항목은 없는가?
- [ ] 크롤링 실현성 분석의 차단 유형 진단이 합리적인가?
- [ ] 수집 가능한 사이트가 35개 이상 예상되는가?

### 7.2 `/review-architecture` (Step 8)

검토 대상:
- [ ] Staged Monolith 아키텍처가 요구사항에 적합한가?
- [ ] Parquet/SQLite 스키마가 PRD §7과 일치하는가?
- [ ] 56개 분석 기법이 8-Stage에 적절히 매핑되었는가?
- [ ] 메모리 관리 전략 (Stage별 모델 로드/해제)이 타당한가?
- [ ] 44개 사이트별 크롤링 전략이 실현 가능한가?

### 7.3 `/review-final` (Step 18)

검토 대상:
- [ ] E2E 테스트 성공률 ≥ 80% (35/44 사이트)?
- [ ] 일일 기사 수 ≥ 500건?
- [ ] E2E 소요 시간 ≤ 3시간?
- [ ] 피크 메모리 < 10GB?
- [ ] 중복 제거율 ≥ 90%?
- [ ] cron 설정이 올바른가?
- [ ] 자기 복구 로직이 정상 동작하는가?

---

## 8. 트러블슈팅

### 8.1 워크플로우 시작 실패

| 증상 | 원인 | 해결 |
|------|------|------|
| `/start` 무반응 | SOT 파일 부재 | `ls .claude/state.yaml` 확인 |
| "blocked" 상태 | 이전 단계 미완료 | SOT `current_step` 확인 → 해당 단계 재실행 |
| Hook 에러 | Python/PyYAML 미설치 | `pip install pyyaml` |

### 8.2 에이전트 실패

| 증상 | 원인 | 해결 |
|------|------|------|
| pACS RED (< 50) | 산출물 품질 미달 | Abductive Diagnosis → 재작업 |
| Review FAIL | 산출물에 Critical 이슈 | 이슈 수정 후 재리뷰 |
| Verification FAIL | 기준 미충족 | 미충족 기준 확인 → 해당 부분 재실행 |
| Team 멤버 실패 | 의존성 오류 등 | SendMessage로 피드백 → 멤버 재시도 |

### 8.3 재시도 예산 소진

재시도 예산이 소진되면 사용자 에스컬레이션이 발생한다:

```bash
# 재시도 예산 확인
python3 .claude/hooks/scripts/validate_retry_budget.py \
  --step N --gate verification --project-dir . --check

# 출력 예시: {"can_retry": false, "retries_used": 10, "max_retries": 10}
```

**해결**: 수동 개입하여 근본 원인을 분석하고, 필요시 Verification 기준 조정 또는 접근법 변경.

### 8.4 P1 검증 스크립트 실패

| 스크립트 | 실패 시 | 해결 |
|---------|--------|------|
| `validate_site_coverage.py` | 44사이트 미달 | 누락 사이트 추가 |
| `validate_technique_coverage.py` | 56기법 미달 | 미매핑 기법 Stage 배정 |
| `validate_code_structure.py` | 디렉터리/파일 미달 | 누락 파일 생성 |
| `validate_data_schema.py` | 스키마 불일치 | PRD §7과 대조 후 수정 |
| `validate_team_state.py` | 팀 상태 불일치 | SOT `active_team` 수정 |
| `validate_step_transition.py` | 전환 조건 미달 | 누락 산출물/검증 완료 |

---

## 9. 구축 완료 후 운영

### 9.1 일상 운영

워크플로우 20단계가 모두 완료되면, 구축된 시스템은 독립적으로 운영된다:

| 시간 | 자동 작업 |
|------|----------|
| 02:00 AM | `scripts/run_daily.sh` → 44사이트 크롤링 |
| 크롤링 직후 | 8-Stage 분석 파이프라인 자동 실행 |
| 일요일 01:00 AM | 사이트 구조 재스캔 |
| 매일 아침 | 사용자: `data/output/` 분석 결과 확인 |

### 9.2 새 사이트 추가

```yaml
# sources.yaml에 추가
- name: new-site
  url: https://new-site.com
  language: en
  sections: [politics, economy, tech]
  crawl_difficulty: medium
  tier: 3
```

→ 시스템이 자동으로 구조를 파악하고 크롤링을 시작한다.

### 9.3 Tier 6 수동 개입

90회 자동 시도가 모두 실패한 사이트가 있을 때:

```bash
# Claude Code에서
Tier 6 분석해줘 [사이트명]
```

Claude Code가 실패 로그를 분석하고, 사이트 특화 우회 코드를 생성한다.

### 9.4 데이터 조회

구축된 시스템의 산출물을 조회하는 방법:

```python
# Parquet (DuckDB)
import duckdb
con = duckdb.connect()
con.sql("SELECT * FROM 'data/output/signals.parquet' WHERE signal_layer = 'L5_singularity'")

# Parquet (pandas)
import pandas as pd
df = pd.read_parquet("data/output/analysis.parquet")

# SQLite (전문 검색)
import sqlite3
con = sqlite3.connect("data/output/index.sqlite")
con.execute("SELECT * FROM articles_fts WHERE articles_fts MATCH '인공지능 AND 싱귤래리티'")

# SQLite (벡터 검색 — sqlite-vec)
con.execute("SELECT * FROM article_embeddings WHERE embedding MATCH ? ORDER BY distance LIMIT 10", [query_vec])
```

---

## 10. 명령어 요약

### 10.1 Claude Code 슬래시 명령

| 명령 | 시점 | 설명 |
|------|------|------|
| `/start` | 워크플로우 시작 | SOT 기반 현재 단계부터 실행 |
| `/review-research` | Step 4 | Research Phase 산출물 리뷰 |
| `/review-architecture` | Step 8 | Planning Phase 설계 승인 |
| `/review-final` | Step 18 | 최종 시스템 리뷰 + 배포 승인 |
| `/install` | 최초 설정 | Hook 인프라 검증 |
| `/maintenance` | 주기적 | 건강 검진 (stale archives, doc-code sync) |

### 10.2 Orchestrator 스크립트

```bash
# SOT 관리
python3 scripts/sot_manager.py --read --project-dir .
python3 scripts/sot_manager.py --record-output N path --project-dir .
python3 scripts/sot_manager.py --advance-step N --project-dir .
python3 scripts/sot_manager.py --update-pacs N --F 85 --C 78 --L 80 --project-dir .

# 도메인 검증
python3 scripts/validate_site_coverage.py --file path --project-dir .
python3 scripts/validate_technique_coverage.py --file path --project-dir .
python3 scripts/validate_code_structure.py --step N --project-dir .

# 단계별 가이드 추출
python3 scripts/extract_orchestrator_step_guide.py --step N --project-dir .
```

### 10.3 품질 검증 스크립트

```bash
# 4계층 품질 게이트
python3 .claude/hooks/scripts/validate_pacs.py --step N --check-l0 --project-dir .
python3 .claude/hooks/scripts/validate_review.py --step N --project-dir . --check-pacs-arithmetic
python3 .claude/hooks/scripts/validate_verification.py --step N --project-dir .
python3 .claude/hooks/scripts/validate_translation.py --step N --project-dir . --check-pacs --check-sequence

# 재시도 예산
python3 .claude/hooks/scripts/validate_retry_budget.py --step N --gate verification --project-dir . --check-and-increment

# 진단
python3 .claude/hooks/scripts/diagnose_context.py --step N --gate verification --project-dir .
python3 .claude/hooks/scripts/validate_diagnosis.py --step N --gate verification --project-dir .
```

---

## 11. 관련 문서

| 문서 | 내용 |
|------|------|
| [`GLOBALNEWS-README.md`](GLOBALNEWS-README.md) | 시스템 개요, 빠른 시작 |
| [`GLOBALNEWS-ARCHITECTURE.md`](GLOBALNEWS-ARCHITECTURE.md) | 시스템 아키텍처, 데이터 흐름 |
| [`prompt/workflow.md`](prompt/workflow.md) | 20-step 설계도 (상세 스펙) |
| [`ORCHESTRATOR-PLAYBOOK.md`](ORCHESTRATOR-PLAYBOOK.md) | Orchestrator 실행 가이드 (스크립트 호출 순서) |
| [`coding-resource/PRD.md`](coding-resource/PRD.md) | 제품 요구사항 정의서 |
| [`AGENTICWORKFLOW-USER-MANUAL.md`](AGENTICWORKFLOW-USER-MANUAL.md) | 부모 프레임워크 사용법 |
