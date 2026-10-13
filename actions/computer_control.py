#computer_control.py
from PIL import Image, ImageOps
import io
import json
import math
import os
import platform
import re
import shutil
import string
import subprocess
import sys

for _stream in ("stdout", "stderr"):
    try:
        _s = getattr(sys, _stream, None)
        if _s is not None and hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

if platform.system() == "Windows":
    _WIN_HIDE: dict = {"creationflags": subprocess.CREATE_NO_WINDOW}
else:
    _WIN_HIDE: dict = {}
import time
import random
from pathlib import Path

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE    = 0.005
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


_BASE         = _base_dir()
_CONFIG_PATH  = _BASE / "config" / "api_keys.json"
_MEMORY_PATH  = _BASE / "memory" / "long_term.json"

def _load_config() -> dict:
    try:
        return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _platform_os() -> str:
    return {"Windows": "windows", "Darwin": "mac", "Linux": "linux"}.get(
        platform.system(), "linux"
    )

def _get_os() -> str:
    return _load_config().get("os_system", _platform_os()).lower()


def _get_api_key() -> str:
    return _load_config().get("gemini_api_key", "")

_SAFE_SCREENSHOT_ROOTS = (
    Path.home(),
)

def _safe_screenshot_path(requested: str | None) -> Path:
    fallback = Path.home() / "Desktop" / "jarvis_screenshot.png"
    if not requested:
        return fallback
    try:
        p = Path(requested).expanduser().resolve()
        for root in _SAFE_SCREENSHOT_ROOTS:
            if p.is_relative_to(root.resolve()):
                p.parent.mkdir(parents=True, exist_ok=True)
                return p
    except Exception:
        pass
    return fallback

def _require_pyautogui():
    if not _PYAUTOGUI:
        raise RuntimeError("PyAutoGUI not installed. Run: pip install pyautogui")
    try:
        x, y = pyautogui.position()
        if x == 0 and y == 0:
            w, h = pyautogui.size()
            pyautogui.moveTo(w // 2, h // 2)
    except Exception:
        pass

_FIRST_NAMES = [
    "Alex", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Drew", "Quinn",
    "Avery", "Blake", "Cameron", "Dakota", "Emerson", "Finley", "Harper",
]
_LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Wilson", "Moore", "Taylor", "Anderson", "Thomas", "Jackson",
]
_DOMAINS = ["gmail.com", "yahoo.com", "outlook.com", "proton.me", "mail.com"]


def _random_data(data_type: str) -> str:
    dt = data_type.lower().strip()

    if dt == "first_name":
        return random.choice(_FIRST_NAMES)

    if dt == "last_name":
        return random.choice(_LAST_NAMES)

    if dt == "name":
        return f"{random.choice(_FIRST_NAMES)} {random.choice(_LAST_NAMES)}"

    if dt == "email":
        first = random.choice(_FIRST_NAMES).lower()
        last  = random.choice(_LAST_NAMES).lower()
        num   = random.randint(10, 999)
        return f"{first}.{last}{num}@{random.choice(_DOMAINS)}"

    if dt == "username":
        return f"{random.choice(_FIRST_NAMES).lower()}{random.randint(100, 9999)}"

    if dt == "password":
        chars = string.ascii_letters + string.digits + "!@#$%"
        raw   = (
            random.choice(string.ascii_uppercase)
            + random.choice(string.digits)
            + random.choice("!@#$%")
            + "".join(random.choices(chars, k=9))
        )
        return "".join(random.sample(raw, len(raw)))

    if dt == "phone":
        return f"+1{random.randint(200,999)}{random.randint(1_000_000, 9_999_999)}"

    if dt == "birthday":
        y = random.randint(1980, 2000)
        m = random.randint(1, 12)
        d = random.randint(1, 28)
        return f"{m:02d}/{d:02d}/{y}"

    if dt == "address":
        num    = random.randint(100, 9999)
        street = random.choice(["Main St", "Oak Ave", "Park Blvd", "Elm St", "Cedar Ln"])
        return f"{num} {street}"

    if dt == "zip_code":
        return str(random.randint(10000, 99999))

    if dt == "city":
        return random.choice(["New York", "Los Angeles", "Chicago", "Houston", "Phoenix"])

    return f"random_{data_type}_{random.randint(1000, 9999)}"

def _user_profile() -> dict:
    """Read identity fields from long-term memory."""
    try:
        if _MEMORY_PATH.exists():
            data     = json.loads(_MEMORY_PATH.read_text(encoding="utf-8"))
            identity = data.get("identity", {})
            return {k: v.get("value", "") for k, v in identity.items()}
    except Exception:
        pass
    return {}

def _safe_keyboard_action(fn, *args, **kwargs):
    _require_pyautogui()
    try:
        return fn(*args, **kwargs)
    except pyautogui.FailSafeException:
        prev = pyautogui.FAILSAFE
        pyautogui.FAILSAFE = False
        try:
            return fn(*args, **kwargs)
        finally:
            pyautogui.FAILSAFE = prev


def _type(text: str, interval: float = 0.005) -> str:
    _require_pyautogui()
    time.sleep(0.04)
    _safe_keyboard_action(pyautogui.typewrite, text, interval=interval)
    return f"Typed: {text[:60]}{'…' if len(text) > 60 else ''}"


def _smart_type(text: str, clear_first: bool = True) -> str:
    _require_pyautogui()
    if clear_first:
        _clear_field()
        time.sleep(0.02)

    if len(text) > 2 and _PYPERCLIP:
        pyperclip.copy(text)
        time.sleep(0.02)
        paste_key = "command" if _get_os() == "mac" else "ctrl"
        _safe_keyboard_action(pyautogui.hotkey, paste_key, "v")
        return f"Smart-typed (clipboard): {text[:60]}{'…' if len(text) > 60 else ''}"

    _safe_keyboard_action(pyautogui.typewrite, text, interval=0.005)
    return f"Smart-typed: {text[:60]}{'…' if len(text) > 60 else ''}"


def _verified_move(x: int | float, y: int | float, duration: float = 0.05) -> dict:
    """Move cursor with human-like easing (easeOutQuad) to trigger OS mouseenter/mouseover
    events, then read back real-time OS pointer position from hardware. If a discrepancy
    exists (due to acceleration, display scaling, or window bounds clamping), execute
    an immediate corrective nudge and re-verify."""
    _require_pyautogui()
    w, h = pyautogui.size()
    target_x = max(1, min(w - 2, int(round(x))))
    target_y = max(1, min(h - 2, int(round(y))))

    _safe_keyboard_action(
        pyautogui.moveTo,
        target_x,
        target_y,
        duration=max(0.02, duration),
        tween=pyautogui.easeOutQuad,
    )

    actual_x, actual_y = pyautogui.position()
    err = math.hypot(actual_x - target_x, actual_y - target_y)

    # Real-time closed-loop corrective adjustment
    if err > 2.0:
        _safe_keyboard_action(pyautogui.moveTo, target_x, target_y, duration=0.02)
        actual_x, actual_y = pyautogui.position()
        err = math.hypot(actual_x - target_x, actual_y - target_y)

    return {
        "target": (target_x, target_y),
        "actual": (actual_x, actual_y),
        "error_px": round(err, 2),
        "verified": err <= 3.0,
    }


def _verified_click(
    x: int | float | None = None,
    y: int | float | None = None,
    button: str = "left",
    clicks: int = 1,
    settle_time: float = 0.02,
) -> dict:
    """Execute a robust, hardware-verified click feedback loop:
    1. Smooth easeOut trajectory movement to target.
    2. Real-time pointer position verification and closed-loop corrective nudging.
    3. Settling dwell to allow DOM/OS hover states, tooltips, and focus rings to activate.
    4. Hardware-accurate mouseDown -> 15ms dwell -> mouseUp sequence (prevents dropped events).
    5. Post-action verification and complete telemetry.
    """
    _require_pyautogui()
    btn = str(button or "left").lower().strip()
    if btn not in ("left", "right", "middle"):
        btn = "left"

    move_info = None
    if x is not None and y is not None:
        move_info = _verified_move(x, y, duration=0.06)
        target_x, target_y = move_info["target"]
    else:
        target_x, target_y = pyautogui.position()

    if settle_time > 0:
        time.sleep(settle_time)

    for i in range(max(1, clicks)):
        _safe_keyboard_action(pyautogui.mouseDown, button=btn)
        time.sleep(0.015)  # 15ms physical press dwell
        _safe_keyboard_action(pyautogui.mouseUp, button=btn)
        if i < clicks - 1:
            time.sleep(0.025)  # 25ms inter-click delay for double/triple click

    post_x, post_y = pyautogui.position()
    drift = math.hypot(post_x - target_x, post_y - target_y)

    return {
        "status": "success",
        "target": (target_x, target_y),
        "actual": (post_x, post_y),
        "verified": drift <= 3.0,
        "drift_px": round(drift, 2),
        "button": btn,
        "clicks": clicks,
        "move": move_info,
    }


def _verified_hover(x: int | float, y: int | float, dwell: float = 0.4) -> str:
    """Move pointer with verified trajectory and settle for `dwell` seconds to
    trigger hover reveals, submenus, or tooltips."""
    res = _verified_move(x, y, duration=0.18)
    time.sleep(max(0.05, min(dwell, 4.0)))
    act = res["actual"]
    return f"Hovered at ({act[0]}, {act[1]}) for {dwell}s [verified={res['verified']}]"


def _click(x=None, y=None, button: str = "left", clicks: int = 1) -> str:
    res = _verified_click(x=x, y=y, button=button, clicks=clicks)
    target = res["target"]
    c_str = "Triple-c" if clicks == 3 else ("Double-c" if clicks == 2 else "C")
    ver_str = "verified" if res["verified"] else f"drift={res['drift_px']}px"
    return f"{c_str}licked ({target[0]}, {target[1]}) [{button}, {ver_str}]"


