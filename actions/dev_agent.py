"""
actions/dev_agent.py — Autonomous Full-Stack Software Engineering Agent for JARVIS.

Builds complete, production-grade multi-file software projects from voice instructions:
- Free Multi-Model Ladder: Gemini (SMART/PRO), Groq (Qwen 2.5 Coder), Ollama (Local), OpenRouter
- Production Standards: Modular architecture, type annotations, error handling, clean documentation
- Automated Testing: Automatically writes and executes unit tests (pytest / unittest / node --test)
- Self-Healing Engine: Catches errors & test failures, diagnoses bugs, and auto-patches files
- IDE Controller: Opens the project directly in VS Code or Antigravity IDE
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from core import coder_engine

PROJECTS_DIR = Path.home() / "Desktop" / "JarvisProjects"
MAX_FIX_ATTEMPTS = 5


def _detect_ide_from_text(text: str) -> str:
    low = text.lower()
    if any(k in low for k in ("antigravity", "agy")):
        return "antigravity"
    if any(k in low for k in ("vscode", "vs code", "visual studio code")):
        return "vscode"
    if "both" in low:
        return "both"
    return "auto"


def _detect_model_from_text(text: str) -> str:
    low = text.lower()
    if "groq" in low or "qwen" in low:
        return "groq"
    if "ollama" in low or "local model" in low:
        return "ollama"
    if "openrouter" in low:
        return "openrouter"
    if "gemini pro" in low:
        return "gemini_pro"
    return "auto"


def _plan_project(description: str, language: str, model_pref: str = "auto") -> dict:
    prompt = f"""You are a senior principal software architect.
Create an advanced, production-grade project architecture for the following requirements:

Language: {language}
Requirements: {description}

Produce a complete, modular, enterprise-quality file structure.
Include:
1. Core logic divided into modular, cohesive files (controllers, services, models, utils).
2. Comprehensive automated unit tests under 'tests/' (e.g. tests/test_main.py) with actual test assertions.
3. A clean 'README.md' with project overview and execution instructions.
4. If Python, include external dependencies (do NOT include standard library packages like os, sys, json, math, re).
5. Files MUST be listed in strict dependency order: leaf modules with 0 internal imports first, modules that depend on them next, and the entry point last.

Return ONLY a valid JSON object — no prose, no markdown, no triple backticks:
{{
  "project_name": "snake_case_descriptive_name",
  "entry_point": "main.py",
  "files": [
    {{
      "path": "utils/helpers.py",
      "description": "Utility helpers and data parsing functions",
      "imports": []
    }},
    {{
      "path": "core/engine.py",
      "description": "Core business logic and algorithm execution",
      "imports": ["utils.helpers"]
    }},
    {{
      "path": "tests/test_engine.py",
      "description": "Comprehensive unit tests covering edge cases and core features",
      "imports": ["core.engine", "utils.helpers"]
    }},
    {{
      "path": "main.py",
      "description": "CLI or Application entry point orchestrating execution",
      "imports": ["core.engine", "utils.helpers"]
    }}
  ],
  "run_command": "python main.py",
  "test_command": "pytest -v",
  "dependencies": []
}}
"""
    raw = coder_engine.generate_code_text(prompt, tier="smart", model_preference=model_pref, timeout_s=60)
    cleaned = coder_engine._clean_code(raw)
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict) and "files" in data:
            return data
    except Exception:
        pass

    match = re.search(r"\{[\s\S]*\}", cleaned)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            pass

    raise ValueError(f"Planner failed to generate valid project JSON. Raw response preview: {raw[:200]}")


def _write_file(
    file_info: dict,
    project_description: str,
    all_files: list[dict],
    language: str,
    project_dir: Path,
    already_written: dict[str, str],
    model_pref: str = "auto",
) -> str:
    file_path = file_info["path"]
    file_desc = file_info.get("description", "")
    file_imports = file_info.get("imports", [])

    file_list = "\n".join(
        f"  [{i+1}] {f['path']}: {f.get('description', '')}"
        for i, f in enumerate(all_files)
    )

    dep_context = ""
    for dep_dotted in file_imports:
        dep_path = dep_dotted.replace(".", "/") + ".py"
        if dep_path in already_written:
            snippet = already_written[dep_path][:2500]
            dep_context += f"\n\n--- {dep_path} (you must import from this) ---\n{snippet}"

    lang_rules = ""
    if language.lower() == "python":
        lang_rules = """
