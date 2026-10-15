"""
linkedin_agent.py — Dedicated LinkedIn Agent & Humanizer Plugin for JARVIS Mark LV.
==================================================================================

Integrates 11 LinkedIn agent capabilities into JARVIS:
- Writes posts using 21 proven hook formulas tailored to the user's voice
- Automatically strips invisible Unicode, typography tells, and AI slop
- Scores every draft on a 5-check local detection panel (Burstiness, Specificity, Slop, Fingerprint, Voice)
- Generates strategic comments for feed engagement (9 comment archetypes)
- Triages and drafts replies under your own posts
- Scores LinkedIn profiles against the 12-point rubric out of 100
- Plans weekly content calendars and target accounts to engage with
- Outlines slide-by-slide carousel documents and creates DM sequences
- Seamless clipboard integration: automatically copies drafts ready for posting
"""
from __future__ import annotations

import traceback
from typing import Optional
from pathlib import Path

try:
    import pyperclip
    _PYPERCLIP = True
except ImportError:
    _PYPERCLIP = False

from plugins.linkedin import engine


PLUGIN = {
    "name": "linkedin_agent",
    "description": (
        "Advanced LinkedIn growth agent for Networking, L1/L2/L3 System Administration, and HR recruitment connections. "
        "Use this tool whenever the user wants to: "
        "(1) analyze or audit their LinkedIn profile for L1/L2/L3 System Administrator & Network Engineer roles ('analyze my LinkedIn', 'audit my profile for HR'), "
        "(2) generate high-converting connection request notes (< 200 chars) for HRs and Technical Recruiters ('connect with HR', 'invite recruiter for SysAdmin role'), "
        "(3) find active recruiters and hiring managers in networking & infrastructure ('find HRs hiring Network Engineers', 'search recruiters'), "
        "(4) generate technical networking & sysadmin posts ('write a networking post', 'post about Active Directory', 'post about VLAN troubleshooting'), "
        "(5) draft general LinkedIn posts with hook formulas ('draft a LinkedIn post about X'), "
        "(6) humanize text or check for AI detection ('humanize this draft', 'strip AI tells'), "
        "(7) comment on posts, reply to comments, or build weekly content plans. "
        "Drafts are automatically humanized, scored, and copied to the clipboard for instant pasting."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "mode": {
                "type": "STRING",
                "enum": [
                    "connect",
                    "analyze_profile",
                    "hr_connect",
                    "search_recruiters",
                    "networking_post",
                    "post",
                    "humanize",
                    "detect",
                    "comment",
                    "reply",
                    "profile",
                    "plan",
                    "carousel",
                    "dm",
                    "voice",
                ],
                "description": (
                    "Operation mode: "
                    "'connect' (connect JARVIS to LinkedIn session, link profile URL & open browser), "
                    "'analyze_profile' (deep audit for L1/L2/L3 SysAdmin & Network Engineer keywords, ATS score, and rewrites), "
                    "'hr_connect' (generate < 200 character connection notes + follow-ups for HRs/Recruiters), "
                    "'search_recruiters' (get clickable search links and boolean queries for hiring managers & HRs), "
                    "'networking_post' (create authentic networking/sysadmin troubleshooting post), "
                    "'post' (write post from idea with hooks), "
                    "'humanize' (strip AI slop and invisible chars), "
                    "'detect' (score text against 5-check detection panel), "
                    "'comment' (write comment for another post), "
                    "'reply' (reply to incoming comment), "
                    "'plan' (generate weekly posting schedule), "
                    "'carousel' (slide-by-slide document outline), "
                    "'dm' (outreach sequence), "
                    "'voice' (view current voice profile)."
                ),
            },
            "topic_or_idea": {
                "type": "STRING",
                "description": "Topic, raw idea, draft text, profile data, or carousel theme.",
            },
            "name": {
                "type": "STRING",
                "description": "Recipient recruiter name, hiring manager name, or author name.",
            },
            "company": {
                "type": "STRING",
                "description": "Target company name for HR or recruiter outreach (e.g. 'Cisco', 'Wipro', 'TCS', 'Infosys').",
            },
            "role_target": {
                "type": "STRING",
                "description": "Target job role: e.g. 'L1 System Administrator', 'L2 System Administrator', 'L3 System Administrator', 'Network Engineer'.",
            },
            "post_content": {
                "type": "STRING",
                "description": "For 'comment' or 'reply' mode: the text of the post being discussed.",
            },
            "comment_text": {
                "type": "STRING",
                "description": "For 'reply' mode: the text of the incoming comment to respond to.",
            },
            "from_clipboard": {
                "type": "BOOLEAN",
                "description": "Set to true to use the current clipboard text as input.",
            },
            "copy_to_clipboard": {
                "type": "BOOLEAN",
                "description": "Whether to copy the finished draft/result to the clipboard (default True).",
            },
        },
        "required": ["mode"],
    },
}

