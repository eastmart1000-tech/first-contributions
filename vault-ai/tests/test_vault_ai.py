import shutil
from pathlib import Path

import pytest

from vault_ai.assistant import VaultAssistant
from vault_ai.index import VaultIndex, to_fts_query
from vault_ai.notes import Note, chunk_note, load_note

SAMPLE = Path(__file__).resolve().parent.parent / "sample_vault"


@pytest.fixture
def vault(tmp_path):
    dest = tmp_path / "vault"
    shutil.copytree(SAMPLE, dest)
    (dest / ".obsidian").mkdir()
    (dest / ".obsidian" / "ignored.md").write_text("# should not be indexed")
    return dest


@pytest.fixture
def index(vault, tmp_path):
    idx = VaultIndex(tmp_path / "index.sqlite")
    idx.build(vault)
    yield idx
    idx.close()


def test_load_note_reads_tags_links_and_folder(vault):
    note = load_note(vault, vault / "College/EE 3714 - Circuits II/Maximum Power Transfer.md")
    assert note.folder == "College/EE 3714 - Circuits II"
    assert note.tags == ["ee3714", "exam2"]
    assert note.links == ["Thevenin Equivalents"]

    acct = load_note(vault, vault / "College/ACCT 3013 - Intermediate Accounting/Revenue Recognition.md")
    assert acct.tags == ["acct3013", "asc606"]
    assert not acct.body.startswith("---")


def test_chunks_follow_headings():
    note = Note(path="a.md", title="A", folder="", body="intro\n# Top\none\n## Sub\ntwo\n# Other\nthree")
    assert [c.heading for c in chunk_note(note)] == ["A", "A > Top", "A > Top > Sub", "A > Other"]


def test_long_sections_are_split():
    body = "\n\n".join("word " * 100 for _ in range(10))
    chunks = chunk_note(Note(path="a.md", title="A", folder="", body=body), max_chars=1200)
    assert len(chunks) > 1 and all(len(c.text) <= 1200 for c in chunks)


def test_fts_query_drops_stopwords_and_quotes_terms():
    assert to_fts_query("What is the Thevenin resistance?") == '"thevenin" OR "resistance"'
    assert to_fts_query("what is it") == ""


def test_search_ranks_relevant_section(index):
    hits = index.search("how do I find thevenin resistance with dependent sources")
    assert hits[0].heading == "Thevenin Equivalents > Finding R_th"


def test_search_folder_filter(index):
    assert {h.folder for h in index.search("revenue", folder="Work")} == {"Work/Meetings"}
    assert all(h.folder.startswith("College") for h in index.search("revenue", folder="College"))


def test_hidden_folders_skipped(index):
    assert index.stats()["notes"] == 5


def test_reindex_picks_up_changes(vault, index):
    note = vault / "Inbox.md"
    note.write_text("# Inbox\nflux capacitor")
    import os
    os.utime(note, (1, 1))
    (vault / "Work/Meetings/2026-10-02 Team Sync.md").unlink()
    stats = index.build(vault)
    assert (stats.updated, stats.removed, stats.unchanged) == (1, 1, 3)
    assert index.search("flux capacitor")[0].path == "Inbox.md"
    assert index.search("accruals") == []


def test_read_note_tool_stays_inside_vault(vault, index, tmp_path):
    (tmp_path / "secret.md").write_text("outside")
    assistant = VaultAssistant(vault, index, client=object())
    read_note = next(t for t in assistant.tools if t.name == "read_note")
    assert "Five steps" in read_note.call({"path": "College/ACCT 3013 - Intermediate Accounting/Revenue Recognition.md"})
    assert read_note.call({"path": "../secret.md"}).startswith("No note found")
