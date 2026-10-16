# vault-ai

Ask questions about your Obsidian vault and get answers drawn from your own notes, with
`[[links]]` back to the notes they came from. It's a custom tool, not an Obsidian plugin:
it reads the `.md` files on disk, so Obsidian doesn't need to be open.

## How it works

```
 your vault (.md files)
        │  notes.py  — read files, frontmatter tags, #tags, [[links]], folder
        ▼
 chunks split at headings ("Thevenin Equivalents > Finding R_th")
        │  index.py  — SQLite FTS5 keyword index (BM25) + a vector per chunk from a
        │              local embedding model, all in one local file
        ▼
 search(question)  ──► keyword hits + meaning hits, merged ──► best excerpts
        │  assistant.py — Claude gets the excerpts plus two tools:
        │                 search_notes(query, folder) and read_note(path)
        ▼
 answer with [[Note]] citations
```

- **Indexing is local and incremental.** Only notes whose modification time changed are
  re-read, and it runs automatically before every command.
- **Search by meaning, not just words.** Each chunk also gets a vector from a small
  embedding model (`BAAI/bge-small-en-v1.5`, about 70 MB) that runs on your computer.
  "How much energy reaches the resistor" finds your *Maximum Power Transfer* note even
  though they share no words. Keyword and meaning results are merged with reciprocal
  rank fusion, so exact terms like course codes still win when they match.
- **Folders become filters.** `--folder College` or `--folder "Work/Meetings"` keeps answers
  inside one part of the vault.
- **Claude can search again.** Plain keyword search misses synonyms, so Claude runs its
  own follow-up searches with better keywords and opens whole notes when an excerpt is cut off.
- **Only the excerpts Claude reads are sent to the API.** The whole vault never is, and indexing and embedding run entirely on your computer.
  `read_note` refuses any path outside the vault.

## Setup

```bash
cd vault-ai
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...       # from console.anthropic.com
export VAULT_PATH=~/Documents/MyVault     # your Obsidian vault folder
```

## Use

```bash
python -m vault_ai index                         # first build (later runs are incremental)
python -m vault_ai stats                         # what's indexed, by top-level folder
python -m vault_ai search thevenin resistance    # search without asking Claude, free
python -m vault_ai ask "How do I find R_th with dependent sources?"
python -m vault_ai ask --folder Work "What do I owe for month-end close?"
python -m vault_ai chat --folder College         # follow-up questions; /new to reset
```

Answers appear as Claude writes them. The searches Claude runs are shown as `· search_notes(...)` lines, and a **Sources** list of the notes it cited follows each answer.

The first `index` with `fastembed` installed downloads the embedding model once and embeds
every note, which takes a minute or two for a large vault. After that only changed notes are
re-embedded. Use `--no-semantic` for keyword-only search, for example when you're offline
before the model has been downloaded (it otherwise spends about 40 seconds retrying).

`--effort low|medium|high|xhigh|max` trades speed and cost for thoroughness (default `medium`).

Try it without your own vault: `python -m vault_ai --vault sample_vault chat`.

The index lives at `<vault>/.vault-ai.sqlite`. Obsidian ignores it, but add it to your sync or
git ignore list if you sync the vault.

## Tests

```bash
pip install pytest && python -m pytest -q
```

## Roadmap

| Phase | What | Why |
|---|---|---|
| **1 (done)** | Read the vault, chunk by heading, keyword index, Claude Q&A with tools and citations, CLI | A working core |
| **2 (done)** | Stream answers as they're written; list the cited notes as sources after each answer | Faster feel on long answers |
| **3 (done)** | Search by meaning: local embeddings (`fastembed`) merged with the keyword ranking | Finds "energy reaching the resistor" when the note says "maximum power transfer" |
| 4 | Use the link graph: pull in notes that `[[link]]` to the top hits | Your vault's links are hand-made relevance signals |
| 5 | Study and work modes: "quiz me on EE 3714", "summarize this week's meetings", date filters from frontmatter | Built for exam prep and work recaps |
| 6 | Small web UI or an Obsidian command that calls this tool | Ask from inside Obsidian |

Suggested vault layout (the tool works with any layout):

```
College/<COURSE> - <Name>/...   e.g. College/EE 3714 - Circuits II/Lecture 05.md
Work/Meetings/, Work/Projects/, Work/Reference/
Inbox.md
```
