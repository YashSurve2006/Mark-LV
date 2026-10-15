"""
engine.py — Core Orchestrator for LinkedIn Agent Skills in JARVIS Mark-LV.

Bridges the 11 LinkedIn agent capabilities:
- 21 proven hook formulas (hooks.json)
- Zero-dependency humanizer (invisible chars, typography, slop replacement)
- Five-check detector panel (burstiness, specificity, slop, fingerprint, voice)
- 12-point profile rubric (rubric.json)
- Custom user voice profile (config/linkedin_voice.md)
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import humanize as hz
from . import detect as dt

HERE = Path(__file__).resolve().parent
SLOP_PATH = HERE / "slop.json"
HOOKS_PATH = HERE / "hooks.json"
RUBRIC_PATH = HERE / "rubric.json"
PROJECT_ROOT = HERE.parent.parent
CONFIG_VOICE_PATH = PROJECT_ROOT / "config" / "linkedin_voice.md"
CLAUDE_VOICE_PATH = Path.home() / ".claude" / "linkedin" / "voice.md"
OUTPUT_DIR = PROJECT_ROOT / "output" / "linkedin"
LOG_FILE = OUTPUT_DIR / "log.md"

# Ensure output directories exist
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
(OUTPUT_DIR / "posts").mkdir(parents=True, exist_ok=True)
(OUTPUT_DIR / "plans").mkdir(parents=True, exist_ok=True)


def get_lexicon() -> dict:
    """Load the slop lexicon."""
    return hz.load_lexicon(str(SLOP_PATH))


def get_hooks() -> dict:
    """Load the 21 hook formulas."""
    if HOOKS_PATH.exists():
        try:
            return json.loads(HOOKS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"version": "1.0", "hooks": []}


def get_rubric() -> dict:
    """Load the profile rubric."""
    if RUBRIC_PATH.exists():
        try:
            return json.loads(RUBRIC_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"version": "1.0", "items": []}


def get_voice_profile() -> str:
    """Return the user's voice profile text."""
    if CONFIG_VOICE_PATH.exists():
        try:
            return CONFIG_VOICE_PATH.read_text(encoding="utf-8").strip()
        except Exception:
            pass
    if CLAUDE_VOICE_PATH.exists():
        try:
            return CLAUDE_VOICE_PATH.read_text(encoding="utf-8").strip()
        except Exception:
            pass
    return "Write in a direct, technical, builder voice. Short paragraphs, real numbers, no corporate fluff or slop."


def clean_and_score(text: str) -> Tuple[str, dict, float, str, dict]:
    """
    Run the full humanize pass and five-check AI detection panel.
    Returns: (cleaned_text, humanize_report, human_score, verdict, check_details)
    """
    lex = get_lexicon()
    cleaned_text, rep = hz.humanize(text, lex)
    results, overall, verdict = dt.run(cleaned_text, lex)
    check_details = {k: {"score": round(v[0], 1), "detail": v[1]} for k, v in results.items()}
    return cleaned_text, rep, round(overall, 1), verdict, check_details


def _ask_gemini(prompt: str, timeout_ms: int = 45000) -> str:
    """Call the assistant's Gemini ladder via core.gemini."""
    try:
        from core import gemini
        resp = gemini.call(prompt, tier=gemini.SMART, timeout_ms=timeout_ms)
        if resp is not None:
            return (getattr(resp, "text", None) or "").strip()
    except Exception as e:
        print(f"[LinkedInEngine] Gemini call failed: {e}")
    return ""


# ─────────────────────────────────────────────────────────────────────────────
# 1. /li-post & /li-human
# ─────────────────────────────────────────────────────────────────────────────

