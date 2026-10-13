"""
workflow.py — JARVIS Named Workflow Save & Execute System

Workflows are named sequences of computer_control steps that the user can
save once and re-run on command.  Think of them as voice-activated macros.

Examples:
  "Save this as 'morning routine'"
  "Run my morning routine"
  "List my workflows"
  "Delete the morning routine workflow"

Storage: JSON file next to the JARVIS config, under
  config/workflows.json

Format:
  {
    "morning routine": {
      "steps": [
        {"action": "hotkey", "params": {"keys": "ctrl+t"}, "note": "New browser tab"},
        {"action": "screen_type_in", "params": {"description": "address bar", "text": "gmail.com"}, "note": "Open Gmail"}
      ],
      "created": "2026-10-13T11:00:00",
      "description": "Opens Gmail and checks calendar"
    },
    ...
  }

The `record` action accumulates steps that the user describes verbally into a
new workflow, rather than requiring them to spell out every step in JSON.  The
user says "record a workflow called X" and then describes the steps one at a
time; saying "done" saves it.
"""
from __future__ import annotations

import json
import time
import sys
from datetime import datetime
from pathlib import Path


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


_WORKFLOWS_PATH = _base_dir() / "config" / "workflows.json"


# ── storage ───────────────────────────────────────────────────────────────────

