import json
import subprocess
import sys
import time
from pathlib import Path

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE    = 0.06
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

def _get_os() -> str:
    try:
        cfg = json.loads(
            (_base_dir() / "config" / "api_keys.json").read_text(encoding="utf-8")
        )
        return cfg.get("os_system", "windows").lower()
    except Exception:
        return "windows"


def _require_pyautogui():
    if not _PYAUTOGUI:
        raise RuntimeError("PyAutoGUI not installed. Run: pip install pyautogui")


def _paste_text(text: str) -> None:
    _require_pyautogui()

    os_name = _get_os()
    paste_hotkey = ("command", "v") if os_name == "mac" else ("ctrl", "v")

    if _PYPERCLIP:
        pyperclip.copy(text)
        time.sleep(0.15)
        pyautogui.hotkey(*paste_hotkey)
        time.sleep(0.1)
    else:
        pyautogui.write(text, interval=0.03)


def _clear_and_paste(text: str) -> None:
    _require_pyautogui()
    os_name = _get_os()
    select_all = ("command", "a") if os_name == "mac" else ("ctrl", "a")
    pyautogui.hotkey(*select_all)
    time.sleep(0.1)
    pyautogui.press("delete")
    time.sleep(0.1)
    _paste_text(text)

def _open_app(app_name: str) -> bool:
    _require_pyautogui()
    os_name = _get_os()

    try:
        if os_name == "windows":
            pyautogui.press("win")
            time.sleep(0.5)
            _paste_text(app_name)
            time.sleep(0.6)
            pyautogui.press("enter")
            time.sleep(2.5)
            return True

        elif os_name == "mac":
            result = subprocess.run(
                ["open", "-a", app_name],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                result = subprocess.run(
                    ["open", "-a", f"{app_name}.app"],
                    capture_output=True, text=True, timeout=10,
                )
            time.sleep(2.5)
            return result.returncode == 0

        else: 
            launched = False
            for launcher in [
                ["gtk-launch", app_name.lower()],
                [app_name.lower()],
            ]:
                try:
                    subprocess.Popen(
                        launcher,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    launched = True
                    break
                except FileNotFoundError:
                    continue
            time.sleep(2.5)
            return launched

    except Exception as e:
        print(f"[SendMessage] ⚠️ Could not open {app_name}: {e}")
        return False


def _open_browser_url(url: str) -> bool:
    import webbrowser
    try:
        webbrowser.open(url)
        time.sleep(4.0) 
        return True
    except Exception as e:
        print(f"[SendMessage] ⚠️ Could not open browser: {e}")
        return False

def _search_in_app(query: str) -> None:
    _require_pyautogui()
    os_name = _get_os()
    search_hotkey = ("command", "f") if os_name == "mac" else ("ctrl", "f")

    pyautogui.hotkey(*search_hotkey)
    time.sleep(0.5)
    _clear_and_paste(query)
    time.sleep(1.0)

def _desktop_send(app_name: str, receiver: str, message: str) -> str:
    if not _open_app(app_name):
        return f"Could not open {app_name}."

    time.sleep(1.0)
    _search_in_app(receiver)
    pyautogui.press("enter")
    time.sleep(0.8)

    _paste_text(message)
    time.sleep(0.2)
    pyautogui.press("enter")
    time.sleep(0.3)
    return f"Message sent to {receiver} via {app_name}."

def _send_whatsapp(receiver: str, message: str, mode: str = "send", phone_number: str = None) -> str:
    """WhatsApp multi-tier verified driver:
    1. Protocol Deep-Link (whatsapp://send?phone=...&text=...)
    2. Desktop/UWP UI Automation (Window focus, Ctrl+F, chat selection)
    3. WhatsApp Web in browser fallback
    """
    try:
        from plugins import _whatsapp_core as wa
    except Exception as e:
        print(f"[SendMessage] WhatsApp driver unavailable ({e}) — typing blind.")
        return _desktop_send("WhatsApp", receiver, message)

    try:
        transport, why = wa.get()
    except Exception as e:
        print(f"[SendMessage] WhatsApp driver failed to start ({e}) — typing blind.")
        return _desktop_send("WhatsApp", receiver, message)

    if transport is None:
        print(f"[SendMessage] {why} — typing blind.")
        return _desktop_send("WhatsApp", receiver, message)

    sent, status_msg = transport.send_message_to(
        receiver=receiver,
        message=message,
        mode=mode,
        phone_override=phone_number,
    )
    if sent:
        return status_msg
    return (f"The message to {receiver} was NOT sent on WhatsApp: {status_msg}. "
            f"Tell the user plainly that it was not sent, and why - do not "
            f"say it was sent.")

def _send_telegram(receiver: str, message: str, **kwargs) -> str:
    return _desktop_send("Telegram", receiver, message)

def _send_signal(receiver: str, message: str, **kwargs) -> str:
    return _desktop_send("Signal", receiver, message)


def _send_discord(receiver: str, message: str, **kwargs) -> str:
    return _desktop_send("Discord", receiver, message)


def _send_instagram(receiver: str, message: str, **kwargs) -> str:
    _require_pyautogui()

    if not _open_browser_url("https://www.instagram.com/direct/new/"):
        return "Could not open Instagram in browser."

    _paste_text(receiver)
    time.sleep(1.5)

    pyautogui.press("down")
    time.sleep(0.3)
    pyautogui.press("enter")   
    time.sleep(0.4)

    for _ in range(4):
        pyautogui.press("tab")
        time.sleep(0.15)
    pyautogui.press("enter")
    time.sleep(2.0)

    _paste_text(message)
    time.sleep(0.2)
    pyautogui.press("enter")
    time.sleep(0.3)

    return f"Message sent to {receiver} via Instagram."


def _send_messenger(receiver: str, message: str, **kwargs) -> str:
    _require_pyautogui()

    if not _open_browser_url("https://www.messenger.com/"):
        return "Could not open Messenger in browser."

    _search_in_app(receiver)
    time.sleep(0.5)
    pyautogui.press("down")
    time.sleep(0.3)
    pyautogui.press("enter")
    time.sleep(1.0)

    _paste_text(message)
    time.sleep(0.2)
    pyautogui.press("enter")
    time.sleep(0.3)

    return f"Message sent to {receiver} via Messenger."

_PLATFORM_MAP = [
    ({"whatsapp", "wp", "wapp"},              _send_whatsapp),
    ({"telegram", "tg"},                      _send_telegram),
    ({"instagram", "ig", "insta"},            _send_instagram),
    ({"signal"},                               _send_signal),
    ({"discord"},                              _send_discord),
    ({"messenger", "facebook", "fb"},         _send_messenger),
]


def _resolve_platform(platform_str: str):
    key = (platform_str or "whatsapp").lower().strip()
    for keywords, handler in _PLATFORM_MAP:
        if any(k in key for k in keywords):
            return handler
    return lambda r, m, **kw: _desktop_send(platform_str.strip().title(), r, m)


def send_message(
    parameters: dict,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params       = parameters or {}
    receiver     = params.get("receiver", "").strip()
    message_text = params.get("message_text", "").strip()
    platform     = params.get("platform", "whatsapp").strip()
    mode         = str(params.get("mode", "send")).strip().lower()
    if mode not in ("send", "draft"):
        mode = "send"
    phone_number = params.get("phone_number", "").strip() or None

    if not receiver:
        return "Please specify a recipient contact name or phone number."
    if not message_text:
        return "Please specify the message content to send."
    if not _PYAUTOGUI:
        return "PyAutoGUI is not installed — cannot control the desktop."

    preview = message_text[:50] + ("…" if len(message_text) > 50 else "")
    action_type = "Drafting" if mode == "draft" else "Sending"
    print(f"[SendMessage] 📨 {action_type} via {platform} → {receiver}: {preview}")
    if player:
        player.write_log(f"[msg] {action_type} {platform} → {receiver}")

    try:
        handler = _resolve_platform(platform)
        if handler == _send_whatsapp:
            result = handler(receiver, message_text, mode=mode, phone_number=phone_number)
        else:
            result = handler(receiver, message_text)
    except Exception as e:
        result = f"Could not send message: {e}"

    lowered = result.lower()
    ok = ("sent" in lowered or "draft" in lowered) and "not sent" not in lowered
    print(f"[SendMessage] {'✅' if ok else '❌'} {result}")
    if player:
        player.write_log(f"[msg] {result}")

    return result


# ── Tool declaration (auto-discovered by core/action_loader.py) ──────────────
TOOL = {
    "name": "send_message",
    "description": (
        "Composes, drafts, and sends messages through WhatsApp, Telegram, or other messaging "
        "platforms. For WhatsApp, supports recipient contact names, relationship nicknames "
        "(e.g. 'Mom', 'Alex', 'brother'), or international phone numbers (e.g. '+919876543210'). "
        "Supports 'mode': 'send' (automatically sends) or 'draft' (composes message in chat input "
        "box for the user to review before sending). Write 'message_text' in the USER'S OWN LANGUAGE, "
        "exactly what they requested to be communicated. If the result says the message was NOT sent, "
        "repeat that plainly along with the specific reason."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "receiver": {
                "type": "STRING",
                "description": "Recipient contact name, relationship alias (e.g. 'Mom', 'boss'), or phone number (e.g. '+919876543210')"
            },
            "message_text": {
                "type": "STRING",
                "description": "The exact message content to compose and send or draft"
            },
            "platform": {
                "type": "STRING",
                "description": "Messaging platform: 'whatsapp' (default), 'telegram', 'discord', 'signal', 'instagram', 'messenger'"
            },
            "mode": {
                "type": "STRING",
                "enum": ["send", "draft"],
                "description": "'send' to dispatch the message immediately, or 'draft' to compose into the WhatsApp input box without pressing Enter so user can visually inspect it"
            },
            "phone_number": {
                "type": "STRING",
                "description": "Optional direct phone number with country code if receiver is a contact name or nickname"
            }
        },
        "required": [
            "receiver",
            "message_text"
        ]
    },
    "handler": send_message,
}
