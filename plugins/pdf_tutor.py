"""
pdf_tutor.py — JARVIS Advanced PDF Study & Exam Tutor Plugin
=============================================================

Drop this file into plugins/ and restart JARVIS. It is auto-discovered.

WHAT IT DOES
    Turns any PDF (notes, textbook chapter, lab manual, syllabus) into a full
    interactive study session. JARVIS reads the document once, caches the text
    for the session, and then acts as a personal tutor for every follow-up.

MODES  (all triggered by voice)
    load        - read + index a PDF, confirm receipt
    study       - deep concept-by-concept walkthrough in plain English
    summary     - short 5-point overview to check understanding quickly
    plan        - personalised day-by-day exam preparation schedule
    quiz        - 10 practice questions (MCQ + short answer)
    flashcards  - key term / definition pairs, spoken and saved to file
    memorize    - mnemonics, chunking tricks, memory palace anchors
    practical   - hands-on exercises / lab walkthrough derived from content
    explain     - ask about ONE concept from the loaded PDF
    status      - report which PDF is loaded and how many pages / characters

VOICE TRIGGER EXAMPLES
    "Jarvis, load my chemistry notes from C:/uni/chem.pdf"
    "Now study it with me, explain everything simply"
    "Give me a quiz on this"
    "How do I memorize the periodic table part?"
    "Make a flashcard set"
    "Build me a 5-day exam plan"
    "What is Le Chatelier's principle from my notes?"

DEPENDENCIES  (already installed by setup.py)
    PyPDF2       - text extraction (primary)
    pdfplumber   - text extraction (better layout, optional)
    core.gemini  - model ladder (SMART tier, 120 s deadline)
"""

from __future__ import annotations

import re
import textwrap
from datetime import datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# PLUGIN DECLARATION -- Gemini reads this to know when to call us
# ---------------------------------------------------------------------------

PLUGIN = {
    "name": "pdf_tutor",
    "description": (
        "Advanced PDF study and exam tutor. "
        "Use this when the user wants to: "
        "(1) load / read / study a PDF file for exam preparation or understanding concepts, "
        "(2) get a quiz, flashcards, or memorization tips from a previously loaded PDF, "
        "(3) get a day-by-day exam study plan based on their notes, "
        "(4) get practical exercises derived from their notes, "
        "(5) ask about a specific concept from the loaded PDF, "
        "(6) get a quick summary of the loaded material. "
        "(7) extract ONLY a specific practical, chapter, or section from the PDF — e.g. 'copy practical 6', 'get chapter 3'. "
        "Do NOT use file_processor for these tasks -- use this tool instead. "
        "The 'mode' field controls what happens; 'file_path' is only needed when mode is 'load'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "mode": {
                "type": "STRING",
                "description": (
                    "What the user wants to do. One of: "
                    "load (read a new PDF), "
                    "study (explain all concepts simply), "
                    "summary (short overview), "
                    "plan (exam study schedule), "
                    "quiz (practice questions), "
                    "flashcards (key terms and definitions), "
                    "memorize (mnemonics and memory tricks), "
                    "practical (exercises and labs), "
                    "explain (explain a specific concept), "
                    "extract_section (extract ONLY one specific practical or chapter by name/number), "
                    "status (which PDF is loaded)."
                ),
            },
            "file_path": {
                "type": "STRING",
                "description": "Absolute path to the PDF file. Required only when mode is 'load'.",
            },
            "topic": {
                "type": "STRING",
                "description": (
                    "Specific concept or topic the user wants explained. "
                    "Used with mode='explain' or mode='memorize'."
                ),
            },
            "section": {
                "type": "STRING",
                "description": (
                    "The specific section, practical number, or chapter name to extract. "
                    "Used with mode='extract_section'. "
                    "Examples: 'Practical 6', 'Chapter 3', 'Lab 2', 'Experiment 4', 'Unit 5'."
                ),
            },
            "days": {
                "type": "STRING",
                "description": (
                    "Number of days available for exam preparation. "
                    "Used with mode='plan'. Default is 7."
                ),
            },
            "num_questions": {
                "type": "STRING",
                "description": (
                    "Number of quiz questions to generate. "
                    "Used with mode='quiz'. Default is 10."
                ),
            },
        },
        "required": ["mode"],
    },
}


