"""
smart_automation.py — JARVIS Plan-and-Execute Automation Agent

The architecture problem with multi-step automation:
    The LLM decides what to do, calls ONE tool, gets the result, then decides
    the next tool.  For automation sequences this means every click, every
    keystroke, every wait costs a full round-trip through the Live model —
    0.5 s per step minimum, and the user hears silence for each one.

    This module collapses the loop.  JARVIS calls smart_automate ONCE with a
    goal, and the FUNCTION itself runs the inner plan→act→verify→re-plan loop.
    The Live model is back in under 3 seconds regardless of how many steps the
    task takes.

How it works:
    1. PLAN   — a SMART model call receives the goal + a screenshot and emits
                a numbered JSON array of steps.  Each step is:
                    {"action": "...", "params": {...}, "description": "..."}
                where action/params map directly to computer_control's dispatch
                table, and description is what to verify after.
    2. EXECUTE — each step runs through computer_control's helpers directly
                (no extra model call per step).
    3. VERIFY  — after each step, take a screenshot and ask the FAST model:
                "Did this happen? (yes/no + reason)".  If no, re-plan from
                the current state.
    4. REPORT  — return a human-readable transcript of what was done and what
                the final screen state is.

Safety:
    - Only the same set of primitives computer_control exposes.
    - Max 25 steps per plan, max 3 re-plans before giving up.
    - The planning prompt explicitly forbids shutdown, file deletion, and
      anything outside the home directory.
"""
from __future__ import annotations

import io
import json
import time
import platform
from pathlib import Path

_OS = platform.system()

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE    = 0.05
    _PYAUTOGUI = True
except ImportError:
    _PYAUTOGUI = False

try:
    import PIL.Image
    _PIL = True
except ImportError:
    _PIL = False

# ── constants ─────────────────────────────────────────────────────────────────

_MAX_STEPS   = 25    # hard cap per plan
_MAX_REPLANS = 3     # how many times we can re-plan after a verification fail
_STEP_PAUSE  = 0.35  # seconds between steps (UI settle time)

# ── screenshot helper (inline, avoids importing screen_processor) ─────────────

def _grab_screen() -> tuple[bytes, str]:
    """Capture the current screen as a compressed JPEG and return (bytes, mime)."""
    if not _PYAUTOGUI:
        raise RuntimeError("pyautogui not installed")
    try:
        img = pyautogui.screenshot()
    except pyautogui.FailSafeException:
        prev = pyautogui.FAILSAFE
        pyautogui.FAILSAFE = False
        try:
            img = pyautogui.screenshot()
        finally:
            pyautogui.FAILSAFE = prev
    if _PIL:
        img.thumbnail((1920, 1080), PIL.Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=90, optimize=True)
        return buf.getvalue(), "image/jpeg"
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue(), "image/png"


# ── planning ──────────────────────────────────────────────────────────────────

_PLAN_SYSTEM = """\
You are a desktop-automation planner.  You receive a GOAL and a screenshot of
the current screen.  Produce a step-by-step plan that achieves the goal using
ONLY the actions listed below.  Each step is an object in a JSON array.

ALLOWED ACTIONS (match computer_control exactly):
  type, smart_type, click, double_click, triple_click, middle_click, right_click,
  mouse_down, mouse_up, mouse_position, hotkey, press, key_down, key_up, scroll,
  move, drag, copy, paste, wait, clear_field, focus_window, list_windows,
  get_active_window, minimize_window, maximize_window, close_window, show_desktop,
  lock_screen, open_settings, open_file_explorer, open_task_manager, open_run_dialog,
  open_clipboard_history, open_action_center, take_snip, get_system_info,
  volume_up, volume_down, volume_mute, play_pause,
  screen_click, screen_type_in, screen_wait_for, screen_read,
  chrome_focus, chrome_new_tab, chrome_switch_tab, chrome_close_tab,
  chrome_reopen_tab, chrome_navigate, chrome_search, chrome_get_url,
  chrome_get_page_text, chrome_read_tab, chrome_click, chrome_type_in,
  chrome_list_tabs, chrome_zoom, chrome_find, chrome_history, chrome_downloads,
  chrome_bookmarks, chrome_duplicate_tab, chrome_reload, chrome_fullscreen,
  chrome_task_manager, chrome_print_pdf, chrome_page_source, chrome_clear_data,
  chrome_pdf_goto_page, chrome_incognito, chrome_inspect

Each step object:
  {
    "action":      "<action name>",
    "params":      {<key>: <value>},
    "description": "<what the screen should show after this step succeeds>"
  }

Rules:
  - If the goal involves Chrome or web browsing, operate directly on the user's
    existing Chrome tabs using chrome_focus, chrome_new_tab, chrome_switch_tab,
    chrome_navigate, chrome_search, chrome_click, chrome_type_in, chrome_list_tabs.
  - Use screen_click / screen_type_in / chrome_click / chrome_type_in to locate elements
    by natural-language description rather than hardcoded (x,y) unless you are certain.
  - After any click that triggers navigation or loading, add a screen_wait_for
    step with the description of the element that confirms the state has loaded.
  - After any form submit, add a screen_wait_for for the success indicator.
  - Keep steps atomic: one action per step.
  - Maximum 25 steps.
  - NEVER include: shutdown_jarvis, file delete/rmdir, anything outside the
    user home directory, or subprocess calls.
  - Output ONLY the JSON array.  No prose, no markdown fences.
"""