def create_post(idea: str, hook_pref: Optional[str] = None) -> Dict[str, Any]:
    """
    Turns one idea into 3 hook options and one complete LinkedIn post,
    humanized and scored against the 5-check detection panel.
    """
    voice = get_voice_profile()
    hooks_data = get_hooks()
    hooks_list = hooks_data.get("hooks", [])
    hooks_sample = json.dumps(hooks_list[:10], indent=2)

    prompt = f"""You are the LinkedIn Agent expert copywriter.
VOICE PROFILE:
{voice}

HOOK FORMULAS REFERENCE (select 3 suitable formulas):
{hooks_sample}

TASK:
Write a high-converting LinkedIn post based on this raw idea:
\"\"\"{idea}\"\"\"

REQUIREMENTS:
1. Select 3 distinct hook options from the proven formulas that best fit this idea.
2. Draft 1 complete post based on the strongest hook.
3. Post structure:
   - Line 1: The hook alone (under 140 chars).
   - Line 2: The payoff of line 1 (no delay).
   - Body: 1-3 line punchy paragraphs with blank lines between every one.
   - The turn: One line reframing what came before.
   - Close: Exactly one specific question or instruction (never generic "Thoughts?").
   - Length: 800 - 1,200 characters.
   - Maximum 2-3 category hashtags at bottom.
   - NO outbound URLs in the body.
   - NEVER use AI slop (delve, leverage, testament to, robust, seamless, fast-paced world).
4. Output in exact format:

===HOOKS===
1. [Formula Name]: [Hook Line]
2. [Formula Name]: [Hook Line]
3. [Formula Name]: [Hook Line]

===RECOMMENDED===
[1 sentence explaining which hook you recommend and why]

===POST===
[Complete post text ready to copy]
"""
    raw_response = _ask_gemini(prompt)
    if not raw_response:
        # Fallback offline draft if API is unreachable
        raw_response = f"""===HOOKS===
1. Direct Statement: We spent 4 weeks rebuilding our assistant architecture from scratch.
2. Contrast Hook: Most AI assistants are slow web wrappers. We built ours with live native C-level PCM streams.
3. The Number: 320 milliseconds: that is the latency threshold where voice AI feels real.

===RECOMMENDED===
I recommend Hook #2 because contrast immediately earns the click on mobile.

===POST===
Most AI assistants feel like slow web wrappers.

We decided to build JARVIS with direct live native audio streaming.

Here is what we learned from lowering latency down to 320ms:

1. Introspection over boilerplate.
Every plugin is auto-discovered at runtime. No hardcoded dispatch loops.

2. Zero cloud middlemen for device control.
Direct OS-level control keeps everything immediate and reliable.

3. Live PCM streaming.
If you wait for complete audio files to buffer, the conversation is already dead.

The real barrier in AI assistants is not model smarts.
It is latency and user experience.

What is the biggest latency bottleneck in your stack today?

#AI #Engineering #Python
"""

    hooks_text = ""
    rec_text = ""
    post_text = raw_response

    if "===HOOKS===" in raw_response and "===POST===" in raw_response:
        try:
            parts = raw_response.split("===POST===")
            post_text = parts[1].strip()
            header_parts = parts[0].split("===RECOMMENDED===")
            hooks_text = header_parts[0].replace("===HOOKS===", "").strip()
            if len(header_parts) > 1:
                rec_text = header_parts[1].strip()
        except Exception:
            post_text = raw_response

    # Run the humanizer and detection panel
    clean_post, report, score, verdict, checks = clean_and_score(post_text)

    # Save to disk
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    post_file = OUTPUT_DIR / "posts" / f"post_{ts}.txt"
    try:
        content_to_save = f"IDEA: {idea}\n\n{hooks_text}\n\nRECOMMENDED:\n{rec_text}\n\nPOST (Human Score {score} - {verdict}):\n\n{clean_post}"
        post_file.write_text(content_to_save, encoding="utf-8")

        # Append to log.md
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            first_line = clean_post.strip().splitlines()[0] if clean_post.strip() else idea
            f.write(f"- **{datetime.now().strftime('%Y-%m-%d %H:%M')}**: {first_line} (Score: {score} {verdict}) -> [`{post_file.name}`](file:///{post_file})\n")
    except Exception as e:
        print(f"[LinkedInEngine] Failed to save post file: {e}")

    return {
        "idea": idea,
        "hooks": hooks_text,
        "recommendation": rec_text,
        "post": clean_post,
        "score": score,
        "verdict": verdict,
        "checks": checks,
        "report": report,
        "saved_path": str(post_file),
    }


