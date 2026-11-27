# eclass

**English** | [한국어](README_KOR.md)

An agent skill that lets an AI agent read your university **Canvas LMS** (often called eClass, e클래스, or LMS at Korean universities): courses, deadlines, unsubmitted and missing work, announcements, exam notices, grades, syllabi, and modules.

> "이번 주 마감인 과제 뭐 있어?" · "기말고사 공지 찾아줘" · "What's still unsubmitted this semester?"

- **Read-only.** It only sends `GET` requests and never submits or changes anything.
- **No dependencies.** It needs only Python 3.10+ (standard library).
- **Built for Korean schools.** Dates are shown in KST, it recognizes semester names like `2026년 1학기` and `2026-2`, and it searches in both Korean and English.

## Does it work with my school?

It works if your school's LMS runs on **Canvas**. Signs that it does: course URLs look like `https://<host>/courses/12345`, and you have an **Account → Settings** page. It does not support Moodle-based or in-house systems.

## Setup

### 1. Get an access token

Log in to your LMS in a browser and go to **Account → Settings → Approved Integrations → + New Access Token**. Copy the token. Some schools disable this button. If yours does, ask your school's LMS support.

### 2. Save your settings

```sh
mkdir -p ~/.config/eclass
cat > ~/.config/eclass/config <<'EOF'
CANVAS_BASE_URL=https://eclass.example.ac.kr
CANVAS_API_TOKEN=paste-your-token-here
EOF
chmod 600 ~/.config/eclass/config
```

Replace the URL with your school's LMS address. Environment variables with the same names override the file.

### 3. Install for your agent

Clone the repo once, then link it where your agent looks for skills:

```sh
git clone https://github.com/chaseungjoon/eclass-skill.git ~/eclass
```

| Agent | Install |
|---|---|
| **Claude Code** | `mkdir -p ~/.claude/skills && ln -s ~/eclass ~/.claude/skills/eclass` |
| **Codex CLI** | `mkdir -p ~/.agents/skills && ln -s ~/eclass ~/.agents/skills/eclass` |
| **Gemini CLI** | `mkdir -p ~/.gemini/skills && ln -s ~/eclass ~/.gemini/skills/eclass` |
| **Cursor** | Cursor also loads `~/.claude/skills` and `~/.codex/skills`, so the Claude Code link works. For one project, link to `<project>/.cursor/skills/eclass` instead. |
| **OpenClaw** | `cd ~ && openclaw skills install ./eclass` (add `--agent AGENT_ID` for a specific agent). Put both settings in `~/.openclaw/.env` and restart the Gateway. |
| **Other agents** | Add this to your `AGENTS.md`, rules file, or system prompt: *"For questions about my university courses, read `~/eclass/SKILL.md` and follow it."* The agent needs a shell tool. |

**Codex note:** the default sandbox blocks network access. Allow it in `~/.codex/config.toml`:

```toml
[sandbox_workspace_write]
network_access = true
```

### 4. Verify

```sh
python3 ~/eclass/scripts/eclass.py check
```

`{"authenticated": true, ...}` means it's working. Start a new agent session and ask *"이번 학기 수강 과목 알려줘"*.

## Commands

Your agent picks these for you. You can also run them yourself:

| Command | What it does |
|---|---|
| `courses [--search NAME] [--term all]` | List enrolled courses (current semester by default) |
| `planner --kind assignment --unsubmitted --days 14` | Upcoming work you haven't submitted |
| `assignments COURSE_ID [--unsubmitted]` | All assignments in a course and their submission status |
| `assignment COURSE_ID ASSIGNMENT_ID` | Instructions, your score, and feedback |
| `missing` | Work Canvas flags as missing |
| `announcements --days 30 [--search 기말 --body]` | Recent announcements |
| `announcement COURSE_ID TOPIC_ID` | Full text of one announcement |
| `calendar --days 30` | Course calendar events |
| `grades` | Canvas-calculated course scores |
| `syllabus` / `modules` / `files COURSE_ID` | Course content |

Add `--help` to any command for its options. See [references/usage.md](references/usage.md) for details and [references/setup.md](references/setup.md) for troubleshooting.

## Privacy

Your token gives access to your LMS account. Keep it in the config file or in environment variables. Never commit it or paste it into a chat. The script redacts the token from its output. Delete the token from the LMS settings page to revoke access.

## License

[MIT](LICENSE)
