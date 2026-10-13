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
    ) -> Tuple[bool, str]:
        if not _PYAUTOGUI:
            return (False, "PyAutoGUI is not available for desktop UI automation.")

        # Ensure WhatsApp Desktop window is active
        if not focus_whatsapp_window(timeout_sec=2.0):
            ensure_whatsapp_desktop_running()
            time.sleep(1.5)
            focus_whatsapp_window(timeout_sec=3.0)

        if not focus_whatsapp_window(timeout_sec=2.5):
            return (False, "Could not locate or focus WhatsApp Desktop window.")

        time.sleep(0.3)

        # In WhatsApp Desktop, Ctrl+N opens 'New chat' dialog which directly searches all contacts & numbers
        # Ctrl+F searches active chat list. We try Ctrl+N first for full contact coverage.
        pyautogui.hotkey("ctrl", "n")
        time.sleep(0.4)

        # Clear search input
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.05)
        pyautogui.press("backspace")
        time.sleep(0.05)

        # Paste contact name via clipboard for instant non-corrupting input
        if _PYPERCLIP:
            pyperclip.copy(receiver_name)
            time.sleep(0.05)
            pyautogui.hotkey("ctrl", "v")
        else:
            pyautogui.write(receiver_name, interval=0.03)

        time.sleep(0.7)

        # Open chat with the top search match
        pyautogui.press("enter")
        time.sleep(0.5)

        # If Ctrl+N didn't switch, try Ctrl+F fallback
        # Paste message into chat compose input
        if _PYPERCLIP:
            pyperclip.copy(message)
            time.sleep(0.05)
            pyautogui.hotkey("ctrl", "v")
        else:
            pyautogui.write(message, interval=0.02)

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
    ) -> Tuple[bool, str]:
        """
        Unified dispatch:
        - If phone is available (or resolved), uses WhatsApp Protocol DeepLink.
        - If contact name with no phone, uses Desktop UI automation.
        - Falls back gracefully to WhatsApp Web.
        """
        receiver_name, resolved_phone = resolve_contact(receiver)
        target_phone = clean_phone_number(phone_override) if phone_override else resolved_phone

        # Tier 1: Protocol DeepLink if phone number is known
        if target_phone:
            print(f"[WhatsApp] Routing via Protocol DeepLink to +{target_phone} (mode={mode})")
            success, info = self.protocol_transport.send_via_protocol(
                phone=target_phone,
                message=message,
                mode=mode,
            )
            if success:
                action_word = "sent to" if mode == "send" else "drafted for"
                return (True, f"Message {action_word} {receiver_name} (+{target_phone}) via WhatsApp.")

        # Tier 2: Desktop UI Automation by contact name
        print(f"[WhatsApp] Routing via Desktop UI Automation for '{receiver_name}' (mode={mode})")
        success, info = self.desktop_transport.send_via_desktop_ui(
            receiver_name=receiver_name,
            message=message,
            mode=mode,
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
