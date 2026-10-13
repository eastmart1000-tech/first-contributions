"""Command line entry point: `python -m vault_ai <command>`."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .index import VaultIndex

DEFAULT_DB = ".vault-ai.sqlite"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="vault-ai", description="Search and ask questions about your Obsidian vault.")
    parser.add_argument("--vault", default=os.environ.get("VAULT_PATH"),
                        help="path to your Obsidian vault (or set VAULT_PATH)")
    parser.add_argument("--db", help=f"index file (default: <vault>/{DEFAULT_DB})")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("index", help="build or refresh the search index")
    sub.add_parser("stats", help="show what is indexed")

    p_search = sub.add_parser("search", help="keyword search, no AI")
    p_search.add_argument("query", nargs="+")
    p_search.add_argument("--folder", help='limit to a folder, e.g. "College"')
    p_search.add_argument("-n", type=int, default=8, help="number of results")

    for name, help_text in [("ask", "ask one question"), ("chat", "ask follow-up questions in a session")]:
        p = sub.add_parser(name, help=help_text)
        if name == "ask":
            p.add_argument("question", nargs="+")
        p.add_argument("--folder", help='only use notes in this folder, e.g. "Work"')
        p.add_argument("--effort", default="medium", choices=["low", "medium", "high", "xhigh", "max"],
                       help="how hard Claude thinks (higher = slower, more thorough, more tokens)")

    args = parser.parse_args(argv)
    if not args.vault:
        parser.error("pass --vault or set VAULT_PATH")
    vault = Path(args.vault).expanduser()
    if not vault.is_dir():
        parser.error(f"vault folder not found: {vault}")

    index = VaultIndex(Path(args.db) if args.db else vault / DEFAULT_DB)
    try:
        # Keep the index fresh automatically; only changed notes are re-read.
        stats = index.build(vault)
        if args.command == "index":
            print(f"Indexed: {stats.added} new, {stats.updated} updated, "
                  f"{stats.removed} removed, {stats.unchanged} unchanged.")
        elif args.command == "stats":
            s = index.stats()
            print(f"{s['notes']} notes, {s['chunks']} chunks")
            for folder, n in s["folders"].items():
                print(f"  {folder}: {n}")
        elif args.command == "search":
            for i, h in enumerate(index.search(" ".join(args.query), limit=args.n, folder=args.folder), 1):
                preview = " ".join(h.text.split())[:160]
                print(f"{i}. {h.heading}  ({h.path})\n   {preview}\n")
        else:
            return run_assistant(args, vault, index)
    finally:
        index.close()
    return 0


def run_assistant(args, vault: Path, index: VaultIndex) -> int:
    import anthropic

    from .assistant import VaultAssistant

    try:
        assistant = VaultAssistant(vault, index, effort=args.effort, folder=args.folder)
    except anthropic.AnthropicError as e:  # usually: no API key configured
        print(f"Could not start the Claude client: {e}", file=sys.stderr)
        return 1

    def show_tool(name, inp):
        print(f"  · {name}({', '.join(f'{k}={v!r}' for k, v in inp.items() if v)})", file=sys.stderr)

    streamed = []

    def show_text(chunk: str):
        streamed.append(chunk)
        print(chunk, end="", flush=True)

    def answer(question: str):
        streamed.clear()
        try:
            print()
            result = assistant.ask(question, on_tool_call=show_tool, on_text=show_text)
            if not streamed:  # nothing came through the stream, e.g. a declined request
                print(result.text, end="")
            print()
            if result.note:
                print(result.note, file=sys.stderr)
            if result.sources:
                print("\nSources:")
                for path in result.sources:
                    print(f"  - {path}")
            print()
        except TypeError as e:
            if "authentication" not in str(e):
                raise
            # The SDK raises this when it finds no credentials at all.
            print("No Anthropic credentials found. Set ANTHROPIC_API_KEY "
                  "(get a key at console.anthropic.com).", file=sys.stderr)
            raise SystemExit(1)
        except anthropic.AuthenticationError:
            print("Authentication failed: check ANTHROPIC_API_KEY.", file=sys.stderr)
        except anthropic.RateLimitError:
            print("Rate limited by the API; wait a moment and try again.", file=sys.stderr)
        except anthropic.APIStatusError as e:
            print(f"API error {e.status_code}: {e.message}", file=sys.stderr)
        except anthropic.APIConnectionError:
            print("Could not reach the API; check your connection.", file=sys.stderr)

    if args.command == "ask":
        answer(" ".join(args.question))
        return 0

    print("Ask about your notes. Commands: /new (start over), /quit")
    while True:
        try:
            q = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if q in {"/quit", "/exit"}:
            return 0
        if q == "/new":
            assistant.reset()
            print("Started a new conversation.")
        elif q:
            answer(q)


if __name__ == "__main__":
    sys.exit(main())
