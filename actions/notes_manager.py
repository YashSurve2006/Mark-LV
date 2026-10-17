"""
notes_manager.py — Voice Knowledge Base & Daily Journaling Engine for JARVIS Mark-LV
=====================================================================================

Provides an autonomous personal knowledge base, voice quick notes, and daily work
journal directly through JARVIS voice commands. Stores notes as clean, portable
markdown files with YAML frontmatter in `memory/notes/`, compatible with Obsidian,
VS Code, Antigravity, and standard markdown tools.

Capabilities:
1.  add_note      — Save a new note with title, content, tags, and category.
2.  daily_log     — Append timestamped voice logs to today's work journal.
3.  append_note   — Append text or action items to an existing note.
4.  list_notes    — View saved notes with dates, tags, and word counts.
5.  get_note      — Read back the full content of any note by title or keyword.
6.  search_notes  — Fast full-text search across all notes, tags, and headers.
7.  delete_note   — Remove an outdated note.
"""

from __future__ import annotations

import datetime
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Optional


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


_NOTES_DIR = _base_dir() / "memory" / "notes"


def _ensure_dir() -> Path:
    _NOTES_DIR.mkdir(parents=True, exist_ok=True)
    return _NOTES_DIR


def _log(player: Any, msg: str) -> None:
    short = str(msg)[:80]
    try:
        print(f"[NotesManager] {short}")
    except UnicodeEncodeError:
        try:
            print(f"[NotesManager] {short.encode('ascii', errors='replace').decode('ascii')}")
        except Exception:
            pass
    if player:
        try:
            if hasattr(player, "write_log"):
                player.write_log(f"[notes] {short[:60]}")
            elif hasattr(player, "log"):
                player.log(short[:60])
        except Exception:
            pass


def _slugify(text: str) -> str:
    s = text.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_-]+", "_", s)
    return s[:40] or "note"


# ══════════════════════════════════════════════════════════════════════════════
# §1  NOTE OPERATIONS
# ══════════════════════════════════════════════════════════════════════════════

def _add_note(title: str, content: str, tags: str = "", category: str = "general") -> str:
    """Create a new markdown note with metadata."""
    _ensure_dir()
    now = datetime.datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")

    t = (title or "Untitled Note").strip()
    slug = _slugify(t)
    filename = f"{date_str}_{slug}.md"
    filepath = _NOTES_DIR / filename

    # Avoid overwriting existing note with identical slug
    counter = 1
    while filepath.exists():
        filepath = _NOTES_DIR / f"{date_str}_{slug}_{counter}.md"
        counter += 1

    tag_list = [tag.strip().lstrip("#") for tag in tags.replace(";", ",").split(",") if tag.strip()]
    tag_str = ", ".join(f"#{tag}" for tag in tag_list) if tag_list else "#note"

    frontmatter = (
        "---\n"
        f"title: \"{t}\"\n"
        f"date: {date_str} {time_str}\n"
        f"category: {category}\n"
        f"tags: [{', '.join(tag_list)}]\n"
        "---\n\n"
    )

    body = f"# {t}\n\n{content.strip()}\n\n---\n*Created by JARVIS on {date_str} at {time_str}* | Tags: {tag_str}\n"
    full_text = frontmatter + body

    filepath.write_text(full_text, encoding="utf-8")
    return f"Saved note '{t}' to {filepath.name} with tags: {tag_str}."


def _daily_log(entry: str) -> str:
    """Append a timestamped log entry to today's daily journal."""
    _ensure_dir()
    now = datetime.datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")

    daily_file = _NOTES_DIR / f"daily_{date_str}.md"
    is_new = not daily_file.exists()

    if is_new:
        header = (
            "---\n"
            f"title: \"Daily Journal - {date_str}\"\n"
            f"date: {date_str}\n"
            "type: daily_log\n"
            "---\n\n"
            f"# 📅 Daily Journal — {now.strftime('%A, %B %d, %Y')}\n\n"
            "## 📝 Log Entries\n\n"
        )
    else:
        header = ""

    log_line = f"### [{time_str}]\n{entry.strip()}\n\n"

    with open(daily_file, "a", encoding="utf-8") as f:
        if is_new:
            f.write(header)
        f.write(log_line)

    status = "Created today's daily journal and logged entry" if is_new else "Logged entry to today's daily journal"
    return f"{status} [{time_str}]: {entry.strip()[:60]}..."


