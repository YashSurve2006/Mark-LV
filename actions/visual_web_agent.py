"""
visual_web_agent.py — Advanced Visual Grounding & Browser Intelligence for JARVIS Mark-LV
==========================================================================================

This module adds four major capabilities on top of the existing browser_control + computer_control:

1.  SET-OF-MARKS (SoM) VISUAL GROUNDING
    Overlays numbered coloured bounding boxes (⌗1, ⌗2, …) on every interactive element
    visible on screen before the AI looks at it.  The AI only needs to say "click ⌗14"
    — it never has to guess a pixel coordinate.  This is the exact technique used by
    Microsoft's OmniParser and SeeClick.

2.  ACCESSIBILITY TREE (A11y) SEMANTIC ACTUATION
    Instead of relying on pixels, reads the browser's internal Accessibility Tree (or the
    Playwright DOM) to find buttons, inputs, comboboxes and links by their ARIA role, label,
    placeholder and semantic context.  10× faster than pure vision and immune to layout
    shifts, infinite scroll reflows and SVG overlays.

3.  SCROLL-AND-SEEK LOOP
    Autonomously scrolls through a page (down then up) in configurable steps, capturing a
    fresh screenshot and re-running visual grounding after each scroll, until the target
    element is found or the scroll budget is exhausted.

4.  VERIFIED FIELD EDITING
    After typing into a field, immediately re-reads the field's value and compares it with
    what was intended.  If the values differ (partial paste, focus lost, rich-text editor
    quirk), it retries with an alternative strategy (click → select-all → paste vs. type).

PUBLIC ENTRY POINT
    visual_web_agent(parameters, response=None, player=None, session_memory=None) -> str

    Actions (parameters["action"]):
        som_click           — SoM overlay click: take screenshot, label elements, AI picks one
        som_type            — SoM overlay type:  same, then type into the chosen element
        a11y_click          — Accessibility-tree semantic click (fastest, most reliable)
        a11y_type           — Accessibility-tree semantic type
        scroll_to_element   — Scroll until element is visible, then optionally click
        wait_for_element    — Poll screen until element appears (with timeout)
        edit_field_verified — Focus, clear, paste, verify — with retry on mismatch
        read_page_structure — Full A11y dump of page structure (for debugging / planning)
        dom_query           — Run a CSS / XPath / text selector query and return matches
        smart_form_fill     — Fill multiple fields with verification, in one call
        multi_step          — Execute a JSON list of sub-actions in sequence
"""

from __future__ import annotations

import asyncio
import io
import json
import re
import time
from typing import Any

# ── Optional imports ───────────────────────────────────────────────────────────
try:
    from PIL import Image, ImageDraw, ImageFont
    _PIL = True
except ImportError:
    _PIL = False

try:
    import pyperclip
    _PYPERCLIP = True
except ImportError:
    _PYPERCLIP = False

try:
    import pyautogui
    _PYAUTOGUI = True
except ImportError:
    _PYAUTOGUI = False

try:
    from playwright.async_api import Page, TimeoutError as PlaywrightTimeout
    _PLAYWRIGHT = True
except ImportError:
    _PLAYWRIGHT = False


# ══════════════════════════════════════════════════════════════════════════════
# §1  HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _gemini_call(parts: list, tier: str = "smart", timeout_ms: int = 30_000):
    """Call Gemini via the existing core.gemini wrapper."""
    try:
        from core import gemini
        tier_obj = gemini.SMART if tier == "smart" else gemini.FAST
        return gemini.call(parts, tier=tier_obj, timeout_ms=timeout_ms)
    except Exception as e:
        print(f"[VWA] gemini_call failed: {e}")
        return None


def _pil_to_bytes(img: Image.Image, fmt: str = "PNG") -> bytes:
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


def _parse_json_from_text(text: str) -> Any:
    """Extract and parse the first JSON object/array embedded in model output."""
    if not text:
        return None
    m = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    try:
        return json.loads(text.strip())
    except Exception:
        return None


def _log(player, msg: str):
    try:
        print(f"[VWA] {msg}")
    except UnicodeEncodeError:
        try:
            print(f"[VWA] {msg.encode('ascii', errors='replace').decode('ascii')}")
        except Exception:
            pass
    try:
        if player and hasattr(player, "log"):
            player.log(msg)
        elif player and hasattr(player, "write_log"):
            player.write_log(f"[vwa] {str(msg)[:60]}")
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════════════
# §2  SET-OF-MARKS (SoM) ENGINE
# ══════════════════════════════════════════════════════════════════════════════