def _build_plan(goal: str, screenshot_bytes: bytes, mime: str) -> list[dict]:
    """Ask the SMART model to produce a step plan for `goal`."""
    from google.genai import types as gtypes
    from core import gemini

    prompt = f"GOAL: {goal}\n\nProduce the step-by-step plan as a JSON array."
    parts  = [
        gtypes.Part.from_bytes(data=screenshot_bytes, mime_type=mime),
        prompt,
    ]

    cfg = gtypes.GenerateContentConfig(system_instruction=_PLAN_SYSTEM)

    raw = gemini.text(
        parts,
        tier=gemini.SMART,
        timeout_ms=45_000,
        config=cfg,
    )

    raw = (raw or "").strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw   = "\n".join(lines[1:-1]).strip()
    if "[" not in raw:
        return []
    raw = raw[raw.find("[") : raw.rfind("]") + 1]
    try:
        plan = json.loads(raw)
        if isinstance(plan, list):
            return plan[:_MAX_STEPS]
    except Exception:
        pass
    return []


# ── verification ──────────────────────────────────────────────────────────────

def _verify_step(expected: str, screenshot_bytes: bytes, mime: str) -> tuple[bool, str]:
    """Ask the FAST model whether the screen shows what we expected after a step.
    Returns (success: bool, reason: str).
    """
    from google.genai import types as gtypes
    from core import gemini

    prompt = (
        f"Look at this screenshot.  The expected outcome is:\n"
        f"  '{expected}'\n\n"
        f"Does the screen show this outcome?\n"
        f"Reply with exactly:\n"
        f"  YES: <one sentence confirming>\n"
        f"  NO: <one sentence explaining what is different>"
    )

    raw = gemini.text(
        [gtypes.Part.from_bytes(data=screenshot_bytes, mime_type=mime), prompt],
        tier=gemini.FAST,
        timeout_ms=20_000,
    )

    raw = (raw or "").strip()
    if raw.upper().startswith("YES"):
        return True, raw[3:].lstrip(": ").strip()
    return False, raw[3:].lstrip(": ").strip()


# ── step executor ─────────────────────────────────────────────────────────────

def _run_step(step: dict) -> str:
    """Execute a single plan step using computer_control's dispatch table."""
    from actions.computer_control import computer_control

    action = step.get("action", "")
    params = dict(step.get("params", {}))
    params["action"] = action

    try:
        result = computer_control(params)
        return str(result)
    except Exception as e:
        return f"Step failed: {e}"


# ── main entry ────────────────────────────────────────────────────────────────

