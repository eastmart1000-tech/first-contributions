"""A local search index over the vault, stored in one SQLite file.

Uses SQLite's built-in FTS5 full-text engine with BM25 ranking, so there is
nothing extra to install and nothing leaves your machine during indexing.
Re-indexing only re-reads notes whose modification time changed.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .notes import chunk_note, iter_markdown_files, load_note

SCHEMA = """
CREATE TABLE IF NOT EXISTS notes (
    path   TEXT PRIMARY KEY,
    title  TEXT NOT NULL,
    folder TEXT NOT NULL,
    tags   TEXT NOT NULL,
    links  TEXT NOT NULL,
    mtime  REAL NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks USING fts5(
    note_path UNINDEXED,
    title,
    heading,
    tags,
    text,
    position UNINDEXED,
    tokenize = 'porter unicode61'
);
"""

# Common words that only add noise to a keyword search.
STOPWORDS = set(
    """a an and are as at be by can did do does for from how i in is it me my of
    on or so that the this to was what when where which who why will with you
    your about explain tell show give find notes note""".split()
)


@dataclass
class Hit:
    path: str
    title: str
    folder: str
    heading: str
    text: str
    score: float


@dataclass
class IndexStats:
    added: int = 0
    updated: int = 0
    removed: int = 0
    unchanged: int = 0


class VaultIndex:
    def __init__(self, db_path: Path):
        self.db = sqlite3.connect(db_path)
        self.db.executescript(SCHEMA)

    def close(self):
        self.db.close()

    def build(self, vault: Path) -> IndexStats:
        """Bring the index in sync with the vault on disk."""
        stats = IndexStats()
        known = dict(self.db.execute("SELECT path, mtime FROM notes"))
        seen = set()
        with self.db:
            for file in iter_markdown_files(vault):
                rel = file.relative_to(vault).as_posix()
                seen.add(rel)
                mtime = file.stat().st_mtime
                if known.get(rel) == mtime:
                    stats.unchanged += 1
                    continue
                if rel in known:
                    stats.updated += 1
                    self._delete(rel)
                else:
                    stats.added += 1
                self._insert(load_note(vault, file))
            for rel in known.keys() - seen:
                self._delete(rel)
                stats.removed += 1
        return stats

    def _insert(self, note):
        tags = " ".join(note.tags)
        self.db.execute(
            "INSERT INTO notes VALUES (?, ?, ?, ?, ?, ?)",
            (note.path, note.title, note.folder, tags, "\n".join(note.links), note.mtime),
        )
        self.db.executemany(
            "INSERT INTO chunks VALUES (?, ?, ?, ?, ?, ?)",
            [(c.note_path, note.title, c.heading, tags, c.text, c.position) for c in chunk_note(note)],
        )

    def _delete(self, rel: str):
        self.db.execute("DELETE FROM notes WHERE path = ?", (rel,))
        self.db.execute("DELETE FROM chunks WHERE note_path = ?", (rel,))

    def search(self, query: str, limit: int = 8, folder: str | None = None) -> list[Hit]:
        """Keyword search. `folder` limits results to one part of the vault,
        e.g. "College" or "Work/Meetings"."""
        match = to_fts_query(query)
        if not match:
            return []
        sql = """
            SELECT c.note_path, n.title, n.folder, c.heading, c.text,
                   bm25(chunks, 0, 5.0, 3.0, 2.0, 1.0) AS score
            FROM chunks c JOIN notes n ON n.path = c.note_path
            WHERE chunks MATCH ?
        """
        params: list = [match]
        if folder:
            folder = folder.strip("/")
            sql += " AND (n.folder = ? OR n.folder LIKE ? ESCAPE '\\')"
            params += [folder, _like_escape(folder) + "/%"]
        sql += " ORDER BY score LIMIT ?"
        params.append(limit)
        return [Hit(*row) for row in self.db.execute(sql, params)]

    def stats(self) -> dict:
        notes = self.db.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
        chunks = self.db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        top = self.db.execute(
            """SELECT CASE WHEN instr(folder, '/') > 0
                           THEN substr(folder, 1, instr(folder, '/') - 1)
                           ELSE folder END AS top, COUNT(*)
               FROM notes GROUP BY top ORDER BY top"""
        ).fetchall()
        return {"notes": notes, "chunks": chunks, "folders": {t or "(root)": n for t, n in top}}


def to_fts_query(text: str) -> str:
    """Turn a natural-language question into an FTS5 OR-query of its keywords.

    Quoting every term keeps user punctuation from being read as FTS syntax.
    """
    words = re.findall(r"[\w']+", text.lower())
    terms = [w.strip("'") for w in words if w not in STOPWORDS and len(w.strip("'")) > 1]
    return " OR ".join(f'"{t}"' for t in dict.fromkeys(terms))


def _like_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
