---
name: subagent-creator
description: Guide for creating custom sub-agents (.md files in .claude/agents/). Generates frontmatter + protocol following AgenticWorkflow DNA inheritance. Use when user requests "에이전트 만들어줘", "create an agent", or "서브에이전트 생성".
---

# Sub-Agent Creator

AgenticWorkflow의 DNA를 상속하는 Claude Code 서브에이전트(.md)를 생성하는 가이드.

## Absolute Rules

1. **Quality over speed** — 에이전트의 산출물 품질이 유일한 기준.
2. **DNA Inheritance** — 모든 에이전트는 부모 게놈의 핵심 유전자를 구조적으로 내장.
3. **English-First Execution** — 에이전트는 영어로 작업하고 영어로 산출물 생성.
4. **SOT Read-Only** — 에이전트는 SOT(state.yaml)를 읽기 전용으로만 접근. 쓰기는 Orchestrator/Team Lead만.

## Frontmatter Specification

```yaml
---
name: [agent-name]           # kebab-case, unique across project
description: [1-2 sentence]  # role + domain expertise
model: [opus|sonnet|haiku]   # see Model Selection Protocol below
tools: [tool list]           # comma-separated
maxTurns: [integer]          # based on task complexity
---
```

### Model Selection Protocol

| 기준 | opus | sonnet | haiku |
|------|------|--------|-------|
| 복잡한 분석·설계·코딩 | O | | |
| 표준 구현·번역 | | O | |
| 단순 검증·변환 | | | O |
| 다단계 추론 필요 | O | | |
| 비용 무관, 품질 최우선 | O | | |

> 절대 기준 1: 의심스러우면 상위 모델 선택. 비용은 기준이 아님.

### Tools Reference

| 도구 | 용도 | 부여 기준 |
|------|------|----------|
| Read | 파일 읽기 | 거의 모든 에이전트 |
| Write | 파일 생성 | 산출물 생성 에이전트 |
| Edit | 파일 수정 | 코드 수정 에이전트 |
| Bash | 시스템 명령 | 코드 실행·테스트 |
| Glob | 파일 검색 | 코드베이스 탐색 |
| Grep | 내용 검색 | 코드/문서 검색 |
| WebFetch | URL 접근 | 외부 데이터 수집 |
| WebSearch | 웹 검색 | 리서치 에이전트 |

> 최소 권한 원칙: 필요한 도구만 부여. 단, 품질에 필요하면 추가 도구 부여 가능 (절대 기준 1).

## Generation Protocol

### Step 1: Role Definition

에이전트의 전문 역할 정의:

- "이 에이전트의 전문 도메인은?"
- "어떤 산출물을 생성하는가?"
- "다른 에이전트와의 차별점은?"

### Step 2: Body Structure

frontmatter 아래에 에이전트 본문 작성:

```markdown
---
[frontmatter]
---

You are a [role description]. You [core capability].

## Absolute Rules

1. **Quality over speed** — [domain-specific quality rule]
2. **English-First** — All outputs in English. Korean translation handled by @translator.
3. **SOT Read-Only** — Read state.yaml for context. NEVER write to SOT directly.
4. **Inherited DNA** — [specific DNA genes this agent expresses]

## Language Rule

- **Working language**: English
- **Output language**: English
- **Translation**: Handled by @translator sub-agent (NOT this agent's responsibility)

## Protocol (MANDATORY)

### Step 1: [Context Loading]
[Read SOT, previous step outputs, relevant specs]

### Step 2: [Core Task]
[Main work — analysis, coding, design, etc.]

### Step 3: [Self-Verification]
[Verify against step's Verification criteria]

### Step 4: [Output Generation]
[Write output to specified path]

## Quality Checklist
- [ ] [criterion 1]
- [ ] [criterion 2]
- [ ] Output written to correct path
- [ ] English language verified
```

### Step 3: DNA Injection

모든 에이전트에 주입할 유전자:

| 유전자 | 에이전트 내 표현 | 필수/선택 |
|-------|----------------|---------|
| Quality Absolutism | Absolute Rules §1 | **필수** |
| English-First | Language Rule 섹션 | **필수** |
| SOT Read-Only | Absolute Rules §3 | **필수** |
| Self-Verification | Protocol Step 3 | **필수** |
| Decision Rationale | 판단 근거를 산출물에 포함 | Team member시 필수 |
| Cross-Reference Cues | 이전 단계 참조 포인터 | Team member시 필수 |

### Step 4: Team Member Specifics

Agent Team의 Teammate로 사용될 에이전트는 추가 요구사항:

```markdown
## Team Collaboration

- **Report format**: Include Decision Rationale + Cross-Reference Cues
- **Checkpoint**: Report intermediate results at CP-1/CP-2/CP-3 (every ~10 turns)
- **pACS self-rating**: Score F/C/L before reporting to Team Lead
- **SOT awareness**: Read active_team state from SOT for context
```

### Step 5: Generate File

`.claude/agents/[agent-name].md` 생성.

### Step 6: Validation

- [ ] Frontmatter: name, description, model, tools, maxTurns 모두 존재
- [ ] name이 kebab-case이고 프로젝트 내 유일
- [ ] model이 opus/sonnet/haiku 중 하나
- [ ] Absolute Rules 섹션 존재 (최소 3개 규칙)
- [ ] Language Rule 섹션 존재 (English-First)
- [ ] Protocol 섹션에 단계별 절차
- [ ] Quality Checklist 섹션 존재
- [ ] DNA 유전자 최소 4개 주입 확인

## Batch Creation Pattern

여러 에이전트를 일괄 생성할 때:

1. 공통 요소(DNA, Language Rule, SOT Rule)를 먼저 정의
2. 에이전트별 차별 요소(role, tools, model, maxTurns)만 변경
3. 일괄 검증 (frontmatter 일관성, 이름 충돌 없음)

## Anti-Patterns

- 에이전트가 SOT를 직접 수정 → 절대 기준 2 위반
- 모델을 비용 이유로 다운그레이드 → 절대 기준 1 위반
- Language Rule 누락 → English-First 위반
- 에이전트가 너무 포괄적 → 분할 (1 에이전트 = 1 전문 역할)
- Team member인데 Decision Rationale 미포함 → Cross-Reference 불가