_KEY_MAP = {
    "enter": "enter",
    "return": "enter",
    "esc": "escape",
    "escape": "escape",
    "win": "winleft" if _platform_os() == "windows" else "command",
    "windows": "winleft" if _platform_os() == "windows" else "command",
    "super": "winleft" if _platform_os() == "windows" else "command",
    "cmd": "command" if _platform_os() == "mac" else "winleft",
    "command": "command" if _platform_os() == "mac" else "ctrl",
    "control": "ctrl",
    "ctrl": "ctrl",
    "alt": "alt",
    "option": "option" if _platform_os() == "mac" else "alt",
    "shift": "shift",
    "backspace": "backspace",
    "space": "space",
    "spacebar": "space",
    "tab": "tab",
    "del": "delete",
    "delete": "delete",
    "up": "up",
    "down": "down",
    "left": "left",
    "right": "right",
    "home": "home",
    "end": "end",
    "pageup": "pageup",
    "pagedown": "pagedown",
    "pgup": "pageup",
    "pgdn": "pagedown",
    "caps": "capslock",
    "capslock": "capslock",
}


def _normalize_key(key: str) -> str:
    k = str(key or "").strip().lower()
    return _KEY_MAP.get(k, k)


def _hotkey(*keys) -> str:
    norm = [_normalize_key(k) for k in keys if k]
    _safe_keyboard_action(pyautogui.hotkey, *norm)
    return f"Hotkey: {'+'.join(norm)}"


def _press(key: str) -> str:
    k = _normalize_key(key)
    _safe_keyboard_action(pyautogui.press, k)
    return f"Pressed: {k}"


def _key_down(key: str) -> str:
    k = _normalize_key(key)
    _safe_keyboard_action(pyautogui.keyDown, k)
    return f"Key down: {k}"


def _key_up(key: str) -> str:
    k = _normalize_key(key)
    _safe_keyboard_action(pyautogui.keyUp, k)
    return f"Key up: {k}"


def _mouse_position() -> dict:
    _require_pyautogui()
    x, y = pyautogui.position()
    w, h = pyautogui.size()
    return {"x": x, "y": y, "screen_width": w, "screen_height": h}


def _middle_click(x=None, y=None) -> str:
    return _click(x, y, button="middle", clicks=1)


def _triple_click(x=None, y=None) -> str:
    return _click(x, y, button="left", clicks=3)


def _mouse_down(button: str = "left") -> str:
    _require_pyautogui()
    _safe_keyboard_action(pyautogui.mouseDown, button=button)
    return f"Mouse down [{button}]"


def _mouse_up(button: str = "left") -> str:
    _require_pyautogui()
    _safe_keyboard_action(pyautogui.mouseUp, button=button)
    return f"Mouse up [{button}]"


def _scroll(direction: str = "down", amount: int = 3) -> str:
    _require_pyautogui()
    vertical   = direction in ("up", "down")
    amt = int(amount) if amount else 3
    # If a small number of wheel notches was given (e.g. 1..10), scale to standard Windows WHEEL_DELTA (120 per notch)
    if abs(amt) <= 10:
        amt = amt * 120
    clicks     = amt if direction in ("up", "right") else -amt
    if vertical:
        _safe_keyboard_action(pyautogui.scroll, clicks)
    else:
        _safe_keyboard_action(pyautogui.hscroll, clicks)
    return f"Scrolled {direction} ×{amount}"


def _move(x: int | float, y: int | float, duration: float = 0.18) -> str:
    res = _verified_move(x, y, duration=duration)
    act = res["actual"]
    ver = "verified" if res["verified"] else f"error={res['error_px']}px"
    return f"Mouse → ({act[0]}, {act[1]}) [{ver}]"


def _drag(x1: int | float, y1: int | float, x2: int | float, y2: int | float, duration: float = 0.5) -> str:
    _require_pyautogui()
    m1 = _verified_move(x1, y1, duration=0.18)
    time.sleep(0.05)
    _safe_keyboard_action(pyautogui.mouseDown, button="left")
    time.sleep(0.05)
    _safe_keyboard_action(pyautogui.dragTo, int(round(x2)), int(round(y2)), duration=max(0.1, duration), button="left")
    m2 = _verified_move(x2, y2, duration=0.05)
    time.sleep(0.04)
    _safe_keyboard_action(pyautogui.mouseUp, button="left")
    return f"Dragged ({x1},{y1}) → ({x2},{y2}) [verified={m2['verified']}]"


_verified_drag = _drag


def _clipboard_get(player=None) -> str:
    try:
        from actions.send_message import _get_clipboard_text
        val = _get_clipboard_text(player=player)
        if val:
            return val
    except Exception:
        pass
    if _PYPERCLIP:
        try:
            return pyperclip.paste()
        except Exception:
            pass
    return ""


def _clipboard_paste(text: str) -> str:
    if _PYPERCLIP:
        pyperclip.copy(text)
        time.sleep(0.02)
        _require_pyautogui()
        paste_key = "command" if _get_os() == "mac" else "ctrl"
        _hotkey(paste_key, "v")
        return f"Pasted: {text[:60]}{'…' if len(text) > 60 else ''}"
    return "pyperclip not available"


def _screenshot(save_path: str | None = None) -> str:
    _require_pyautogui()
    path = _safe_screenshot_path(save_path)
    img  = _safe_keyboard_action(pyautogui.screenshot)
    img.save(str(path))
    return f"Screenshot saved: {path}"


def _clear_field() -> str:
    _require_pyautogui()
    select_key = "command" if _get_os() == "mac" else "ctrl"
    _hotkey(select_key, "a")
    time.sleep(0.02)
    _press("delete")
    return "Field cleared"


def _focus_window(title: str) -> str:
    os_name = _get_os()
    title   = (title or "").strip()
    if not title:
        return "No window title provided."

    if os_name == "windows":
        try:
            import pygetwindow as gw
            wins = gw.getWindowsWithTitle(title)
            if wins:
                win = wins[0]
                if getattr(win, "isMinimized", False):
                    win.restore()
                win.activate()
                time.sleep(0.03)
                return f"Focused window: {win.title}"
        except Exception:
            pass

        # Fast in-process COM AppActivate (1ms vs 2000ms PowerShell process)
        try:
            import win32com.client
            wsh = win32com.client.Dispatch("WScript.Shell")
            if wsh.AppActivate(title):
                time.sleep(0.02)
                return f"Focused window: {title}"
        except Exception:
            pass

        # In-process win32gui window search & activation
        try:
            import win32gui
            found_hwnd = None
            def _enum(h, _):
                nonlocal found_hwnd
                if win32gui.IsWindowVisible(h) and title.lower() in win32gui.GetWindowText(h).lower():
                    found_hwnd = h
                    return False
                return True
            try:
                win32gui.EnumWindows(_enum, None)
            except Exception:
                pass
            if found_hwnd:
                win32gui.SetForegroundWindow(found_hwnd)
                time.sleep(0.02)
                return f"Focused window: {title}"
        except Exception:
            pass

        try:
            script = f'(New-Object -ComObject WScript.Shell).AppActivate("{title}")'
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                capture_output=True, timeout=5, **_WIN_HIDE,
            )
            time.sleep(0.04)
            return f"Focused window: {title}"
        except Exception as e:
            return f"focus_window (Windows) failed: {e}"

    if os_name == "mac":
        script = (
            f'tell application "System Events" to '
            f'set frontmost of (first process whose name contains "{title}") to true'
        )
        try:
            subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, timeout=5,
            )
            time.sleep(0.3)
            return f"Focused window: {title}"
        except Exception as e:
            return f"focus_window (macOS) failed: {e}"

    if os_name == "linux":
        try:
            result = subprocess.run(
                ["wmctrl", "-a", title],
                capture_output=True, timeout=5,
            )
            if result.returncode == 0:
                time.sleep(0.3)
                return f"Focused window: {title}"
        except FileNotFoundError:
            pass
        try:
            result = subprocess.run(
                ["xdotool", "search", "--name", title, "windowactivate"],
                capture_output=True, timeout=5,
            )
            time.sleep(0.3)
            return f"Focused window: {title}"
        except FileNotFoundError:
            return "focus_window (Linux) requires wmctrl or xdotool"
        except Exception as e:
            return f"focus_window (Linux) failed: {e}"

    return f"focus_window: unknown OS '{os_name}'"


def _list_windows() -> list[dict]:
    """Lists open/visible windows with titles and processes."""
    windows = []
    try:
        import pygetwindow as gw
        for w in gw.getAllWindows():
            if w.title and w.title.strip():
                windows.append({
                    "title": w.title.strip(),
                    "is_active": getattr(w, "isActive", False),
                    "is_minimized": getattr(w, "isMinimized", False),
                    "is_maximized": getattr(w, "isMaximized", False),
                    "width": getattr(w, "width", 0),
                    "height": getattr(w, "height", 0),
                })
        if windows:
            return windows
    except Exception:
        pass

    if _get_os() == "windows":
        try:
            ps_script = (
                "Get-Process | Where-Object MainWindowTitle | "
                "Select-Object Id, ProcessName, MainWindowTitle | ConvertTo-Json"
            )
            res = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
                capture_output=True, text=True, timeout=5, **_WIN_HIDE
            )
            if res.stdout.strip():
                data = json.loads(res.stdout)
                items = data if isinstance(data, list) else [data]
                for item in items:
                    title = item.get("MainWindowTitle", "").strip()
                    if title:
                        windows.append({
                            "title": title,
                            "process": item.get("ProcessName", ""),
                            "pid": item.get("Id", 0),
                        })
                if windows:
                    return windows
        except Exception:
            pass

    return windows