def _load_workflows() -> dict:
    try:
        if _WORKFLOWS_PATH.exists():
            return json.loads(_WORKFLOWS_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[Workflow] Load error: {e}")
    return {}


def _save_workflows(wf: dict) -> None:
    try:
        _WORKFLOWS_PATH.parent.mkdir(parents=True, exist_ok=True)
        _WORKFLOWS_PATH.write_text(
            json.dumps(wf, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception as e:
        print(f"[Workflow] Save error: {e}")


# ── step builder (from plain-language description) ────────────────────────────

def _describe_to_steps(step_descriptions: list[str]) -> list[dict]:
    """Convert a list of plain-English step descriptions into computer_control
    step dicts using the SMART model.

    Each description like "click the Send button" becomes:
      {"action": "screen_click", "params": {"description": "Send button"}, "note": "..."}
    """
    from core import gemini

    if not step_descriptions:
        return []

    numbered = "\n".join(f"{i+1}. {s}" for i, s in enumerate(step_descriptions))
    prompt   = (
        "Convert each numbered step below into a JSON object for computer_control.\n"
        "Allowed actions: type, smart_type, click, double_click, triple_click, middle_click,\n"
        "  right_click, mouse_down, mouse_up, mouse_position, hotkey, press, key_down, key_up,\n"
        "  scroll, move, drag, copy, paste, wait, clear_field, focus_window, list_windows,\n"
        "  get_active_window, minimize_window, maximize_window, close_window, show_desktop,\n"
        "  lock_screen, open_settings, open_file_explorer, open_task_manager, open_run_dialog,\n"
        "  open_clipboard_history, open_action_center, take_snip, get_system_info,\n"
        "  volume_up, volume_down, volume_mute, play_pause,\n"
        "  screen_click, screen_type_in, screen_wait_for, screen_read,\n"
        "  chrome_focus, chrome_new_tab, chrome_switch_tab, chrome_close_tab,\n"
        "  chrome_reopen_tab, chrome_navigate, chrome_search, chrome_get_url,\n"
        "  chrome_get_page_text, chrome_read_tab, chrome_click, chrome_type_in,\n"
        "  chrome_list_tabs, chrome_zoom, chrome_find, chrome_history, chrome_downloads,\n"
        "  chrome_bookmarks, chrome_duplicate_tab, chrome_reload, chrome_fullscreen,\n"
        "  chrome_task_manager, chrome_print_pdf, chrome_page_source, chrome_clear_data,\n"
        "  chrome_incognito, chrome_inspect.\n"
        "Each object: {\"action\": \"...\", \"params\": {...}, \"note\": \"<original text>\"}\n"
        "Output ONLY a JSON array. No prose, no fences.\n\n"
        + numbered
    )

    raw = gemini.text(prompt, tier=gemini.SMART, timeout_ms=30_000)
    raw = (raw or "").strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw   = "\n".join(lines[1:-1]).strip()
    if "[" not in raw:
        return []
    raw = raw[raw.find("[") : raw.rfind("]") + 1]
    try:
        steps = json.loads(raw)
        if isinstance(steps, list):
            return steps
    except Exception as e:
        print(f"[Workflow] Step parse error: {e}")
    return []


# ── runner ────────────────────────────────────────────────────────────────────

def _run_workflow(name: str, wf: dict, player=None) -> str:
    """Execute a saved workflow step by step."""
    steps = wf.get("steps", [])
    if not steps:
        return f"Workflow '{name}' has no steps."

    from actions.computer_control import computer_control

    log: list[str] = []
    print(f"[Workflow] Running '{name}' ({len(steps)} steps)")
    if player:
        player.write_log(f"[Workflow] Running: {name}")

    for i, step in enumerate(steps, 1):
        action  = step.get("action", "")
        params  = dict(step.get("params", {}))
        note    = step.get("note", action)
        params["action"] = action

        print(f"[Workflow]   {i}/{len(steps)}: [{action}] {note}")
        try:
            result = computer_control(params)
            log.append(f"Step {i} [{action}]: {result}")
        except Exception as e:
            log.append(f"Step {i} [{action}]: FAILED — {e}")

        time.sleep(0.3)   # UI settle

    summary = f"Ran '{name}': {len(steps)} step(s) complete."
    if player:
        player.write_log(f"[Workflow] {summary}")
    return summary


# ── main handler ──────────────────────────────────────────────────────────────

def workflow(
    parameters: dict,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    """
    Save, run, list, or delete named workflows (voice-activated macros).

    actions:
      save  — create or overwrite a named workflow from a list of step descriptions
      run   — execute a saved workflow
      list  — list all saved workflows
      show  — show the steps of a specific workflow
      delete — remove a workflow
    """
    params = parameters or {}
    action = params.get("action", "").lower().strip()
    name   = (params.get("name") or "").strip().lower()

    if player:
        player.write_log(f"[Workflow] {action} {name}")

    print(f"[Workflow] {action!r} name={name!r}")

    wf_store = _load_workflows()

    # ── list ──────────────────────────────────────────────────────────────────
    if action == "list":
        if not wf_store:
            return "No workflows saved yet. Say 'save a workflow called X' to create one."
        lines = []
        for wf_name, wf_data in sorted(wf_store.items()):
            n     = len(wf_data.get("steps", []))
            desc  = wf_data.get("description", "")
            lines.append(f"• {wf_name} ({n} step{'s' if n != 1 else ''})"
                         + (f" — {desc}" if desc else ""))
        return "Saved workflows:\n" + "\n".join(lines)

    # ── run ───────────────────────────────────────────────────────────────────
    if action == "run":
        if not name:
            return "Specify the workflow name to run."
        if name not in wf_store:
            close = [k for k in wf_store if name in k or k in name]
            hint  = f" Did you mean: {', '.join(close[:3])}?" if close else ""
            return f"No workflow named '{name}' found.{hint}"
        return _run_workflow(name, wf_store[name], player=player)

    # ── save ──────────────────────────────────────────────────────────────────
    if action == "save":
        if not name:
            return "Specify a name for the workflow."

        raw_steps = params.get("steps", [])
        if isinstance(raw_steps, str):
            # Single string — one step
            raw_steps = [raw_steps]

        if not raw_steps:
            return (
                f"Provide the steps for workflow '{name}'. "
                f"Pass them as a list of plain-English descriptions in the 'steps' field."
            )

        print(f"[Workflow] Converting {len(raw_steps)} step description(s) to actions…")
        steps = _describe_to_steps(raw_steps)
        if not steps:
            # Fallback: store as screen_click steps verbatim
            steps = [
                {"action": "screen_click",
                 "params": {"description": s},
                 "note": s}
                for s in raw_steps
            ]

        wf_store[name] = {
            "steps": steps,
            "description": params.get("description", ""),
            "created": datetime.now().isoformat(timespec="seconds"),
        }
        _save_workflows(wf_store)
        n = len(steps)
        return f"Workflow '{name}' saved with {n} step{'s' if n != 1 else ''}."

    # ── show ──────────────────────────────────────────────────────────────────
    if action == "show":
        if not name:
            return "Specify the workflow name."
        if name not in wf_store:
            return f"No workflow named '{name}'."
        wf    = wf_store[name]
        steps = wf.get("steps", [])
        lines = [f"Workflow '{name}' ({len(steps)} steps):"]
        for i, s in enumerate(steps, 1):
            note = s.get("note") or s.get("action", "?")
            lines.append(f"  {i}. [{s.get('action', '?')}] {note}")
        return "\n".join(lines)

    # ── delete ────────────────────────────────────────────────────────────────
    if action in ("delete", "remove"):
        if not name:
            return "Specify the workflow name to delete."
        if name not in wf_store:
            return f"No workflow named '{name}'."
        del wf_store[name]
        _save_workflows(wf_store)
        return f"Workflow '{name}' deleted."

    return f"Unknown workflow action '{action}'. Use: save | run | list | show | delete."


# ── Tool declaration (auto-discovered by core/action_loader.py) ───────────────
TOOL = {
    "name": "workflow",
    "description": (
        "Save, run, and manage named automation workflows (voice macros). "
        "A workflow is a named sequence of screen actions that can be saved once "
        "and replayed instantly on command. "
        "Use 'save' to record a new workflow from plain-language step descriptions. "
        "Use 'run' to replay a saved workflow. "
        "Use 'list' to show all saved workflows. "
        "Use 'show' to inspect a workflow's steps. "
        "Use 'delete' to remove one. "
        "Example: save a 'morning routine' that opens Gmail, checks calendar, starts Spotify. "
        "Do NOT use this for single actions — use computer_control instead."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "save | run | list | show | delete",
            },
            "name": {
                "type": "STRING",
                "description": "Name of the workflow (e.g. 'morning routine', 'login to gmail')",
            },
            "steps": {
                "type": "ARRAY",
                "items": {"type": "STRING"},
                "description": (
                    "List of plain-English step descriptions for 'save'. "
                    "Each string becomes one automation step. "
                    "Example: ['open Chrome', 'go to gmail.com', 'click Sign In']"
                ),
            },
            "description": {
                "type": "STRING",
                "description": "Optional human-readable description of what this workflow does.",
            },
        },
        "required": ["action"],
    },
    "handler": workflow,
}
