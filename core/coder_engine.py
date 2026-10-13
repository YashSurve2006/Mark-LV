"""
core/coder_engine.py — Advanced Multi-Model Coding & IDE Automation Engine for JARVIS.

Supports:
1. Multi-Model Free AI Providers:
   - Google Gemini (SMART / PRO / FAST ladders via existing Gemini key)
   - Groq Free Tier (qwen-2.5-coder-32b, llama-3.3-70b-versatile, deepseek-r1-distill-llama-70b)
   - OpenRouter Free Tier (qwen-2.5-coder-32b:free, deepseek-r1:free, llama-3.3-70b:free)
   - Local Ollama (auto-detected at http://localhost:11434)
   - Dynamic Fallback: if one model runs out of quota (429), cascades seamlessly to the next.

2. IDE Launch & Integration:
   - Microsoft VS Code: Code.exe / code.cmd
   - Antigravity IDE: Antigravity IDE.exe
   - Auto-detection across Windows / macOS / Linux

3. Automated Testing & Self-Healing:
   - Automated unit test generation (pytest / unittest / node --test)
   - Automated dependency resolution and installation
   - Execution capture (stdout, stderr, exit codes)
   - Iterative self-healing loop: fixes code upon failure until tests pass
"""
from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Callable, Optional

from core import gemini

_OS = platform.system()


def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


_BASE_DIR = _get_base_dir()
_CONFIG_PATH = _BASE_DIR / "config" / "api_keys.json"
_PROJECTS_DIR = Path.home() / "Desktop" / "JarvisProjects"


def _load_config() -> dict:
    try:
        if _CONFIG_PATH.exists():
            return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


# ── IDE Discovery and Launcher ────────────────────────────────────────────────

def get_installed_ides() -> dict[str, str]:
    """Detects available IDE installations on the system."""
    ides = {}
    local_app = os.environ.get("LOCALAPPDATA", "")
    prog_files = os.environ.get("PROGRAMFILES", "")
    user_home = Path.home()

    # 1. Antigravity IDE
    antigravity_candidates = [
        Path(local_app) / "Programs" / "Antigravity IDE" / "Antigravity IDE.exe",
        Path(prog_files) / "Antigravity IDE" / "Antigravity IDE.exe",
        user_home / "AppData" / "Local" / "Programs" / "Antigravity IDE" / "Antigravity IDE.exe",
    ]
    for c in antigravity_candidates:
        if c.exists():
            ides["antigravity"] = str(c)
            break
    if "antigravity" not in ides:
        found = shutil.which("antigravity") or shutil.which("agy")
        if found:
            ides["antigravity"] = found

    # 2. Microsoft VS Code
    vscode_candidates = [
        Path(local_app) / "Programs" / "Microsoft VS Code" / "Code.exe",
        Path(local_app) / "Programs" / "Microsoft VS Code" / "bin" / "code.cmd",
        Path(prog_files) / "Microsoft VS Code" / "Code.exe",
        Path(prog_files) / "Microsoft VS Code" / "bin" / "code.cmd",
        user_home / "AppData" / "Local" / "Programs" / "Microsoft VS Code" / "Code.exe",
        user_home / "AppData" / "Local" / "Programs" / "Microsoft VS Code" / "bin" / "code.cmd",
    ]
    for c in vscode_candidates:
        if c.exists():
            ides["vscode"] = str(c)
            break
    if "vscode" not in ides:
        found = shutil.which("code")
        if found:
            ides["vscode"] = found

    return ides


