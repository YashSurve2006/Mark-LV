"""
doc_writer.py — JARVIS Advanced Document & Tab Controller Plugin
================================================================

Drop into plugins/ — auto-discovered on next launch.

WHAT IT DOES
    Bridges the gap between JARVIS's raw keyboard/browser tools and real
    document-editing workflows. Specifically built for:

    • Switching Chrome tabs (by title keyword or direction)
    • Writing structured, formatted content into Google Docs
    • Pasting content into any active text field cleanly
    • Creating professional document sections (headers, code blocks, bullet lists)
    • Writing extracted PDF section content directly into an open Google Doc

MODES
    switch_tab       — switch to a Chrome tab matching a keyword (e.g. "docs", "pdf")
    write_doc        — type formatted content into the currently active document / text field
    create_section   — create a titled section with body text in a Google Doc
    paste_clean      — paste clipboard content without formatting noise
    clear_doc        — select all and delete in the active document
    new_line         — move to a new line / paragraph
    save_doc         — Ctrl+S the active document

VOICE TRIGGER EXAMPLES
    "Switch to my Google Docs tab"
    "Switch to the PDF tab"
    "Write this into the document: ..."
    "Create a section called Introduction with this content: ..."
    "Paste cleanly into the doc"
    "Clear the document"
    "Save the document"
"""

from __future__ import annotations

import time
import subprocess

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE    = 0.04
    _PYAUTOGUI = True
except ImportError:
    _PYAUTOGUI = False

try:
    import pyperclip
    _PYPERCLIP = True
except ImportError:
    _PYPERCLIP = False


# ---------------------------------------------------------------------------
# PLUGIN DECLARATION
# ---------------------------------------------------------------------------

PLUGIN = {
    "name": "doc_writer",
    "description": (
        "Advanced document editor and tab switcher. "
        "Use this when the user wants to: "
        "(1) switch Chrome tabs — say 'switch to docs tab' or 'go to PDF tab', "
        "(2) write or type formatted content into Google Docs or any active document, "
        "(3) create a new titled section with content in Google Docs, "
        "(4) paste content cleanly without formatting, "
        "(5) clear / wipe the current document, "
        "(6) save the current document, "
        "(7) format text as a header (H1/H2) in Google Docs, "
        "(8) format text as a bulleted list in Google Docs. "
        "Use this tool INSTEAD OF computer_control for any document-editing task. "
        "Do NOT use computer_settings for tab switching — use this tool."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "mode": {
                "type": "STRING",
                "description": (
                    "What to do. One of: "
                    "switch_tab (switch Chrome tab by keyword), "
                    "write_doc (type content into active document), "
                    "create_section (add a titled section with body text), "
                    "paste_clean (paste clipboard without formatting), "
                    "clear_doc (select all and delete), "
                    "new_line (add blank line), "
                    "save_doc (Ctrl+S), "
                    "format_header (apply Google Docs header style), "
                    "format_list (apply Google Docs bullet list)."
                ),
            },
            "tab_keyword": {
                "type": "STRING",
                "description": (
                    "Keyword to match against open tab titles. "
                    "Used with mode='switch_tab'. "
                    "Examples: 'docs', 'google docs', 'pdf', 'gmail', 'youtube'."
                ),
            },
            "content": {
                "type": "STRING",
                "description": (
                    "The text content to type or write into the document. "
                    "Used with mode='write_doc' or mode='create_section'."
                ),
            },
            "section_title": {
                "type": "STRING",
                "description": (
                    "Title / heading for the section. "
                    "Used with mode='create_section'."
                ),
            },
            "direction": {
                "type": "STRING",
                "description": (
                    "Tab switch direction: 'next' or 'prev'. "
                    "Used with mode='switch_tab' when no keyword is given."
                ),
            },
            "header_level": {
                "type": "STRING",
                "description": (
                    "Header level for Google Docs (1 or 2). "
                    "Used with mode='format_header'."
                ),
            },
        },
        "required": ["mode"],
    },
}


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _require_pyautogui() -> str | None:
    if not _PYAUTOGUI:
        return "PyAutoGUI is not installed. Run: pip install pyautogui"
    return None


def _hotkey(*keys):
    if _PYAUTOGUI:
        pyautogui.hotkey(*keys)
        time.sleep(0.15)


def _press(key: str):
    if _PYAUTOGUI:
        pyautogui.press(key)
        time.sleep(0.08)


def _type_text(text: str):
    """Type text using clipboard to handle unicode, special chars and speed."""
    if not _PYAUTOGUI:
        return
    if _PYPERCLIP:
        pyperclip.copy(text)
        time.sleep(0.1)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.15)
    else:
        # Fallback: typewrite (ASCII only, slower)
        pyautogui.typewrite(text, interval=0.02)


