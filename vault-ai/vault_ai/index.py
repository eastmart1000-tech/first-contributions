"""A local search index over the vault, stored in one SQLite file.

Two kinds of search, combined:
- Keyword: SQLite's built-in FTS5 full-text engine with BM25 ranking.
- Meaning (optional): each chunk also gets a vector from a local embedding
  model, so "power delivered to the load" finds "Maximum Power Transfer".
The two rankings are merged with reciprocal rank fusion. Nothing leaves your
machine during indexing, and re-indexing only re-reads notes whose
modification time changed.
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
CREATE TABLE IF NOT EXISTS vectors (
    chunk_id  INTEGER PRIMARY KEY,  -- rowid in chunks
    note_path TEXT NOT NULL,
    vec       BLOB NOT NULL         -- float32, length 1
);
CREATE INDEX IF NOT EXISTS vectors_by_note ON vectors(note_path);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""

# Reciprocal rank fusion constant; 60 is the value from the original paper and
# keeps one list's top hit from drowning out the other list.
RRF_K = 60

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
    chunk_id: int = 0


@dataclass
class IndexStats:
    added: int = 0
    updated: int = 0
    removed: int = 0
    unchanged: int = 0
    embedded: int = 0  # chunks that got a new vector this run


class VaultIndex:
    def __init__(self, db_path: Path, embedder=None):
        """`embedder` (see embeddings.py) turns on search by meaning; without
        one the index is keyword-only."""
        self.db = sqlite3.connect(db_path)
        self.db.executescript(SCHEMA)
        self.embedder = embedder
        self._matrix = None  # (chunk ids, vectors) loaded on first semantic search

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
        if self.embedder:
            stats.embedded = self._embed_missing()
        return stats

    def _embed_missing(self, batch_size: int = 64) -> int:
        """Give every chunk that lacks a vector one. A different model than the
        one that built the index means re-embedding everything."""
        model = self.db.execute("SELECT value FROM meta WHERE key = 'embedding_model'").fetchone()
        with self.db:
            if not model or model[0] != self.embedder.name:
                self.db.execute("DELETE FROM vectors")
                self.db.execute("INSERT OR REPLACE INTO meta VALUES ('embedding_model', ?)", (self.embedder.name,))
        todo = self.db.execute(
            "SELECT rowid, note_path, heading, text FROM chunks "
            "WHERE rowid NOT IN (SELECT chunk_id FROM vectors) ORDER BY rowid"
        ).fetchall()
        for i in range(0, len(todo), batch_size):
            batch = todo[i : i + batch_size]
            vecs = self.embedder.embed_documents([f"{heading}\n{text}" for _, _, heading, text in batch])
            with self.db:  # commit per batch so an interrupted first run keeps its progress
                self.db.executemany(
                    "INSERT INTO vectors VALUES (?, ?, ?)",
                    [(cid, path, vec.astype("float32").tobytes()) for (cid, path, _, _), vec in zip(batch, vecs)],
                )
        if todo:
            self._matrix = None
        return len(todo)

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
        self.db.execute("DELETE FROM vectors WHERE note_path = ?", (rel,))
        self._matrix = None

    def search(self, query: str, limit: int = 8, folder: str | None = None) -> list[Hit]:
        """Find the chunks that best match `query`, by keyword and (when an
        embedder is set) by meaning. `folder` limits results to one part of the
        vault, e.g. "College" or "Work/Meetings"."""
        pool = max(limit * 4, 30)  # look deeper in each list before merging
        keyword = self.keyword_search(query, pool, folder)
        if not self.embedder:
            return keyword[:limit]
        return fuse([keyword, self.semantic_search(query, pool, folder)], limit)

    def keyword_search(self, query: str, limit: int = 8, folder: str | None = None) -> list[Hit]:
        match = to_fts_query(query)
        if not match:
            return []
        sql = """
            SELECT c.note_path, n.title, n.folder, c.heading, c.text,
                   bm25(chunks, 0, 5.0, 3.0, 2.0, 1.0) AS score, c.rowid
            FROM chunks c JOIN notes n ON n.path = c.note_path
            WHERE chunks MATCH ?
        """
        params: list = [match]
        clause, folder_params = _folder_filter(folder)
        sql += clause + " ORDER BY score LIMIT ?"
        params += folder_params + [limit]
        return [Hit(*row) for row in self.db.execute(sql, params)]

    def semantic_search(self, query: str, limit: int = 8, folder: str | None = None) -> list[Hit]:
        import numpy as np

        if self._matrix is None:
            rows = self.db.execute("SELECT chunk_id, vec FROM vectors ORDER BY chunk_id").fetchall()
            if not rows:
                return []
            ids = np.array([r[0] for r in rows])
            self._matrix = (ids, np.vstack([np.frombuffer(r[1], dtype=np.float32) for r in rows]))
        ids, vectors = self._matrix
        sims = vectors @ self.embedder.embed_query(query)
        if folder:  # rank only chunks inside the folder, however small it is
            clause, folder_params = _folder_filter(folder)
            allowed = [r[0] for r in self.db.execute(
                "SELECT c.rowid FROM chunks c JOIN notes n ON n.path = c.note_path WHERE 1" + clause, folder_params)]
            sims = np.where(np.isin(ids, allowed), sims, -np.inf)
        top = [i for i in np.argsort(-sims)[:limit] if np.isfinite(sims[i])]
        if not top:
            return []
        order = {int(ids[i]): float(sims[i]) for i in top}
        rows = self.db.execute(
            f"""SELECT c.note_path, n.title, n.folder, c.heading, c.text, 0, c.rowid
                FROM chunks c JOIN notes n ON n.path = c.note_path
                WHERE c.rowid IN ({",".join("?" * len(order))})""",
            list(order),
        ).fetchall()
        hits = [Hit(*row[:5], order[row[6]], row[6]) for row in rows]
        return sorted(hits, key=lambda h: -h.score)

    def resolve_links(self, links: list[str]) -> list[str]:
        """Map [[link]] targets to note paths, the way Obsidian does: by file
        name, or by path when the link includes folders. Unknown links are dropped."""
        paths = []
        for link in dict.fromkeys(l.strip() for l in links):
            row = self.db.execute(
                "SELECT path FROM notes WHERE lower(title) = lower(?) OR lower(path) = lower(?) "
                "ORDER BY path LIMIT 1",
                (link.rsplit("/", 1)[-1].removesuffix(".md"), link if link.endswith(".md") else link + ".md"),
            ).fetchone()
            if row and row[0] not in paths:
                paths.append(row[0])
        return paths

    def stats(self) -> dict:
        notes = self.db.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
        chunks = self.db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        top = self.db.execute(
            """SELECT CASE WHEN instr(folder, '/') > 0
                           THEN substr(folder, 1, instr(folder, '/') - 1)
                           ELSE folder END AS top, COUNT(*)
               FROM notes GROUP BY top ORDER BY top"""
        ).fetchall()
        vectors = self.db.execute("SELECT COUNT(*) FROM vectors").fetchone()[0]
        model = self.db.execute("SELECT value FROM meta WHERE key = 'embedding_model'").fetchone()
        return {"notes": notes, "chunks": chunks, "vectors": vectors,
                "embedding_model": model[0] if model else None,
                "folders": {t or "(root)": n for t, n in top}}


def fuse(rankings: list[list[Hit]], limit: int) -> list[Hit]:
    """Reciprocal rank fusion: a chunk's score is the sum of 1/(K + rank) over
    the lists it appears in, so chunks both searches like rise to the top."""
    scores: dict[int, float] = {}
    hits: dict[int, Hit] = {}
    for ranking in rankings:
        for rank, hit in enumerate(ranking):
            scores[hit.chunk_id] = scores.get(hit.chunk_id, 0.0) + 1.0 / (RRF_K + rank + 1)
            hits.setdefault(hit.chunk_id, hit)
    best = sorted(scores, key=lambda cid: -scores[cid])[:limit]
    return [Hit(**{**hits[cid].__dict__, "score": scores[cid]}) for cid in best]


def to_fts_query(text: str) -> str:
    """Turn a natural-language question into an FTS5 OR-query of its keywords.

    Quoting every term keeps user punctuation from being read as FTS syntax.
    """
    words = re.findall(r"[\w']+", text.lower())
    terms = [w.strip("'") for w in words if w not in STOPWORDS and len(w.strip("'")) > 1]
    return " OR ".join(f'"{t}"' for t in dict.fromkeys(terms))


def _folder_filter(folder: str | None) -> tuple[str, list]:
    if not folder:
        return "", []
    folder = folder.strip("/")
    return " AND (n.folder = ? OR n.folder LIKE ? ESCAPE '\\')", [folder, _like_escape(folder) + "/%"]


def _like_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
