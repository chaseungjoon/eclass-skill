# eclass

[English](README.md) | **한국어**

AI 에이전트가 대학교 **Canvas LMS**(학교마다 eClass, e클래스, LMS 등으로 부름)를 읽을 수 있게 해 주는 에이전트 스킬입니다. 수강 과목, 마감일, 미제출·누락 과제, 공지사항, 시험 공지, 성적, 강의계획서, 주차별 모듈을 조회할 수 있습니다.

> "이번 주 마감인 과제 뭐 있어?" · "기말고사 공지 찾아줘" · "이번 학기 아직 안 낸 과제 정리해줘"

- **읽기 전용**: `GET` 요청만 보내며 제출이나 수정은 하지 않습니다.
- **의존성 없음**: Python 3.10 이상(표준 라이브러리)만 있으면 됩니다.
- **국내 대학 기준**: 날짜를 한국 시간(KST)으로 표시하고, `2026년 1학기`·`2026-2` 같은 학기명을 인식하며, 한국어·영어로 검색합니다.

## 우리 학교도 되나요?

학교 LMS가 **Canvas** 기반이면 됩니다. 과목 주소가 `https://<주소>/courses/12345` 형태이고 **계정 → 설정** 메뉴가 있으면 Canvas입니다. Moodle 기반이나 학교 자체 개발 시스템은 지원하지 않습니다.

## 설치

### 1. 액세스 토큰 발급

브라우저에서 LMS에 로그인한 뒤 **계정 → 설정 → 승인된 통합 → + 새 액세스 토큰**에서 토큰을 만들고 복사합니다. 학교에 따라 이 버튼이 막혀 있을 수 있으며, 그 경우 학교 LMS 담당 부서에 문의하세요.

### 2. 설정 저장

```sh
mkdir -p ~/.config/eclass
cat > ~/.config/eclass/config <<'EOF'
CANVAS_BASE_URL=https://eclass.example.ac.kr
CANVAS_API_TOKEN=여기에-토큰-붙여넣기
EOF
chmod 600 ~/.config/eclass/config
```

URL은 우리 학교 LMS 주소로 바꾸세요. 같은 이름의 환경 변수가 있으면 파일보다 우선합니다.

### 3. 에이전트별 설치

저장소를 한 번 받은 뒤, 사용하는 에이전트가 스킬을 찾는 위치에 링크합니다.

```sh
git clone https://github.com/chaseungjoon/eclass-skill.git ~/eclass
```

| 에이전트 | 설치 방법 |
|---|---|
| **Claude Code** | `mkdir -p ~/.claude/skills && ln -s ~/eclass ~/.claude/skills/eclass` |
| **Codex CLI** | `mkdir -p ~/.agents/skills && ln -s ~/eclass ~/.agents/skills/eclass` |
| **Gemini CLI** | `mkdir -p ~/.gemini/skills && ln -s ~/eclass ~/.gemini/skills/eclass` |
| **Cursor** | Cursor는 `~/.claude/skills`, `~/.codex/skills`도 읽으므로 Claude Code용 링크로 충분합니다. 특정 프로젝트에서만 쓰려면 `<프로젝트>/.cursor/skills/eclass`에 링크하세요. |
| **OpenClaw** | `cd ~ && openclaw skills install ./eclass` (특정 에이전트는 `--agent AGENT_ID` 추가). 두 설정값을 `~/.openclaw/.env`에 넣고 Gateway를 재시작하세요. |
| **기타 에이전트** | `AGENTS.md`, 규칙 파일, 시스템 프롬프트 등에 다음을 추가하세요: *"대학 수업 관련 질문에는 `~/eclass/SKILL.md`를 읽고 그대로 따를 것."* 셸 실행 도구가 있어야 합니다. |

**Codex 참고:** 기본 샌드박스는 네트워크를 막습니다. `~/.codex/config.toml`에서 허용하세요.

```toml
[sandbox_workspace_write]
network_access = true
```

### 4. 확인

```sh
python3 ~/eclass/scripts/eclass.py check
```

`{"authenticated": true, ...}`가 나오면 성공입니다. 에이전트 세션을 새로 열고 *"이번 학기 수강 과목 알려줘"*라고 물어보세요.

## 명령어

명령어는 에이전트가 알아서 고르지만, 직접 실행할 수도 있습니다.

| 명령어 | 설명 |
|---|---|
| `courses [--search 과목명] [--term all]` | 수강 과목 목록 (기본값: 현재 학기) |
| `planner --kind assignment --unsubmitted --days 14` | 다가오는 미제출 과제 |
| `assignments COURSE_ID [--unsubmitted]` | 과목의 전체 과제와 제출 상태 |
| `assignment COURSE_ID ASSIGNMENT_ID` | 과제 설명, 내 점수, 피드백 |
| `missing` | Canvas가 누락으로 표시한 과제 |
| `announcements --days 30 [--search 기말 --body]` | 최근 공지사항 |
| `announcement COURSE_ID TOPIC_ID` | 공지 하나의 전문 |
| `calendar --days 30` | 과목 캘린더 일정 |
| `grades` | Canvas가 계산한 과목 점수 |
| `syllabus` / `modules` / `files COURSE_ID` | 강의계획서, 모듈, 파일 |

각 명령어 뒤에 `--help`를 붙이면 옵션을 볼 수 있습니다. 자세한 내용은 [references/usage.md](references/usage.md)를, 문제 해결은 [references/setup.md](references/setup.md)를 참고하세요.

## 개인정보

토큰이 있으면 내 LMS 계정에 접근할 수 있습니다. 토큰은 설정 파일이나 환경 변수에만 두고, 커밋하거나 채팅에 붙여 넣지 마세요. 스크립트는 출력에서 토큰을 가립니다. LMS 설정 페이지에서 토큰을 삭제하면 접근 권한이 사라집니다.

## 라이선스

[MIT](LICENSE)