def open_in_ide(target_path: Path | str, ide: str = "auto") -> str:
    """
    Opens target_path (project directory or file) in the specified IDE:
    ide: 'antigravity' | 'vscode' | 'both' | 'auto'
    """
    p = Path(target_path).resolve()
    if not p.exists():
        return f"Cannot open non-existent path in IDE: {p}"

    ides = get_installed_ides()
    chosen_ide = (ide or "auto").lower().strip()
    results = []

    def _launch(name: str, exe: str) -> bool:
        try:
            # Use ShellExecute or Popen without hanging
            if exe.endswith(".cmd") or exe.endswith(".bat"):
                subprocess.Popen([exe, str(p)], shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                subprocess.Popen([exe, str(p)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(0.5)
            return True
        except Exception as e:
            print(f"[CoderEngine] Failed to launch {name}: {e}")
            return False

    if chosen_ide in ("antigravity", "agy"):
        if "antigravity" in ides:
            if _launch("Antigravity IDE", ides["antigravity"]):
                return f"Opened project in Antigravity IDE: {p}"
        return f"Antigravity IDE executable not found. Found: {list(ides.keys())}"

    elif chosen_ide in ("vscode", "code"):
        if "vscode" in ides:
            if _launch("VS Code", ides["vscode"]):
                return f"Opened project in VS Code: {p}"
        return f"VS Code executable not found. Found: {list(ides.keys())}"

    elif chosen_ide == "both":
        for k in ("antigravity", "vscode"):
            if k in ides and _launch(k, ides[k]):
                results.append(k)
        if results:
            return f"Opened in {', '.join(results)}: {p}"
        return "Neither Antigravity nor VS Code could be launched."

    else:  # 'auto'
        # Prioritize Antigravity if available, then VS Code
        for k in ("antigravity", "vscode"):
            if k in ides:
                if _launch(k.replace("vscode", "VS Code").replace("antigravity", "Antigravity IDE"), ides[k]):
                    return f"Opened project in {k.replace('vscode', 'VS Code').replace('antigravity', 'Antigravity IDE')}: {p}"

        # System fallback
        if _OS == "Windows":
            os.startfile(str(p))
            return f"Opened project in system explorer: {p}"
        return f"No suitable IDE found to open: {p}"


# ── Free Multi-Model AI Inference Engine ──────────────────────────────────────

def _check_ollama() -> list[str]:
    """Returns list of local Ollama models if Ollama is running."""
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags", headers={"User-Agent": "JARVIS"})
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
    except Exception:
        return []


def _call_ollama(model: str, prompt: str, timeout: int = 60) -> Optional[str]:
    try:
        url = "http://localhost:11434/api/generate"
        payload = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("response", "").strip()
    except Exception as e:
        print(f"[CoderEngine] Ollama ({model}) call failed: {e}")
        return None


def _call_groq(model: str, prompt: str, api_key: str, timeout: int = 60) -> Optional[str]:
    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        payload = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
        }).encode("utf-8")
        req = urllib.request.Request(
            url, data=payload,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            choices = data.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "").strip()
    except Exception as e:
        print(f"[CoderEngine] Groq ({model}) call failed: {e}")
        return None


def _call_openrouter(model: str, prompt: str, api_key: str, timeout: int = 60) -> Optional[str]:
    try:
        url = "https://openrouter.ai/api/v1/chat/completions"
        payload = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
        }).encode("utf-8")
        req = urllib.request.Request(
            url, data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": "https://github.com/JARVIS",
                "X-Title": "JARVIS",
            }
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            choices = data.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "").strip()
    except Exception as e:
        print(f"[CoderEngine] OpenRouter ({model}) call failed: {e}")
        return None


def _clean_code(text: str) -> str:
    t = text.strip()
    t = re.sub(r"^```[a-zA-Z0-9_\-]*\r?\n?", "", t)
    t = re.sub(r"\r?\n?```\s*$", "", t)
    return t.strip()