def _append_note(target: str, text: str) -> str:
    """Append content to an existing note or today's daily log."""
    _ensure_dir()
    tgt = (target or "today").lower().strip()

    if tgt in ("today", "daily", "journal"):
        return _daily_log(text)

    # Search for matching file
    match = None
    for f in _NOTES_DIR.glob("*.md"):
        if tgt in f.stem.lower():
            match = f
            break

    if not match:
        return f"No note matching '{target}' found to append to."

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    append_block = f"\n\n### Updated [{now}]\n{text.strip()}\n"

    with open(match, "a", encoding="utf-8") as fh:
        fh.write(append_block)

    return f"Appended update to '{match.name}'."


def _list_notes(limit: int = 15) -> str:
    """List recently created notes with dates and tags."""
    _ensure_dir()
    files = sorted(_NOTES_DIR.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return "No notes found in knowledge base (memory/notes/)."

    lines = []
    for i, f in enumerate(files[:limit]):
        try:
            content = f.read_text(encoding="utf-8")
            title_match = re.search(r'^title:\s*["\']?([^"\']+)["\']?', content, re.M)
            title = title_match.group(1) if title_match else f.stem
            tags_match = re.search(r'tags:\s*\[([^\]]*)\]', content)
            tags = tags_match.group(1) if tags_match else ""
            words = len(content.split())
            lines.append(f"  [{i+1}] {title} ({words} words) -> {f.name}" + (f" [{tags}]" if tags else ""))
        except Exception:
            lines.append(f"  [{i+1}] {f.stem} -> {f.name}")

    return f"Notes Knowledge Base ({len(files)} total):\n" + "\n".join(lines)


def _get_note(query: str) -> str:
    """Retrieve the full content of a note by title, keyword, or filename."""
    _ensure_dir()
    q = (query or "").lower().strip()
    if not q:
        return "Please specify a note title or keyword to retrieve."

    if q in ("today", "daily"):
        today_file = _NOTES_DIR / f"daily_{datetime.datetime.now().strftime('%Y-%m-%d')}.md"
        if today_file.exists():
            return today_file.read_text(encoding="utf-8")
        return "No daily journal entries recorded yet today."

    match = None
    for f in _NOTES_DIR.glob("*.md"):
        if q in f.stem.lower() or q in f.name.lower():
            match = f
            break

    if not match:
        # Check by title inside frontmatter
        for f in _NOTES_DIR.glob("*.md"):
            try:
                c = f.read_text(encoding="utf-8")
                if q in c.lower():
                    match = f
                    break
            except Exception:
                pass

    if match:
        return match.read_text(encoding="utf-8")
    return f"Could not find any note matching '{query}'."


def _search_notes(query: str) -> str:
    """Full-text search across all notes."""
    _ensure_dir()
    q = (query or "").lower().strip()
    if not q:
        return "Please provide a query to search notes."

    matches = []
    for f in sorted(_NOTES_DIR.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            content = f.read_text(encoding="utf-8")
            if q in content.lower():
                # Extract first matching snippet
                lines = content.splitlines()
                snippet = ""
                for line in lines:
                    if q in line.lower() and not line.startswith("tags:") and not line.startswith("title:"):
                        snippet = line.strip()[:100]
                        break
                matches.append(f"  - {f.stem}: \"{snippet or content[:80]}\"")
        except Exception:
            pass

    if matches:
        return f"Found {len(matches)} note(s) matching '{query}':\n" + "\n".join(matches[:15])
    return f"No notes found containing '{query}'."


def _delete_note(query: str) -> str:
    """Delete a note matching the query."""
    _ensure_dir()
    q = (query or "").lower().strip()
    if not q:
        return "Please specify the note to delete."

    for f in _NOTES_DIR.glob("*.md"):
        if q in f.stem.lower() or q == f.name.lower():
            try:
                f.unlink()
                return f"Deleted note '{f.name}'."
            except Exception as e:
                return f"Could not delete note '{f.name}': {e}"
    return f"No note matching '{query}' found to delete."


# ══════════════════════════════════════════════════════════════════════════════
# §2  PUBLIC ENTRY POINT & DISPATCHER
# ══════════════════════════════════════════════════════════════════════════════

def notes_manager(
    parameters: dict = None,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    """
    Main entry point for JARVIS Knowledge Base & Notes Manager.

    Supported actions:
        add_note      — Save a new note with title, content, tags, category
        daily_log     — Append timestamped entry to today's daily work log
        append_note   — Append text or action items to existing note
        list_notes    — View recent notes with tags and dates
        get_note      — Retrieve full markdown content of a note
        search_notes  — Full-text search across notes
        delete_note   — Delete an existing note
    """
    params = parameters or {}
    action = str(params.get("action", "list_notes")).lower().strip()
    title = str(params.get("title", params.get("target", params.get("name", "")))).strip()
    content = str(params.get("content", params.get("text", params.get("entry", "")))).strip()
    tags = str(params.get("tags", params.get("tag", ""))).strip()
    category = str(params.get("category", "general")).strip()

    _log(player, f"notes_manager -> action='{action}', title='{title}'")

    if action in ("add_note", "create_note", "save_note", "note"):
        if not content and title:
            # If user said "Note: remember to check DNS", title might hold content
            content = title
            title = "Quick Note"
        return _add_note(title=title, content=content, tags=tags, category=category)

    elif action in ("daily_log", "log", "journal", "daily"):
        entry = content or title
        return _daily_log(entry)

    elif action in ("append_note", "append", "update_note"):
        return _append_note(target=title, text=content)

    elif action in ("list_notes", "list", "notes"):
        limit = int(params.get("limit", 15))
        return _list_notes(limit=limit)

    elif action in ("get_note", "read_note", "view_note", "open_note"):
        return _get_note(title or content)

    elif action in ("search_notes", "search", "find_notes"):
        query = params.get("query", title or content)
        return _search_notes(query)

    elif action in ("delete_note", "remove_note"):
        return _delete_note(title or content)

    else:
        return (
            f"Unknown notes_manager action '{action}'. "
            f"Available: add_note | daily_log | append_note | list_notes | get_note | search_notes | delete_note"
        )


# ══════════════════════════════════════════════════════════════════════════════
# §3  TOOL REGISTRATION (Auto-discovered by core/action_loader.py)
# ══════════════════════════════════════════════════════════════════════════════

TOOL = {
    "name": "notes_manager",
    "description": (
        "Voice Knowledge Base & Daily Work Journaling Engine. "
        "Use for: taking quick notes by voice, maintaining a daily work log with automatic timestamps, "
        "tagging notes (#networking, #docker, #todo), searching past notes, and reading back saved notes. "
        "All notes are stored locally in memory/notes/ as standard Markdown files compatible with Obsidian."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": (
                    "add_note (save a new note with title, content and tags) | "
                    "daily_log (append timestamped entry to today's daily journal) | "
                    "append_note (append update to an existing note by title) | "
                    "list_notes (list recent notes with word counts and tags) | "
                    "get_note (read full text of a note by title/query) | "
                    "search_notes (search across all notes by keyword) | "
                    "delete_note (remove a note)."
                ),
            },
            "title": {
                "type": "STRING",
                "description": "Title of the note, target note name to append to, or search query.",
            },
            "content": {
                "type": "STRING",
                "description": "Text content of the note, daily log entry, or append payload.",
            },
            "tags": {
                "type": "STRING",
                "description": "Comma-separated tags for organization (e.g. 'cisco, vlan, sysadmin' or 'todo, urgent').",
            },
            "category": {
                "type": "STRING",
                "description": "Category for the note (e.g. 'engineering', 'meeting', 'ideas', 'todo'). Default: 'general'.",
            },
            "query": {
                "type": "STRING",
                "description": "Search query for search_notes.",
            },
            "limit": {
                "type": "INTEGER",
                "description": "Maximum number of notes to list (default: 15).",
            },
        },
        "required": ["action"],
    },
    "handler": notes_manager,
}
