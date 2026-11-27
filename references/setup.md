# Setup reference

The helper needs Python 3.10 or newer, a shell execution tool, and HTTPS access to the school's LMS. It uses only Python's standard library.

## Settings

| Variable | Value |
|---|---|
| `CANVAS_BASE_URL` | The school's Canvas address, such as `https://eclass.example.ac.kr`. A bare host name is accepted. |
| `CANVAS_API_TOKEN` | A personal access token from the LMS: **Account → Settings → Approved Integrations → + New Access Token**. |

The helper reads environment variables first, then `KEY=VALUE` lines in `~/.config/eclass/config` (or `$XDG_CONFIG_HOME/eclass/config`, or the path in `ECLASS_CONFIG`). The config file is the simplest option for agents that filter environment variables, such as Codex, which strips names containing `TOKEN` by default. Keep the file private (`chmod 600`).

## Sandboxes and remote runners

If the agent runs commands in a sandbox, a container, or on a separate node, that runner needs Python, outbound HTTPS to the LMS host, and access to the settings. Codex's default sandbox blocks network access, so allow network access for the session or approve the command when asked. In OpenClaw Docker sandboxes, pass the variables through your deployment's secret handling ([sandboxed skill configuration](https://docs.openclaw.ai/tools/skills-config#sandboxed-skills-and-env-vars)).

## Verify

Run `python3 scripts/eclass.py check`. It confirms authentication without printing profile details. Then ask the agent "이번 학기 e클래스 과목이 뭐야?" or "List my courses this semester."

| Error | Fix |
|---|---|
| `CANVAS_BASE_URL is not set` / `CANVAS_API_TOKEN is not set` | The runner can't see the settings. Use the config file or export them in the agent's environment. |
| `HTTP 401` on `check` | The token is wrong, expired, or for a different school. |
| `Could not reach …` | The runner has no network access or the host is wrong. |
| `HTTP 401` on `files` only | The school restricts the Files API. Open the course in a browser instead. |