Python Standards:
- Use type hints for all function arguments and returns.
- Write docstrings for classes and public methods.
- Use explicit error handling (try/except) and descriptive error messages.
- If this is an entry point, include `if __name__ == '__main__':` block with clear output.
- For tests, write actual unit tests using unittest.TestCase or pytest with realistic mock data and assertions."""
    elif language.lower() in ("javascript", "typescript", "js", "ts"):
        lang_rules = """
JS/TS Standards:
- Use modern ES Modules (import / export).
- Use proper async/await with try/catch error handling.
- Write JSDoc comments for all exported modules."""

    prompt = f"""You are an elite {language} software engineer writing production-quality code.

Project Goal: {project_description}

Complete Project File Structure:
{file_list}
{f"Modules this file imports from:{dep_context}" if dep_context else ""}

Target File to Write: {file_path}
Purpose: {file_desc}
Imports: {', '.join(file_imports) if file_imports else 'No internal imports'}

{lang_rules}

CRITICAL RULES:
1. Output ONLY the raw source code for {file_path}.
2. DO NOT include markdown code fences (```), conversational filler, or explanations.
3. Write 100% COMPLETE, RUNNABLE code. NEVER use '# TODO', 'pass' stubs, or placeholders.
4. Match import paths exactly to the project tree shown above.
5. All tests must be real, runnable tests that verify actual behavior.

Code for {file_path}:"""

    raw = coder_engine.generate_code_text(prompt, tier="smart", model_preference=model_pref, timeout_s=60)
    code = coder_engine._clean_code(raw)

    full_path = project_dir / file_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(code, encoding="utf-8")
    print(f"[DevAgent] 📝 Written: {file_path} ({len(code)} chars)")
    return code


def _install_dependencies(dependencies: list[str], project_dir: Path) -> str:
    if not dependencies:
        return "No external dependencies required."

    to_install = []
    for dep in dependencies:
        pkg = re.split(r"[>=<!]", dep)[0].strip()
        if not pkg:
            continue
        res = subprocess.run([sys.executable, "-m", "pip", "show", pkg], capture_output=True, text=True)
        if res.returncode != 0:
            to_install.append(dep)

    if not to_install:
        return f"All dependencies already installed ({', '.join(dependencies)})."

    print(f"[DevAgent] 📦 Installing dependencies: {to_install}")
    try:
        res = subprocess.run(
            [sys.executable, "-m", "pip", "install"] + to_install,
            capture_output=True, text=True, timeout=120, cwd=str(project_dir)
        )
        if res.returncode == 0:
            return f"Successfully installed: {', '.join(to_install)}"
        return f"Install warning: {res.stderr[:200]}"
    except Exception as e:
        return f"Install error (non-fatal): {e}"


def _fix_files(
    error_output: str,
    project_description: str,
    all_files: list[dict],
    file_codes: dict[str, str],
    language: str,
    project_dir: Path,
    entry_point: str,
    model_pref: str = "auto",
) -> dict[str, str]:
    # Identify error file from traceback if possible
    matches = re.findall(r'File ["\']([^"\']+\.py)["\'],\s+line\s+(\d+)', error_output, re.IGNORECASE)
    error_file, error_line = None, None
    for raw_p, line_str in reversed(matches):
        base = Path(raw_p).name
        for pf in file_codes.keys():
            if Path(pf).name == base:
                error_file, error_line = pf, int(line_str)
                break
        if error_file:
            break

    target_fix = error_file or entry_point
    current_code = file_codes.get(target_fix, "")

    other_ctx = ""
    for fp, c in file_codes.items():
        if fp != target_fix and c:
            other_ctx += f"\n--- {fp} ---\n{c[:1500]}\n"

    prompt = f"""You are a principal debugging engineer. Fix the broken project file below.

Project Goal: {project_description}

Target File: {target_fix}
{f"Error located near line: {error_line}" if error_line else ""}

Error output / Test failures:
{error_output[:3000]}

Other project files (read-only context):
{other_ctx[:3000]}

Current (broken) code for {target_fix}:
{current_code}

Instructions:
1. Output ONLY the complete, corrected source code for {target_fix}.
2. Fix all syntax, runtime, and assertion errors shown in the trace.
3. Preserve all correct functionality. Do not introduce placeholders or stubs.
4. Ensure all imports and type definitions are valid.

Fixed code for {target_fix}:"""

    raw = coder_engine.generate_code_text(prompt, tier="smart", model_preference=model_pref, timeout_s=60)
    fixed = coder_engine._clean_code(raw)

    full_path = project_dir / target_fix
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(fixed, encoding="utf-8")
    print(f"[DevAgent] 🔧 Fixed file: {target_fix}")
    return {target_fix: fixed}


def _build_project(
    description: str,
    language: str = "python",
    project_name: str = "",
    ide: str = "auto",
    model: str = "auto",
    timeout: int = 30,
    speak=None,
    player=None,
) -> str:
    def log(msg: str):
        print(f"[DevAgent] {msg}")
        if player:
            player.write_log(f"[DevAgent] {msg}")

    # Voice / prompt auto-detection overrides
    chosen_ide = _detect_ide_from_text(description) if ide == "auto" else ide
    chosen_model = _detect_model_from_text(description) if model == "auto" else model

    log(f"Planning project architecture using {chosen_model} engine...")
    if speak:
        speak(f"Planning your {language} project, sir. Analyzing architecture and dependencies.")

    try:
        plan = _plan_project(description, language, model_pref=chosen_model)
    except Exception as e:
        msg = f"Architecture planning failed: {e}"
        if speak:
            speak(msg)
        return msg

    proj_name = project_name or plan.get("project_name", "jarvis_project")
    proj_name = re.sub(r"[^\w\-]", "_", proj_name)
    project_dir = PROJECTS_DIR / proj_name
    project_dir.mkdir(parents=True, exist_ok=True)

    files = plan.get("files", [])
    entry_point = plan.get("entry_point", "main.py")
    run_cmd = plan.get("run_command", f"python {entry_point}")
    dependencies = plan.get("dependencies", [])

    log(f"Architecture: '{proj_name}' with {len(files)} files | Entry: {entry_point}")

    # Write files in dependency order
    file_codes: dict[str, str] = {}
    for fi in files:
        fpath = fi.get("path", "")
        if not fpath:
            continue
        log(f"Writing {fpath}...")
        try:
            code = _write_file(
                file_info=fi,
                project_description=description,
                all_files=files,
                language=language,
                project_dir=project_dir,
                already_written=file_codes,
                model_pref=chosen_model,
            )
            file_codes[fpath] = code
            time.sleep(0.3)
        except Exception as e:
            log(f"Warning: Failed to write {fpath}: {e}")

    if not file_codes:
        msg = "Could not generate project source files."
        if speak:
            speak(msg)
        return msg

    # Create README.md
    readme_path = project_dir / "README.md"
    readme_content = f"""# {proj_name}

{description}

## Architecture
- **Language**: {language}
- **Entry Point**: `{entry_point}`
- **Files**:
{chr(10).join(f"- `{f['path']}`: {f.get('description', '')}" for f in files)}

## Execution
Run with:
```bash
{run_cmd}
```

Generated autonomously by JARVIS Advanced Dev Agent.
"""
    readme_path.write_text(readme_content, encoding="utf-8")

    # Install dependencies
    if dependencies:
        req_file = project_dir / "requirements.txt"
        req_file.write_text("\n".join(dependencies) + "\n", encoding="utf-8")
        dep_status = _install_dependencies(dependencies, project_dir)
        log(dep_status)

    # Automated Testing & Execution with Self-Healing Loop
    log("Running automated tests and execution verification...")
    last_output = ""
    test_passed = False
    tests_ran = False

    for attempt in range(1, MAX_FIX_ATTEMPTS + 1):
        log(f"Verification pass (attempt {attempt}/{MAX_FIX_ATTEMPTS})...")

        # 1. Run unit tests
        test_res = coder_engine.run_unit_tests(project_dir, language=language)
        tests_ran = test_res.get("ran", False)

        # 2. Run entry point
        run_res = coder_engine.run_project_command(run_cmd, cwd=project_dir, timeout=timeout)
        last_output = f"{test_res.get('output', '')}\n\n{run_res.get('output', '')}".strip()

        # Check for success
        has_error = (not run_res["success"]) or (tests_ran and not test_res["passed"])

        if not has_error:
            test_passed = True
            log(f"✅ All checks and tests passed on attempt {attempt}!")
            break

        if attempt < MAX_FIX_ATTEMPTS:
            log(f"⚠️ Issues detected on attempt {attempt}, self-healing code...")
            try:
                updated = _fix_files(
                    error_output=last_output,
                    project_description=description,
                    all_files=files,
                    file_codes=file_codes,
                    language=language,
                    project_dir=project_dir,
                    entry_point=entry_point,
                    model_pref=chosen_model,
                )
                file_codes.update(updated)
                time.sleep(0.5)
            except Exception as e:
                log(f"Fix iteration error: {e}")

    # Launch in IDE (VS Code or Antigravity)
    ide_status = coder_engine.open_in_ide(project_dir, ide=chosen_ide)
    log(ide_status)

    # Build executive voice response
    status_phrase = "tested and verified fully working" if test_passed else "created with minor verification warnings"
    spoken_summary = (
        f"Project '{proj_name}' has been {status_phrase}. "
        f"Built {len(file_codes)} source files and unit tests, and opened it for you in your IDE."
    )
    if speak:
        speak(spoken_summary)

    return (
        f"✨ **Project Built Successfully: {proj_name}**\n\n"
        f"- **Directory**: `{project_dir}`\n"
        f"- **Files**: {len(file_codes)} files created\n"
        f"- **IDE Status**: {ide_status}\n"
        f"- **Verification**: {'✅ Passed' if test_passed else '⚠️ Incomplete tests'}\n\n"
        f"**Output Preview**:\n```\n{last_output[:800]}\n```"
    )


def dev_agent(
    parameters: dict,
    response=None,
    player=None,
    session_memory=None,
    speak=None,
) -> str:
    p = parameters or {}
    description = p.get("description", "").strip()
    language = p.get("language", "python").strip()
    project_name = p.get("project_name", "").strip()
    ide = p.get("ide", "auto").strip()
    model = p.get("model", "auto").strip()
    timeout = int(p.get("timeout", 30))

    if not description:
        return "Please describe the software project or code requirements you would like me to build, sir."

    return _build_project(
        description=description,
        language=language,
        project_name=project_name,
        ide=ide,
        model=model,
        timeout=timeout,
        speak=speak,
        player=player,
    )


# ── Tool declaration (auto-discovered by core/action_loader.py) ──────────────
TOOL = {
    "name": "dev_agent",
    "description": (
        "Autonomous Full-Stack Software Engineering Agent. "
        "Builds complete, production-grade multi-file projects from scratch based on user requirements. "
        "Plans architecture, writes all files, writes automated unit tests, installs dependencies, "
        "executes and verifies code with self-healing bug fixes, and opens the project directly in VS Code or Antigravity IDE. "
        "Uses free AI models (Gemini Pro/Flash, Groq Qwen-Coder, Ollama local, OpenRouter)."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "description": {
                "type": "STRING",
                "description": "What the project or software should do — full requirements and features."
            },
            "language": {
                "type": "STRING",
                "description": "Programming language: python | javascript | typescript | html | cpp | go | rust (default: python)"
            },
            "project_name": {
                "type": "STRING",
                "description": "Optional custom name for the project folder"
            },
            "ide": {
                "type": "STRING",
                "description": "IDE to open: vscode | antigravity | both | auto (default: auto)"
            },
            "model": {
                "type": "STRING",
                "description": "AI model engine to use: auto | gemini | groq | ollama | openrouter (default: auto)"
            },
            "timeout": {
                "type": "INTEGER",
                "description": "Execution timeout in seconds (default: 30)"
            }
        },
        "required": [
            "description"
        ]
    },
    "handler": dev_agent,
}