def _log(player, msg: str) -> None:
    if player:
        try:
            player.write_log(f"JARVIS: {msg}")
        except Exception:
            pass

def _ui_notify(player, ui_msg: str) -> None:
    """Displays a HUD indicator in the UI (Phase 4: User Feedback Loop)."""
    if player and hasattr(player, 'ui'):
        try:
            player.ui.write_log(f"SYS: {ui_msg}")
        except Exception:
            pass

def _switch_tab_by_keyword(keyword: str) -> str:
    """
    Use Windows PowerShell to enumerate Chrome windows by title and bring the
    matching one to focus, then switch to it with Ctrl+Tab cycling.
    Falls back to Ctrl+Tab cycling if window enumeration fails.
    """
    try:
        import subprocess
        kw = keyword.lower().strip()

        # Use PowerShell to find the Chrome window with a matching title
        ps_cmd = (
            f'$w = Get-Process chrome -ErrorAction SilentlyContinue | '
            f'Where-Object {{$_.MainWindowTitle -like "*{kw}*"}} | '
            f'Select-Object -First 1; '
            f'if ($w) {{ $w.Id }} else {{ "" }}'
        )
        result = subprocess.run(
            ["powershell", "-Command", ps_cmd],
            capture_output=True, text=True, timeout=5
        )
        pid = result.stdout.strip()

        if pid:
            # Bring that specific window to front via SetForegroundWindow
            bring_cmd = (
                f'Add-Type -A System.Windows.Forms; '
                f'$p = Get-Process -Id {pid} -ErrorAction SilentlyContinue; '
                f'if ($p) {{ '
                f'  [System.Windows.Forms.SendKeys]::Flush(); '
                f'  $hwnd = $p.MainWindowHandle; '
                f'  $null = [System.Runtime.InteropServices.Marshal]::GetActiveObject; '
                f'  Add-Type -A "Microsoft.VisualBasic"; '
                f'  [Microsoft.VisualBasic.Interaction]::AppActivate({pid}) '
                f'}}'
            )
            # Simpler: just use AppActivate via PowerShell
            activate_cmd = (
                f'$ErrorActionPreference="SilentlyContinue"; '
                f'$s = New-Object -ComObject WScript.Shell; '
                f'$p = Get-Process -Id {pid}; '
                f'$s.AppActivate($p.MainWindowTitle)'
            )
            subprocess.run(
                ["powershell", "-Command", activate_cmd],
                capture_output=True, timeout=5
            )
            time.sleep(0.5)
            return f"Switched to tab matching '{keyword}'."

    except Exception:
        pass

    # Fallback: cycle through tabs with Ctrl+Tab (up to 15 attempts)
    # This works when Chrome is already focused
    if _PYAUTOGUI:
        pyautogui.hotkey("ctrl", "tab")
        time.sleep(0.3)
        return f"Cycled to next tab (could not find '{keyword}' by title — try focusing Chrome first)."

    return "Could not switch tab — PyAutoGUI not available."


# ---------------------------------------------------------------------------
# MODE HANDLERS
# ---------------------------------------------------------------------------

def _mode_switch_tab(params: dict, player) -> str:
    err = _require_pyautogui()
    if err:
        return err

    keyword   = params.get("tab_keyword", "").strip()
    direction = params.get("direction", "next").lower()

    if keyword:
        _log(player, f"Switching to tab: {keyword} ...")
        result = _switch_tab_by_keyword(keyword)
        _log(player, result)
        return result

    # No keyword — just cycle
    if direction == "prev":
        _hotkey("ctrl", "shift", "tab")
        return "Switched to previous tab."
    else:
        _hotkey("ctrl", "tab")
        return "Switched to next tab."


def _mode_write_doc(params: dict, player) -> str:
    err = _require_pyautogui()
    if err:
        return err

    content = params.get("content", "").strip()
    if not content:
        return "Sir, no content was provided to write."

    _log(player, "Writing content to active document ...")
    _ui_notify(player, "📝 Structuring Data into Document...")

    # Click the active area to make sure it has focus
    time.sleep(0.3)

    # Replace literal \n with actual newlines
    content = content.replace("\\n", "\n")

    # Type using clipboard for speed and unicode support
    _type_text(content)
    time.sleep(0.2)

    preview = content[:60].replace("\n", " ")
    _log(player, f"Written: {preview}...")
    return f"Sir, I have written the content into the document. ({len(content)} characters)"