_SOM_COLOURS = [
    "#FF4444", "#FF8C00", "#FFD700", "#32CD32", "#00BFFF",
    "#9370DB", "#FF69B4", "#00CED1", "#FF6347", "#7FFF00",
    "#DC143C", "#1E90FF", "#FF1493", "#00FA9A", "#FF8C00",
]

_SOM_DOM_SCRIPT = """
() => {
    const ROLES = ['button','a','input','select','textarea',
                   '[role=button]','[role=tab]','[role=menuitem]',
                   '[role=checkbox]','[role=radio]','[role=combobox]',
                   '[role=listbox]','[role=option]','[role=switch]','[tabindex]'];
    const selector = ROLES.join(',');
    const els = Array.from(document.querySelectorAll(selector));
    const results = [];
    for (const el of els) {
        const r = el.getBoundingClientRect();
        if (r.width < 4 || r.height < 4) continue;
        if (r.top < -50 || r.bottom > window.innerHeight + 50) continue;
        const style = window.getComputedStyle(el);
        if (style.display === 'none' || style.visibility === 'hidden' ||
            parseFloat(style.opacity) < 0.05) continue;
        results.push({
            tag:   el.tagName.toLowerCase(),
            role:  el.getAttribute('role') || el.tagName.toLowerCase(),
            label: (el.getAttribute('aria-label') || el.getAttribute('title') ||
                    el.getAttribute('placeholder') || el.innerText || '').slice(0,80),
            type:  el.getAttribute('type') || '',
            name:  el.getAttribute('name') || el.getAttribute('id') || '',
            x:     Math.round(r.left + r.width  / 2),
            y:     Math.round(r.top  + r.height / 2),
            w:     Math.round(r.width),
            h:     Math.round(r.height),
            left:  Math.round(r.left),
            top:   Math.round(r.top),
        });
    }
    return results;
}
"""