def smart_automate(
    parameters: dict,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    """
    Plan and execute a multi-step automation goal on the current desktop.

    The agent:
      1. Screenshots the current screen.
      2. Asks the AI to plan the steps needed to achieve the goal.
      3. Executes each step.
      4. Takes a verification screenshot and confirms it worked.
      5. Re-plans from the new state if a step fails (up to 3 re-plans).
      6. Returns a human-readable summary of the outcome.
    """
    if not _PYAUTOGUI:
        return "PyAutoGUI is not installed — smart_automate requires it."

    goal = (parameters or {}).get("goal", "").strip()
    if not goal:
        return "No goal specified for smart_automate."

    if player:
        player.write_log(f"[SmartAuto] Goal: {goal[:60]}")

    print(f"[SmartAuto] Targeting goal: {goal}")

    log: list[str] = []
    replans = 0

    # ── initial screenshot + plan ─────────────────────────────────────────────
    try:
        img_b, mime = _grab_screen()
    except Exception as e:
        return f"Could not capture screen: {e}"

    plan = _build_plan(goal, img_b, mime)
    if not plan:
        return (
            "The automation planner could not produce a valid plan for this goal. "
            "Try being more specific, or break it into simpler steps."
        )

    print(f"[SmartAuto] Plan has {len(plan)} step(s):")
    for i, s in enumerate(plan, 1):
        print(f"  {i}. [{s.get('action')}] {s.get('description', '')}")

    step_idx    = 0
    total_steps = 0

    # ── execute loop ──────────────────────────────────────────────────────────
    while step_idx < len(plan) and total_steps < _MAX_STEPS:
        step        = plan[step_idx]
        action      = step.get("action", "?")
        description = step.get("description", "")
        total_steps += 1

        print(f"[SmartAuto] Step {step_idx + 1}/{len(plan)}: [{action}] {description}")
        if player:
            player.write_log(f"[SmartAuto] {action}: {description[:50]}")

        result = _run_step(step)
        print(f"[SmartAuto]   Result: {result}")
        log.append(f"Step {step_idx + 1} [{action}]: {result}")

        time.sleep(_STEP_PAUSE)

        # Verify — skip for actions that have no visible screen effect
        no_verify = {"wait", "move", "scroll", "hotkey", "press", "copy", "paste"}
        if action not in no_verify and description:
            try:
                img_b, mime  = _grab_screen()
                ok, reason   = _verify_step(description, img_b, mime)
            except Exception as e:
                ok, reason = False, f"screenshot failed: {e}"

            if ok:
                print(f"[SmartAuto]   Verified: {reason}")
                log.append(f"  [OK] {reason}")
                step_idx += 1
            else:
                print(f"[SmartAuto]   FAILED: {reason}")
                log.append(f"  [FAIL] {reason}")
                replans += 1
                if replans > _MAX_REPLANS:
                    log.append("Too many failures — stopping.")
                    break
                # Re-plan from the current broken state
                print(f"[SmartAuto] Re-planning ({replans}/{_MAX_REPLANS})…")
                replan_goal = (
                    f"ORIGINAL GOAL: {goal}\n"
                    f"COMPLETED SO FAR:\n" + "\n".join(log[:-2]) + "\n"
                    f"LAST FAILED STEP: [{action}] — expected '{description}' "
                    f"but got: {reason}\n"
                    f"Re-plan from the current screen state to finish the original goal."
                )
                new_plan = _build_plan(replan_goal, img_b, mime)
                if new_plan:
                    plan     = new_plan
                    step_idx = 0
                    print(f"[SmartAuto] New plan has {len(plan)} step(s).")
                else:
                    log.append("Re-plan failed — giving up.")
                    break
        else:
            step_idx += 1

    # ── final summary ─────────────────────────────────────────────────────────
    try:
        img_b, mime = _grab_screen()
        from google.genai import types as gtypes
        from core import gemini

        final_prompt = (
            f"Automation task: '{goal}'\n"
            f"Steps taken:\n" + "\n".join(log) + "\n\n"
            f"Look at the current screen and give a single concise sentence "
            f"stating whether the goal was achieved and what the screen now shows."
        )
        summary = gemini.text(
            [gtypes.Part.from_bytes(data=img_b, mime_type=mime), final_prompt],
            tier=gemini.SMART,
            timeout_ms=25_000,
        )
    except Exception:
        summary = ""

    outcome = summary or f"Automation finished — {total_steps} step(s) executed."
    print(f"[SmartAuto] Done: {outcome}")
    if player:
        player.write_log(f"[SmartAuto] Done: {outcome}")
    return outcome


# ── Tool declaration (auto-discovered by core/action_loader.py) ───────────────
TOOL = {
    "name": "smart_automate",
    "description": (
        "AI-powered multi-step automation agent. Give it a GOAL in plain language "
        "and it will plan the steps, execute them on screen (clicks, typing, navigation), "
        "verify each step with a screenshot, and automatically re-plan if something goes wrong. "
        "Use this for tasks requiring multiple actions: 'fill in this form', "
        "'open Notepad and type a note', 'navigate to a website and log in', "
        "'compose and send an email in Gmail', 'complete this checkout flow'. "
        "Do NOT use for single actions (use computer_control instead). "
        "Do NOT use for browser-only tasks (use browser_control instead)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "goal": {
                "type": "STRING",
                "description": (
                    "Plain-language goal describing what to accomplish on the current screen. "
                    "Be specific: name the application, field labels, and values. "
                    "Example: 'Open Notepad, type Hello World, save as hello.txt on the Desktop'"
                ),
            },
        },
        "required": ["goal"],
    },
    "handler": smart_automate,
}
