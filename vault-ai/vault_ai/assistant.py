"""Answer questions about the vault with Claude.

Flow for each question:
  1. Search the local index with the question and hand Claude the best excerpts.
  2. Give Claude two tools, `search_notes` and `read_note`, so it can run its
     own follow-up searches (better keywords, a specific class folder) or open
     a whole note when an excerpt is cut off.
  3. Claude answers from the notes and cites them as [[Note Title]] links,
     which you can click straight into in Obsidian.
"""

from __future__ import annotations

from pathlib import Path

import anthropic
from anthropic import beta_tool

from .index import Hit, VaultIndex

MODEL = "claude-opus-5-5"

SYSTEM_PROMPT = """\
You answer questions using the user's personal Obsidian vault: their notes from \
college classes (electrical engineering and accounting) and from their job, \
organized by folder.

Ground every answer in the notes. You start with excerpts found by a keyword \
search of the question. If they don't cover it well, call search_notes with \
different keywords, synonyms, or a folder filter, and call read_note when an \
excerpt is cut off or you need the rest of a note. A few searches are fine; \
stop when you have what you need.

Cite the notes you used inline as Obsidian links, e.g. [[Thevenin Equivalents]] \
or [[Thevenin Equivalents#Worked Example]] for a section. If the notes don't \
answer the question, say so plainly. You may add general knowledge to fill a \
gap, but label it as not from their notes. When notes disagree or look \
outdated, point that out rather than silently picking one."""


def format_hits(hits: list[Hit]) -> str:
    if not hits:
        return "No matching notes."
    return "\n\n".join(
        f'<excerpt note="{h.title}" folder="{h.folder}" path="{h.path}" section="{h.heading}">\n'
        f"{h.text}\n</excerpt>"
        for h in hits
    )


def echoable(content: list) -> list:
    """Make an assistant turn safe to send back after a mid-answer model fallback.

    When a fallback happens partway through, the API asks that thinking and
    tool-call blocks from before the switch be left out of later requests.
    """
    cut = max((i for i, b in enumerate(content) if b.type == "fallback"), default=-1)
    dropped = {"thinking", "redacted_thinking", "tool_use"}
    return [b for i, b in enumerate(content) if i > cut or b.type not in dropped]


class VaultAssistant:
    def __init__(self, vault: Path, index: VaultIndex, client: anthropic.Anthropic | None = None,
                 effort: str = "medium", folder: str | None = None):
        self.vault = vault.resolve()
        self.index = index
        self.client = client or anthropic.Anthropic()
        self.effort = effort
        self.folder = folder  # optional default scope, e.g. "College"
        self.history: list = []  # kept across questions so follow-ups work
        self.tools = self._make_tools()

    def _make_tools(self):
        index, vault, default_folder = self.index, self.vault, self.folder

        @beta_tool
        def search_notes(query: str, folder: str = "") -> str:
            """Keyword search over the user's notes. Returns the best-matching excerpts.

            Args:
                query: Keywords to look for, e.g. "thevenin norton equivalent". Plain words work best.
                folder: Optional folder to search within, e.g. "College", "Work", or "College/ACCT 3013 - Intermediate Accounting". Empty searches everything.
            """
            return format_hits(index.search(query, limit=8, folder=folder or default_folder))

        @beta_tool
        def read_note(path: str) -> str:
            """Read the full text of one note.

            Args:
                path: The note's path relative to the vault, exactly as shown in an excerpt's path attribute.
            """
            target = (vault / path).resolve()
            # Only ever read Markdown files that are inside the vault.
            if not target.is_relative_to(vault) or target.suffix != ".md" or not target.is_file():
                return f"No note found at {path!r}."
            return target.read_text(encoding="utf-8", errors="replace")

        return [search_notes, read_note]

    def ask(self, question: str, on_tool_call=None) -> str:
        hits = self.index.search(question, limit=8, folder=self.folder)
        self.history.append({
            "role": "user",
            "content": f"<search_results>\n{format_hits(hits)}\n</search_results>\n\n{question}",
        })

        runner = self.client.beta.messages.tool_runner(
            model=MODEL,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            tools=self.tools,
            messages=self.history,
            thinking={"type": "adaptive"},
            output_config={"effort": self.effort},
            cache_control={"type": "ephemeral"},  # re-sent history is billed at the cache rate
            # If a safety classifier declines, let the API retry on its recommended model.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            max_iterations=10,
        )

        final = None
        for message in runner:
            final = message
            # Mirror the conversation so the next question has full context.
            self.history.append({"role": "assistant", "content": echoable(message.content)})
            if on_tool_call:
                for block in message.content:
                    if block.type == "tool_use":
                        on_tool_call(block.name, block.input)
            tool_response = runner.generate_tool_call_response()
            if tool_response is not None:
                self.history.append(tool_response)

        if final is None:
            return "(no response)"
        if final.stop_reason == "refusal":
            return "Claude declined to answer this one."
        text = "".join(b.text for b in final.content if b.type == "text")
        if final.stop_reason == "max_tokens":
            text += "\n\n[answer cut off: hit the max_tokens limit]"
        return text

    def reset(self):
        self.history.clear()