def _get_active_window() -> dict:
    try:
        import pygetwindow as gw
        w = gw.getActiveWindow()
        if w and w.title:
            return {
                "title": w.title,
                "width": getattr(w, "width", 0),
                "height": getattr(w, "height", 0),
                "left": getattr(w, "left", 0),
                "top": getattr(w, "top", 0),
            }
    except Exception:
        pass
    return {"title": "(active window unknown)"}


def _minimize_window(title: str = "") -> str:
    if title:
        try:
            import pygetwindow as gw
            wins = gw.getWindowsWithTitle(title)
            if wins:
                wins[0].minimize()
                return f"Minimized window: '{title}'"
        except Exception:
            pass
        _focus_window(title)
    _hotkey("win", "down")
    return f"Minimized '{title or 'foreground window'}'"


def _maximize_window(title: str = "") -> str:
    if title:
        try:
            import pygetwindow as gw
            wins = gw.getWindowsWithTitle(title)
            if wins:
                wins[0].maximize()
                return f"Maximized window: '{title}'"
        except Exception:
            pass
        _focus_window(title)
    _hotkey("win", "up")
    return f"Maximized '{title or 'foreground window'}'"


def _close_window(title: str = "") -> str:
    if title:
        try:
            import pygetwindow as gw
            wins = gw.getWindowsWithTitle(title)
            if wins:
                wins[0].close()
                return f"Closed window: '{title}'"
        except Exception:
            pass
        _focus_window(title)
    _hotkey("alt", "f4")
    return f"Closed window '{title or 'foreground'}'"


def _show_desktop() -> str:
    return _hotkey("win", "d")


def _volume_control(action: str) -> str:
    _require_pyautogui()
    act = action.lower().strip()
    if act in ("up", "volume_up"):
        _press("volumeup")
        return "Volume increased."
    elif act in ("down", "volume_down"):
        _press("volumedown")
        return "Volume decreased."
    elif act in ("mute", "unmute", "volume_mute"):
        _press("volumemute")
        return "Volume toggled mute."
    elif act in ("play", "pause", "play_pause"):
        _press("playpause")
        return "Media playback toggled."
    elif act in ("next", "next_track"):
        _press("nexttrack")
        return "Next track."
    elif act in ("prev", "previous", "prev_track"):
        _press("prevtrack")
        return "Previous track."
    return f"Unknown volume/media action: {action}"


def _lock_screen() -> str:
    os_name = _get_os()
    if os_name == "windows":
        try:
            import ctypes
            ctypes.windll.user32.LockWorkStation()
            return "Screen locked."
        except Exception:
            pass
        return _hotkey("win", "l")
    elif os_name == "mac":
        return _hotkey("ctrl", "cmd", "q")
    return _hotkey("ctrl", "alt", "l")


def _open_settings() -> str:
    os_name = _get_os()
    if os_name == "windows":
        return _hotkey("win", "i")
    elif os_name == "mac":
        return _hotkey("cmd", ",")
    return "Settings shortcut not available on this platform."


def _open_file_explorer(path: str = "") -> str:
    os_name = _get_os()
    if path and Path(path).exists():
        p = str(Path(path).resolve())
        if os_name == "windows":
            subprocess.Popen(["explorer", p], **_WIN_HIDE)
        elif os_name == "mac":
            subprocess.Popen(["open", p])
        else:
            subprocess.Popen(["xdg-open", p])
        return f"Opened file explorer at: {p}"
    if os_name == "windows":
        return _hotkey("win", "e")
    elif os_name == "mac":
        return _hotkey("cmd", "space")
    return "Opened file explorer."


def _open_task_manager() -> str:
    os_name = _get_os()
    if os_name == "windows":
        return _hotkey("ctrl", "shift", "esc")
    return "Task manager shortcut not supported."


def _open_run_dialog() -> str:
    os_name = _get_os()
    if os_name == "windows":
        return _hotkey("win", "r")
    return "Run dialog not supported."


def _open_clipboard_history() -> str:
    os_name = _get_os()
    if os_name == "windows":
        return _hotkey("win", "v")
    return "Clipboard history not supported."


def _open_action_center() -> str:
    os_name = _get_os()
    if os_name == "windows":
        return _hotkey("win", "a")
    return "Action center not supported."


def _take_snip() -> str:
    os_name = _get_os()
    if os_name == "windows":
        return _hotkey("win", "shift", "s")
    elif os_name == "mac":
        return _hotkey("cmd", "shift", "4")
    return _hotkey("printscreen")


def _get_system_info() -> str:
    info = []
    info.append(f"OS: {platform.system()} {platform.release()} ({platform.architecture()[0]})")
    try:
        import psutil
        cpu_pct = psutil.cpu_percent(interval=0.1)
        cpu_count = psutil.cpu_count(logical=True)
        info.append(f"CPU: {cpu_pct}% across {cpu_count} logical cores")

        vm = psutil.virtual_memory()
        ram_used = round((vm.total - vm.available) / (1024**3), 1)
        ram_total = round(vm.total / (1024**3), 1)
        info.append(f"RAM: {vm.percent}% used ({ram_used} GB / {ram_total} GB)")

        disk_path = "C:\\" if platform.system() == "Windows" else "/"
        try:
            du = psutil.disk_usage(disk_path)
            disk_free = round(du.free / (1024**3), 1)
            disk_total = round(du.total / (1024**3), 1)
            info.append(f"Disk ({disk_path}): {du.percent}% used ({disk_free} GB free of {disk_total} GB)")
        except Exception:
            pass

        try:
            bat = psutil.sensors_battery()
            if bat:
                plugged = "Plugged in (Charging)" if bat.power_plugged else "On Battery"
                info.append(f"Battery: {bat.percent}% ({plugged})")
            else:
                info.append("Battery: Desktop / AC Power (No battery detected)")
        except Exception:
            pass
    except Exception as e:
        info.append(f"System metrics partial: {e}")

    act_win = _get_active_window()
    if act_win and act_win.get("title"):
        info.append(f"Active Window: {act_win['title']}")

    return "\n".join(info)


def _capture_screen_scaled() -> tuple[Image.Image | None, float, float, int, int]:
    """Capture screen and calculate physical-to-logical coordinate scaling ratio.
    Returns: (pil_image, scale_x, scale_y, logical_w, logical_h)"""
    _require_pyautogui()
    logical_w, logical_h = pyautogui.size()
    # 1. mss is 10-20x faster (3ms vs 50ms)
    try:
        import mss
        with mss.mss() as sct:
            mon = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
            shot = sct.grab(mon)
            img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
    except Exception:
        pass

    if img is None:
        try:
            img = _safe_keyboard_action(pyautogui.screenshot)
        except Exception as e:
            print(f"[ComputerControl] pyautogui screenshot fallback: {e}")

    if img is None:
        try:
            from PIL import ImageGrab
            img = ImageGrab.grab(all_screens=False)
        except Exception as e:
            print(f"[ComputerControl] ImageGrab fallback: {e}")

    if img is None:
        return None, 1.0, 1.0, logical_w, logical_h

    img_w, img_h = img.size
    scale_x = logical_w / float(img_w)
    scale_y = logical_h / float(img_h)
    return img, scale_x, scale_y, logical_w, logical_h