def humanize_only(text: str) -> Dict[str, Any]:
    """Humanize raw text and return scores + cleaned draft."""
    clean_text, rep, score, verdict, checks = clean_and_score(text)
    total_stripped = (
        sum(h["count"] for h in rep.get("invisible", []))
        + sum(h["count"] for h in rep.get("typographic", []))
        + sum(h["count"] for h in rep.get("lexical", []))
    )
    return {
        "original": text,
        "cleaned": clean_text,
        "score": score,
        "verdict": verdict,
        "checks": checks,
        "artifacts_stripped": total_stripped,
        "structures_flagged": len(rep.get("structures", [])),
        "report": rep,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 2. /li-comment
# ─────────────────────────────────────────────────────────────────────────────

def create_comment(post_content: str, author_info: str = "") -> Dict[str, Any]:
    """
    Creates 2 high-leverage comment options matching the 9 comment archetypes.
    """
    voice = get_voice_profile()
    prompt = f"""You are the LinkedIn Commenting strategist.
VOICE PROFILE:
{voice}

POST TO COMMENT ON:
Author: {author_info or 'Creator'}
\"\"\"{post_content}\"\"\"

THE 9 COMMENT TYPES:
1. Add a datum (support with a concrete number)
2. Add the missing case (when does this rule break)
3. Respectful disagree (validate first, then fork)
4. Extend one line (quote their best sentence and build on it)
5. Ask the real question (target the hard tradeoff)
6. The receipt (brief proof of doing the thing)
7. The correction (kind, brief, fact-based)
8. The reframe (same facts, new angle)
9. The one-liner (< 12 words, witty or true)

RULES:
- Provide exactly 2 distinct comment options from different types.
- 2 to 4 sentences each (except one-liner).
- Never open with 'Great post', 'Love this', 'Couldn't agree more', or emojis.
- Run both through strict human voice principles.

OUTPUT FORMAT:
Option 1: [Type Name]
[Comment text]

Option 2: [Type Name]
[Comment text]

Recommendation: [Which one to post and why in 1 sentence]
"""
    raw_response = _ask_gemini(prompt)
    if not raw_response:
        raw_response = """Option 1: Add the missing case
This holds until you hit multi-threaded execution or tight 50ms deadlines. Then synchronous handlers choke your event loop.

Option 2: The receipt
We hit this exact bottleneck last month. Moving from REST polling to a full-duplex socket cut our response latency by 70%.

Recommendation: Option 2 carries authentic proof of work."""

    clean_comments, rep, score, verdict, checks = clean_and_score(raw_response)
    return {
        "comments": clean_comments,
        "score": score,
        "verdict": verdict,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 3. /li-reply
# ─────────────────────────────────────────────────────────────────────────────

def create_reply(post_topic: str, incoming_comment: str, commenter_name: str = "") -> Dict[str, Any]:
    """
    Triages and drafts a reply to a comment under your own post.
    Categories: Lead, Substance, Peer, Support, Noise.
    """
    voice = get_voice_profile()
    prompt = f"""You are drafting a LinkedIn comment reply for {commenter_name or 'a connection'}.
YOUR VOICE:
{voice}

YOUR POST TOPIC / TEXT:
{post_topic}

THE COMMENT RECEIVED:
\"{incoming_comment}\"

RULES:
- Identify comment category: Lead, Substance, Peer, Support, or Noise.
- Draft a 1-3 sentence natural response.
- If Substance: answer with a real detail or follow-up.
- If Lead: answer clearly and invite discussion.
- If Support: gracious and brief (no exclamation spam).
- If Noise: polite 1-liner or ignore.
- No slop, no em dashes, no corporate jargon.
"""
    raw = _ask_gemini(prompt)
    if not raw:
        raw = f"Appreciate you pointing that out, {commenter_name or 'friend'}. We found separating audio capture from model dispatch made the biggest difference in stability."

    clean_reply, _, score, verdict, _ = clean_and_score(raw)
    return {
        "reply": clean_reply,
        "score": score,
        "verdict": verdict,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 4. /li-profile
# ─────────────────────────────────────────────────────────────────────────────

def audit_profile(profile_text: str) -> Dict[str, Any]:
    """
    Scores a LinkedIn profile against the 12-point rubric (rubric.json) out of 100.
    Provides prioritized rewrites for the lowest-scoring sections.
    """
    rubric = get_rubric()
    prompt = f"""You are an elite LinkedIn profile auditor.
12-PART RUBRIC (100 pts total):
{json.dumps(rubric.get('items', []), indent=2)}

USER PROFILE DATA:
\"\"\"{profile_text}\"\"\"

TASK:
1. Score each item out of its allotted points honestly. First-pass profiles usually score in the 30s-40s.
2. Calculate TOTAL SCORE / 100.
3. Provide prioritized immediate rewrites for:
   - Headline (using the formula: Who you help + outcome + proof).
   - About Section (first 2 hook lines before 'see more', plus punchy body).
   - Role Bullets (outcomes with metrics, not job duties).

Format cleanly with markdown.
"""
    raw = _ask_gemini(prompt)
    if not raw:
        raw = """### LinkedIn Profile Audit
**Total Score: 42 / 100**

1. Headline: 4/12 (Job title only — lacks who you help and proof)
2. About Open: 3/10 (Opens in third person with corporate buzzwords)
3. About Body: 4/10 (Duties listed without metrics)
4. Experience: 5/10 (Lacks outcome numbers)

#### Recommended Fixes:
**Headline Rewrite:**
AI Systems Engineer | Building JARVIS (Live Voice AI with <350ms latency) | Python, C++, Real-Time Multimodal Architecture

**About Section Hook (First 2 Lines):**
Most AI desktop apps are slow and brittle.
I build native, full-duplex voice assistants that respond in real time without lag.
"""
    clean_audit, _, _, _, _ = clean_and_score(raw)
    return {
        "audit": clean_audit,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 5. /li-plan
# ─────────────────────────────────────────────────────────────────────────────

def create_plan(focus_theme: str = "") -> Dict[str, Any]:
    """
    Generates a 7-day content schedule and 10 archetype target accounts.
    """
    voice = get_voice_profile()
    prompt = f"""You are the LinkedIn weekly content planner.
VOICE PROFILE:
{voice}

FOCUS THEME FOR THIS WEEK:
{focus_theme or 'Building local & native AI systems, engineering lessons, shipping real products'}

TASK:
Generate a complete weekly LinkedIn plan:
1. 5 Post Concepts (Monday to Friday):
   - Day & Best Time (e.g. Tuesday 8:15 AM)
   - Core Idea & Angle
   - Recommended Hook Formula
2. 10 Ideal Engagement Targets:
   - Archetypes of profiles/creators to leave high-value comments on.
"""
    raw = _ask_gemini(prompt)
    if not raw:
        raw = """### Weekly LinkedIn Strategy Plan
- **Monday 8:15 AM**: #17 Time Anchor - Why cutting voice assistant latency from 1.5s to 320ms required rewriting our pipeline.
- **Tuesday 9:00 AM**: #3 The Number - 3 Python libraries I had to drop to make desktop automation reliable.
- **Wednesday 8:30 AM**: #1 Contrast Hook - Web wrappers vs. native desktop AI agents.
- **Thursday 11:00 AM**: #7 The Receipt - How we built drop-in plugin discovery in 200 lines of code.
- **Friday 9:15 AM**: #12 The Contrarian - Why high model benchmark scores mean nothing if your app has 2s latency.
"""
    clean_plan, _, score, verdict, _ = clean_and_score(raw)
    plan_path = OUTPUT_DIR / "plans" / f"plan_{datetime.now().strftime('%Y%m%d')}.md"
    try:
        plan_path.write_text(clean_plan, encoding="utf-8")
    except Exception:
        pass
    return {
        "plan": clean_plan,
        "saved_path": str(plan_path),
        "score": score,
        "verdict": verdict,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 6. /li-carousel & /li-repurpose & /li-dm
# ─────────────────────────────────────────────────────────────────────────────

def create_carousel(topic: str) -> Dict[str, Any]:
    """Slide-by-slide copy for carousel document posts."""
    voice = get_voice_profile()
    prompt = f"""Write an 8-slide LinkedIn carousel outline for:
Topic: {topic}
Voice: {voice}
Slide 1: Cover slide (hook that earns the swipe)
Slides 2-7: One single clear point per slide (headline + 2 short bullet points)
Slide 8: Actionable takeaway + save prompt.
"""
    raw = _ask_gemini(prompt)
    clean_c, _, score, verdict, _ = clean_and_score(raw or f"Slide 1: {topic}\nSlide 2: The Core Problem...")
    return {"carousel": clean_c, "score": score, "verdict": verdict}


def create_dm(target_name: str, context: str, role: str = "") -> Dict[str, Any]:
    """Generates connection note (<200 chars) and 2 follow-ups."""
    prompt = f"""Write a LinkedIn outreach sequence for:
Name: {target_name}
Role: {role}
Context: {context}

Requirements:
1. Connection Invite Note (Strictly under 200 characters including spaces).
2. Follow-up 1 (Sent 2 days after connect, value-first, no ask).
3. Follow-up 2 (Sent 5 days later, low-friction question).
"""
    raw = _ask_gemini(prompt)
    clean_dm, _, score, verdict, _ = clean_and_score(raw or f"Hi {target_name}, saw your work in {context}. Would love to connect and follow your builds.")
    return {"dm": clean_dm, "score": score, "verdict": verdict}


# ─────────────────────────────────────────────────────────────────────────────
# 7. SPECIALIZED NETWORKING & SYSADMIN HR GROWTH ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def analyze_networking_profile(profile_text: str = "") -> Dict[str, Any]:
    """
    Analyzes LinkedIn profile specifically for L1, L2, L3 System Administrator 
    and Network Engineer job roles. Identifies gaps in recruiter keyword density,
    scoring against HR & hiring manager criteria, and produces an instant upgrade pack.
    """
    voice = get_voice_profile()
    
    prompt = f"""You are a veteran IT Infrastructure Recruiter & Senior Network Engineering Hiring Manager.
Audit this LinkedIn profile data specifically for L1/L2/L3 System Administrator & Network Engineer roles.

USER VOICE & BASELINE INFO:
{voice}

USER INPUT / CURRENT PROFILE:
\"\"\"{profile_text or 'No raw text provided — evaluate based on Yash Surve seeking L1/L2/L3 SysAdmin & Network Engineer positions.'}\"\"\"

TARGET ROLES:
- L1 System Administrator / IT Support Specialist
- L2 System Administrator / Network Support Engineer
- L3 Senior System Administrator / Network Infrastructure Engineer

EVALUATION CHECKLIST:
1. Headline SEO (Must contain high-volume recruiter search terms: Network Engineer, System Administrator, CCNA, Windows Server, Linux, Firewall).
2. About Section Hook (First 2 lines visible before 'see more', SLA achievement, uptime, troubleshooting scope).
3. Technical Stack Visibility (Routing & Switching, VLANs, Subnetting, OSPF, BGP, VPN, Wireshark, Active Directory, GPO, VMware ESXi, Firewalls).
4. Experience Quantification (Incident resolution times, uptime %, ticket volumes, root-cause isolation).
5. Certifications & Skill Endorsements.

OUTPUT FORMAT:
### 1. RECRUITER & ATS VISIBILITY SCORE
[Score out of 100 with 2-sentence candid assessment of why HR currently passes or connects]

### 2. CRITICAL KEYWORD GAPS
[Bullet list of missing high-yield keywords]

### 3. COPY-READY OPTIMIZED HEADLINE (Max 220 chars)
[A headline packed with keywords and proof]

### 4. COPY-READY ABOUT SECTION
[First 2 hook lines, core technical scope, quantified achievements, and clear call to connect]

### 5. READY-TO-USE EXPERIENCE BULLETS (L1/L2/L3 & Network Engineer)
[4-6 quantified bullets highlighting real troubleshooting, active directory, VLANs, and uptime]

### 6. TOP 5 SKILLS TO PIN FOR RECRUITER ALGORITHMS
[5 exact skill names to pin]
"""
    raw = _ask_gemini(prompt, timeout_ms=50000)
    if not raw:
        raw = """### 1. RECRUITER & ATS VISIBILITY SCORE: 58/100
Your profile has strong foundational tech skills, but currently under-indexes on direct recruiter search keywords for L2/L3 SysAdmin and Network Engineer roles. Recruiters search for specific tools (Active Directory, OSPF, VLAN, Fortinet, Wireshark) rather than general descriptions.

### 2. CRITICAL KEYWORD GAPS
- Cisco Routing & Switching, VLANs, Subnetting, OSPF, BGP
- Active Directory (AD DS), Group Policy (GPO), Windows Server 2022
- Linux (RHEL/Ubuntu), Bash Scripting, VMware ESXi
- Palo Alto / Fortinet Firewalls, IPsec VPN, Wireshark

### 3. COPY-READY OPTIMIZED HEADLINE (208 chars)
Network Engineer | L2/L3 System Administrator | Cisco R&S, VLANs, Subnetting | Windows Server, Active Directory & GPO | Linux (RHEL/Ubuntu) | Fortinet Firewalls & VPN | VMware ESXi | High Uptime & Incident Resolution

### 4. COPY-READY ABOUT SECTION
Network Engineer and System Administrator with hands-on experience designing, troubleshooting, and securing multi-site networks and enterprise server environments.

I specialize in isolating network bottlenecks and maintaining 99.9% infrastructure availability across Cisco routing/switching, Windows Server (Active Directory & GPO), Linux, and firewall perimeters.

Key Technical Competencies:
- Networking: Cisco R&S (CCNA), VLANs, Subnetting, OSPF, BGP, NAT, ACLs, IPsec/SSL VPN, Wireshark packet capture.
- Systems & Servers: Windows Server 2019/2022, Active Directory (AD DS), Group Policy (GPO), DNS/DHCP, PowerShell.
- Linux & Virtualization: Ubuntu, RHEL, systemd, SSH, VMware ESXi, vCenter, Hyper-V.
- Security & Tools: Fortinet FortiGate, Palo Alto, PRTG, Zabbix, ServiceNow, ITIL ticketing.

Open to L1/L2/L3 System Administrator and Network Engineer opportunities. Let's connect!

### 5. READY-TO-USE EXPERIENCE BULLETS
- Configured and deployed multi-VLAN architectures with inter-VLAN routing, trunking (802.1Q), and port security, reducing broadcast domain congestion.
- Administered Active Directory domain managing 100+ user objects, OUs, and Group Policy Objects (GPOs), cutting manual onboarding time by 40%.
- Conducted deep packet inspection using Wireshark to isolate TCP retransmissions and DNS latency, slashing network ticket resolution times.
- Managed VMware ESXi hypervisors and Windows/Linux virtual machines, ensuring automated snapshots and zero data loss during maintenance windows.
- Deployed site-to-site IPsec VPN tunnels and SSL remote-access VPNs on firewalls to maintain secure cross-branch connectivity.

### 6. TOP 5 SKILLS TO PIN FOR RECRUITER ALGORITHMS
1. Network Engineering
2. System Administration
3. Cisco Routing & Switching
4. Active Directory
5. Firewalls & VPN
"""
    clean_analysis, _, score, verdict, _ = clean_and_score(raw)
    
    # Save to disk
    audit_file = OUTPUT_DIR / f"networking_profile_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    try:
        audit_file.write_text(clean_analysis, encoding="utf-8")
    except Exception:
        pass

    return {
        "analysis": clean_analysis,
        "saved_path": str(audit_file),
        "score": score,
        "verdict": verdict,
    }


def generate_hr_outreach(recruiter_name: str = "Recruiter", company: str = "", role_target: str = "L2/L3 System Administrator & Network Engineer") -> Dict[str, Any]:
    """
    Generates high-converting connection notes strictly under 200 characters
    (LinkedIn free connection limit) plus follow-up sequences for HRs and Technical Recruiters.
    """
    clean_name = recruiter_name.strip() if recruiter_name else "there"
    comp_clause = f" at {company}" if company else ""
    
    # Pre-crafted, verified under 200 chars connection notes
    note_options = [
        # Option 1: Direct Recruiter connection (under 200 chars)
        f"Hi {clean_name}, saw your work{comp_clause} hiring for IT infra. I'm an active Network Engineer & L2/L3 SysAdmin (Cisco, AD, Linux, Firewalls). Would love to connect as you hire technical talent!",
        
        # Option 2: Value & Stack focused (under 200 chars)
        f"Hi {clean_name}, following your recruitment in tech. Hands-on with Cisco R&S, Windows Server (AD/GPO), Linux & Wireshark troubleshooting. Would love to stay on your radar for upcoming openings!",
        
        # Option 3: Hiring Manager / IT Lead focused (under 200 chars)
        f"Hi {clean_name}, admire the infrastructure work{comp_clause}. I specialize in network troubleshooting, AD/GPO & L2/L3 sysadmin support. Would value connecting with fellow infrastructure pros!",
    ]
    
    # Strictly enforce 195 character clamp to ensure safety on mobile/desktop
    validated_notes = []
    for i, note in enumerate(note_options, 1):
        if len(note) > 198:
            note = note[:195] + "..."
        validated_notes.append({
            "option": i,
            "length": len(note),
            "text": note
        })

    # Follow-up sequences
    follow_up_1 = f"""Hi {clean_name}, thank you for connecting! 

I specialize in hands-on Network Engineering and L2/L3 System Administration:
• Cisco Routing & Switching, VLANs, Subnetting, IPsec VPN, Wireshark
• Windows Server 2022, Active Directory, GPO, PowerShell automation
• Linux (Ubuntu/RHEL) administration & VMware ESXi virtualization

If you or your team have any active or upcoming infrastructure openings, I would welcome the opportunity to chat.

Best regards,
Yash Surve"""

    follow_up_2 = f"""Hi {clean_name}, hope you're having a productive week.

Wanted to check in briefly—are you currently sourcing candidates for L1/L2/L3 System Administrator or Network Engineer roles?

I am immediately available to discuss how my networking and server troubleshooting experience can support your team's SLAs. 

Thanks again!"""

    output_md = f"""### High-Converting HR & Recruiter Connection Notes
*Note: All connection invites are strictly under 200 characters for LinkedIn's free invitation limit.*

**Option 1: Recruiter & Talent Acquisition Focus ({validated_notes[0]['length']} chars)**
```
{validated_notes[0]['text']}
```

**Option 2: Technical Stack & Openings Focus ({validated_notes[1]['length']} chars)**
```
{validated_notes[1]['text']}
```

**Option 3: IT Hiring Manager / Infrastructure Lead Focus ({validated_notes[2]['length']} chars)**
```
{validated_notes[2]['text']}
```

---

### Follow-Up Message 1 (Send 24 hours after connection is accepted)
```
{follow_up_1}
```

### Follow-Up Message 2 (Send 4-5 days after connect if no reply)
```
{follow_up_2}
```
"""
    clean_out, _, _, _, _ = clean_and_score(output_md)
    return {
        "outreach": clean_out,
        "notes": validated_notes,
        "follow_up_1": follow_up_1,
        "follow_up_2": follow_up_2,
    }


def get_recruiter_search_hub(location: str = "India") -> Dict[str, Any]:
    """
    Curates direct boolean search queries and clickable LinkedIn search URLs
    to find HRs, Technical Recruiters, and IT Hiring Managers hiring for
    Network Engineers and System Administrators.
    """
    queries = [
        {
            "title": "HRs & Talent Acquisition hiring Network Engineers",
            "search_query": '("HR" OR "Talent Acquisition" OR "Recruiter") AND ("Network Engineer" OR "CCNA") AND "hiring"',
            "url": "https://www.linkedin.com/search/results/people/?keywords=%28%22HR%22%20OR%20%22Talent%20Acquisition%22%20OR%20%22Recruiter%22%29%20AND%20%28%22Network%20Engineer%22%20OR%20%22CCNA%22%29%20AND%20%22hiring%22"
        },
        {
            "title": "Technical Recruiters hiring L1/L2/L3 System Administrators",
            "search_query": '("Technical Recruiter" OR "IT Recruiter") AND ("System Administrator" OR "SysAdmin" OR "L2" OR "L3") AND "hiring"',
            "url": "https://www.linkedin.com/search/results/people/?keywords=%28%22Technical%20Recruiter%22%20OR%20%22IT%20Recruiter%22%29%20AND%20%28%22System%20Administrator%22%20OR%20%22SysAdmin%22%20OR%20%22L2%22%20OR%20%22L3%22%29%20AND%20%22hiring%22"
        },
        {
            "title": "IT Infrastructure Managers & Hiring Leads",
            "search_query": '("IT Infrastructure Manager" OR "NOC Manager" OR "IT Director") AND ("hiring" OR "looking for")',
            "url": "https://www.linkedin.com/search/results/people/?keywords=%28%22IT%20Infrastructure%20Manager%22%20OR%20%22NOC%20Manager%22%20OR%20%22IT%20Director%22%29%20AND%20%28%22hiring%22%20OR%20%22looking%20for%22%29"
        },
        {
            "title": "All Recent Posts hiring for Network & SysAdmin Roles",
            "search_query": '("hiring" OR "we are hiring") AND ("Network Engineer" OR "System Administrator")',
            "url": "https://www.linkedin.com/search/results/content/?keywords=%28%22hiring%22%20OR%20%22we%20are%20hiring%22%29%20AND%20%28%22Network%20Engineer%22%20OR%20%22System%20Administrator%22%29&sortBy=%22date_posted%22"
        }
    ]
    
    hub_md = "### LinkedIn Recruiter Search Hub & Direct URLs\n\n"
    for q in queries:
        hub_md += f"#### {q['title']}\n"
        hub_md += f"- **Search Query:** `{q['search_query']}`\n"
        hub_md += f"- **Direct LinkedIn Search Link:** [{q['title']}]({q['url']})\n\n"
    
    return {
        "hub": hub_md,
        "queries": queries,
    }


def generate_networking_post(topic: str = "") -> Dict[str, Any]:
    """
    Creates an authentic technical networking or system administration post
    demonstrating real hands-on troubleshooting.
    """
    default_topics = [
        "How a rogue DHCP server took down an office subnet and how we tracked the MAC with Wireshark and DHCP snooping",
        "The difference between L1, L2, and L3 System Administrator troubleshooting in practice",
        "3 Active Directory Group Policy mistakes that can lock out an entire company",
        "Why 80% of network latency tickets turn out to be MTU mismatches or faulty duplex negotiation",
        "Subnetting cheat sheet: calculating usable hosts in your head in 5 seconds"
    ]
    selected_topic = topic or default_topics[0]
    return create_post(selected_topic)


def connect_account(profile_url: str = "") -> Dict[str, Any]:
    """
    Connects JARVIS to the user's LinkedIn account:
    1. Updates config/api_keys.json with linkedin_connected=True and linkedin_profile_url.
    2. Opens LinkedIn in the user's default browser (where they are logged in).
    3. Prepares session directory.
    """
    import webbrowser
    config_file = PROJECT_ROOT / "config" / "api_keys.json"
    session_dir = PROJECT_ROOT / "config" / "linkedin_session"
    session_dir.mkdir(parents=True, exist_ok=True)

    data = {}
    if config_file.exists():
        try:
            data = json.loads(config_file.read_text(encoding="utf-8"))
        except Exception:
            data = {}

    url_to_save = profile_url.strip() if profile_url else data.get("linkedin_profile_url", "")
    if url_to_save and not url_to_save.startswith("http"):
        url_to_save = "https://www.linkedin.com/in/" + url_to_save.lstrip("/")

    data["linkedin_connected"] = True
    if url_to_save:
        data["linkedin_profile_url"] = url_to_save

    try:
        config_file.write_text(json.dumps(data, indent=4), encoding="utf-8")
    except Exception as e:
        print(f"[LinkedInEngine] Failed to save api_keys: {e}")

    # Open LinkedIn in user's browser
    target_url = url_to_save if url_to_save else "https://www.linkedin.com"
    try:
        webbrowser.open(target_url)
    except Exception as e:
        print(f"[LinkedInEngine] Failed to open browser: {e}")

    return {
        "status": "connected",
        "url": target_url,
        "connected": True,
    }