# ---------------------------------------------------------------------------
# MODULE-LEVEL DOCUMENT CACHE
# Extracted text and metadata survive across calls within one JARVIS session,
# so the user never has to re-upload the same PDF for follow-up questions.
# ---------------------------------------------------------------------------

_cache: dict = {
    "path":       None,   # str        -- absolute path of the loaded PDF
    "text":       None,   # str        -- full extracted text (all pages joined)
    "pages_text": [],     # list[str]  -- per-page text, index 0 = page 1
    "pages":      0,      # int        -- page count
    "loaded_at":  None,   # str        -- human-readable timestamp
    "filename":   None,   # str        -- basename
}

# Characters sent to Gemini per call (well within the context window)
_CHUNK = 60_000


# ---------------------------------------------------------------------------
# PRIVATE HELPERS
# ---------------------------------------------------------------------------

def _extract_text(path: Path) -> tuple[str, int, list[str]]:
    """Return (full_text, page_count, pages_text_list). Tries pdfplumber first, then PyPDF2."""
    full_text  = ""
    pages_list: list[str] = []
    pages      = 0

    # pdfplumber handles tables and multi-column layouts better
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            pages = len(pdf.pages)
            for pg in pdf.pages:
                chunk = pg.extract_text() or ""
                pages_list.append(chunk)
                full_text += chunk + "\n"
        if full_text.strip():
            return full_text, pages, pages_list
    except Exception:
        pass

    # PyPDF2 fallback
    pages_list = []
    full_text  = ""
    try:
        import PyPDF2
        with open(path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            pages = len(reader.pages)
            for pg in reader.pages:
                chunk = pg.extract_text() or ""
                pages_list.append(chunk)
                full_text += chunk + "\n"
    except ImportError:
        return "", 0, []
    except Exception as exc:
        return f"__ERROR__: {exc}", 0, []

    return full_text, pages, pages_list


def _gemini(prompt: str, timeout_ms: int = 120_000) -> str:
    """PRO-tier Gemini call (gemini-2.5-pro first, SMART fallback).

    Every other plugin and action in JARVIS uses FAST or SMART tier.
    pdf_tutor is the ONLY place in the whole app that uses PRO, because
    deep document comprehension, concept explanation, and exam planning
    genuinely benefit from the higher-capability model. Everything else
    (browser, files, system control, reminders, etc.) stays on Flash.
    """
    try:
        from core import gemini
        resp = gemini.call(prompt, tier=gemini.PRO, timeout_ms=timeout_ms)
        if resp is None:
            return "Sir, every model on the ladder failed to respond. Please try again."
        return (getattr(resp, "text", None) or "").strip()
    except Exception as exc:
        return f"Sir, the AI call failed: {exc}"


def _save_output(tag: str, content: str, source_path: str | None = None) -> Path:
    """Save AI-generated content next to the source PDF (or in home folder)."""
    base = Path(source_path).parent if source_path else Path.home()
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = Path(source_path).stem if source_path else "notes"
    out  = base / f"{stem}_{tag}_{ts}.txt"
    try:
        out.write_text(content, encoding="utf-8")
    except Exception:
        pass
    return out


def _log(player, msg: str) -> None:
    if player:
        try:
            player.write_log(f"JARVIS: {msg}")
        except Exception:
            pass


def _loaded_or_err() -> str | None:
    """Return None if a PDF is loaded, else an error string for JARVIS to speak."""
    if not _cache["text"]:
        return (
            "Sir, no PDF is loaded yet. Please say something like: "
            "'Jarvis, load my notes from C:/path/to/file.pdf' first."
        )
    return None


def _chunk(max_chars: int = _CHUNK) -> str:
    """Safely slice the cached text for a prompt."""
    return (_cache["text"] or "")[:max_chars]


# ---------------------------------------------------------------------------
# MODE HANDLERS
# ---------------------------------------------------------------------------

def _mode_load(params: dict, player) -> str:
    raw_path = params.get("file_path", "").strip().strip("'\"")
    if not raw_path:
        return "Sir, I need the full path to the PDF file. Please say the path clearly."

    path = Path(raw_path)
    if not path.exists():
        return f"Sir, I cannot find a file at: {raw_path}. Please check the path."
    if path.suffix.lower() != ".pdf":
        return f"Sir, '{path.name}' does not appear to be a PDF file."

    _log(player, f"Loading PDF: {path.name} ...")
    text, pages, pages_list = _extract_text(path)

    if isinstance(text, str) and text.startswith("__ERROR__"):
        return f"Sir, I hit an error reading the PDF: {text[10:]}"
    if not text.strip():
        return (
            "Sir, I could not extract any text from that PDF. "
            "It may be a scanned image. Try running it through an OCR tool first."
        )

    _cache["path"]       = str(path)
    _cache["text"]       = text
    _cache["pages_text"] = pages_list
    _cache["pages"]      = pages
    _cache["filename"]   = path.name
    _cache["loaded_at"]  = datetime.now().strftime("%d %b %Y, %I:%M %p")

    _log(player, "Generating overview ...")
    overview = _gemini(
        f"In exactly 2-3 sentences, describe what this document is about "
        f"in very simple English:\n\n{text[:4000]}",
        timeout_ms=30_000,
    )

    char_k = len(text) // 1000
    return (
        f"Sir, I have loaded '{path.name}' -- {pages} pages, "
        f"roughly {char_k} thousand characters of content. "
        f"Here is what it covers: {overview} "
        "You can now say: study, quiz, flashcards, memorize, plan, practical, "
        "or explain a concept."
    )


def _mode_status(player) -> str:
    if not _cache["text"]:
        return "Sir, no PDF is currently loaded. Please load one first."
    char_k = len(_cache["text"]) // 1000
    return (
        f"Sir, the loaded document is '{_cache['filename']}', "
        f"{_cache['pages']} pages, approximately {char_k} thousand characters. "
        f"Loaded at {_cache['loaded_at']}."
    )


def _mode_summary(player) -> str:
    err = _loaded_or_err()
    if err:
        return err

    _log(player, "Generating document summary ...")
    prompt = textwrap.dedent(f"""
        You are an expert tutor. Summarise this study material for a student
        preparing for an exam. Structure your summary as:

        1. Subject / Topic
        2. Five most important key points (each in one simple sentence)
        3. Three things the student absolutely must not forget

        Use the simplest possible language. No jargon without explanation.

        DOCUMENT:
        {_chunk()}
    """).strip()

    reply = _gemini(prompt)
    _save_output("summary", reply, _cache["path"])
    _log(player, "Summary saved.")
    return reply


def _mode_study(player) -> str:
    err = _loaded_or_err()
    if err:
        return err

    _log(player, "Building concept-by-concept explanation ...")
    prompt = textwrap.dedent(f"""
        You are the best teacher in the world. A student has given you their
        study notes and you must explain EVERY concept in them as if the student
        is hearing it for the first time. Use:
        - Very simple words (avoid heavy jargon; if you must use a term, explain it)
        - Real-life analogies and examples wherever possible
        - Short sentences
        - A warm, encouraging tone

        For each concept:
        1. State the concept name clearly
        2. Explain what it means in plain English
        3. Give a real-life example or analogy
        4. State why it matters / how it connects to other concepts

        After all concepts, write a short "big picture" recap that ties everything
        together.

        STUDY MATERIAL:
        {_chunk()}
    """).strip()

    reply = _gemini(prompt, timeout_ms=180_000)
    _save_output("study_guide", reply, _cache["path"])
    _log(player, "Full study guide saved.")
    return reply


def _mode_plan(params: dict, player) -> str:
    err = _loaded_or_err()
    if err:
        return err

    days = max(1, int(params.get("days") or 7))
    _log(player, f"Building {days}-day exam preparation plan ...")

    prompt = textwrap.dedent(f"""
        You are an academic coach. Create a detailed, realistic {days}-day exam
        preparation plan for a student based on the study material below.

        Rules:
        - Each day must have clear, specific tasks (not vague like "review chapter")
        - Estimate time required for each task (in minutes)
        - Balance new learning with revision
        - Include short breaks and self-test checkpoints
        - Day {days} must be pure revision -- no new material
        - If days is 1 or 2, create an emergency cramming plan and prioritise the
          most heavily tested concepts
        - End with: "PRIORITY TOPICS" -- the 5 most important topics to master

        Format each day like:
        DAY X -- [Theme for the day]
        * [Task] -- [Time estimate]
        ...
        Self-check: [Brief quiz question to test understanding]

        STUDY MATERIAL:
        {_chunk()}
    """).strip()

    reply = _gemini(prompt, timeout_ms=120_000)
    _save_output(f"{days}day_plan", reply, _cache["path"])
    _log(player, f"{days}-day plan saved.")
    return reply


def _mode_quiz(params: dict, player) -> str:
    err = _loaded_or_err()
    if err:
        return err

    n = max(1, int(params.get("num_questions") or 10))
    _log(player, f"Generating {n}-question quiz ...")

    prompt = textwrap.dedent(f"""
        You are a university exam setter. Generate exactly {n} practice questions
        from the study material below. Mix the difficulty:
        - 40% easy   (recall)
        - 40% medium (application / understanding)
        - 20% hard   (analysis / multi-step reasoning)

        Include a variety of question types:
        - Multiple choice (4 options, mark the correct one with a checkmark)
        - Short answer
        - Fill in the blank
        - True / False with a brief justification

        After ALL questions, provide a separate ANSWER KEY section with clear
        explanations for every answer.

        Questions must come directly from the material, not from general knowledge.

        STUDY MATERIAL:
        {_chunk()}
    """).strip()

    reply = _gemini(prompt, timeout_ms=120_000)
    _save_output(f"quiz_{n}q", reply, _cache["path"])
    _log(player, "Quiz saved.")
    return reply


def _mode_flashcards(player) -> str:
    err = _loaded_or_err()
    if err:
        return err

    _log(player, "Generating flashcard set ...")

    prompt = textwrap.dedent(f"""
        You are a study assistant. Extract all important terms, definitions,
        formulas, and concepts from the material below and format them as
        flashcards.

        Format EXACTLY like this:
        FRONT: [Term / Concept / Formula]
        BACK: [Clear, simple definition in 1-3 sentences]
        ---

        Rules:
        - Every technical term must have a card
        - Definitions must be in the simplest possible English
        - For formulas: front = formula name, back = formula + one-line explanation
          of every variable
        - Generate as many cards as needed -- do not skip important terms
        - At the end add a "TOP 5" section marking the 5 most exam-critical cards

        STUDY MATERIAL:
        {_chunk()}
    """).strip()

    reply  = _gemini(prompt, timeout_ms=180_000)
    out    = _save_output("flashcards", reply, _cache["path"])
    count  = reply.count("FRONT:")
    _log(player, f"{count} flashcards saved to {out.name}.")

    return (
        f"Sir, I have generated {count} flashcards from your notes. "
        f"They have been saved to {out.name}. "
        "Here are the first few: " + reply[:1200]
    )


def _mode_memorize(params: dict, player) -> str:
    err = _loaded_or_err()
    if err:
        return err

    topic = params.get("topic", "").strip()
    scope = f"specifically about: {topic}" if topic else "for all concepts in the material"
    _log(player, "Building memorization guide ...")

    prompt = textwrap.dedent(f"""
        You are a memory coach and expert in learning science. A student needs to
        memorize and truly understand content {scope}.

        Provide a complete memorization guide that includes:

        1. CHUNKING STRATEGY
           Break the material into logical groups of 3-5 related items.
           Give each group a memorable name.

        2. MNEMONICS
           Create acronyms, rhymes, or first-letter tricks for lists, sequences,
           and definitions. Make them catchy and easy to remember.

        3. MEMORY PALACE ANCHORS
           Suggest 5-10 vivid, memorable images or locations that a student can
           mentally "place" to remember the most important facts.

        4. STORY METHOD
           Weave the key concepts into a short story (3-5 sentences) that is easy
           to visualise and retell.

        5. SPACED REPETITION SCHEDULE
           Tell the student EXACTLY when to review this material:
           - First review: X hours after initial study
           - Second review: X days later
           - Third review: X days after that
           Base this on the Ebbinghaus forgetting curve.

        6. COMMON MISTAKES TO AVOID
           List 3-5 common errors students make on exams about this material and
           how to avoid them.

        7. ONE-LINE ANCHORS
           For each major concept, write one unforgettable one-liner that captures
           its essence -- like a hashtag for the brain.

        Use simple, energetic language. Make the student feel they CAN master this.

        STUDY MATERIAL:
        {_chunk()}
    """).strip()

    reply = _gemini(prompt, timeout_ms=180_000)
    _save_output("memorize_guide", reply, _cache["path"])
    _log(player, "Memorization guide saved.")
    return reply


def _mode_practical(player) -> str:
    err = _loaded_or_err()
    if err:
        return err

    _log(player, "Building practical exercises ...")

    prompt = textwrap.dedent(f"""
        You are a laboratory instructor and practical exam coach.
        Generate a complete set of practical exercises from the study material below.

        Include ALL of the following that are relevant:

        1. HANDS-ON EXPERIMENTS / PROBLEMS
           Step-by-step practical tasks the student can do themselves.
           Include equipment / resources needed and expected outcomes.

        2. WORKED EXAMPLES
           For each major concept or formula, provide at least one fully worked
           numerical or conceptual example with every step explained.

        3. COMMON LAB SCENARIOS
           Describe typical lab / practical exam scenarios for this material and
           how to approach each one.

        4. TROUBLESHOOTING GUIDE
           List 5 common mistakes made during practicals on this topic and how to
           fix them.

        5. EXAM PRACTICAL TIPS
           Specific advice on how to score full marks in a practical or applied
           exam based on this material.

        Make every explanation crystal clear. Assume the student is doing this
        for the very first time.

        STUDY MATERIAL:
        {_chunk()}
    """).strip()

    reply = _gemini(prompt, timeout_ms=180_000)
    _save_output("practicals", reply, _cache["path"])
    _log(player, "Practical guide saved.")
    return reply


def _mode_explain(params: dict, player) -> str:
    err = _loaded_or_err()
    if err:
        return err

    topic = params.get("topic", "").strip()
    if not topic:
        return (
            "Sir, please tell me which concept you want explained. "
            "For example: 'Explain photosynthesis from my notes.'"
        )

    _log(player, f"Explaining concept: {topic} ...")

    # Pull the most relevant paragraphs using keyword matching
    text     = _cache["text"]
    keywords = [w for w in re.split(r"\W+", topic.lower()) if len(w) > 3]
    chunks   = [p for p in text.split("\n\n") if any(kw in p.lower() for kw in keywords)]
    context  = "\n\n".join(chunks[:20]) or text[:8000]

    prompt = textwrap.dedent(f"""
        You are the world's best teacher. A student wants to understand: "{topic}"

        Using ONLY the context from their study notes below, explain this concept:

        1. WHAT IT IS       -- define it in one clear sentence in the simplest words
        2. HOW IT WORKS     -- step-by-step mechanism or process in plain English
        3. REAL-LIFE ANALOGY -- relate it to something from everyday life
        4. WHY IT MATTERS   -- why is this important for the exam and in real life?
        5. COMMON EXAM QUESTIONS -- 2-3 example questions that test this concept
        6. ONE-LINE MEMORY HOOK -- a single catchy phrase to remember it forever

        If the concept is not covered in their notes, say so clearly and give a
        brief general explanation instead.

        STUDENT'S NOTES (relevant section):
        {context}
    """).strip()

    reply = _gemini(prompt, timeout_ms=60_000)
    _log(player, f"Explained: {topic}")
    return reply


def _mode_extract_section(params: dict, player) -> str:
    """Extract ONLY a specific practical / chapter / section from the loaded PDF.

    Uses a two-stage approach:
    Stage 1 — fast keyword scan across per-page text to find candidate pages
    Stage 2 — Gemini PRO to isolate exactly the requested section boundaries
              and return only that content, formatted cleanly
    """
    err = _loaded_or_err()
    if err:
        return err

    section = params.get("section", "").strip()
    if not section:
        return (
            "Sir, please tell me which section to extract. "
            "For example: 'Practical 6', 'Chapter 3', 'Lab 2'."
        )

    _log(player, f"Locating section: {section} ...")

    pages_list = _cache["pages_text"]
    total_pages = _cache["pages"]

    # ── Stage 1: Keyword scan ─────────────────────────────────────────────
    # Find the page range that is most likely to contain the requested section.
    # We look for the section heading AND the next section heading to define the
    # boundary — so we never copy more than one section.
    keywords = re.split(r"\W+", section.lower())
    keywords = [k for k in keywords if len(k) > 1]

    scored: list[tuple[int, int]] = []  # (score, page_index)
    for i, page_text in enumerate(pages_list):
        low = page_text.lower()
        score = sum(1 for k in keywords if k in low)
        if score:
            scored.append((score, i))

    if not scored:
        # Fallback — send the full text to Gemini and ask it to find the section
        _log(player, "Keyword scan found nothing — asking Gemini to locate the section ...")
        context = _chunk()[:40_000]
    else:
        # Take the best-scoring page ± 4 pages as context window
        scored.sort(key=lambda x: -x[0])
        best_page = scored[0][1]
        start_pg  = max(0, best_page - 2)
        end_pg    = min(total_pages, best_page + 8)  # grab up to 8 pages after
        context   = "\n".join(pages_list[start_pg:end_pg])
        _log(player, f"Found candidate pages {start_pg+1}–{end_pg} — asking Gemini to isolate section ...")

    # ── Stage 2: Gemini isolates the exact section ────────────────────────
    prompt = textwrap.dedent(f"""
        You are extracting a SPECIFIC SECTION from a student's PDF notes.
        The student asked for: "{section}"

        From the text below, extract ONLY the content that belongs to "{section}".

        Rules:
        - Return ONLY the content of "{section}" — nothing before it, nothing after it.
        - Include the section heading/title at the top.
        - Include ALL code, steps, diagrams-as-text, and explanations that are part of this section.
        - STOP the moment the next section / practical / chapter begins.
        - Format the output cleanly with proper line breaks.
        - If you cannot find "{section}" in the text, say so clearly.

        TEXT FROM PDF:
        {context}
    """).strip()

    result = _gemini(prompt, timeout_ms=90_000)

    if not result or "cannot find" in result.lower() or "not found" in result.lower():
        return (
            f"Sir, I could not locate '{section}' in the loaded PDF. "
            f"Try loading the PDF first or check the section name."
        )

    # Save extracted section to file alongside the source PDF
    out = _save_output(
        section.lower().replace(" ", "_"),
        result,
        _cache["path"]
    )
    _log(player, f"Section '{section}' extracted and saved to {out.name}.")

    # Also copy to clipboard for immediate paste into Google Docs
    try:
        import pyperclip
        pyperclip.copy(result)
        clipboard_note = " It has also been copied to your clipboard — switch to Google Docs and paste."
    except Exception:
        clipboard_note = f" Saved to: {out.name}."

    char_count = len(result)
    return (
        f"Sir, I have extracted '{section}' from your PDF ({char_count} characters)."
        f"{clipboard_note} Here is a preview: {result[:400]}..."
    )


# ---------------------------------------------------------------------------
# MAIN ENTRY POINT
# ---------------------------------------------------------------------------

def run(parameters: dict, player=None, session_memory=None) -> str:
    mode = (parameters.get("mode") or "").lower().strip()

    try:
        if mode == "load":
            return _mode_load(parameters, player)
        if mode == "status":
            return _mode_status(player)
        if mode == "summary":
            return _mode_summary(player)
        if mode == "study":
            return _mode_study(player)
        if mode == "plan":
            return _mode_plan(parameters, player)
        if mode == "quiz":
            return _mode_quiz(parameters, player)
        if mode == "flashcards":
            return _mode_flashcards(player)
        if mode == "memorize":
            return _mode_memorize(parameters, player)
        if mode == "practical":
            return _mode_practical(player)
        if mode == "explain":
            return _mode_explain(parameters, player)
        if mode == "extract_section":
            return _mode_extract_section(parameters, player)

        return (
            f"Sir, I don't recognise the mode '{mode}'. "
            "Available modes: load, study, summary, plan, quiz, flashcards, "
            "memorize, practical, explain, extract_section, status."
        )

    except Exception as exc:
        _log(player, f"pdf_tutor error: {exc}")
        return f"Sir, the PDF tutor encountered an unexpected error: {exc}"
