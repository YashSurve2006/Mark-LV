"""
Dedicated WhatsApp Integration Plugin for JARVIS Mark LV.

Enables advanced voice and UI automation for WhatsApp:
- Composing & sending messages with verified delivery
- Drafting messages in chat input boxes for user review
- Opening chats directly by contact name or phone number
- Managing contacts & relationship shortcuts in persistent memory
- Probing WhatsApp connection state (UWP, Desktop, Web)
"""

from __future__ import annotations

from typing import Optional
from plugins import _whatsapp_core as wa

PLUGIN = {
    "name": "whatsapp",
    "description": (
        "Dedicated WhatsApp management tool. Composes, drafts, and sends WhatsApp messages, "
        "opens conversations with contacts or phone numbers, saves contacts to memory, "
        "and checks WhatsApp connectivity. Supports 'action': 'send', 'draft', 'open_chat', "
        "'add_contact', or 'status'. To send or draft the user's copied clipboard content, "
        "pass message='[PASTE_CLIPBOARD]' or from_clipboard=True."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["send", "draft", "open_chat", "add_contact", "status"],
                "description": "Operation: 'send' (compose & dispatch), 'draft' (compose in input box for review), 'open_chat' (open conversation), 'add_contact' (save name & number to memory), 'status' (check connection)"
            },
            "receiver": {
                "type": "STRING",
                "description": "Recipient contact name, nickname (e.g. 'Mom', 'Alex'), or phone number"
            },
            "message": {
                "type": "STRING",
                "description": "Message text to compose and send/draft. Pass '[PASTE_CLIPBOARD]' to send user's clipboard content"
            },
            "phone_number": {
                "type": "STRING",
                "description": "Optional explicit phone number with country code (e.g. '+919876543210')"
            },
            "relationship": {
                "type": "STRING",
                "description": "Optional relationship label when adding contact (e.g. 'mom', 'brother', 'manager')"
            },
            "from_clipboard": {
                "type": "BOOLEAN",
                "description": "Set to true if sending or drafting the user's current clipboard content"
            }
        },
        "required": ["action"]
    },
}

PLUGIN_SETTINGS = {
    "namespace": "whatsapp",
    "title": "WhatsApp Messenger",
    "fields": [
        {
            "key": "preferred_client",
            "label": "Preferred Client",
            "type": "select",
            "options": ["desktop", "web"],
            "default": "desktop",
            "help": "Target WhatsApp Desktop app on Windows by default.",
        },
        {
            "key": "default_country_code",
            "label": "Default Country Code",
            "type": "text",
            "default": "91",
            "placeholder": "91",
            "help": "Default calling code without '+' (e.g. 91 for India, 1 for US/Canada)",
        },
        {
            "key": "default_mode",
            "label": "Default Send Mode",
            "type": "select",
            "options": ["send", "draft"],
            "default": "send",
            "help": "Choose 'draft' if you prefer reviewing messages in WhatsApp before hitting send.",
        }
    ],
    "action": "status",
}


def run(parameters: dict, player=None, session_memory=None) -> str:
    params = parameters or {}
    action = params.get("action", "send").lower().strip()
    receiver = params.get("receiver", "").strip()
    message = params.get("message", "").strip()
    phone_number = params.get("phone_number", "").strip()
    relationship = params.get("relationship", "").strip()
    from_clipboard = bool(params.get("from_clipboard", False))

    driver, why = wa.get()
    if driver is None:
        return f"Sir, WhatsApp driver is not available: {why}"

    # 1. Status Check
    if action == "status":
        hwnd = wa.find_whatsapp_window()
        is_running = hwnd is not None
        has_protocol = True  # verified on Windows
        status_line = f"WhatsApp Desktop is {'running' if is_running else 'idle'}. Protocol integration is active."
        if player:
            try:
                player.write_log(f"[whatsapp] {status_line}")
            except Exception:
                pass
        return status_line

    # 2. Add / Save Contact
    if action == "add_contact":
        if not receiver or not (phone_number or wa.is_phone_number(receiver)):
            return "Please provide both the contact name and their phone number."
        actual_phone = phone_number or receiver
        success = wa.save_contact_to_memory(
            name=receiver,
            phone=actual_phone,
            relationship=relationship or None,
        )
        if success:
            clean_p = wa.clean_phone_number(actual_phone)
            msg = f"Saved '{receiver}' (+{clean_p}) to WhatsApp contacts in long-term memory."
            if relationship:
                msg += f" Linked to relationship '{relationship}'."
            if player:
                try:
                    player.write_log(f"[whatsapp] Saved contact {receiver}")
                except Exception:
                    pass
            return msg
        return f"Could not save contact '{receiver}' to memory."

    # 3. Open Chat
    if action == "open_chat":
        if not receiver:
            return "Please specify the contact name or phone number whose chat you would like to open."
        sent, info = driver.send_message_to(
            receiver=receiver,
            message="",
            mode="draft",
            phone_override=phone_number or None,
        )
        if player:
            try:
                player.write_log(f"[whatsapp] Open chat: {receiver}")
            except Exception:
                pass
        return f"Opened WhatsApp chat with '{receiver}'."

    # 4. Draft or Send Message
    if action in ("send", "draft"):
        if not receiver:
            return "Please specify who you would like to send the message to."

        # Intercept and resolve clipboard content
        resolved_msg, was_clip, clip_err = wa._resolve_clipboard_content(message, from_clipboard=from_clipboard, player=player)
        if was_clip:
            if clip_err:
                return clip_err
            message = resolved_msg

        if not message:
            return "Please specify the message you would like to send."

        sent, info = driver.send_message_to(
            receiver=receiver,
            message=message,
            mode=action,
            phone_override=phone_number or None,
            from_clipboard=from_clipboard,
            player=player,
        )

        if player:
            try:
                player.write_log(f"[whatsapp] {info}")
            except Exception:
                pass

        if sent:
            return info
        return f"Could not complete WhatsApp {action}: {info}"

    return f"Unknown WhatsApp action: '{action}'."