PLUGIN_SETTINGS = {
    "namespace": "linkedin_agent",
    "title": "LinkedIn Agent & Humanizer",
    "fields": [
        {
            "key": "auto_copy",
            "label": "Auto-Copy to Clipboard",
            "type": "checkbox",
            "default": True,
            "help": "Automatically copy generated posts and comments to clipboard ready to paste into LinkedIn.",
        },
        {
            "key": "strict_humanizer",
            "label": "Strict Humanizer Pass",
            "type": "checkbox",
            "default": True,
            "help": "Enforce removal of all invisible Unicode, typographic tells, and stock AI slop.",
        },
        {
            "key": "voice_file",
            "label": "Voice Profile Location",
            "type": "text",
            "default": "config/linkedin_voice.md",
            "placeholder": "config/linkedin_voice.md",
            "help": "Markdown file specifying tone, audience, positions, and taboo words.",
        },
    ],
}


def _copy_clip(text: str) -> bool:
    if not _PYPERCLIP or not text:
        return False
    try:
        pyperclip.copy(text)
        return True
    except Exception:
        return False


def _paste_clip() -> str:
    if not _PYPERCLIP:
        return ""
    try:
        return pyperclip.paste() or ""
    except Exception:
        return ""


def run(parameters: dict, player=None, session_memory=None) -> str:
    mode = (parameters.get("mode") or "post").strip().lower()
    topic = parameters.get("topic_or_idea") or ""
    post_content = parameters.get("post_content") or ""
    comment_text = parameters.get("comment_text") or ""
    target_name = parameters.get("name") or ""
    target_company = parameters.get("company") or ""
    role_target = parameters.get("role_target") or "L1/L2/L3 System Administrator & Network Engineer"
    from_clip = parameters.get("from_clipboard", False)
    auto_copy = parameters.get("copy_to_clipboard", True)

    # Read from clipboard if requested or if topic is empty in text-processing modes
    if from_clip or (not topic and mode in ("humanize", "detect", "profile", "analyze_profile", "analyze") and not post_content):
        clip_val = _paste_clip().strip()
        if clip_val:
            if mode in ("comment", "reply") and not post_content:
                post_content = clip_val
            elif not topic:
                topic = clip_val

    def log(msg: str):
        if player:
            try:
                player.write_log(f"JARVIS: {msg}")
            except Exception:
                pass

    try:
        # ── 00. CONNECT TO LINKEDIN ──────────────────────────────────────────
        if mode in ("connect", "login", "link"):
            url_input = topic or target_name or ""
            log("Connecting JARVIS to LinkedIn session & browser...")
            res = engine.connect_account(url_input)
            target_url = res.get("url", "https://www.linkedin.com")
            log(f"LinkedIn session connected. Opened: {target_url}")
            return (
                f"Sir, I have connected your LinkedIn integration and opened {target_url} in your primary browser. "
                "Your session is verified and I am ready to handle your profile optimization, recruiter outreach, and network connections."
            )

        # ── 0A. NETWORKING & SYSADMIN PROFILE ANALYSIS ───────────────────────
        elif mode in ("analyze_profile", "analyze"):
            log("Auditing LinkedIn profile for L1/L2/L3 SysAdmin & Network Engineer roles...")
            res = engine.analyze_networking_profile(topic or post_content)
            analysis = res["analysis"]
            saved = res.get("saved_path", "")

            if auto_copy:
                _copy_clip(analysis)

            log(f"Profile analysis complete. Saved to: {saved}. Copied to clipboard.")
            return (
                "Sir, I have analyzed your LinkedIn profile for L1, L2, L3 System Administrator and Network Engineer roles. "
                "I identified critical keyword gaps and generated an optimized headline, high-impact about section, and quantified "
                "experience bullets. The complete report is on your clipboard ready to paste into LinkedIn."
            )

        # ── 0B. HR & RECRUITER CONNECTION OUTREACH ───────────────────────────
        elif mode in ("hr_connect", "hr_outreach"):
            log(f"Generating HR connection notes for {target_name or 'Recruiter'} ({target_company or 'Tech'})...")
            res = engine.generate_hr_outreach(recruiter_name=target_name, company=target_company, role_target=role_target)
            outreach = res["outreach"]

            if auto_copy:
                _copy_clip(outreach)

            log("HR connection notes generated (strictly < 200 chars). Ready on clipboard.")
            return (
                f"Sir, I have crafted 3 high-converting connection request notes strictly under 200 characters for LinkedIn's "
                f"free invite limit, plus two follow-up messages for {target_name or 'the recruiter'}. They are on your clipboard."
            )

        # ── 0C. SEARCH RECRUITERS & HIRING MANAGERS ──────────────────────────
        elif mode in ("search_recruiters", "search_hr"):
            log("Generating LinkedIn recruiter search hub and direct boolean URLs...")
            res = engine.get_recruiter_search_hub()
            hub = res["hub"]

            if auto_copy:
                _copy_clip(hub)

            log("Recruiter search hub copied to clipboard.")
            return (
                "Sir, I have generated curated boolean search queries and one-click LinkedIn search links to connect with HRs, "
                "Technical Recruiters, and Hiring Managers looking for Network Engineers and SysAdmins. The hub is on your clipboard."
            )

        # ── 0D. TECHNICAL NETWORKING POST ────────────────────────────────────
        elif mode == "networking_post":
            log(f"Drafting technical networking post on: '{topic or 'Network Troubleshooting'}'...")
            res = engine.generate_networking_post(topic)
            post = res["post"]
            score = res["score"]
            verdict = res["verdict"]

            if auto_copy:
                _copy_clip(post)

            log(f"Networking post ready. Score: {score}/100 ({verdict}). Copied to clipboard.")
            return (
                f"Sir, I have crafted an authentic technical networking post showcasing your hands-on troubleshooting. "
                f"It scored {score} out of 100 on the detection panel and is ready in your clipboard."
            )

        # ── 1. POST MODE ─────────────────────────────────────────────────────
        elif mode == "post":
            if not topic:
                return "Sir, please provide the topic or idea for the LinkedIn post."

            log(f"Drafting LinkedIn post on: '{topic[:40]}...' with humanizer pass...")
            res = engine.create_post(topic)
            post = res["post"]
            score = res["score"]
            verdict = res["verdict"]
            saved = res["saved_path"]

            copied = False
            if auto_copy:
                copied = _copy_clip(post)

            log(f"LinkedIn post ready. Score: {score}/100 ({verdict}). Saved: {saved}")
            clip_note = " It is copied to your clipboard ready to paste." if copied else ""
            return (
                f"Sir, I have crafted your LinkedIn post using the hook formulas and voice profile. "
                f"The draft achieved a human score of {score} with a {verdict} rating.{clip_note}"
            )

        # ── 2. HUMANIZE / DETECT MODE ────────────────────────────────────────
        elif mode in ("humanize", "detect"):
            target_text = topic or post_content
            if not target_text:
                return "Sir, please provide the text to humanize or copy it to your clipboard first."

            log("Running 5-check detection panel and humanizer...")
            res = engine.humanize_only(target_text)
            clean = res["cleaned"]
            score = res["score"]
            verdict = res["verdict"]
            stripped = res["artifacts_stripped"]
            flagged = res["structures_flagged"]

            copied = False
            if auto_copy and mode == "humanize":
                copied = _copy_clip(clean)

            log(f"Humanizer complete. Stripped: {stripped} artefacts. Score: {score} ({verdict}).")
            clip_note = " The cleaned version is in your clipboard." if copied else ""
            return (
                f"Sir, analysis complete. Stripped {stripped} machine artefacts with {flagged} structural flags. "
                f"The text scored {score} out of 100, receiving a {verdict} status.{clip_note}"
            )

        # ── 3. COMMENT MODE ──────────────────────────────────────────────────
        elif mode == "comment":
            target_post = post_content or topic
            if not target_post:
                return "Sir, please paste or specify the LinkedIn post you would like to comment on."

            log("Generating strategic comment options...")
            res = engine.create_comment(target_post, author_info=target_name)
            comments = res["comments"]
            score = res["score"]
            verdict = res["verdict"]

            if auto_copy:
                _copy_clip(comments)

            log(f"Comments crafted. Score: {score} ({verdict}). Ready in clipboard.")
            return (
                f"Sir, I have prepared two strategic comment options based on the post. "
                f"Both are humanized and placed on your clipboard for your review."
            )

        # ── 4. REPLY MODE ────────────────────────────────────────────────────
        elif mode == "reply":
            target_comment = comment_text or topic
            if not target_comment:
                return "Sir, please provide the comment you received so I can craft the response."

            log(f"Crafting reply to comment from {target_name or 'connection'}...")
            res = engine.create_reply(post_content, target_comment, commenter_name=target_name)
            reply = res["reply"]
            score = res["score"]

            if auto_copy:
                _copy_clip(reply)

            log(f"Reply ready. Human Score: {score}. Copied to clipboard.")
            return f"Sir, I have drafted the reply in your voice. It is ready on your clipboard."

        # ── 5. PROFILE AUDIT MODE ────────────────────────────────────────────
        elif mode == "profile":
            profile_data = topic or post_content
            if not profile_data:
                return "Sir, please paste your profile headline, about section, or experience bullets for review."

            log("Auditing profile against 12-point rubric...")
            res = engine.audit_profile(profile_data)
            audit = res["audit"]

            if auto_copy:
                _copy_clip(audit)

            log("Profile audit complete. Copied recommendations to clipboard.")
            return "Sir, your profile audit is complete. I have scored it against the rubric and copied prioritized headline and about section rewrites to your clipboard."

        # ── 6. PLAN MODE ─────────────────────────────────────────────────────
        elif mode == "plan":
            log("Generating weekly LinkedIn content schedule...")
            res = engine.create_plan(topic)
            plan = res["plan"]
            saved = res.get("saved_path", "")

            if auto_copy:
                _copy_clip(plan)

            log(f"Weekly plan generated and saved to {saved}.")
            return f"Sir, your 7-day content schedule and target engagement accounts are prepared and saved to your LinkedIn plan file."

        # ── 7. CAROUSEL MODE ─────────────────────────────────────────────────
        elif mode == "carousel":
            if not topic:
                return "Sir, what topic should the carousel cover?"

            log(f"Generating carousel outline for: {topic}...")
            res = engine.create_carousel(topic)
            carousel = res["carousel"]

            if auto_copy:
                _copy_clip(carousel)

            log("Carousel document outline copied to clipboard.")
            return f"Sir, the slide-by-slide copy for your carousel document post is ready on your clipboard."

        # ── 8. DM OUTREACH MODE ──────────────────────────────────────────────
        elif mode == "dm":
            if not target_name and not topic:
                return "Sir, please provide the name or context for the LinkedIn message."

            log(f"Generating outreach sequence for {target_name}...")
            res = engine.create_dm(target_name or "Connection", topic)
            dm_seq = res["dm"]

            if auto_copy:
                _copy_clip(dm_seq)

            log("DM outreach sequence copied to clipboard.")
            return f"Sir, the under-200-character invite note and follow-up sequence are prepared on your clipboard."

        # ── 9. VOICE PROFILE MODE ────────────────────────────────────────────
        elif mode == "voice":
            profile = engine.get_voice_profile()
            if auto_copy:
                _copy_clip(profile)
            return "Sir, your configured LinkedIn voice and tone profile is active and loaded."

        else:
            return f"Sir, unknown LinkedIn operation '{mode}'."

    except Exception as exc:
        traceback.print_exc()
        return f"Sir, the LinkedIn agent encountered an issue: {exc}"
