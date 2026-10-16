"""Read an Obsidian vault from disk and split each note into searchable chunks."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

# Folders Obsidian and common tools create that never hold real notes.
SKIP_DIRS = {".obsidian", ".trash", ".git", "node_modules"}

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$", re.MULTILINE)
TAG_RE = re.compile(r"(?<![\w/])#([A-Za-z][\w/-]*)")
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
CODE_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)


@dataclass
class Note:
    path: str  # relative to the vault root, with forward slashes
    title: str
    folder: str  # e.g. "College/EE 3714 - Circuits II"; "" for the vault root
    body: str
    tags: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)
    mtime: float = 0.0


@dataclass
class Chunk:
    note_path: str
    heading: str  # "Title > Section > Subsection", so search hits show context
    text: str
    position: int  # order of the chunk inside its note


def iter_markdown_files(vault: Path):
    """Yield every .md file in the vault, skipping hidden and tool folders."""
    for root, dirs, files in os.walk(vault):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))
        for name in sorted(files):
            if name.endswith(".md"):
                yield Path(root) / name


def parse_frontmatter_tags(frontmatter: str) -> list[str]:
    """Pull `tags:` out of YAML frontmatter without a YAML dependency.

    Handles the two forms Obsidian writes: `tags: [a, b]` and a `- item` list.
    """
    tags: list[str] = []
    lines = frontmatter.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^tags?:\s*(.*)$", line.strip())
        if not m:
            continue
        inline = m.group(1).strip()
        if inline:
            tags += [t.strip(" '\"#") for t in inline.strip("[]").split(",")]
        else:
            for item in lines[i + 1 :]:
                im = re.match(r"^\s*-\s*(.+)$", item)
                if not im:
                    break
                tags.append(im.group(1).strip(" '\"#"))
    return [t for t in tags if t]


def load_note(vault: Path, file: Path) -> Note:
    raw = file.read_text(encoding="utf-8", errors="replace")
    tags: list[str] = []
    body = raw
    fm = FRONTMATTER_RE.match(raw)
    if fm:
        tags += parse_frontmatter_tags(fm.group(1))
        body = raw[fm.end() :]

    prose = CODE_FENCE_RE.sub("", body)
    tags += TAG_RE.findall(prose)
    rel = file.relative_to(vault).as_posix()
    folder = rel.rsplit("/", 1)[0] if "/" in rel else ""
    return Note(
        path=rel,
        title=file.stem,
        folder=folder,
        body=body,
        tags=sorted(set(tags)),
        links=sorted(set(l.strip() for l in WIKILINK_RE.findall(body))),
        mtime=file.stat().st_mtime,
    )


def chunk_note(note: Note, max_chars: int = 1500) -> list[Chunk]:
    """Split a note at its headings, then split long sections by paragraph.

    Each chunk remembers its heading path so an answer can point to
    "Lecture 5 > Thevenin Equivalents" instead of just the file.
    """
    sections: list[tuple[str, str]] = []
    stack: list[str] = []
    last = 0
    current = note.title
    for m in HEADING_RE.finditer(note.body):
        sections.append((current, note.body[last : m.start()]))
        level = len(m.group(1))
        stack = stack[: level - 1] + [m.group(2).strip()]
        # Most notes open with "# <file name>"; don't repeat it in the path.
        path = stack[1:] if stack and stack[0].lower() == note.title.lower() else stack
        current = " > ".join([note.title, *path])
        last = m.end()
    sections.append((current, note.body[last:]))

    chunks: list[Chunk] = []
    for heading, text in sections:
        for piece in _split_long(text.strip(), max_chars):
            chunks.append(Chunk(note.path, heading, piece, len(chunks)))
    if not chunks:  # a note with only a title still deserves to be findable
        chunks.append(Chunk(note.path, note.title, "", 0))
    return chunks


def _split_long(text: str, max_chars: int) -> list[str]:
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]
    pieces, buf = [], ""
    for para in re.split(r"\n\s*\n", text):
        if buf and len(buf) + len(para) + 2 > max_chars:
            pieces.append(buf)
            buf = ""
        while len(para) > max_chars:  # one giant paragraph: hard-split it
            pieces.append(para[:max_chars])
            para = para[max_chars:]
        buf = f"{buf}\n\n{para}" if buf else para
    if buf:
        pieces.append(buf)
    return pieces