def _draw_som_overlay(
    img: "Image.Image", elements: list[dict]
) -> "tuple[Image.Image, list[dict]]":
    """
    Draw numbered coloured bounding boxes + labels on `img`.
    Returns (annotated_image, elements_with_index).
    """
    if not _PIL or not elements:
        return img, elements

    annotated = img.copy()
    draw = ImageDraw.Draw(annotated, "RGBA")

    # Font loading with multi-path fallback
    def _load_font(size: int):
        for path in ("arial.ttf", "Arial.ttf",
                     "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
        return ImageFont.load_default()

    font_idx = _load_font(11)

    labelled = []
    for i, el in enumerate(elements):
        idx      = i + 1
        colour   = _SOM_COLOURS[i % len(_SOM_COLOURS)]
        w, h     = max(el.get("w", 30), 20), max(el.get("h", 20), 14)
        left     = el.get("left", el.get("x", 0) - w // 2)
        top      = el.get("top",  el.get("y", 0) - h // 2)

        # Semi-transparent fill + solid border
        fill_rgba  = tuple(int(colour.lstrip("#")[i:i+2], 16) for i in (0, 2, 4)) + (40,)
        draw.rectangle([left, top, left + w, top + h],
                       fill=fill_rgba, outline=colour, width=2)

        # Index badge
        badge_text = f"#{idx}"
        try:
            bbox = draw.textbbox((0, 0), badge_text, font=font_idx)
            bw, bh = bbox[2] - bbox[0], bbox[3] - bbox[1]
        except Exception:
            bw, bh = 22, 13

        bx = max(0, left)
        by = max(0, top - bh - 2)
        badge_fill = tuple(int(colour.lstrip("#")[j:j+2], 16) for j in (0, 2, 4)) + (230,)
        draw.rectangle([bx - 1, by - 1, bx + bw + 2, by + bh + 2], fill=badge_fill)
        draw.text((bx, by), badge_text, fill="white", font=font_idx)

        labelled.append({**el, "som_index": idx})

    return annotated, labelled


async def _page_som_elements(page) -> list[dict]:
    """Extract interactive elements from the page DOM using JavaScript injection."""
    try:
        els = await page.evaluate(_SOM_DOM_SCRIPT)
        if els:
            return els
    except Exception:
        pass
    # Minimal fallback
    try:
        fallback_script = """() => {
            return Array.from(document.querySelectorAll('a,button,input,select,textarea,[role=button],[tabindex]'))
            .filter(el => {
                const r = el.getBoundingClientRect();
                const s = window.getComputedStyle(el);
                return r.width>4 && r.height>4 && s.display!=='none';
            }).map(el => {
                const r = el.getBoundingClientRect();
                return {tag:el.tagName.toLowerCase(),
                        label:(el.getAttribute('aria-label')||el.innerText||'').slice(0,60),
                        x:Math.round(r.left+r.width/2), y:Math.round(r.top+r.height/2),
                        w:Math.round(r.width), h:Math.round(r.height),
                        left:Math.round(r.left), top:Math.round(r.top)};
            });
        }"""
        els = await page.evaluate(fallback_script)
        return els or []
    except Exception:
        return []


async def _som_pick_element(page, description: str) -> dict | None:
    """
    Full SoM pipeline:
    1. Extract DOM elements → draw numbered overlay → ask AI which number → return element.
    """
    from google.genai import types as gtypes

    elements = await _page_som_elements(page)
    if not elements:
        print("[VWA][SoM] No DOM elements -- falling back to full-screen grounding")
        return None

    # Screenshot of current viewport
    raw_png = await page.screenshot(full_page=False)
    if not _PIL:
        print("[VWA][SoM] PIL not available -- cannot draw overlay")
        return None

    base_img = Image.open(io.BytesIO(raw_png)).convert("RGB")
    annotated, labelled = _draw_som_overlay(base_img, elements)

    # Compact element manifest
    manifest_lines = []
    for el in labelled[:80]:
        line = f"  #{el['som_index']} [{el.get('tag','?')}] \"{el.get('label','').strip()}\""
        if el.get("type"):
            line += f" type={el['type']}"
        manifest_lines.append(line)
    manifest = "\n".join(manifest_lines)

    prompt = (
        f"You are a GUI agent. The screenshot shows an annotated web page.\n"
        f"Every interactive element has a numbered badge (#1, #2, …) drawn on it.\n\n"
        f"TASK: Find the element that best matches: \"{description}\"\n\n"
        f"ELEMENT MANIFEST (index, tag, label):\n{manifest}\n\n"
        f"OUTPUT FORMAT — strict JSON only:\n"
        f'```json\n{{"found": true, "index": <integer>, "label": "<matched label>", "confidence": 0.97}}\n```\n'
        f'If no element matches: {{"found": false, "reason": "<why>"}}'
    )

    annotated_bytes = _pil_to_bytes(annotated, "PNG")
    resp = _gemini_call(
        [gtypes.Part.from_bytes(data=annotated_bytes, mime_type="image/png"), prompt],
        tier="fast",
        timeout_ms=18_000,
    )
    if not resp:
        return None

    data = _parse_json_from_text(resp.text or "")
    if not isinstance(data, dict) or not data.get("found"):
        print(f"[VWA][SoM] No match for '{description}': {(resp.text or '')[:120]}")
        return None

    idx = int(data.get("index", 0))
    matched = next((e for e in labelled if e.get("som_index") == idx), None)
    if matched:
        print(f"[VWA][SoM] #{idx} '{matched.get('label', description)}' conf={data.get('confidence',0):.2f}")
    return matched


# ══════════════════════════════════════════════════════════════════════════════
# §3  ACCESSIBILITY TREE & DOM SEMANTIC ACTUATION
# ══════════════════════════════════════════════════════════════════════════════

_A11Y_ROLES_CLICKABLE = [
    "button", "link", "menuitem", "tab", "checkbox", "radio",
    "switch", "option", "treeitem", "columnheader", "rowheader",
]


async def _a11y_find_clickable(
    page, description: str, scroll_budget: int = 5
) -> dict | None:
    """
    Find a clickable element using the Playwright Accessibility Tree.
    Tries exact-match aria-label/text first, then fuzzy substring match.
    Scrolls up to `scroll_budget` times for off-screen elements.
    Returns dict with {locator, label, role, method} or None.
    """
    desc_lower = description.lower().strip()

    async def _try_roles(pg) -> dict | None:
        # 1. Try each semantic role with case-insensitive name regex
        for role in _A11Y_ROLES_CLICKABLE:
            try:
                loc = pg.get_by_role(role, name=re.compile(re.escape(description), re.I))
                if await loc.count() > 0:
                    return {"locator": loc.first, "role": role,
                            "label": description, "method": "role-exact"}
            except Exception:
                pass

        # 2. ARIA attribute fuzzy selectors
        try:
            loc = pg.locator(
                f'[aria-label*="{description}" i],[title*="{description}" i],'
                f'[alt*="{description}" i],[data-testid*="{desc_lower}"]'
            )
            if await loc.count() > 0:
                return {"locator": loc.first, "role": "aria-attr",
                        "label": description, "method": "aria-attr"}
        except Exception:
            pass

        # 3. Inner-text partial match — prefer small interactive elements
        try:
            loc = pg.get_by_text(description, exact=False)
            cnt = await loc.count()
            if cnt > 0:
                for i in range(min(cnt, 5)):
                    el  = loc.nth(i)
                    tag = await el.evaluate("el => el.tagName.toLowerCase()")
                    if tag in ("button", "a", "li", "span", "div", "input"):
                        return {"locator": el, "role": tag,
                                "label": description, "method": "text"}
                return {"locator": loc.first, "role": "text",
                        "label": description, "method": "text"}
        except Exception:
            pass

        # 4. :has-text() for button/link wrappers
        try:
            loc = pg.locator(
                f'button:has-text("{description}"),a:has-text("{description}"),'
                f'[role=button]:has-text("{description}")'
            )
            if await loc.count() > 0:
                return {"locator": loc.first, "role": "has-text",
                        "label": description, "method": "has-text"}
        except Exception:
            pass

        return None

    result = await _try_roles(page)
    if result:
        return result

    for i in range(scroll_budget):
        await page.mouse.wheel(0, 500)
        await asyncio.sleep(0.4)
        result = await _try_roles(page)
        if result:
            print(f"[VWA][A11y] Found '{description}' after {i+1} scroll(s)")
            return result

    return None


async def _a11y_find_typeable(
    page, description: str, scroll_budget: int = 4
) -> dict | None:
    """Find a text-input (textbox, searchbox, combobox) by semantic label/placeholder."""
    desc_lower = description.lower().strip()

    async def _try_inputs(pg) -> dict | None:
        candidates = [
            ("placeholder", pg.get_by_placeholder(description, exact=False)),
            ("label",       pg.get_by_label(description, exact=False)),
            ("role-textbox",pg.get_by_role("textbox",
                                           name=re.compile(re.escape(description), re.I))),
            ("role-search", pg.get_by_role("searchbox")),
            ("role-combo",  pg.get_by_role("combobox",
                                           name=re.compile(re.escape(description), re.I))),
            ("css-name",    pg.locator(f'input[name*="{desc_lower}" i],'
                                       f'textarea[name*="{desc_lower}" i]')),
            ("css-id",      pg.locator(f'input[id*="{desc_lower}" i],'
                                       f'textarea[id*="{desc_lower}" i]')),
            ("css-ph",      pg.locator(f'input[placeholder*="{description}" i],'
                                       f'textarea[placeholder*="{description}" i]')),
            ("contenteditable",
                            pg.locator(f'[aria-label*="{description}" i][contenteditable]')),
        ]
        for method, loc in candidates:
            try:
                if await loc.count() > 0:
                    return {"locator": loc.first, "method": method, "label": description}
            except Exception:
                pass
        return None

    result = await _try_inputs(page)
    if result:
        return result

    for i in range(scroll_budget):
        await page.mouse.wheel(0, 500)
        await asyncio.sleep(0.35)
        result = await _try_inputs(page)
        if result:
            print(f"[VWA][A11y] Found input '{description}' after {i+1} scroll(s)")
            return result

    return None


# ══════════════════════════════════════════════════════════════════════════════
# §4  SCROLL-AND-SEEK LOOP
# ══════════════════════════════════════════════════════════════════════════════

async def _scroll_to_element_and_click(
    page,
    description: str,
    click: bool = True,
    max_scrolls: int = 12,
    scroll_step: int = 600,
) -> str:
    """
    Scroll through the page incrementally (down pass then up pass),
    re-running A11y search after each step, until found.
    Optionally click the element once found.
    """

    async def _try(pg):
        found = await _a11y_find_clickable(pg, description, scroll_budget=0)
        if not found:
            found = await _a11y_find_typeable(pg, description, scroll_budget=0)
        return found

    # No-scroll attempt
    found = await _try(page)
    if found:
        loc = found["locator"]
        try:
            await loc.scroll_into_view_if_needed(timeout=4_000)
        except Exception:
            pass
        if click:
            await loc.click(timeout=6_000)
            return f"Clicked '{description}' [{found['method']}] without scrolling"
        return f"Found '{description}' [{found['method']}] without scrolling"

    # Down pass
    for i in range(max_scrolls // 2):
        await page.mouse.wheel(0, scroll_step)
        await asyncio.sleep(0.3)
        found = await _try(page)
        if found:
            loc = found["locator"]
            try:
                await loc.scroll_into_view_if_needed(timeout=4_000)
            except Exception:
                pass
            if click:
                await loc.click(timeout=6_000)
                return f"Clicked '{description}' [{found['method']}] after {i+1} down-scrolls"
            return f"Found '{description}' [{found['method']}] after {i+1} down-scrolls"

    # Reset to top + up pass
    await page.keyboard.press("Control+Home")
    await asyncio.sleep(0.4)

    for i in range(max_scrolls // 2):
        found = await _try(page)
        if found:
            loc = found["locator"]
            try:
                await loc.scroll_into_view_if_needed(timeout=4_000)
            except Exception:
                pass
            if click:
                await loc.click(timeout=6_000)
                return f"Clicked '{description}' [{found['method']}] on upward pass (step {i})"
            return f"Found '{description}' on upward pass"
        await page.mouse.wheel(0, scroll_step // 2)
        await asyncio.sleep(0.25)

    return f"Could not find '{description}' after {max_scrolls} scroll passes"


# ══════════════════════════════════════════════════════════════════════════════
# §5  VERIFIED FIELD EDITING
# ══════════════════════════════════════════════════════════════════════════════

async def _edit_field_verified(
    page,
    field_description: str,
    text: str,
    max_retries: int = 3,
) -> str:
    """
    Locate a field, clear it, paste the text, then read back the field value
    and verify it matches. Retries with 4 escalating strategies on mismatch.

    Strategies:
        1. triple-click select-all → clipboard paste
        2. click → Ctrl+A → clipboard paste
        3. JavaScript native value setter + input/change events
        4. Playwright fill() (bypasses React/Vue synthetic event quirks)
    """
    found = await _a11y_find_typeable(page, field_description)
    if not found:
        found_click = await _a11y_find_clickable(page, field_description)
        if not found_click:
            return f"Could not find field '{field_description}' via A11y"
        loc = found_click["locator"]
    else:
        loc = found["locator"]

    try:
        await loc.scroll_into_view_if_needed(timeout=5_000)
    except Exception:
        pass

    async def _read_value(el) -> str:
        try:
            return await el.input_value(timeout=2_000)
        except Exception:
            pass
        try:
            return str(await el.evaluate(
                "el => el.value || el.innerText || el.textContent || ''"
            ) or "")
        except Exception:
            return ""

    async def _strategy_1(el):
        """Triple-click select-all + clipboard paste."""
        await el.click(click_count=3, timeout=5_000)
        await asyncio.sleep(0.1)
        if _PYPERCLIP:
            pyperclip.copy(text)
            if _PYAUTOGUI:
                pyautogui.hotkey("ctrl", "v")
            else:
                await page.keyboard.press("Control+v")
        else:
            await el.type(text, delay=20)

    async def _strategy_2(el):
        """Click → Ctrl+A → clipboard paste."""
        await el.click(timeout=5_000)
        await asyncio.sleep(0.05)
        await page.keyboard.press("Control+a")
        await asyncio.sleep(0.05)
        if _PYPERCLIP:
            pyperclip.copy(text)
            await page.keyboard.press("Control+v")
        else:
            await el.type(text, delay=20)

    async def _strategy_3(el):
        """JavaScript native value setter + React/Angular event dispatch."""
        await el.focus(timeout=5_000)
        await asyncio.sleep(0.1)
        escaped = json.dumps(text)
        await page.evaluate(
            f"""(el) => {{
                el.focus();
                const nativeSetter = (
                    Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value') ||
                    Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value')
                )?.set;
                if (nativeSetter) {{
                    nativeSetter.call(el, {escaped});
                    el.dispatchEvent(new Event('input',  {{bubbles: true}}));
                    el.dispatchEvent(new Event('change', {{bubbles: true}}));
                }} else {{
                    document.execCommand('selectAll');
                    document.execCommand('insertText', false, {escaped});
                }}
            }}""",
            el,
        )

    async def _strategy_4(el):
        """Playwright fill() — cleanest for SPAs."""
        await el.fill(text, timeout=8_000)

    strategies = [_strategy_1, _strategy_2, _strategy_3, _strategy_4]

    for attempt, strategy in enumerate(strategies, 1):
        if attempt > max_retries + 1:
            break
        try:
            await strategy(loc)
            await asyncio.sleep(0.3)
            current = await _read_value(loc)
            if text.strip().lower() in current.strip().lower() or current.strip() == text.strip():
                return (
                    f"Edited '{field_description}' OK "
                    f"[strategy {attempt}, value='{current[:60]}']"
                )
            print(
                f"[VWA][EditVerify] Attempt {attempt} mismatch: "
                f"expected '{text[:40]}' got '{current[:40]}'"
            )
        except Exception as e:
            print(f"[VWA][EditVerify] Strategy {attempt} error: {e}")

    # Last-resort unverified paste
    try:
        await loc.click(timeout=5_000)
        await page.keyboard.press("Control+a")
        await asyncio.sleep(0.1)
        if _PYPERCLIP:
            pyperclip.copy(text)
            await page.keyboard.press("Control+v")
        else:
            await loc.type(text, delay=30)
        return f"Edited '{field_description}' [fallback, unverified]"
    except Exception as e:
        return f"All edit strategies failed for '{field_description}': {e}"


# ══════════════════════════════════════════════════════════════════════════════
# §6  PAGE STRUCTURE READER (A11y DUMP)
# ══════════════════════════════════════════════════════════════════════════════

_PAGE_STRUCTURE_SCRIPT = """
() => {
    function walk(el, depth) {
        if (depth > 5) return null;
        const role  = el.getAttribute('role') || el.tagName.toLowerCase();
        const label = (el.getAttribute('aria-label') || el.getAttribute('title') ||
                       el.innerText || '').trim().slice(0, 60);
        const r = el.getBoundingClientRect();
        const visible = r.width > 0 && r.height > 0;
        const children = [];
        for (const child of el.children) {
            const c = walk(child, depth + 1);
            if (c) children.push(c);
        }
        if (!visible && !children.length) return null;
        const node = {role, label};
        if (children.length) node.children = children;
        return node;
    }
    return walk(document.body, 0);
}
"""


async def _read_page_structure(page) -> str:
    """Return a compact hierarchical summary of the page's interactive structure."""
    try:
        tree = await page.evaluate(_PAGE_STRUCTURE_SCRIPT)
        return json.dumps(tree, indent=2)[:6000]
    except Exception as e:
        return f"Could not read page structure: {e}"


# ══════════════════════════════════════════════════════════════════════════════
# §7  DOM QUERY
# ══════════════════════════════════════════════════════════════════════════════

async def _dom_query(page, selector: str, query_type: str = "css") -> str:
    """
    Run a CSS selector, XPath, text, aria_label, or role query and return matches.
    """
    try:
        qt = query_type.lower().strip()
        if qt == "xpath":
            loc = page.locator(f"xpath={selector}")
        elif qt == "text":
            loc = page.get_by_text(selector, exact=False)
        elif qt == "aria_label":
            loc = page.get_by_label(selector, exact=False)
        elif qt == "role":
            loc = page.get_by_role(selector)
        else:
            loc = page.locator(selector)

        count = await loc.count()
        if count == 0:
            return f"No elements matched '{selector}' ({qt})"

        results = []
        for i in range(min(count, 20)):
            el = loc.nth(i)
            try:
                text  = (await el.inner_text(timeout=1_000)).strip()[:80]
                tag   = await el.evaluate("e => e.tagName.toLowerCase()")
                vis   = await el.is_visible()
                results.append(f"  [{i+1}] <{tag}> visible={vis} text='{text}'")
            except Exception:
                results.append(f"  [{i+1}] (error inspecting element)")
        return f"Found {count} element(s) for '{selector}' ({qt}):\n" + "\n".join(results)
    except Exception as e:
        return f"DOM query error: {e}"


# ══════════════════════════════════════════════════════════════════════════════
# §8  WAIT-FOR-ELEMENT
# ══════════════════════════════════════════════════════════════════════════════

async def _wait_for_element(
    page,
    description: str,
    timeout: float = 20.0,
    poll: float = 1.5,
) -> str:
    """Poll until `description` appears in the A11y tree, or timeout expires."""
    deadline = time.time() + timeout
    attempt  = 0
    while time.time() < deadline:
        attempt += 1
        found = await _a11y_find_clickable(page, description, scroll_budget=0)
        if not found:
            found = await _a11y_find_typeable(page, description, scroll_budget=0)
        if found:
            return f"'{description}' appeared after {attempt} poll(s) [{found['method']}]"
        remaining = deadline - time.time()
        await asyncio.sleep(min(poll, max(0, remaining)))
    return f"'{description}' did not appear within {timeout:.0f}s ({attempt} polls)"


# ══════════════════════════════════════════════════════════════════════════════
# §9  SMART FORM FILL
# ══════════════════════════════════════════════════════════════════════════════

async def _smart_form_fill(page, fields: dict, verify: bool = True) -> str:
    """
    Fill multiple form fields in one call with optional verification.
    fields: {field_description: value_string, ...}
    """
    results = []
    for field_desc, value in fields.items():
        if verify:
            r = await _edit_field_verified(page, field_desc, str(value))
        else:
            found = await _a11y_find_typeable(page, field_desc)
            if found:
                try:
                    await found["locator"].fill(str(value), timeout=8_000)
                    r = f"Filled '{field_desc}'"
                except Exception as e:
                    r = f"Error filling '{field_desc}': {e}"
            else:
                r = f"Could not find '{field_desc}'"
        results.append(r)
        await asyncio.sleep(0.2)
    return "Form fill results:\n" + "\n".join(results)


# ══════════════════════════════════════════════════════════════════════════════
# §10  MULTI-STEP EXECUTOR
# ══════════════════════════════════════════════════════════════════════════════

async def _multi_step(page, steps: list[dict]) -> str:
    """Execute a list of sub-action dicts in sequence, collecting results."""
    results = []
    for i, step in enumerate(steps):
        action = step.get("action", "").lower().strip()
        label  = f"Step {i+1}/{len(steps)} [{action}]"
        try:
            r = await _dispatch_async(page, step)
            results.append(f"{label}: {r}")
            print(f"[VWA][Multi] {label}: {r[:80]}")
        except Exception as e:
            results.append(f"{label}: ERROR: {e}")
            print(f"[VWA][Multi] {label}: ERROR: {e}")
        await asyncio.sleep(float(step.get("delay", 0.4)))
    return "\n".join(results)


# ══════════════════════════════════════════════════════════════════════════════
# §11  ASYNC DISPATCH
# ══════════════════════════════════════════════════════════════════════════════

async def _dispatch_async(page, params: dict) -> str:
    """Route a single action to the correct async handler."""
    action = params.get("action", "").lower().strip()
    desc   = params.get("description", params.get("selector", params.get("text", ""))).strip()
    text   = params.get("text", params.get("value", "")).strip()

    if action == "som_click":
        el = await _som_pick_element(page, desc)
        if el:
            # JS elementFromPoint click -- works for SVG/Canvas overlays
            await page.evaluate(
                "(args) => { const el = document.elementFromPoint(args.x, args.y);"
                " if (el) el.click(); }",
                {"x": el["x"], "y": el["y"]},
            )
            return f"SoM-clicked #{el.get('som_index')} '{el.get('label', desc)}'"
        return f"SoM could not find '{desc}'"

    elif action == "som_type":
        el = await _som_pick_element(page, desc)
        if el:
            await page.mouse.click(el["x"], el["y"])
            await asyncio.sleep(0.2)
            return await _edit_field_verified(page, desc, text)
        return f"SoM could not find input '{desc}'"

    elif action == "a11y_click":
        found = await _a11y_find_clickable(page, desc)
        if found:
            loc = found["locator"]
            await loc.scroll_into_view_if_needed(timeout=5_000)
            await loc.click(timeout=8_000)
            return f"A11y-clicked '{desc}' [{found['method']}]"
        return f"A11y could not find clickable '{desc}'"

    elif action == "a11y_type":
        found = await _a11y_find_typeable(page, desc)
        if found:
            loc = found["locator"]
            await loc.scroll_into_view_if_needed(timeout=5_000)
            await loc.fill(text, timeout=8_000)
            return f"A11y-typed into '{desc}' [{found['method']}]"
        return f"A11y could not find typeable '{desc}'"

    elif action == "scroll_to_element":
        return await _scroll_to_element_and_click(
            page, desc,
            click=bool(params.get("click", True)),
            max_scrolls=int(params.get("max_scrolls", 12)),
            scroll_step=int(params.get("scroll_step", 600)),
        )

    elif action == "wait_for_element":
        return await _wait_for_element(
            page, desc,
            timeout=float(params.get("timeout", 20)),
            poll=float(params.get("poll", 1.5)),
        )

    elif action == "edit_field_verified":
        return await _edit_field_verified(
            page, desc, text,
            max_retries=int(params.get("max_retries", 3)),
        )

    elif action == "read_page_structure":
        return await _read_page_structure(page)

    elif action == "dom_query":
        return await _dom_query(
            page, desc,
            query_type=params.get("query_type", "css"),
        )

    elif action == "smart_form_fill":
        fields = params.get("fields", {})
        return await _smart_form_fill(
            page, fields,
            verify=bool(params.get("verify", True)),
        )

    elif action == "multi_step":
        steps = params.get("steps", [])
        return await _multi_step(page, steps)

    else:
        return f"Unknown visual_web_agent action: '{action}'"


# ══════════════════════════════════════════════════════════════════════════════
# §12  PUBLIC ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def visual_web_agent(
    parameters:    dict = None,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    """
    Main entry point for JARVIS's action dispatcher.

    Bridges the synchronous JARVIS action dispatcher to the async Playwright
    page object held by the existing _BrowserSession / _SessionRegistry.

    Supported actions:
        som_click, som_type         — Set-of-Marks visual grounding
        a11y_click, a11y_type       — Accessibility Tree DOM actuation (fastest)
        scroll_to_element           — Scroll-and-seek with optional click
        wait_for_element            — Poll until element appears
        edit_field_verified         — Type with read-back verification + 4-strategy retry
        read_page_structure         — Full hierarchical A11y dump
        dom_query                   — CSS/XPath/text/role selector query
        smart_form_fill             — Multi-field fill with verification
        multi_step                  — Sequential sub-action executor
    """
    params = parameters or {}
    action = params.get("action", "").lower().strip()

    _log(player, f"visual_web_agent -> action='{action}'")

    # Acquire the active Playwright page via the existing session registry
    try:
        from actions.browser_control import _registry
        sess = _registry.get(params.get("browser") or None)
    except Exception as e:
        return f"Could not get browser session: {e}"

    async def _run():
        page = await sess._get_page()
        if page is None:
            return (
                "No active Playwright page -- browser may be in Native mode. "
                "Use browser_control action='go_to' first to open a Playwright session."
            )
        return await _dispatch_async(page, params)

    try:
        result = sess.run(_run(), timeout=120)
    except Exception as e:
        result = f"visual_web_agent error ({action}): {e}"

    _log(player, result[:160])
    return result


# ══════════════════════════════════════════════════════════════════════════════
# §13  TOOL REGISTRATION  (auto-discovered by core/action_loader.py)
# ══════════════════════════════════════════════════════════════════════════════

TOOL = {
    "name": "visual_web_agent",
    "description": (
        "Advanced visual browser interaction agent. "
        "Use this when you need to interact with a web page in the browser with "
        "high reliability — finding buttons, editing text fields, scrolling to elements, "
        "or filling forms — especially on complex sites like LinkedIn, Gmail, or SPAs "
        "where basic clicks may fail. "
        "Supports Set-of-Marks visual grounding (screenshot + numbered overlay), "
        "Accessibility Tree DOM actuation (fastest), scroll-and-seek loops, "
        "verified field editing (read-back + retry on mismatch), "
        "and multi-step sequential execution."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": (
                    "What to do. One of: "
                    "som_click — visually label all elements and click the matching one; "
                    "som_type — same but type text into the matched element; "
                    "a11y_click — find a button/link by ARIA role, label, or text and click it (fastest); "
                    "a11y_type — find an input field by label/placeholder and type text into it; "
                    "scroll_to_element — scroll until element is visible, then optionally click it; "
                    "wait_for_element — poll page until element appears (with timeout); "
                    "edit_field_verified — type into a field and verify the value was set, retry on mismatch; "
                    "read_page_structure — return the hierarchical A11y tree of the page (for planning); "
                    "dom_query — query elements by CSS/XPath/text/role selector; "
                    "smart_form_fill — fill multiple fields with verification in one call; "
                    "multi_step — run a list of sub-actions sequentially."
                ),
            },
            "description": {
                "type": "STRING",
                "description": (
                    "Natural-language description of the element to find or interact with. "
                    "Examples: 'Edit button next to Experience', 'About section pencil icon', "
                    "'Headline text box', 'Save button', 'First name field'. "
                    "Required for all actions except smart_form_fill and multi_step."
                ),
            },
            "text": {
                "type": "STRING",
                "description": (
                    "Text to type into the field (for som_type, a11y_type, edit_field_verified, som_type). "
                    "Leave empty for click-only actions."
                ),
            },
            "fields": {
                "type": "OBJECT",
                "description": (
                    "For smart_form_fill: a dict mapping field descriptions to values. "
                    "Example: {\"Headline\": \"AI Developer\", \"Summary\": \"Building things...\"}."
                ),
            },
            "steps": {
                "type": "ARRAY",
                "description": (
                    "For multi_step: a list of sub-action parameter dicts, each with the same "
                    "shape as the outer parameters (action, description, text, etc.). "
                    "Each step may also have a 'delay' key (seconds) to pause after it."
                ),
                "items": {"type": "OBJECT"},
            },
            "click": {
                "type": "BOOLEAN",
                "description": "For scroll_to_element: whether to click after scrolling to the element. Default true.",
            },
            "max_scrolls": {
                "type": "INTEGER",
                "description": "For scroll_to_element: maximum number of scroll steps. Default 12.",
            },
            "timeout": {
                "type": "NUMBER",
                "description": "For wait_for_element: maximum seconds to wait. Default 20.",
            },
            "query_type": {
                "type": "STRING",
                "description": (
                    "For dom_query: selector type — 'css' (default), 'xpath', 'text', 'aria_label', or 'role'."
                ),
            },
            "verify": {
                "type": "BOOLEAN",
                "description": "For smart_form_fill: whether to verify each field's value after typing. Default true.",
            },
            "max_retries": {
                "type": "INTEGER",
                "description": "For edit_field_verified: how many strategies to try before giving up. Default 3.",
            },
            "browser": {
                "type": "STRING",
                "description": "Browser to operate on. Default: active browser. Options: chrome, edge, firefox.",
            },
        },
        "required": ["action"],
    },
    "handler": visual_web_agent,
}

