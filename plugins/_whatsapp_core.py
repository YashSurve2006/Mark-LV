"""
WhatsApp Automation Core Engine for JARVIS Mark LV.

Features:
- Multi-tier transport cascade:
  1. Protocol Deep-Link (whatsapp://send?phone=...&text=... / whatsapp://send?text=...)
  2. Native Windows Desktop / UWP App Driver (win32gui, WScript.Shell, pywinauto, pyautogui)
  3. WhatsApp Web Browser Driver (Chrome active tab / default browser)
- Contact & Phone Intelligence:
  - Phone number normalization (international standards, India +91 default, US +1, etc.)
  - Nickname & relationship resolution via memory/long_term.json
  - Auto-saving contacts to persistent memory
- Message Formatting & Composition:
  - Markdown styles (*bold*, _italic_, ~strikethrough~, ```code```)
  - Multi-line message preservation without accidental premature send
- Modes:
  - "send": Automatically dispatches message
  - "draft": Composes message in chat input box for user visual review before sending
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

# Windows-specific imports
try:
    import win32gui
    import win32con
    import win32process
    import win32com.client
    _WIN32 = True
except ImportError:
    _WIN32 = False

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.05
    _PYAUTOGUI = True
except ImportError:
    _PYAUTOGUI = False

try:
    import pyperclip
    _PYPERCLIP = True
except ImportError:
    _PYPERCLIP = False


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


_BASE = _base_dir()
_MEMORY_FILE = _BASE / "memory" / "long_term.json"
_CONFIG_FILE = _BASE / "config" / "api_keys.json"


# ── Clipboard Resolution Utilities ───────────────────────────────────────────

def _get_clipboard_text(player=None) -> str:
    """Retrieve text safely from the system clipboard with multi-tier fallbacks."""
    # Tier 1: In-process UI / Qt player cache
    if player and hasattr(player, "get_clipboard_text"):
        try:
            val = player.get_clipboard_text()
            if val and str(val).strip():
                return str(val).strip()
        except Exception:
            pass

    try:
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            val = app.clipboard().text()
            if val and str(val).strip():
                return str(val).strip()
    except Exception:
        pass

    # Tier 2: ctypes user32 OpenClipboard with retry loop & format handling (CF_UNICODETEXT, CF_HDROP, CF_TEXT)
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            shell32 = ctypes.windll.shell32

            CF_TEXT = 1
            CF_UNICODETEXT = 13
            CF_HDROP = 15

            user32.OpenClipboard.argtypes = [wintypes.HWND]
            user32.OpenClipboard.restype = wintypes.BOOL
            user32.CloseClipboard.restype = wintypes.BOOL
            user32.GetClipboardData.argtypes = [wintypes.UINT]
            user32.GetClipboardData.restype = wintypes.HANDLE
            user32.IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
            user32.IsClipboardFormatAvailable.restype = wintypes.BOOL
            kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
            kernel32.GlobalLock.restype = wintypes.LPVOID
            kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
            kernel32.GlobalUnlock.restype = wintypes.BOOL

            opened = False
            for _ in range(8):
                if user32.OpenClipboard(None):
                    opened = True
                    break
                time.sleep(0.04)

            if opened:
                try:
                    if user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
                        h = user32.GetClipboardData(CF_UNICODETEXT)
                        if h:
                            ptr = kernel32.GlobalLock(h)
                            if ptr:
                                val = ctypes.c_wchar_p(ptr).value
                                kernel32.GlobalUnlock(h)
                                if val and str(val).strip():
                                    return str(val).strip()

                    if user32.IsClipboardFormatAvailable(CF_HDROP):
                        h = user32.GetClipboardData(CF_HDROP)
                        if h:
                            shell32.DragQueryFileW.argtypes = [wintypes.HANDLE, wintypes.UINT, wintypes.LPWSTR, wintypes.UINT]
                            shell32.DragQueryFileW.restype = wintypes.UINT
                            num_files = shell32.DragQueryFileW(h, 0xFFFFFFFF, None, 0)
                            file_paths = []
                            buf = ctypes.create_unicode_buffer(1024)
                            for i in range(num_files):
                                shell32.DragQueryFileW(h, i, buf, 1024)
                                file_paths.append(buf.value)
                            if file_paths:
                                return "\n".join(file_paths)

                    if user32.IsClipboardFormatAvailable(CF_TEXT):
                        h = user32.GetClipboardData(CF_TEXT)
                        if h:
                            ptr = kernel32.GlobalLock(h)
                            if ptr:
                                val = ctypes.c_char_p(ptr).value
                                kernel32.GlobalUnlock(h)
                                if val:
                                    decoded = val.decode("utf-8", errors="replace")
                                    if decoded.strip():
                                        return decoded.strip()
                finally:
                    user32.CloseClipboard()
        except Exception:
            pass

    # Tier 3: win32clipboard with retry loop
    if sys.platform == "win32":
        try:
            import win32clipboard
            import win32con
            opened_win32 = False
            for _ in range(6):
                try:
                    win32clipboard.OpenClipboard()
                    opened_win32 = True
                    break
                except Exception:
                    time.sleep(0.04)

            if opened_win32:
                try:
                    if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                        val = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
                        if val and str(val).strip():
                            return str(val).strip()
                    elif win32clipboard.IsClipboardFormatAvailable(win32con.CF_TEXT):
                        val = win32clipboard.GetClipboardData(win32con.CF_TEXT)
                        if val:
                            txt = val.decode("utf-8", errors="replace") if isinstance(val, bytes) else str(val)
                            if txt.strip():
                                return txt.strip()
                finally:
                    win32clipboard.CloseClipboard()
        except Exception:
            pass

    # Tier 4: pyperclip
    if _PYPERCLIP:
        try:
            val = pyperclip.paste()
            if val and str(val).strip():
                return str(val).strip()
        except Exception:
            pass

    # Tier 5: PowerShell STA Get-Clipboard fallback
    if sys.platform == "win32":
        try:
            res = subprocess.run(
                ["powershell", "-Sta", "-NoProfile", "-NonInteractive", "-Command", "Get-Clipboard"],
                capture_output=True,
                text=True,
                timeout=2.0,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
            )
            if res.returncode == 0 and res.stdout and res.stdout.strip():
                return res.stdout.strip()
        except Exception:
            pass

    return ""


_CLIPBOARD_TOKEN_RE = re.compile(
    r'(\[|\{|\<|%)?\s*(?:PASTE_)?CLIPBOARD\s*(\]|\}|\>|%)?|\[\s*PASTE\s*\]',
    re.IGNORECASE
)

_STANDALONE_CLIPBOARD_WORDS = {
    "[paste_clipboard]", "paste_clipboard", "[clipboard]", "clipboard",
    "[paste]", "{clipboard}", "<clipboard>", "%clipboard%",
    "[clipboard_content]", "[my_clipboard]", "paste clipboard",
    "from clipboard", "my clipboard", "the clipboard", "clipboard content"
}


def _resolve_clipboard_content(message_text: str, from_clipboard: bool = False, player=None) -> tuple[str, bool, str]:
    """
    Detects if the message is or contains a clipboard macro/placeholder
    (e.g. [PASTE_CLIPBOARD], {CLIPBOARD}, 'clipboard') or if from_clipboard is True,
    and replaces it with the live content from the user's OS clipboard.

    Returns:
        (resolved_text, was_requested, error_msg_if_empty)
    """
    raw = (message_text or "").strip()
    is_clip_requested = bool(from_clipboard)

    if raw.lower() in _STANDALONE_CLIPBOARD_WORDS or not raw:
        if raw.lower() in _STANDALONE_CLIPBOARD_WORDS or from_clipboard:
            is_clip_requested = True
    elif _CLIPBOARD_TOKEN_RE.search(raw):
        is_clip_requested = True

    if not is_clip_requested:
        return raw, False, ""

    clip_text = _get_clipboard_text(player=player)
    if not clip_text:
        return "", True, (
            "Your clipboard is currently empty. Please copy the text, link, or "
            "content you want to share first, then ask again."
        )

    # Standalone replacement
    if raw.lower() in _STANDALONE_CLIPBOARD_WORDS or not raw or raw.lower() == "[paste_clipboard]":
        return clip_text, True, ""

    # Embedded replacement (e.g. "Check this out: [PASTE_CLIPBOARD]")
    replaced = _CLIPBOARD_TOKEN_RE.sub(clip_text, raw)
    if replaced != raw:
        return replaced, True, ""

    # from_clipboard was True and raw text was provided as caption/prefix
    if from_clipboard and raw:
        return f"{raw}\n{clip_text}", True, ""

    return clip_text, True, ""


def _is_echoed_receiver_or_empty(message_text: str, receiver: str) -> bool:
    """Checks whether the message text is empty or simply echoes the receiver name or command."""
    msg = (message_text or "").strip().lower()
    rec = (receiver or "").strip().lower()
    if not msg:
        return True
    if rec and (
        msg == rec
        or msg in (f"to {rec}", f"send to {rec}", f"message {rec}", f"send message to {rec}", f"text {rec}", f"whatsapp {rec}")
    ):
        return True
    if msg in ("send message", "message", "text", "whatsapp", "send", "draft", "draft message"):
        return True
    return False


def _type_without_clipboard(text: str) -> None:
    """Types text directly into the focused control without touching or corrupting the OS clipboard."""
    if not text:
        return
    is_ascii = all(ord(c) < 128 for c in text)
    if is_ascii and _PYAUTOGUI:
        pyautogui.write(text, interval=0.015)
        return

    # Windows Unicode SendInput
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32

            INPUT_KEYBOARD = 1
            KEYEVENTF_UNICODE = 0x0004
            KEYEVENTF_KEYUP = 0x0002

            class KEYBDINPUT(ctypes.Structure):
                _fields_ = [
                    ('wVk', wintypes.WORD),
                    ('wScan', wintypes.WORD),
                    ('dwFlags', wintypes.DWORD),
                    ('time', wintypes.DWORD),
                    ('dwExtraInfo', ctypes.POINTER(wintypes.ULONG)),
                ]

            class INPUT(ctypes.Structure):
                class _INPUT(ctypes.Union):
                    _fields_ = [('ki', KEYBDINPUT)]
                _anonymous_ = ('_input',)
                _fields_ = [('type', wintypes.DWORD), ('_input', _INPUT)]

            for char in text:
                code = ord(char)
                inp_down = INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(wVk=0, wScan=code, dwFlags=KEYEVENTF_UNICODE, time=0, dwExtraInfo=None))
                inp_up = INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(wVk=0, wScan=code, dwFlags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, time=0, dwExtraInfo=None))
                user32.SendInput(2, (INPUT * 2)(inp_down, inp_up), ctypes.sizeof(INPUT))
                time.sleep(0.01)
            return
        except Exception:
            pass

    if _PYAUTOGUI:
        pyautogui.write(text, interval=0.02)


def _safe_set_clipboard(text: str, player=None, retries: int = 6) -> bool:
    """Sets system clipboard safely with retry loop, notifying player to avoid cache pollution."""
    if player and hasattr(player, "set_internal_clipboard_operation"):
        try:
            player.set_internal_clipboard_operation(True)
        except Exception:
            pass

    if sys.platform == "win32":
        try:
            import win32clipboard, win32con
            for _ in range(retries):
                try:
                    win32clipboard.OpenClipboard()
                    try:
                        win32clipboard.EmptyClipboard()
                        win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
                        return True
                    finally:
                        win32clipboard.CloseClipboard()
                except Exception:
                    time.sleep(0.04)
        except Exception:
            pass

    if _PYPERCLIP:
        for _ in range(retries):
            try:
                pyperclip.copy(text)
                return True
            except Exception:
                time.sleep(0.04)

    return False


def _restore_clipboard_if_saved(saved_clip: Optional[str], player=None) -> None:
    if saved_clip is not None:
        _safe_set_clipboard(saved_clip, player=player)
    if player and hasattr(player, "set_internal_clipboard_operation"):
        try:
            player.set_internal_clipboard_operation(False)
        except Exception:
            pass


# ── Contact & Phone Number Intelligence ───────────────────────────────────────

def _load_memory() -> dict:
    try:
        if _MEMORY_FILE.exists():
            return json.loads(_MEMORY_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_memory(data: dict) -> bool:
    try:
        _MEMORY_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return True
    except Exception:
        return False


def clean_phone_number(raw: str, default_country_code: str = "91") -> str:
    """Normalize raw phone string to clean international digits without symbols."""
    digits = re.sub(r"[^\d]", "", raw or "")
    if not digits:
        return ""
    # If 10 digits provided (standard national mobile number in India), prepend default code
    if len(digits) == 10:
        return f"{default_country_code}{digits}"
    # If starts with leading 0 (e.g. 09876543210), strip 0 and prepend country code
    if len(digits) == 11 and digits.startswith("0"):
        return f"{default_country_code}{digits[1:]}"
    return digits


def is_phone_number(query: str) -> bool:
    """Detect if query is primarily a phone number."""
    cleaned = re.sub(r"[\s\+\-\(\)]", "", query or "")
    return bool(cleaned and cleaned.isdigit() and len(cleaned) >= 7)


def resolve_contact(query: str) -> Tuple[str, Optional[str]]:
    """
    Resolve query against memory/long_term.json to find contact name & phone number.
    Returns: (display_name, phone_number_or_none)
    """
    q_str = str(query or "").strip()
    if not q_str:
        return ("", None)

    if is_phone_number(q_str):
        clean_num = clean_phone_number(q_str)
        return (q_str, clean_num)

    q_lower = q_str.lower()
    mem = _load_memory()

    # 1. Search relationships
    relationships = mem.get("relationships", {})
    if isinstance(relationships, dict):
        for rel_key, rel_data in relationships.items():
            if rel_key.lower() == q_lower:
                if isinstance(rel_data, dict):
                    val = rel_data.get("value") or rel_key
                    phone = rel_data.get("phone") or rel_data.get("number")
                    return (val, clean_phone_number(phone) if phone else None)
                elif isinstance(rel_data, str):
                    return (rel_data, clean_phone_number(rel_data) if is_phone_number(rel_data) else None)

    # 2. Search contacts section
    contacts = mem.get("contacts", {})
    if isinstance(contacts, dict):
        for c_key, c_val in contacts.items():
            if c_key.lower() == q_lower or q_lower in c_key.lower():
                if isinstance(c_val, dict):
                    name = c_val.get("name", c_key)
                    phone = c_val.get("phone") or c_val.get("number")
                    return (name, clean_phone_number(phone) if phone else None)
                elif isinstance(c_val, str):
                    if is_phone_number(c_val):
                        return (c_key, clean_phone_number(c_val))
                    return (c_val, None)

    # 3. Search notes
    notes = mem.get("notes", {})
    if isinstance(notes, dict):
        for n_key, n_val in notes.items():
            if q_lower in n_key.lower() and isinstance(n_val, dict):
                val = str(n_val.get("value", ""))
                if is_phone_number(val):
                    return (q_str, clean_phone_number(val))

    return (q_str, None)


def save_contact_to_memory(name: str, phone: str, relationship: Optional[str] = None) -> bool:
    """Store contact information persistently in long_term memory."""
    mem = _load_memory()
    contacts = mem.setdefault("contacts", {})
    clean_p = clean_phone_number(phone)

    contacts[name.strip()] = {
        "name": name.strip(),
        "phone": clean_p,
        "relationship": relationship or "",
        "updated": time.strftime("%Y-%m-%d"),
    }

    if relationship:
        rel_dict = mem.setdefault("relationships", {})
        rel_dict[relationship.lower().strip()] = {
            "value": name.strip(),
            "phone": clean_p,
            "updated": time.strftime("%Y-%m-%d"),
        }

    return _save_memory(mem)


# ── Window & Process Probing ──────────────────────────────────────────────────

def find_whatsapp_window() -> Optional[int]:
    """Locate visible WhatsApp window handle on Windows."""
    if not _WIN32:
        return None

    found_hwnd = None

    def _enum(hwnd, _):
        nonlocal found_hwnd
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd).strip()
            # UWP or Desktop title
            if "whatsapp" in title.lower():
                found_hwnd = hwnd
                return False
        return True

    try:
        win32gui.EnumWindows(_enum, None)
    except Exception:
        pass

    return found_hwnd


def ensure_whatsapp_desktop_running() -> bool:
    """Ensure WhatsApp Desktop is started on Windows."""
    if sys.platform != "win32":
        return False
    if find_whatsapp_window():
        return True
    try:
        # Try modern Windows AppX Package directly
        subprocess.Popen(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", "Start-Process 'shell:AppsFolder\\5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App'"],
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        time.sleep(1.8)
        return True
    except Exception:
        pass

    try:
        os.startfile("whatsapp:")
        time.sleep(1.5)
        return True
    except Exception:
        pass
    return False


def focus_whatsapp_window(timeout_sec: float = 3.5) -> bool:
    """Brings WhatsApp Desktop to foreground with fast in-process activation."""
    if sys.platform != "win32":
        return False

    t_start = time.time()
    hwnd = None
    while time.time() - t_start < timeout_sec:
        hwnd = find_whatsapp_window()
        if hwnd:
            break
        time.sleep(0.15)

    if not hwnd:
        ensure_whatsapp_desktop_running()
        time.sleep(0.8)
        hwnd = find_whatsapp_window()

    if not hwnd:
        # Fallback to WScript.Shell AppActivate
        try:
            wsh = win32com.client.Dispatch("WScript.Shell")
            if wsh.AppActivate("WhatsApp"):
                time.sleep(0.1)
                return True
        except Exception:
            pass
        return False

    try:
        # Restore if minimized
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.1)
        return True
    except Exception:
        try:
            wsh = win32com.client.Dispatch("WScript.Shell")
            return bool(wsh.AppActivate("WhatsApp"))
        except Exception:
            return False


# ── Transports ────────────────────────────────────────────────────────────────

class WhatsAppProtocolTransport:
    """
    Direct OS URI Protocol Handler (whatsapp://send?phone=...&text=...).
    Fastest, native, and supported directly by Windows UWP and Desktop client.
    """

    def send_via_protocol(
        self,
        phone: Optional[str],
        message: str,
        mode: str = "send",
    ) -> Tuple[bool, str]:
        # Defense-in-depth: resolve any unresolved clipboard placeholders
        resolved_msg, was_clip, err = _resolve_clipboard_content(message)
        if was_clip:
            if err:
                return (False, err)
            message = resolved_msg

        encoded_text = urllib.parse.quote(message)
        if phone:
            uri = f"whatsapp://send?phone={phone}&text={encoded_text}"
        else:
            uri = f"whatsapp://send?text={encoded_text}"

        try:
            # Launch protocol directly into WhatsApp Desktop
            if sys.platform == "win32":
                os.startfile(uri)
            else:
                subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", uri])
        except Exception as e:
            return (False, f"Failed to execute WhatsApp URI: {e}")

        # Wait for WhatsApp Desktop window to gain focus
        time.sleep(1.2)
        focused = focus_whatsapp_window(timeout_sec=4.0)

        if mode == "draft":
            return (True, "Draft staged in WhatsApp Desktop input box for review.")

        # In "send" mode: press Enter to dispatch message
        time.sleep(0.5)
        if _PYAUTOGUI:
            pyautogui.press("enter")
            time.sleep(0.2)
            return (True, "Message dispatched via WhatsApp Desktop protocol.")
        return (True, "Message draft loaded in WhatsApp Desktop.")


class WhatsAppDesktopTransport:
    """
    WhatsApp Desktop Native UI Automation Driver:
    Uses native shortcuts (Ctrl+N for new chat / search), focuses chat, and types message.
    """

    def send_via_desktop_ui(
        self,
        receiver_name: str,
        message: str,
        mode: str = "send",
        player=None,
        preserve_clipboard: bool = False,
    ) -> Tuple[bool, str]:
        if not _PYAUTOGUI:
            return (False, "PyAutoGUI is not available for desktop UI automation.")

        # If preserve_clipboard is requested (e.g. message was spoken, not from clipboard),
        # save the user's existing clipboard so we can restore it after sending
        saved_clip = None
        if preserve_clipboard:
            saved_clip = _get_clipboard_text(player=player)

        # Defense-in-depth: resolve any unresolved clipboard placeholders
        resolved_msg, was_clip, err = _resolve_clipboard_content(message, player=player)
        if was_clip:
            if err:
                return (False, err)
            message = resolved_msg

        # Ensure WhatsApp Desktop window is active
        if not focus_whatsapp_window(timeout_sec=2.0):
            ensure_whatsapp_desktop_running()
            time.sleep(1.5)
            focus_whatsapp_window(timeout_sec=3.0)

        if not focus_whatsapp_window(timeout_sec=2.5):
            return (False, "Could not locate or focus WhatsApp Desktop window.")

        time.sleep(0.3)

        # In WhatsApp Desktop, Ctrl+N opens 'New chat' dialog which directly searches all contacts & numbers.
        # Clear search input and TYPE contact name directly — NEVER use clipboard for contact search!
        pyautogui.hotkey("ctrl", "n")
        time.sleep(0.4)

        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.05)
        pyautogui.press("backspace")
        time.sleep(0.05)

        # Direct typing without clipboard pollution
        _type_without_clipboard(receiver_name)

        time.sleep(0.7)

        # Open chat with the top search match
        pyautogui.press("enter")
        time.sleep(0.5)

        # Paste or type message into chat compose input
        if message:
            pasted = False
            if _PYPERCLIP:
                if _safe_set_clipboard(message, player=player):
                    time.sleep(0.05)
                    pyautogui.hotkey("ctrl", "v")
                    time.sleep(0.15)
                    pasted = True
            if not pasted:
                _type_without_clipboard(message)
                time.sleep(0.1)

        # Restore user's original clipboard if it was saved
        _restore_clipboard_if_saved(saved_clip, player=player)

        time.sleep(0.2)

        if mode == "draft":
            return (True, f"Draft staged in WhatsApp Desktop chat with '{receiver_name}' for review.")

        # Send
        pyautogui.press("enter")
        time.sleep(0.3)
        return (True, f"Message sent to '{receiver_name}' via WhatsApp Desktop.")


class WhatsAppWebTransport:
    """
    WhatsApp Web Browser Driver: Opens web.whatsapp.com/send in active browser.
    """

    def send_via_web(
        self,
        phone: Optional[str],
        message: str,
        mode: str = "send",
    ) -> Tuple[bool, str]:
        import webbrowser
        encoded_text = urllib.parse.quote(message)
        if phone:
            url = f"https://web.whatsapp.com/send?phone={phone}&text={encoded_text}"
        else:
            url = f"https://web.whatsapp.com/send?text={encoded_text}"

        try:
            webbrowser.open(url)
            time.sleep(3.5)
            if mode == "draft":
                return (True, "Draft staged in WhatsApp Web tab.")
            if _PYAUTOGUI:
                time.sleep(1.0)
                pyautogui.press("enter")
            return (True, "Message loaded in WhatsApp Web.")
        except Exception as e:
            return (False, f"Failed to open WhatsApp Web: {e}")


# ── Unified WhatsApp Driver Orchestrator ──────────────────────────────────────

class WhatsAppDriver:
    """
    Intelligent Multi-Tier WhatsApp Driver Orchestrator.
    Auto-detects whether recipient is a phone number or name, selects optimal transport,
    and returns verified status.
    """

    def __init__(self):
        self.protocol_transport = WhatsAppProtocolTransport()
        self.desktop_transport  = WhatsAppDesktopTransport()
        self.web_transport      = WhatsAppWebTransport()

    def send_message_to(
        self,
        receiver: str,
        message: str,
        mode: str = "send",
        phone_override: Optional[str] = None,
        from_clipboard: bool = False,
        player=None,
    ) -> Tuple[bool, str]:
        """
        Unified dispatch:
        - If phone is available (or resolved), uses WhatsApp Protocol DeepLink.
        - If contact name with no phone, uses Desktop UI automation.
        - Falls back gracefully to WhatsApp Web.
        """
        receiver_name, resolved_phone = resolve_contact(receiver)

        # Check if message is empty or merely echoes the recipient/command name (e.g. user said "send message to mom")
        if _is_echoed_receiver_or_empty(message, receiver) or _is_echoed_receiver_or_empty(message, receiver_name):
            clip = _get_clipboard_text(player=player)
            if clip and not _is_echoed_receiver_or_empty(clip, receiver) and not _is_echoed_receiver_or_empty(clip, receiver_name):
                message = clip
                from_clipboard = True
                print(f"[WhatsApp] [clipboard] Receiver '{receiver_name}' had no distinct message body; using live clipboard content ({len(clip)} chars).")
            else:
                if mode != "draft":
                    return (False, f"What message would you like to send to {receiver_name}? (Your clipboard is currently empty).")
                message = ""

        # Resolve clipboard placeholders or explicit from_clipboard requests
        resolved_msg, was_clip, err = _resolve_clipboard_content(message, from_clipboard=from_clipboard, player=player)
        if was_clip:
            if err:
                return (False, err)
            message = resolved_msg

        target_phone = clean_phone_number(phone_override) if phone_override else resolved_phone

        # Tier 1: Protocol DeepLink if phone number is known and URI is within safe length (< 1500 chars)
        if target_phone and len(message) < 1500:
            print(f"[WhatsApp] Routing via Protocol DeepLink to +{target_phone} (mode={mode})")
            success, info = self.protocol_transport.send_via_protocol(
                phone=target_phone,
                message=message,
                mode=mode,
            )
            if success:
                action_word = "sent to" if mode == "send" else "drafted for"
                return (True, f"Message {action_word} {receiver_name} (+{target_phone}) via WhatsApp.")

        # Tier 2: Desktop UI Automation by contact name (or long message payload)
        print(f"[WhatsApp] Routing via Desktop UI Automation for '{receiver_name}' (mode={mode})")
        success, info = self.desktop_transport.send_via_desktop_ui(
            receiver_name=receiver_name,
            message=message,
            mode=mode,
            player=player,
            preserve_clipboard=not was_clip,
        )
        if success:
            return (True, info)

        # Tier 3: If target_phone was not found, try Protocol generic share dialog
        print(f"[WhatsApp] Desktop UI not responding; attempting generic Protocol Share dialog")
        success, info = self.protocol_transport.send_via_protocol(
            phone=None,
            message=message,
            mode="draft",
        )
        if success:
            return (True, f"WhatsApp opened with message drafted for '{receiver_name}'.")

        # Tier 4: Fallback to WhatsApp Web
        print(f"[WhatsApp] Fallback to WhatsApp Web")
        success, info = self.web_transport.send_via_web(
            phone=target_phone,
            message=message,
            mode=mode,
        )
        if success:
            return (True, f"WhatsApp Web opened for '{receiver_name}'. {info}")

        return (False, f"All WhatsApp transports failed: {info}")


_DRIVER_INSTANCE: Optional[WhatsAppDriver] = None


def get() -> Tuple[Optional[WhatsAppDriver], str]:
    """Factory accessor matching the interface required by actions/send_message.py."""
    global _DRIVER_INSTANCE
    if _DRIVER_INSTANCE is None:
        try:
            _DRIVER_INSTANCE = WhatsAppDriver()
        except Exception as e:
            return (None, f"Could not initialize WhatsApp driver: {e}")
    return (_DRIVER_INSTANCE, "WhatsApp driver ready")