def _mode_create_section(params: dict, player) -> str:
    err = _require_pyautogui()
    if err:
        return err

    title   = params.get("section_title", "").strip()
    content = params.get("content", "").strip()

    if not title and not content:
        return "Sir, I need at least a section title or content to create a section."

    _log(player, f"Creating section: {title} ...")
    _ui_notify(player, f"📑 Generating Academic Section: {title}")
    time.sleep(0.3)

    # Add two blank lines before a new section (for spacing)
    _press("end")        # go to end of current line
    _press("return")
    _press("return")

    if title:
        # Type the title in UPPERCASE for visual distinction
        _type_text(title.upper())
        _press("return")
        _press("return")

    if content:
        content = content.replace("\\n", "\n")
        _type_text(content)
        _press("return")

    _log(player, f"Section '{title}' created.")
    return f"Sir, section '{title}' has been created in the document."


def _mode_paste_clean(params: dict, player) -> str:
    err = _require_pyautogui()
    if err:
        return err

    _log(player, "Pasting content cleanly ...")
    _ui_notify(player, "📋 Injecting Formatting-Free Content...")
    time.sleep(0.3)

    # Ctrl+Shift+V = paste without formatting (works in Google Docs)
    _hotkey("ctrl", "shift", "v")
    time.sleep(0.3)

    return "Sir, content pasted without formatting."


def _mode_clear_doc(params: dict, player) -> str:
    err = _require_pyautogui()
    if err:
        return err

    _log(player, "Clearing document ...")
    _ui_notify(player, "⚠️ WARNING: Executing Document Wipe (Ctrl+A -> Del)")
    time.sleep(0.3)
    _hotkey("ctrl", "a")
    time.sleep(0.15)
    _press("delete")
    time.sleep(0.15)
    _log(player, "Document cleared.")
    return "Sir, the document has been cleared."


def _mode_new_line(params: dict, player) -> str:
    err = _require_pyautogui()
    if err:
        return err
    _press("end")
    _press("return")
    _press("return")
    return "New paragraph added."


def _mode_save_doc(params: dict, player) -> str:
    err = _require_pyautogui()
    if err:
        return err
    _hotkey("ctrl", "s")
    time.sleep(0.3)
    return "Sir, document saved."


def _mode_format_header(params: dict, player) -> str:
    """Applies Google Docs header formatting (Ctrl+Alt+1 or 2)."""
    err = _require_pyautogui()
    if err:
        return err
    
    level = params.get("header_level", "1").strip()
    key = "1" if level == "1" else "2"
    
    _ui_notify(player, f"🖋️ Applying Heading {key} Format")
    
    # Select the current line
    _press("home")
    _hotkey("shift", "end")
    time.sleep(0.1)
    
    # Apply Google Docs Heading Shortcut
    _hotkey("ctrl", "alt", key)
    time.sleep(0.2)
    
    # Deselect and move down
    _press("right")
    
    return f"Sir, current line formatted as Heading {key}."


def _mode_format_list(params: dict, player) -> str:
    """Applies Google Docs bulleted list formatting (Ctrl+Shift+8)."""
    err = _require_pyautogui()
    if err:
        return err
        
    _ui_notify(player, "⏺️ Structuring Bulleted List")
    
    # Apply Google Docs Bulleted List Shortcut
    _hotkey("ctrl", "shift", "8")
    time.sleep(0.2)
    
    return "Sir, bulleted list formatting applied."


# ---------------------------------------------------------------------------
# MAIN ENTRY POINT
# ---------------------------------------------------------------------------

def run(parameters: dict, player=None, session_memory=None) -> str:
    mode = (parameters.get("mode") or "").lower().strip()

    try:
        if mode == "switch_tab":
            return _mode_switch_tab(parameters, player)
        if mode == "write_doc":
            return _mode_write_doc(parameters, player)
        if mode == "create_section":
            return _mode_create_section(parameters, player)
        if mode == "paste_clean":
            return _mode_paste_clean(parameters, player)
        if mode == "clear_doc":
            return _mode_clear_doc(parameters, player)
        if mode == "new_line":
            return _mode_new_line(parameters, player)
        if mode == "save_doc":
            return _mode_save_doc(parameters, player)
        if mode == "format_header":
            return _mode_format_header(parameters, player)
        if mode == "format_list":
            return _mode_format_list(parameters, player)

        return (
            f"Sir, I don't recognise the mode '{mode}'. "
            "Available: switch_tab, write_doc, create_section, paste_clean, "
            "clear_doc, new_line, save_doc, format_header, format_list."
        )

    except Exception as exc:
        if player:
            try:
                player.write_log(f"JARVIS: doc_writer error: {exc}")
            except Exception:
                pass
        return f"Sir, the document writer encountered an error: {exc}"