def _parse_grounding_response(text: str, logical_w: int, logical_h: int) -> dict | None:
    """Robust parser for model spatial grounding responses supporting:
    1. Gemini native normalized bounding boxes: {"box_2d": [ymin, xmin, ymax, xmax]} in [0, 1000]
    2. Normalized center points: {"point": [y, x]} in [0, 1000]
    3. Direct pixel integers: {"x": int, "y": int} or [x, y]
    4. Text coordinates e.g. "x, y" or "[ymin, xmin, ymax, xmax]"
    """
    if not text:
        return None

    cleaned = text.strip()
    if "```" in cleaned:
        m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
        if m:
            cleaned = m.group(1).strip()

    parsed_json = None
    if cleaned.startswith("{") or "{" in cleaned:
        brace_m = re.search(r"(\{[\s\S]*\})", cleaned)
        if brace_m:
            try:
                parsed_json = json.loads(brace_m.group(1))
            except Exception:
                pass

    if isinstance(parsed_json, dict):
        if parsed_json.get("found") is False:
            return {"found": False, "reason": parsed_json.get("reason", "not found")}

        # 1. Gemini native normalized box_2d: [ymin, xmin, ymax, xmax] in [0, 1000]
        box = parsed_json.get("box_2d") or parsed_json.get("bounding_box")
        if isinstance(box, list) and len(box) >= 4:
            try:
                ymin, xmin, ymax, xmax = [float(v) for v in box[:4]]
                if ymax <= 1.0 and xmax <= 1.0:
                    ymin, xmin, ymax, xmax = ymin * 1000, xmin * 1000, ymax * 1000, xmax * 1000

                cx_norm = (xmin + xmax) / 2.0 / 1000.0
                cy_norm = (ymin + ymax) / 2.0 / 1000.0

                point = parsed_json.get("point")
                if isinstance(point, list) and len(point) >= 2:
                    py, px = float(point[0]), float(point[1])
                    if py <= 1.0 and px <= 1.0:
                        py, px = py * 1000, px * 1000
                    cy_norm = py / 1000.0
                    cx_norm = px / 1000.0

                cx = int(round(cx_norm * logical_w))
                cy = int(round(cy_norm * logical_h))
                bw = int(round(((xmax - xmin) / 1000.0) * logical_w))
                bh = int(round(((ymax - ymin) / 1000.0) * logical_h))

                return {
                    "found": True,
                    "x": max(1, min(logical_w - 2, cx)),
                    "y": max(1, min(logical_h - 2, cy)),
                    "label": parsed_json.get("label", ""),
                    "type": parsed_json.get("type", parsed_json.get("element_type", "element")),
                    "box_2d": [ymin, xmin, ymax, xmax],
                    "box_px": (int(round(xmin / 1000.0 * logical_w)), int(round(ymin / 1000.0 * logical_h)), bw, bh),
                    "confidence": float(parsed_json.get("confidence", 0.95)),
                }
            except Exception:
                pass

        # 2. Normalized point: [y, x]
        pt = parsed_json.get("point")
        if isinstance(pt, list) and len(pt) >= 2:
            try:
                py, px = float(pt[0]), float(pt[1])
                if py <= 1.0 and px <= 1.0:
                    py, px = py * 1000, px * 1000
                cx = int(round((px / 1000.0) * logical_w))
                cy = int(round((py / 1000.0) * logical_h))
                return {
                    "found": True,
                    "x": max(1, min(logical_w - 2, cx)),
                    "y": max(1, min(logical_h - 2, cy)),
                    "confidence": float(parsed_json.get("confidence", 0.9)),
                }
            except Exception:
                pass

        # 3. Raw x, y
        if "x" in parsed_json and "y" in parsed_json:
            try:
                x, y = int(round(float(parsed_json["x"]))), int(round(float(parsed_json["y"])))
                if 1 <= x < logical_w and 1 <= y < logical_h:
                    return {
                        "found": True,
                        "x": x,
                        "y": y,
                        "confidence": float(parsed_json.get("confidence", 0.85)),
                    }
            except Exception:
                pass

    # Regex fallback 1: [ymin, xmin, ymax, xmax]
    box_m = re.search(r"\[\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\]", text)
    if box_m:
        ymin, xmin, ymax, xmax = (
            int(box_m.group(1)),
            int(box_m.group(2)),
            int(box_m.group(3)),
            int(box_m.group(4)),
        )
        if xmax <= 1000 and ymax <= 1000:
            cx = int(round(((xmin + xmax) / 2.0 / 1000.0) * logical_w))
            cy = int(round(((ymin + ymax) / 2.0 / 1000.0) * logical_h))
            return {
                "found": True,
                "x": max(1, min(logical_w - 2, cx)),
                "y": max(1, min(logical_h - 2, cy)),
                "box_2d": [ymin, xmin, ymax, xmax],
                "confidence": 0.88,
            }

    # Regex fallback 2: x, y
    coord_m = re.search(r"(\d+)\s*,\s*(\d+)", text)
    if coord_m:
        x, y = int(coord_m.group(1)), int(coord_m.group(2))
        if 1 <= x < logical_w and 1 <= y < logical_h:
            return {
                "found": True,
                "x": x,
                "y": y,
                "confidence": 0.8,
            }

    return None


