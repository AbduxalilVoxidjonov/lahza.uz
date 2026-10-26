"""Claude montaj (docs/15-claude-montaj.md): foydalanuvchi kompyuteridagi Claude bilan ulanish.

* Funksiya standart holatda O'CHIQ (`library.db` -> `settings`, kalit `claude_montage`).
* `detect` - Claude Code CLI va Claude Desktop'ni topish (tarmoqsiz, qisqa kesh).
* `connect` - Lahza MCP serverini (`lahza-engine mcp`) Claude Code/Desktop'ga ro'yxatdan o'tkazish.
* `planner` - `claude -p` headless (tool'larsiz) orqali `lahza.edit-plan/1` reja tuzish.

Claude'ga faqat chegaralangan timeline tavsifi va transkript matni boradi; video, audio va
fayl yo'llari yuborilmaydi (`editing_agent.planner.compact_context`).
"""

from __future__ import annotations


class ClaudeError(RuntimeError):
    """Kodli xato; API `detail` = `"kod: xabar"` (routes_license uslubi)."""

    STATUS = {"claude_disabled": 409, "claude_busy": 409, "claude_config_invalid": 409,
              "claude_not_installed": 503, "claude_not_logged_in": 503, "claude_error": 502,
              "claude_timeout": 504, "claude_cancelled": 409, "claude_bad_plan": 422}

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code

    @property
    def http_status(self) -> int:
        return self.STATUS.get(self.code, 500)

    @property
    def detail(self) -> str:
        return f"{self.code}: {self}"