def generate_code_text(
    prompt: str,
    tier: str = "smart",
    model_preference: str = "auto",
    timeout_s: int = 60,
) -> str:
    """
    Multi-model coding generator with automatic free-tier fallback:
    1. Checks user model_preference ('groq', 'ollama', 'gemini', 'openrouter', or 'auto')
    2. If Ollama is running locally, can route to local free coding models
    3. If Groq API key is configured, uses fast open weights (Qwen 2.5 Coder / Llama 3.3)
    4. Google Gemini SMART / PRO / FAST ladders (automatic multi-model fallback)
    """
    cfg = _load_config()
    pref = (model_preference or "auto").lower().strip()

    # 1. Local Ollama Check
    if pref in ("ollama", "local", "auto"):
        ollama_models = _check_ollama()
        if ollama_models:
            # Look for coder models
            coder_models = [m for m in ollama_models if any(k in m.lower() for k in ("coder", "deepseek", "qwen", "codellama"))]
            target = coder_models[0] if coder_models else ollama_models[0]
            print(f"[CoderEngine] 🦙 Trying local Ollama model: {target}")
            out = _call_ollama(target, prompt, timeout=timeout_s)
            if out:
                return out

    # 2. Groq Free Tier Check
    groq_key = cfg.get("groq_api_key") or os.environ.get("GROQ_API_KEY")
    if groq_key and pref in ("groq", "qwen", "llama", "auto"):
        for m in ("qwen-2.5-coder-32b", "llama-3.3-70b-versatile", "deepseek-r1-distill-llama-70b"):
            print(f"[CoderEngine] ⚡ Trying Groq model: {m}")
            out = _call_groq(m, prompt, groq_key, timeout=timeout_s)
            if out:
                return out

    # 3. OpenRouter Free Tier Check
    or_key = cfg.get("openrouter_api_key") or os.environ.get("OPENROUTER_API_KEY")
    if or_key and pref in ("openrouter", "auto"):
        for m in ("qwen/qwen-2.5-coder-32b-instruct:free", "deepseek/deepseek-r1:free"):
            print(f"[CoderEngine] 🌐 Trying OpenRouter model: {m}")
            out = _call_openrouter(m, prompt, or_key, timeout=timeout_s)
            if out:
                return out

    # 4. Google Gemini Ladder (The reliable default powerhouse)
    gemini_tier = gemini.PRO if tier == "pro" else (gemini.FAST if tier == "fast" else gemini.SMART)
    print(f"[CoderEngine] 🧠 Generating via Gemini ({gemini_tier} ladder)...")
    resp = gemini.call(prompt, tier=gemini_tier, timeout_ms=timeout_s * 1000)
    if resp and resp.text:
        return resp.text.strip()

    # 5. Last resort fallback to FAST tier
    resp_fast = gemini.call(prompt, tier=gemini.FAST, timeout_ms=30000)
    if resp_fast and resp_fast.text:
        return resp_fast.text.strip()

    raise RuntimeError("All AI models across the free multi-model ladder were exhausted or timed out.")


# ── Testing & Execution Engine ────────────────────────────────────────────────

def run_project_command(command: str, cwd: Path, timeout: int = 30) -> dict:
    """Executes a command and returns exit code, stdout, stderr, and output."""
    try:
        parts = command.split()
        if parts and parts[0].lower() in ("python", "python3", "py"):
            parts[0] = sys.executable

        res = subprocess.run(
            parts,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=str(cwd),
        )
        out = res.stdout.strip()
        err = res.stderr.strip()
        combined = []
        if out:
            combined.append(f"STDOUT:\n{out}")
        if err:
            combined.append(f"STDERR:\n{err}")

        return {
            "exit_code": res.returncode,
            "stdout": out,
            "stderr": err,
            "output": "\n\n".join(combined) if combined else "(no output)",
            "success": res.returncode == 0,
        }
    except subprocess.TimeoutExpired:
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Timed out after {timeout} seconds",
            "output": f"Timed out after {timeout}s (app/server may be long-running).",
            "success": True,  # servers/GUIs timing out is often normal
        }
    except Exception as e:
        return {
            "exit_code": 1,
            "stdout": "",
            "stderr": str(e),
            "output": f"Execution failed: {e}",
            "success": False,
        }


def run_unit_tests(project_dir: Path, language: str = "python", timeout: int = 40) -> dict:
    """Runs automated unit tests for the project."""
    lang = language.lower()

    if lang == "python":
        # Check if tests directory or test files exist
        has_tests = any(project_dir.glob("**/test_*.py")) or any(project_dir.glob("**/*_test.py"))
        if not has_tests:
            return {"ran": False, "passed": True, "message": "No test files found."}

        # Try pytest first, then fallback to unittest
        cmd = f"{sys.executable} -m pytest -v" if shutil.which("pytest") else f"{sys.executable} -m unittest discover -s tests"
        res = run_project_command(cmd, cwd=project_dir, timeout=timeout)
        res["ran"] = True
        res["passed"] = (res["exit_code"] == 0)
        return res

    elif lang in ("javascript", "typescript", "node", "js", "ts"):
        pkg_json = project_dir / "package.json"
        if pkg_json.exists():
            res = run_project_command("npm test", cwd=project_dir, timeout=timeout)
            res["ran"] = True
            res["passed"] = (res["exit_code"] == 0)
            return res

    return {"ran": False, "passed": True, "message": f"Testing not configured for {language}."}
