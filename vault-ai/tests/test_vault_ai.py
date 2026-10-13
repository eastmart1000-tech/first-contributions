import json
import shutil
from pathlib import Path

import anthropic
import httpx2
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


def test_resolve_links(index):
    assert index.resolve_links(["Thevenin Equivalents", "thevenin equivalents", "Nope", "Work/Meetings/2026-10-02 Team Sync"]) == [
        "College/EE 3714 - Circuits II/Thevenin Equivalents.md",
        "Work/Meetings/2026-10-02 Team Sync.md",
    ]


def _sse(message_id, content, stop_reason):
    """Encode one model turn as the server-sent events the streaming API returns."""
    events = [("message_start", {"type": "message_start", "message": {
        "id": message_id, "type": "message", "role": "assistant", "model": "claude-opus-5-5", "content": [],
        "stop_reason": None, "stop_sequence": None, "usage": {"input_tokens": 1, "output_tokens": 0}}})]
    for i, block in enumerate(content):
        if block["type"] == "text":
            events.append(("content_block_start", {"type": "content_block_start", "index": i, "content_block": {"type": "text", "text": ""}}))
            for word in block["text"].split(" "):
                events.append(("content_block_delta", {"type": "content_block_delta", "index": i,
                                                       "delta": {"type": "text_delta", "text": word + " "}}))
        else:
            events.append(("content_block_start", {"type": "content_block_start", "index": i, "content_block": {**block, "input": {}}}))
            events.append(("content_block_delta", {"type": "content_block_delta", "index": i,
                                                   "delta": {"type": "input_json_delta", "partial_json": json.dumps(block["input"])}}))
        events.append(("content_block_stop", {"type": "content_block_stop", "index": i}))
    events.append(("message_delta", {"type": "message_delta", "delta": {"stop_reason": stop_reason, "stop_sequence": None},
                                     "usage": {"output_tokens": 5}}))
    events.append(("message_stop", {"type": "message_stop"}))
    return "".join(f"event: {name}\ndata: {json.dumps(data)}\n\n" for name, data in events)


def fake_client(turns):
    """An Anthropic client whose API replies with the given (content, stop_reason) turns in order."""
    requests = []

    def handler(request):
        requests.append(json.loads(request.content))
        content, stop = turns[len(requests) - 1]
        return httpx2.Response(200, headers={"content-type": "text/event-stream"},
                               content=_sse(f"msg_{len(requests)}", content, stop).encode())

    client = anthropic.Anthropic(api_key="test", http_client=anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(handler)))
    return client, requests


def test_ask_streams_runs_tools_and_lists_sources(vault, index):
    client, requests = fake_client([
        ([{"type": "tool_use", "id": "t1", "name": "search_notes", "input": {"query": "norton", "folder": "College"}}], "tool_use"),
        ([{"type": "text", "text": "Use [[Thevenin Equivalents#Finding R_th]] and [[Maximum Power Transfer|max power]]."}], "end_turn"),
    ])
    assistant = VaultAssistant(vault, index, client=client)
    tools, chunks = [], []
    answer = assistant.ask("Is Norton related to Thevenin?", on_tool_call=lambda n, i: tools.append((n, i)), on_text=chunks.append)

    assert tools == [("search_notes", {"query": "norton", "folder": "College"})]
    assert len(chunks) > 1 and "".join(chunks) == answer.text
    assert answer.sources == ["College/EE 3714 - Circuits II/Thevenin Equivalents.md",
                              "College/EE 3714 - Circuits II/Maximum Power Transfer.md"]
    assert requests[0]["stream"] is True and requests[0]["fallbacks"] == "default"
    assert "<excerpt" in json.dumps(requests[1]["messages"][-1])  # tool result sent back
    assert [m["role"] for m in assistant.history] == ["user", "assistant", "user", "assistant"]


def test_ask_refusal_does_not_run_tools(vault, index):
    client, requests = fake_client([([], "refusal")])
    assistant = VaultAssistant(vault, index, client=client)
    answer = assistant.ask("anything")
    assert answer.text.startswith("Claude declined") and len(requests) == 1