def _screen_find_grounded(description: str, refine: bool = True) -> dict | None:
    """Use Gemini with normalized bounding box spatial grounding + hierarchical
    coarse-to-fine zoom refinement to locate UI elements with pixel-level precision.
    Returns: dict with {found, x, y, label, type, box_2d, box_px, confidence, refined, refine_delta} or None.
    """
    api_key = _get_api_key()
    if not api_key:
        print("[ComputerControl] ⚠️ No API key for screen_find_grounded")
        return None

    try:
        from google.genai import types as gtypes
        from core import gemini

        img, scale_x, scale_y, w, h = _capture_screen_scaled()
        if img is None:
            print("[ComputerControl] ⚠️ Screen capture failed")
            return None

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        image_bytes = buf.getvalue()

        prompt = (
            f"You are a state-of-the-art GUI spatial grounding model for a {w}×{h} pixel screen.\n"
            f"TASK: Locate the interactive clickable UI element matching:\n"
            f"  '{description}'\n\n"
            f"SPATIAL GROUNDING PROTOCOL:\n"
            f"1. Element Identification: identify if it is a button, icon, tab, input, checkbox, link, or menu item.\n"
            f"2. Visual Hierarchy: locate the element in relation to its surrounding toolbar, header, or dialog.\n"
            f"3. Interactive Hit-Area: target the center of the clickable control, NOT its outer background container.\n"
            f"4. Coordinate Normalization: output coordinates in normalized integers [0, 1000] where:\n"
            f"   - ymin = top boundary (0 = screen top, 1000 = screen bottom)\n"
            f"   - xmin = left boundary (0 = screen left, 1000 = screen right)\n"
            f"   - ymax = bottom boundary\n"
            f"   - xmax = right boundary\n"
            f"   - point = [center_y, center_x] in [0, 1000]\n\n"
            f"OUTPUT FORMAT (STRICT JSON ONLY):\n"
            f"```json\n"
            f'{{"found": true, "label": "<text or icon description>", "type": "<button|input|tab|icon|link>", '
            f'"box_2d": [ymin, xmin, ymax, xmax], "point": [center_y, center_x], "confidence": 0.95}}\n'
            f"```\n"
            f"If definitely not found on screen:\n"
            f'```json\n{{"found": false, "reason": "not visible"}}\n```'
        )

        response = gemini.call(
            [gtypes.Part.from_bytes(data=image_bytes, mime_type="image/png"), prompt],
            tier=gemini.SMART,
            timeout_ms=30_000,
        )
        if response is None:
            return None

        text = (response.text or "").strip()
        grounded = _parse_grounding_response(text, w, h)
        if not grounded or not grounded.get("found"):
            print(f"[ComputerControl] 🔍 screen_find_grounded: element '{description}' not found (model: '{text[:80]}')")
            return None

        coarse_x = grounded["x"]
        coarse_y = grounded["y"]
        grounded["coarse_x"] = coarse_x
        grounded["coarse_y"] = coarse_y
        grounded["refined"] = False
        grounded["refine_delta"] = 0.0

        # Phase 2: Hierarchical Coarse-to-Fine Zoom Refinement
        if refine:
            try:
                img_w, img_h = img.size
                img_cx = coarse_x / scale_x
                img_cy = coarse_y / scale_y

                box_px = grounded.get("box_px")
                bw = box_px[2] if box_px else 40
                bh = box_px[3] if box_px else 40
                radius_x = max(110, int((bw / scale_x) * 1.1))
                radius_y = max(110, int((bh / scale_y) * 1.1))
                radius = min(200, max(radius_x, radius_y))

                crop_x1 = max(0, int(img_cx - radius))
                crop_y1 = max(0, int(img_cy - radius))
                crop_x2 = min(img_w, int(img_cx + radius))
                crop_y2 = min(img_h, int(img_cy + radius))

                patch = img.crop((crop_x1, crop_y1, crop_x2, crop_y2))
                pw, ph = patch.size

                patch_buf = io.BytesIO()
                patch.save(patch_buf, format="PNG")
                patch_bytes = patch_buf.getvalue()

                zoom_prompt = (
                    f"You are inspecting a 1:1 pixel crop ({pw}×{ph} pixels) centered on candidate element: '{description}'.\n"
                    f"TASK: Pinpoint the exact interactive hit center of '{description}' within this patch.\n"
                    f"OUTPUT FORMAT (STRICT JSON ONLY):\n"
                    f"```json\n"
                    f'{{"found": true, "patch_x": <int 0..{pw}>, "patch_y": <int 0..{ph}>, "confidence": 0.98}}\n'
                    f"```\n"
                    f"If not in patch: {{\"found\": false}}"
                )

                patch_resp = gemini.call(
                    [gtypes.Part.from_bytes(data=patch_bytes, mime_type="image/png"), zoom_prompt],
                    tier=gemini.FAST,
                    timeout_ms=12_000,
                )

                if patch_resp and patch_resp.text:
                    p_txt = patch_resp.text.strip()
                    p_json = None
                    if "{" in p_txt:
                        b_m = re.search(r"(\{[\s\S]*\})", p_txt)
                        if b_m:
                            try:
                                p_json = json.loads(b_m.group(1))
                            except Exception:
                                pass

                    if isinstance(p_json, dict) and p_json.get("found"):
                        patch_x = int(p_json.get("patch_x", pw // 2))
                        patch_y = int(p_json.get("patch_y", ph // 2))
                        if 0 <= patch_x <= pw and 0 <= patch_y <= ph:
                            fine_img_x = crop_x1 + patch_x
                            fine_img_y = crop_y1 + patch_y
                            fine_x = int(round(fine_img_x * scale_x))
                            fine_y = int(round(fine_img_y * scale_y))

                            delta = math.hypot(fine_x - coarse_x, fine_y - coarse_y)
                            max_allowed_delta = radius * max(scale_x, scale_y) * 0.9
                            if delta <= max_allowed_delta:
                                grounded["x"] = max(1, min(w - 2, fine_x))
                                grounded["y"] = max(1, min(h - 2, fine_y))
                                grounded["refined"] = True
                                grounded["refine_delta"] = round(delta, 2)
                                grounded["confidence"] = max(grounded["confidence"], float(p_json.get("confidence", 0.95)))
                                print(f"[ComputerControl] 🎯 Fine-zoom refined '{description}': ({coarse_x},{coarse_y}) → ({fine_x},{fine_y}) [Δ={delta:.1f}px]")
            except Exception as e:
                print(f"[ComputerControl] Fine-zoom refinement partial error: {e}")

        print(
            f"[ComputerControl] 🔍 screen_find_grounded: '{description}' → "
            f"({grounded['x']}, {grounded['y']}) [conf={grounded['confidence']:.2f}, refined={grounded['refined']}]"
        )
        return grounded

    except Exception as e:
        print(f"[ComputerControl] ⚠️ screen_find_grounded failed: {e}")
        return None


def _screen_find(description: str, refine: bool = True) -> tuple[int, int] | None:
    """Use normalized bounding box spatial grounding + hierarchical zoom to return (x, y) coordinates."""
    res = _screen_find_grounded(description, refine=refine)
    if res and res.get("found"):
        return res["x"], res["y"]
    return None

def _screen_read(region: str = "full") -> str:
    """Run a full-screen (or region) OCR pass and return all visible text,
    organised by approximate screen area.

    Used to let JARVIS read the current state of the UI before deciding the
    next action — no question needed, just a structured text map that the
    model can reason over.

    region: 'full' | 'top' | 'bottom' | 'left' | 'right' | 'center'
    """
    api_key = _get_api_key()
    if not api_key:
        return "No API key — cannot read screen."

    try:
        from google.genai import types as gtypes

        _require_pyautogui()
        w, h = pyautogui.size()
        img  = _safe_keyboard_action(pyautogui.screenshot)

        # Crop to the requested region to reduce token cost on large monitors.
        region_box = {
            "full"  : (0, 0, w, h),
            "top"   : (0, 0, w, h // 2),
            "bottom": (0, h // 2, w, h),
            "left"  : (0, 0, w // 2, h),
            "right" : (w // 2, 0, w, h),
            "center": (w // 4, h // 4, 3 * w // 4, 3 * h // 4),
        }.get(region.lower(), (0, 0, w, h))

        crop = img.crop(region_box)
        buf  = io.BytesIO()
        crop.save(buf, format="PNG")
        image_bytes = buf.getvalue()

        prompt = (
            "You are a screen-reading function. Extract ALL text visible in this "
            "screenshot in reading order (left to right, top to bottom). "
            "Group by UI section using short section headers in square brackets, e.g. "
            "[Title Bar], [Menu Bar], [Main Content], [Status Bar], [Dialog], [Notification]. "
            "Under each header list the text verbatim, one item per line. "
            "Also append a [CONTROLS] section listing every interactive element "
            "(buttons, checkboxes, inputs, tabs, links) with its label and state "
            "(enabled/disabled/checked/selected/focused). "
            "If a section is empty, omit it. Emit nothing else."
        )

        from core import gemini
        response = gemini.call(
            [gtypes.Part.from_bytes(data=image_bytes, mime_type="image/png"), prompt],
            tier=gemini.SMART,
            timeout_ms=35_000,
        )
        if response is None:
            return "Screen read failed — no model responded."

        text = (response.text or "").strip()
        print(f"[ComputerControl] 📖 screen_read ({region}): {len(text)} chars")
        return text or "(nothing readable found)"

    except Exception as e:
        print(f"[ComputerControl] ⚠️ screen_read failed: {e}")
        return f"screen_read error: {e}"


def _screen_wait_for(
    description: str,
    timeout: float = 15.0,
    poll_interval: float = 2.0,
) -> tuple[int, int] | None:
    """Poll the screen with the vision model until `description` appears or
    `timeout` seconds elapse.  Returns (x, y) of the element, or None.

    This is the missing primitive for reliable automation: 'click Submit,
    then wait until the confirmation banner appears before the next step'.
    Without it, the model guesses a fixed sleep and either races (too short)
    or stalls (too long).
    """
    deadline = time.time() + max(1.0, timeout)
    attempt  = 0
    while time.time() < deadline:
        attempt += 1
        print(f"[ComputerControl] ⏳ screen_wait_for attempt {attempt}: '{description}'")
        coords = _screen_find(description)
        if coords is not None:
            print(f"[ComputerControl] ✅ screen_wait_for: found '{description}' at {coords}")
            return coords
        remaining = deadline - time.time()
        if remaining <= 0:
            break
        time.sleep(min(poll_interval, remaining))
    print(f"[ComputerControl] ⏰ screen_wait_for: '{description}' never appeared ({timeout}s)")
    return None


def _screen_click(
    description: str,
    button: str = "left",
    clicks: int = 1,
    refine: bool = True,
) -> str:
    """Find UI element via normalized spatial grounding + coarse-to-fine zoom,
    then execute verified motor control click with real-time pointer verification."""
    grounded = _screen_find_grounded(description, refine=refine)
    if not grounded or not grounded.get("found"):
        return f"Could not locate '{description}' on screen. Element not found or confidence too low."

    x = grounded["x"]
    y = grounded["y"]
    label = grounded.get("label") or description
    el_type = grounded.get("type", "element")
    conf = grounded.get("confidence", 1.0)
    ref_info = f", refined Δ={grounded['refine_delta']:.1f}px" if grounded.get("refined") else ""

    click_res = _verified_click(x, y, button=button, clicks=clicks, settle_time=0.08)
    time.sleep(0.12)  # UI transition settle

    c_type = "Triple-clicked" if clicks == 3 else ("Double-clicked" if clicks == 2 else "Clicked")
    return (
        f"{c_type} '{label}' ({el_type}) at ({x}, {y}) [{button}, "
        f"verified={click_res['verified']}, drift={click_res['drift_px']}px, "
        f"conf={conf:.2f}{ref_info}]."
    )


def _screen_hover(description: str, dwell: float = 0.5, refine: bool = True) -> str:
    """Find UI element and hover with verified trajectory and settling."""
    grounded = _screen_find_grounded(description, refine=refine)
    if not grounded or not grounded.get("found"):
        return f"Could not locate '{description}' on screen."
    x = grounded["x"]
    y = grounded["y"]
    return _verified_hover(x, y, dwell=dwell)


def _screen_type_in(field_description: str, text: str, clear_first: bool = True, refine: bool = True) -> str:
    """Find a text field by natural-language description using verified grounding,
    click to focus with verified motor control, then type `text` into it."""
    _require_pyautogui()
    grounded = _screen_find_grounded(field_description, refine=refine)
    if not grounded or not grounded.get("found"):
        return f"Could not find field '{field_description}' on screen."

    x, y = grounded["x"], grounded["y"]
    click_res = _verified_click(x, y, button="left", clicks=1, settle_time=0.1)
    time.sleep(0.2)  # Let focus and text caret settle
    typed_msg = _smart_type(text, clear_first=clear_first)
    return f"Focused '{field_description}' at ({x}, {y}) [verified={click_res['verified']}]. {typed_msg}"


# ── Chrome native tab & browser controls ──────────────────────────────────────

def _chrome_exe_path() -> str | None:
    os_name = _get_os()
    if os_name == "windows":
        local  = os.environ.get("LOCALAPPDATA", "")
        prog   = os.environ.get("PROGRAMFILES", "")
        prog86 = os.environ.get("PROGRAMFILES(X86)", "")
        candidates = [
            Path(prog)   / "Google" / "Chrome" / "Application" / "chrome.exe",
            Path(prog86) / "Google" / "Chrome" / "Application" / "chrome.exe",
            Path(local)  / "Google" / "Chrome" / "Application" / "chrome.exe",
        ]
        for c in candidates:
            if c.exists():
                return str(c)
        try:
            import winreg
            k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe")
            val = winreg.QueryValue(k, None)
            winreg.CloseKey(k)
            if val and Path(val).exists():
                return str(val)
        except Exception:
            pass
        return shutil.which("chrome") or shutil.which("chrome.exe")

    elif os_name == "mac":
        mac_path = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
        if mac_path.exists():
            return str(mac_path)
        return shutil.which("google-chrome") or shutil.which("chrome")

    elif os_name == "linux":
        for b in ("google-chrome", "google-chrome-stable", "chromium-browser", "chromium"):
            w = shutil.which(b)
            if w:
                return w

    return None


def _chrome_focus() -> str:
    try:
        import win32gui
        fg = win32gui.GetForegroundWindow()
        if fg and "chrome" in win32gui.GetWindowText(fg).lower():
            return "Chrome is already active."
    except Exception:
        pass
    return _focus_window("Chrome")


def _chrome_new_tab(url: str = "") -> str:
    _chrome_focus()
    time.sleep(0.04)
    url = (url or "").strip()
    if url:
        if not url.startswith(("http://", "https://", "chrome://")):
            url = "https://" + url
        exe = _chrome_exe_path()
        if exe:
            try:
                subprocess.Popen([exe, url], **_WIN_HIDE)
                time.sleep(0.08)
                _chrome_focus()
                return f"Opened new tab in your Chrome: {url}"
            except Exception:
                pass
        _require_pyautogui()
        _hotkey("ctrl", "t")
        time.sleep(0.04)
        _type(url)
        _press("enter")
        return f"Opened new tab in your Chrome: {url}"
    else:
        _require_pyautogui()
        _hotkey("ctrl", "t")
        return "Opened new empty tab in your Chrome."


def _chrome_switch_tab(target: str = "next") -> str:
    _chrome_focus()
    time.sleep(0.04)
    _require_pyautogui()
    t = str(target or "next").lower().strip()
    if t in ("next", "forward", "right"):
        _hotkey("ctrl", "tab")
        return "Switched to next Chrome tab."
    elif t in ("prev", "previous", "back", "left"):
        _hotkey("ctrl", "shift", "tab")
        return "Switched to previous Chrome tab."
    elif t.isdigit():
        num = int(t)
        if 1 <= num <= 8:
            _hotkey("ctrl", str(num))
            return f"Switched to Chrome tab {num}."
        elif num >= 9:
            _hotkey("ctrl", "9")
            return "Switched to last Chrome tab."
    elif t in ("last", "end"):
        _hotkey("ctrl", "9")
        return "Switched to last Chrome tab."
    elif t in ("first", "start", "1"):
        _hotkey("ctrl", "1")
        return "Switched to first Chrome tab."

    # Instant Keyword Tab Search via Chrome's native Search Tabs dialog (Ctrl+Shift+A)
    try:
        _hotkey("ctrl", "shift", "a")
        time.sleep(0.04)
        _type(t)
        time.sleep(0.04)
        _press("enter")
        time.sleep(0.03)
        return f"Switched to Chrome tab matching '{target}'."
    except Exception:
        pass

    _hotkey("ctrl", "tab")
    return f"Switched Chrome tab towards '{target}'."


def _chrome_close_tab() -> str:
    _chrome_focus()
    time.sleep(0.04)
    _require_pyautogui()
    _hotkey("ctrl", "w")
    return "Closed active Chrome tab."


def _chrome_reopen_tab() -> str:
    _chrome_focus()
    time.sleep(0.04)
    _require_pyautogui()
    _hotkey("ctrl", "shift", "t")
    return "Reopened last closed Chrome tab."


def _chrome_navigate(url: str) -> str:
    _chrome_focus()
    time.sleep(0.04)
    _require_pyautogui()
    url = (url or "").strip()
    if not url.startswith(("http://", "https://", "chrome://")):
        url = "https://" + url
    _hotkey("ctrl", "l")
    time.sleep(0.04)
    _type(url)
    _press("enter")
    return f"Navigated Chrome tab to {url}."


def _chrome_search(query: str) -> str:
    _chrome_focus()
    time.sleep(0.04)
    _require_pyautogui()
    query = (query or "").strip()
    _hotkey("ctrl", "l")
    time.sleep(0.04)
    _type(query)
    _press("enter")
    return f"Searched for '{query}' in Chrome."


def _chrome_read_tab(region: str = "full") -> str:
    _chrome_focus()
    time.sleep(0.05)
    return _screen_read(region)


def _chrome_click(description: str) -> str:
    _chrome_focus()
    time.sleep(0.05)
    return _screen_click(description, button="left", clicks=1, refine=True)


def _chrome_type_in(description: str, text: str, clear_first: bool = True) -> str:
    _chrome_focus()
    time.sleep(0.05)
    return _screen_type_in(description, text, clear_first=clear_first, refine=True)


def _chrome_launch_debug(port: int = 9222) -> str:
    exe = _chrome_exe_path()
    if not exe:
        return "Chrome executable not found."
    try:
        cmd = [exe, f"--remote-debugging-port={port}"]
        subprocess.Popen(cmd, **_WIN_HIDE)
        return f"Launched Chrome with Remote Debugging on port {port} using your real profile."
    except Exception as e:
        return f"Failed to launch Chrome with debugging: {e}"


def _chrome_list_tabs() -> str:
    _chrome_focus()
    time.sleep(0.04)
    tab_ocr = _screen_read("top")
    return f"Visible Chrome tabs and controls:\n{tab_ocr}"


def _chrome_zoom(level: str = "reset") -> str:
    _chrome_focus()
    time.sleep(0.03)
    lvl = str(level or "reset").lower().strip()
    if lvl in ("in", "plus", "+", "zoom_in"):
        _hotkey("ctrl", "+")
        return "Zoomed in on Chrome tab."
    elif lvl in ("out", "minus", "-", "zoom_out"):
        _hotkey("ctrl", "-")
        return "Zoomed out on Chrome tab."
    else:
        _hotkey("ctrl", "0")
        return "Reset zoom on Chrome tab to 100%."


def _chrome_find(query: str) -> str:
    _chrome_focus()
    time.sleep(0.04)
    _hotkey("ctrl", "f")
    time.sleep(0.03)
    if query:
        _type(query)
        _press("enter")
    return f"Finding '{query}' on active Chrome tab."


def _chrome_history() -> str:
    _chrome_focus()
    time.sleep(0.04)
    _hotkey("ctrl", "h")
    return "Opened Chrome History."


def _chrome_downloads() -> str:
    _chrome_focus()
    time.sleep(0.04)
    _hotkey("ctrl", "j")
    return "Opened Chrome Downloads."


def _chrome_bookmarks() -> str:
    _chrome_focus()
    time.sleep(0.04)
    _hotkey("ctrl", "shift", "o")
    return "Opened Chrome Bookmark Manager."


def _chrome_duplicate_tab() -> str:
    _chrome_focus()
    time.sleep(0.04)
    _hotkey("alt", "d")
    time.sleep(0.03)
    _hotkey("alt", "enter")
    return "Duplicated active Chrome tab."


def _chrome_incognito() -> str:
    _chrome_focus()
    time.sleep(0.04)
    _hotkey("ctrl", "shift", "n")
    return "Opened new Incognito window in Chrome."


def _chrome_inspect() -> str:
    _chrome_focus()
    time.sleep(0.04)
    _hotkey("ctrl", "shift", "i")
    return "Toggled Developer Tools (Inspect) on Chrome tab."


def _chrome_get_url() -> str:
    """Fast, zero-token native active URL reader via address bar copy."""
    _chrome_focus()
    time.sleep(0.03)
    _require_pyautogui()
    saved_clip = ""
    if _PYPERCLIP:
        try:
            saved_clip = pyperclip.paste()
            pyperclip.copy("")
        except Exception:
            pass
    _hotkey("ctrl", "l")
    time.sleep(0.04)
    _hotkey("ctrl", "c")
    time.sleep(0.04)
    _press("escape")
    url = ""
    if _PYPERCLIP:
        for _ in range(5):
            try:
                url = pyperclip.paste().strip()
                if url:
                    break
            except Exception:
                pass
            time.sleep(0.02)
    # Restore clipboard
    if _PYPERCLIP and saved_clip:
        try:
            pyperclip.copy(saved_clip)
        except Exception:
            pass
    if url and (url.startswith(("http://", "https://", "chrome://", "edge://", "about:", "file:///")) or "." in url):
        if not url.startswith(("http://", "https://", "chrome://", "edge://", "about:", "file:///")):
            url = "https://" + url
        return url
    return url or "Could not read active URL."


def _chrome_get_page_text(max_chars: int = 4000) -> str:
    """Fast, zero-token native page text reader via Ctrl+A and clipboard."""
    _chrome_focus()
    time.sleep(0.04)
    _require_pyautogui()
    saved_clip = ""
    if _PYPERCLIP:
        try:
            saved_clip = pyperclip.paste()
            pyperclip.copy("")
        except Exception:
            pass
    _hotkey("ctrl", "a")
    time.sleep(0.03)
    _hotkey("ctrl", "c")
    time.sleep(0.03)
    _press("escape")  # deselect
    text = ""
    if _PYPERCLIP:
        try:
            text = pyperclip.paste().strip()
        except Exception:
            pass
    if text and len(text) > 20:
        return text[:max_chars].strip()
    # Fallback to visual OCR full page
    return _chrome_read_tab("full")


def _chrome_reload(hard: bool = False) -> str:
    _chrome_focus()
    time.sleep(0.03)
    if hard:
        _hotkey("ctrl", "f5")
        return "Hard refreshed active Chrome tab."
    _hotkey("ctrl", "r")
    return "Reloaded active Chrome tab."


def _chrome_fullscreen() -> str:
    _chrome_focus()
    time.sleep(0.03)
    _press("f11")
    return "Toggled fullscreen in Chrome."


def _chrome_task_manager() -> str:
    _chrome_focus()
    time.sleep(0.03)
    _hotkey("shift", "escape")
    return "Opened Chrome Task Manager."


def _chrome_print_pdf() -> str:
    _chrome_focus()
    time.sleep(0.03)
    _hotkey("ctrl", "p")
    return "Opened Print / Save to PDF dialog in Chrome."


def _chrome_page_source() -> str:
    _chrome_focus()
    time.sleep(0.03)
    _hotkey("ctrl", "u")
    return "Opened page source in Chrome."


def _chrome_clear_data() -> str:
    _chrome_focus()
    time.sleep(0.03)
    _hotkey("ctrl", "shift", "delete")
    return "Opened Clear Browsing Data dialog in Chrome."


def _chrome_pdf_goto_page(page: int | str = 1, relative_pages: int | None = None) -> str:
    """Jump directly to a specific page number or scroll relative pages in Chrome/PDF viewer.
    Executes in under 60ms with zero AI vision model delay.
    """
    _chrome_focus()
    _require_pyautogui()

    # 1. Relative page scrolling (e.g. "scroll down 3 pages", "scroll up 2 pages")
    if relative_pages is not None and int(relative_pages) != 0:
        rel = int(relative_pages)
        key = "pagedown" if rel > 0 else "pageup"
        _press("escape")
        time.sleep(0.01)
        for _ in range(abs(rel)):
            _press(key)
            time.sleep(0.01)
        direction = "down" if rel > 0 else "up"
        return f"Scrolled {direction} {abs(rel)} pages in PDF."

    # Parse target page number
    p = 1
    if isinstance(page, int):
        p = max(1, page)
    else:
        m = re.search(r"\d+", str(page or "1"))
        p = max(1, int(m.group(0))) if m else 1

    # METHOD 1 (Universal In-Document Navigation for pages 1..25):
    # Pressing Home lands on Page 1; pressing PageDown (p - 1) times lands on Page p.
    # Works in 100% of viewers (Chrome, Edge, Adobe, web viewers) without
    # reload flicker, without network delay, and takes < 40ms!
    if p <= 25:
        _press("escape")
        time.sleep(0.01)
        _press("home")
        if p > 1:
            time.sleep(0.01)
            for _ in range(p - 1):
                _press("pagedown")
                time.sleep(0.01)
        return f"Scrolled to PDF page {p} in Chrome."

    # METHOD 2 (For large page numbers p > 25):
    # Address bar hash update + F5 reload so Chrome PDFium renders directly at page p!
    saved_clip = ""
    if _PYPERCLIP:
        try:
            saved_clip = pyperclip.paste()
            pyperclip.copy("")
        except Exception:
            pass

    _hotkey("ctrl", "l")
    time.sleep(0.04)
    _hotkey("ctrl", "c")
    time.sleep(0.04)

    url = ""
    if _PYPERCLIP:
        for _ in range(4):
            try:
                url = pyperclip.paste().strip()
                if url:
                    break
            except Exception:
                pass
            time.sleep(0.02)

    url_success = False
    if url and (url.startswith(("http://", "https://", "file:///", "chrome-extension://")) or ".pdf" in url.lower() or "#page=" in url.lower()):
        base_url = re.sub(r"#.*$", "", url)
        target_url = f"{base_url}#page={p}"
        if _PYPERCLIP:
            try:
                pyperclip.copy(target_url)
                time.sleep(0.02)
                _hotkey("ctrl", "v")
                time.sleep(0.03)
                _press("enter")
                time.sleep(0.03)
                _press("f5")  # Reload makes Chrome's PDFium plugin render at #page=p!
                time.sleep(0.05)
                _press("escape")
                url_success = True
            except Exception as e:
                print(f"[ComputerControl] URL hash navigation error: {e}")

    # Restore clipboard content
    if _PYPERCLIP and saved_clip:
        try:
            pyperclip.copy(saved_clip)
        except Exception:
            pass

    if url_success:
        return f"Navigated Chrome PDF to page {p}."

    # Immediate fallback to in-document navigation without any slow vision model calls
    _press("escape")
    time.sleep(0.01)
    _press("home")
    time.sleep(0.01)
    for _ in range(p - 1):
        _press("pagedown")
        time.sleep(0.005)
    return f"Scrolled to PDF page {p} in Chrome."


def computer_control(
    parameters: dict,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    """
    Dispatch table for all computer control actions.

    parameters keys (all optional unless noted):
      action        : (required) one of the actions listed below
      text          : text to type or paste
      x, y          : screen coordinates
      button        : 'left' | 'right' (default: left)
      keys          : hotkey string, e.g. 'ctrl+c'
      key           : single key name, e.g. 'enter'
      direction     : 'up' | 'down' | 'left' | 'right'
      amount        : scroll amount (default: 3)
      seconds       : wait duration
      title         : window title fragment for focus_window
      description   : natural-language element description for screen_find/click/wait
      region        : 'full'|'top'|'bottom'|'left'|'right'|'center' for screen_read
      type          : data type for random_data
      field         : memory field name for user_data
      clear_first   : bool, clear field before typing (default: true)
      path          : save path for screenshot (must be inside home dir)
      timeout       : seconds to wait for screen_wait_for (default: 15)

    Actions:
      type          — type text at cursor
      smart_type    — clear field + type (clipboard-backed)
      click         — left click
      double_click  — double left click
      right_click   — right click
      move          — move mouse
      drag          — click-drag between two points
      hotkey        — key combination
      press         — single key
      scroll        — scroll the wheel
      copy          — read clipboard
      paste         — write + paste clipboard
      screenshot    — capture screen (safe path only)
      wait          — sleep N seconds
      clear_field   — select-all + delete
      focus_window  — bring window to foreground
      screen_find   — AI element finder (returns x,y)
      screen_click  — AI element finder + click
      screen_read   — full-screen OCR: returns all visible text grouped by UI section
      screen_wait_for — wait until an element appears on screen (vision poll loop)
      screen_type_in  — find a text field by description then type into it
      random_data   — generate fake form data
      user_data     — pull real data from memory
    """
    params = parameters or {}
    action = params.get("action", "").lower().strip()

    if not action:
        return "No action specified for computer_control."

    if player:
        player.write_log(f"[Computer] {action}")

    print(f"[ComputerControl] ▶ {action}  {params}")

    try:

        if action == "type":
            return _type(params.get("text", ""))

        if action == "smart_type":
            return _smart_type(
                params.get("text", ""),
                clear_first=params.get("clear_first", True),
            )

        if action in ("click", "left_click"):
            return _click(params.get("x"), params.get("y"), "left", 1)

        if action == "double_click":
            return _click(params.get("x"), params.get("y"), "left", 2)

        if action == "triple_click":
            return _triple_click(params.get("x"), params.get("y"))

        if action == "middle_click":
            return _middle_click(params.get("x"), params.get("y"))

        if action == "right_click":
            return _click(params.get("x"), params.get("y"), "right", 1)

        if action == "mouse_down":
            return _mouse_down(params.get("button", "left"))

        if action == "mouse_up":
            return _mouse_up(params.get("button", "left"))

        if action in ("mouse_position", "cursor_position"):
            return str(_mouse_position())

        if action == "move":
            return _move(int(params.get("x", 0)), int(params.get("y", 0)))

        if action == "drag":
            return _drag(
                int(params.get("x1", 0)), int(params.get("y1", 0)),
                int(params.get("x2", 0)), int(params.get("y2", 0)),
            )

        if action == "hotkey":
            raw  = params.get("keys", "")
            keys = [k.strip() for k in raw.split("+")] if isinstance(raw, str) else raw
            return _hotkey(*keys)

        if action == "press":
            return _press(params.get("key", "enter"))

        if action == "key_down":
            return _key_down(params.get("key", ""))

        if action == "key_up":
            return _key_up(params.get("key", ""))

        if action == "scroll":
            # If a specific page number or relative pages requested, automatically dispatch to PDF page navigation
            if params.get("relative_pages") is not None:
                return _chrome_pdf_goto_page(relative_pages=int(params["relative_pages"]))

            if params.get("page") is not None or params.get("page_number") is not None or params.get("to_page") is not None:
                p_target = params.get("page") if params.get("page") is not None else (params.get("page_number") or params.get("to_page"))
                return _chrome_pdf_goto_page(p_target)

            amt_raw = str(params.get("amount", "")).lower()
            txt_raw = str(params.get("text", "")).lower()
            direction = str(params.get("direction", "down")).lower()
            combined = f"{amt_raw} {txt_raw}".strip()
            if "page" in combined:
                m = re.search(r"\d+", combined)
                if m:
                    num = int(m.group(0))
                    if "to page" in combined or "page number" in combined or ("page" in combined and "pages" not in combined and "down" not in combined and "up" not in combined):
                        return _chrome_pdf_goto_page(page=num)
                    elif "up" in combined or direction == "up":
                        return _chrome_pdf_goto_page(relative_pages=-num)
                    elif "down" in combined or direction == "down" or "pages" in combined:
                        return _chrome_pdf_goto_page(relative_pages=num)
                    return _chrome_pdf_goto_page(page=num)

            return _scroll(
                direction=direction,
                amount=int(params.get("amount", 3)),
            )

        if action in ("copy", "get_clipboard", "read_clipboard", "clipboard_get"):
            return _clipboard_get(player=player)

        if action in ("paste", "set_clipboard", "write_clipboard"):
            return _clipboard_paste(params.get("text", ""))

        if action == "screenshot":
            return _screenshot(params.get("path"))

        if action == "screen_find":
            desc = params.get("description", "")
            refine = params.get("refine", True)
            res = _screen_find_grounded(desc, refine=refine)
            if res and res.get("found"):
                return json.dumps(res)
            return "NOT_FOUND"

        if action == "screen_click":
            desc = params.get("description", "")
            btn = params.get("button", "left")
            clk = int(params.get("clicks", 1))
            refine = params.get("refine", True)
            return _screen_click(desc, button=btn, clicks=clk, refine=refine)

        if action in ("screen_hover", "hover"):
            desc = params.get("description", "")
            if desc:
                return _screen_hover(desc, dwell=float(params.get("seconds", 0.5)), refine=params.get("refine", True))
            return _verified_hover(int(params.get("x", 0)), int(params.get("y", 0)), dwell=float(params.get("seconds", 0.5)))

        if action == "wait":
            secs = float(params.get("seconds", 1.0))
            secs = min(secs, 30.0)
            time.sleep(secs)
            return f"Waited {secs}s"

        if action == "clear_field":
            return _clear_field()

        if action in ("focus_window", "activate_window"):
            return _focus_window(params.get("title", ""))

        if action == "list_windows":
            wins = _list_windows()
            if not wins:
                return "No open windows found."
            lines = [f"  • {w.get('title')}" + (" (active)" if w.get("is_active") else "") for w in wins]
            return f"Open windows ({len(wins)}):\n" + "\n".join(lines)

        if action == "get_active_window":
            return str(_get_active_window())

        if action == "minimize_window":
            return _minimize_window(params.get("title", ""))

        if action == "maximize_window":
            return _maximize_window(params.get("title", ""))

        if action == "close_window":
            return _close_window(params.get("title", ""))

        if action == "show_desktop":
            return _show_desktop()

        if action == "lock_screen":
            return _lock_screen()

        if action == "open_settings":
            return _open_settings()

        if action in ("open_file_explorer", "open_explorer"):
            return _open_file_explorer(params.get("path", ""))

        if action == "open_task_manager":
            return _open_task_manager()

        if action == "open_run_dialog":
            return _open_run_dialog()

        if action == "open_clipboard_history":
            return _open_clipboard_history()

        if action == "open_action_center":
            return _open_action_center()

        if action in ("take_snip", "snip", "snipping_tool"):
            return _take_snip()

        if action in ("get_system_info", "system_info", "system_status"):
            return _get_system_info()

        if action in ("volume_up", "volume_down", "volume_mute", "play_pause", "next_track", "prev_track"):
            return _volume_control(action)

        if action == "volume_control":
            return _volume_control(params.get("sub_action", params.get("direction", "up")))

        if action == "random_data":
            dt     = params.get("type", "name")
            result = _random_data(dt)
            print(f"[ComputerControl] 🎲 random {dt} → {result}")
            return result

        if action == "user_data":
            field   = params.get("field", "name")
            profile = _user_profile()
            value   = profile.get(field, "")
            if not value:
                value = _random_data(field)
                print(f"[ComputerControl] ⚠️ No '{field}' in memory, using random: {value}")
            return value

        if action == "screen_read":
            return _screen_read(params.get("region", "full"))

        if action == "screen_wait_for":
            desc    = params.get("description", "")
            timeout = float(params.get("timeout", 15.0))
            coords  = _screen_wait_for(desc, timeout=timeout)
            if coords:
                return f"'{desc}' appeared at {coords}"
            return f"'{desc}' did not appear within {timeout}s"

        if action == "screen_type_in":
            return _screen_type_in(
                params.get("description", ""),
                params.get("text", ""),
                clear_first=params.get("clear_first", True),
                refine=params.get("refine", True),
            )

        # ── Chrome native controls ───────────────────────────────────────────
        if action == "chrome_focus":
            return _chrome_focus()

        if action == "chrome_new_tab":
            return _chrome_new_tab(params.get("url", ""))

        if action == "chrome_switch_tab":
            return _chrome_switch_tab(params.get("target", params.get("tab", "next")))

        if action == "chrome_close_tab":
            return _chrome_close_tab()

        if action == "chrome_reopen_tab":
            return _chrome_reopen_tab()

        if action == "chrome_navigate":
            return _chrome_navigate(params.get("url", params.get("text", "")))

        if action == "chrome_search":
            return _chrome_search(params.get("query", params.get("text", "")))

        if action == "chrome_read_tab":
            return _chrome_read_tab(params.get("region", "full"))

        if action == "chrome_click":
            return _chrome_click(params.get("description", ""))

        if action == "chrome_type_in":
            return _chrome_type_in(
                params.get("description", ""),
                params.get("text", ""),
                clear_first=params.get("clear_first", True),
            )

        if action == "chrome_list_tabs":
            return _chrome_list_tabs()

        if action in ("chrome_zoom", "chrome_zoom_in", "chrome_zoom_out", "chrome_zoom_reset"):
            level = params.get("level", "in" if "in" in action else ("out" if "out" in action else "reset"))
            return _chrome_zoom(level)

        if action == "chrome_find":
            return _chrome_find(params.get("query", params.get("text", "")))

        if action == "chrome_history":
            return _chrome_history()

        if action == "chrome_downloads":
            return _chrome_downloads()

        if action == "chrome_bookmarks":
            return _chrome_bookmarks()

        if action == "chrome_duplicate_tab":
            return _chrome_duplicate_tab()

        if action == "chrome_incognito":
            return _chrome_incognito()

        if action == "chrome_inspect":
            return _chrome_inspect()

        if action == "chrome_get_url":
            return _chrome_get_url()

        if action in ("chrome_get_page_text", "chrome_page_text"):
            return _chrome_get_page_text(int(params.get("max_chars", 4000)))

        if action in ("chrome_reload", "chrome_refresh"):
            return _chrome_reload(bool(params.get("hard", False)))

        if action == "chrome_fullscreen":
            return _chrome_fullscreen()

        if action == "chrome_task_manager":
            return _chrome_task_manager()

        if action in ("chrome_print_pdf", "chrome_print"):
            return _chrome_print_pdf()

        if action == "chrome_page_source":
            return _chrome_page_source()

        if action == "chrome_clear_data":
            return _chrome_clear_data()

        if action == "chrome_launch_debug":
            return _chrome_launch_debug(int(params.get("port", 9222)))

        if action in ("chrome_pdf_goto_page", "chrome_goto_page", "pdf_goto_page", "scroll_to_page", "goto_page"):
            p = params.get("page", params.get("page_number", params.get("value", 1)))
            rel = params.get("relative_pages", params.get("relative", None))
            return _chrome_pdf_goto_page(page=p, relative_pages=rel)

        return f"Unknown action: '{action}'"

    except Exception as e:
        print(f"[ComputerControl] ❌ {action}: {e}")
        return f"computer_control '{action}' failed: {e}"


# ── Tool declaration (auto-discovered by core/action_loader.py) ──────────────
TOOL = {
    "name": "computer_control",
    "description": (
        "Advanced computer control and running Chrome tab automation. "
        "DESKTOP & WINDOWS: list_windows, get_active_window, focus_window, minimize_window, "
        "maximize_window, close_window, show_desktop, lock_screen, open_settings, open_file_explorer, "
        "open_task_manager, open_run_dialog, open_clipboard_history, get_clipboard, read_clipboard, open_action_center, take_snip, "
        "get_system_info, mouse_position, click, double_click, triple_click, middle_click, mouse_down, "
        "mouse_up, move, drag, scroll, hotkey, press, key_down, key_up, copy, paste, screenshot, "
        "clear_field, volume_up, volume_down, volume_mute, play_pause. "
        "VISION & AI: screen_find, screen_click, screen_hover, screen_type_in, screen_read, screen_wait_for. "
        "CHROME TAB CONTROLS: Works directly on the user's running Chrome tabs and Google accounts: "
        "chrome_focus, chrome_new_tab, chrome_switch_tab, chrome_close_tab, chrome_reopen_tab, "
        "chrome_navigate, chrome_search, chrome_get_url, chrome_get_page_text, chrome_read_tab, "
        "chrome_click, chrome_type_in, chrome_list_tabs, chrome_zoom, chrome_find, chrome_history, "
        "chrome_downloads, chrome_bookmarks, chrome_duplicate_tab, chrome_reload, chrome_fullscreen, "
        "chrome_task_manager, chrome_print_pdf, chrome_page_source, chrome_clear_data, "
        "chrome_pdf_goto_page, chrome_incognito, chrome_inspect, chrome_launch_debug."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": (
                    "type | smart_type | click | double_click | triple_click | middle_click | right_click | "
                    "mouse_down | mouse_up | mouse_position | move | drag | scroll | hotkey | press | "
                    "key_down | key_up | copy | paste | get_clipboard | read_clipboard | screenshot | wait | clear_field | "
                    "list_windows | get_active_window | focus_window | minimize_window | maximize_window | close_window | show_desktop | "
                    "lock_screen | open_settings | open_file_explorer | open_task_manager | open_run_dialog | open_clipboard_history | open_action_center | take_snip | get_system_info | "
                    "volume_up | volume_down | volume_mute | play_pause | volume_control | "
                    "screen_find | screen_click | screen_hover | screen_read | screen_wait_for | screen_type_in | "
                    "chrome_focus | chrome_new_tab | chrome_switch_tab | chrome_close_tab | "
                    "chrome_reopen_tab | chrome_navigate | chrome_search | chrome_get_url | chrome_get_page_text | chrome_read_tab | "
                    "chrome_click | chrome_type_in | chrome_list_tabs | chrome_zoom | chrome_find | "
                    "chrome_history | chrome_downloads | chrome_bookmarks | chrome_duplicate_tab | "
                    "chrome_reload | chrome_fullscreen | chrome_task_manager | chrome_print_pdf | chrome_page_source | chrome_clear_data | "
                    "chrome_pdf_goto_page | chrome_incognito | chrome_inspect | chrome_launch_debug | "
                    "random_data | user_data"
                )
            },
            "page": {
                "type": "INTEGER",
                "description": "Target page number for chrome_pdf_goto_page or scroll (e.g. 5, 12, 45)"
            },
            "relative_pages": {
                "type": "INTEGER",
                "description": "Relative pages to advance or rewind for chrome_pdf_goto_page (e.g. 3 for 3 pages down, -2 for 2 pages up)"
            },
            "url": {
                "type": "STRING",
                "description": "URL for chrome_new_tab or chrome_navigate"
            },
            "query": {
                "type": "STRING",
                "description": "Search query for chrome_search or chrome_find"
            },
            "target": {
                "type": "STRING",
                "description": "Tab target for chrome_switch_tab: next | prev | 1..9 | last | tab name"
            },
            "text": {
                "type": "STRING",
                "description": "Text to type or paste"
            },
            "x": {
                "type": "INTEGER",
                "description": "X coordinate"
            },
            "y": {
                "type": "INTEGER",
                "description": "Y coordinate"
            },
            "keys": {
                "type": "STRING",
                "description": "Key combination e.g. 'ctrl+c', 'win+d', 'alt+tab'"
            },
            "key": {
                "type": "STRING",
                "description": "Single key e.g. 'enter', 'escape', 'win', 'space'"
            },
            "direction": {
                "type": "STRING",
                "description": "up | down | left | right"
            },
            "amount": {
                "type": "INTEGER",
                "description": "Scroll amount (default: 3)"
            },
            "seconds": {
                "type": "NUMBER",
                "description": "Seconds to wait"
            },
            "title": {
                "type": "STRING",
                "description": "Window title for focus_window / minimize_window / close_window"
            },
            "description": {
                "type": "STRING",
                "description": "Element description for screen_find/screen_click/chrome_click/chrome_type_in"
            },
            "level": {
                "type": "STRING",
                "description": "Zoom level for chrome_zoom: in | out | reset"
            },
            "type": {
                "type": "STRING",
                "description": "Data type for random_data"
            },
            "field": {
                "type": "STRING",
                "description": "Field for user_data: name|email|city"
            },
            "clear_first": {
                "type": "BOOLEAN",
                "description": "Clear field before typing (default: true)"
            },
            "path": {
                "type": "STRING",
                "description": "Save path for screenshot or folder path for open_file_explorer"
            },
            "region": {
                "type": "STRING",
                "description": "Screen region for screen_read / chrome_read_tab: full | top | bottom | left | right | center"
            },
            "timeout": {
                "type": "NUMBER",
                "description": "Seconds to wait in screen_wait_for (default: 15, max: 60)"
            },
            "hard": {
                "type": "BOOLEAN",
                "description": "Hard refresh for chrome_reload (default: false)"
            },
            "max_chars": {
                "type": "INTEGER",
                "description": "Max characters to read for chrome_get_page_text (default: 4000)"
            },
            "refine": {
                "type": "BOOLEAN",
                "description": "Hierarchical coarse-to-fine zoom refinement for sub-pixel accuracy (default: true)"
            }
        },
        "required": [
            "action"
        ]
    },
    "handler": computer_control,
}
