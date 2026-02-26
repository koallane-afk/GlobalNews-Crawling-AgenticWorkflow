---
name: skill-creator
description: Guide for creating effective Claude Code skills. Generates SKILL.md + references/ following AgenticWorkflow DNA inheritance. Use when user requests "스킬 만들어줘", "create a skill", or "새 스킬 생성".
---

# Skill Creator

AgenticWorkflow의 DNA를 상속하는 Claude Code 스킬을 생성하는 가이드.

## Absolute Rules

1. **Quality over speed** — 생성되는 스킬의 품질이 유일한 기준. 토큰 비용·분량 무시.
2. **DNA Inheritance** — 모든 스킬은 부모 게놈의 핵심 유전자를 구조적으로 내장 (soul.md §0).
3. **English-First Execution** — 스킬 실행 시 에이전트는 영어로 작업. 번역은 @translator 위임.

## Prerequisites

스킬 생성 전 반드시 확인:

1. `.claude/skills/` 디렉터리 구조 파악
2. 기존 스킬 패턴 확인 (workflow-generator, doctoral-writing)
3. 스킬이 사용할 에이전트, 도구, MCP 서버 식별

## Generation Protocol

### Step 1: Intent Clarification

사용자의 스킬 목적 파악:

- "이 스킬이 해결하는 문제는?"
- "주요 입력과 산출물은?"
- "반복 사용 빈도는?" (일회성 → 스킬 불필요, 반복 → 스킬 적합)

> P4 (설계 원칙): 최대 3개 질문, 각 2-3개 선택지. 명확하면 질문 없이 진행.

### Step 2: Structure Design

#### SKILL.md 필수 구조

```markdown
---
name: [skill-name]
description: [1-2문장 설명. 사용 트리거 패턴 포함]
---

# [Skill Name]

## Absolute Rules
[절대 기준 1(품질) + 도메인 특화 규칙]

## Protocol
[단계별 실행 절차]

## Quality Checklist
[완료 전 필수 확인 항목]
```

#### references/ 디렉터리 (선택적)

| 파일 | 용도 |
|------|------|
| `templates/` | 산출물 템플릿 |
| `examples/` | 참조 예시 |
| `checklists/` | 검증 체크리스트 |

### Step 3: DNA Injection

모든 스킬에 주입해야 할 게놈:

| 유전자 | 스킬 내 표현 |
|-------|------------|
| Quality Absolutism | `## Absolute Rules`에 "품질이 유일한 기준" 명시 |
| SOT Pattern | 상태 관리가 필요하면 단일 파일 SOT 설계 |
| 4-Layer QA | Verification 기준 + pACS 채점이 필요한 산출물 식별 |
| English-First | 실행 언어 규칙 명시 (영어 작업 → @translator 번역) |
| Safety Hooks | P1 검증이 필요한 반복 작업 식별 → Python 스크립트 설계 |

### Step 4: P1 Identification

스킬 내에서 "반복적으로 100% 정확해야 하는" 작업 식별:

- [ ] 파일 존재/크기 확인 → P1 Python 스크립트
- [ ] 스키마 검증 → P1 Python 스크립트
- [ ] 수량 카운트 (N개 항목 누락 없음) → P1 Python 스크립트
- [ ] 산술 검증 (min, sum, range) → P1 Python 스크립트
- [ ] 순서 강제 (A 완료 후 B) → P1 Python 스크립트

### Step 5: Generate Files

1. `SKILL.md` 생성
2. `references/` 필요 파일 생성
3. P1 스크립트 식별 시 `scripts/` 에 검증 스크립트 생성

### Step 6: Validation

- [ ] SKILL.md frontmatter 유효 (name, description 필수)
- [ ] Absolute Rules 섹션 존재
- [ ] Protocol 섹션에 단계별 절차 명시
- [ ] DNA 유전자 최소 3개 주입 확인
- [ ] P1 대상 작업 식별 완료

## Anti-Patterns

- 스킬이 너무 포괄적 → 분할 (1 스킬 = 1 명확한 목적)
- references/가 과도 → 핵심만 (스킬은 가벼워야 함)
- P1 대상을 LLM에게 맡김 → Python 스크립트로 강제
- DNA 유전 누락 → 부모 게놈 미상속 스킬은 거부
