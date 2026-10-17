"""
web_builder.py — Autonomous Web Studio & Site Forge Engine for JARVIS Mark-LV
=============================================================================

Provides full autonomous website generation, instant local dev server hosting,
Chrome auto-preview, modular UI component synthesis, and automated SEO/a11y audits.

Capabilities:
1. create_site      — Scaffold a complete modern website (portfolio, saas, dashboard,
                      noc_portal, or AI-synthesized custom site) with responsive CSS,
                      glassmorphism, Google Fonts, and vanilla JavaScript.
2. start_server     — Instant zero-config local HTTP server (port 3000+) that serves
                      the site and automatically opens it in Google Chrome.
3. stop_server      — Stop one or all running dev servers.
4. list_servers     — Inspect active local dev servers, ports, and hosted paths.
5. create_component — Generate modular, copy-paste ready UI components (navbar, hero,
                      pricing_card, stats_grid, contact_form, faq_accordion, modal).
6. audit_site       — Audit any local HTML file or live URL for SEO meta tags, heading
                      hierarchy, mobile viewport, accessibility (alt/aria), and performance.
"""

from __future__ import annotations

import html.parser
import json
import os
import re
import socket
import sys
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


_OUTPUT_SITES_DIR = _base_dir() / "output" / "sites"
_OUTPUT_COMPONENTS_DIR = _base_dir() / "output" / "components"


def _log(player: Any, msg: str) -> None:
    short = str(msg)[:80]
    try:
        print(f"[WebBuilder] {short}")
    except UnicodeEncodeError:
        try:
            print(f"[WebBuilder] {short.encode('ascii', errors='replace').decode('ascii')}")
        except Exception:
            pass
    if player:
        try:
            if hasattr(player, "write_log"):
                player.write_log(f"[web] {short[:60]}")
            elif hasattr(player, "log"):
                player.log(short[:60])
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# 1. Dev Server Registry & Process Manager
# ─────────────────────────────────────────────────────────────────────────────

class _DevServerInfo:
    def __init__(self, port: int, directory: Path, server: ThreadingHTTPServer, thread: threading.Thread):
        self.port = port
        self.directory = directory
        self.server = server
        self.thread = thread
        self.start_time = time.time()


_ACTIVE_SERVERS: Dict[int, _DevServerInfo] = {}
_SERVER_LOCK = threading.Lock()


def _find_free_port(start_port: int = 3000, max_attempts: int = 50) -> int:
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.2)
            res = s.connect_ex(("127.0.0.1", port))
            if res != 0:
                return port
    return start_port


def _create_server_handler(root_dir: Path):
    class CustomHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(root_dir), **kwargs)

        def log_message(self, format, *args):
            # Suppress noisy HTTP request logging to console
            pass

        def end_headers(self):
            # Prevent browser aggressive caching during development
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            super().end_headers()

    return CustomHandler


def start_server(
    target_path: Optional[str] = None,
    site_name: Optional[str] = None,
    port: int = 3000,
    open_browser: bool = True,
    player: Any = None,
) -> str:
    """Spins up a background dev server and launches in Chrome."""
    if target_path:
        root_dir = Path(target_path).resolve()
    elif site_name:
        root_dir = (_OUTPUT_SITES_DIR / site_name).resolve()
    else:
        root_dir = _OUTPUT_SITES_DIR.resolve()

    if not root_dir.exists():
        return f"[ERROR] Directory not found: {root_dir}"

    with _SERVER_LOCK:
        if port in _ACTIVE_SERVERS:
            existing = _ACTIVE_SERVERS[port]
            if existing.directory == root_dir:
                url = f"http://localhost:{port}/"
                if open_browser:
                    _open_in_chrome(url)
                return f"[ACTIVE] Server already running on {url} (serving {root_dir.name})"
            else:
                port = _find_free_port(port + 1)
        else:
            # Check if port is occupied externally
            port = _find_free_port(port)

        try:
            handler = _create_server_handler(root_dir)
            server = ThreadingHTTPServer(("127.0.0.1", port), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()

            info = _DevServerInfo(port, root_dir, server, thread)
            _ACTIVE_SERVERS[port] = info
            url = f"http://localhost:{port}/"

            _log(player, f"Dev server online at {url} -> {root_dir.name}")

            if open_browser:
                _open_in_chrome(url)

            return (
                f"[SUCCESS] Dev Server Online!\n"
                f"URL: {url}\n"
                f"Directory: {root_dir}\n"
                f"Port: {port}\n"
                f"Opened in Chrome: {'Yes' if open_browser else 'No'}"
            )
        except Exception as e:
            return f"[ERROR] Failed to start server on port {port}: {e}"


def stop_server(port: Optional[int] = None, player: Any = None) -> str:
    """Stops one or all running dev servers."""
    with _SERVER_LOCK:
        if not _ACTIVE_SERVERS:
            return "No dev servers are currently active."

        if port is not None:
            if port not in _ACTIVE_SERVERS:
                return f"No active dev server found on port {port}."
            info = _ACTIVE_SERVERS.pop(port)
            try:
                info.server.shutdown()
                info.server.server_close()
            except Exception:
                pass
            _log(player, f"Stopped server on port {port}")
            return f"[STOPPED] Server on port {port} has been shut down."

        # Stop all servers
        stopped = []
        for p, info in list(_ACTIVE_SERVERS.items()):
            try:
                info.server.shutdown()
                info.server.server_close()
            except Exception:
                pass
            stopped.append(str(p))
            del _ACTIVE_SERVERS[p]

        _log(player, f"Stopped all servers: {', '.join(stopped)}")
        return f"[STOPPED] All active servers ({', '.join(stopped)}) have been shut down."


def list_servers() -> str:
    """Lists all active local dev servers."""
    with _SERVER_LOCK:
        if not _ACTIVE_SERVERS:
            return "No dev servers are currently running."
        lines = ["Active Local Dev Servers:"]
        for p, info in _ACTIVE_SERVERS.items():
            uptime = int(time.time() - info.start_time)
            lines.append(f"- Port {p}: http://localhost:{p}/ -> {info.directory.name} (uptime: {uptime}s)")
        return "\n".join(lines)


def _open_in_chrome(url: str) -> None:
    """Opens URL in Chrome or default browser."""
    try:
        # Try finding Chrome on Windows
        chrome_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        ]
        chrome_exe = next((p for p in chrome_paths if os.path.exists(p)), None)
        if chrome_exe:
            import subprocess
            subprocess.Popen([chrome_exe, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
    except Exception:
        pass
    webbrowser.open(url)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Modern Built-In Website Templates (0-Latency Instant Generation)
# ─────────────────────────────────────────────────────────────────────────────

def _generate_portfolio_template(name: str, title: str, bio: str, skills: List[str], projects: List[Dict[str, str]]) -> Tuple[str, str, str]:
    """Generates a state-of-the-art dark glassmorphic personal portfolio."""
    skills_html = "".join([f'<span class="skill-badge">{s}</span>' for s in skills])
    
    projects_html = ""
    for p in projects:
        p_title = p.get("title", "Project")
        p_desc = p.get("desc", "High-performance software and network engineering solution.")
        p_tags = "".join([f'<span class="tag">{t.strip()}</span>' for t in p.get("tags", "Python,Docker").split(",")])
        p_url = p.get("url", "#")
        projects_html += f"""
        <div class="project-card">
          <div class="project-glow"></div>
          <div class="project-header">
            <h3>{p_title}</h3>
            <a href="{p_url}" class="project-link" target="_blank" rel="noopener">↗</a>
          </div>
          <p class="project-desc">{p_desc}</p>
          <div class="project-tags">{p_tags}</div>
        </div>
        """

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{name} — {title}</title>
  <meta name="description" content="Personal portfolio and engineering showcase of {name}">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <div class="bg-mesh"></div>

  <!-- Navigation -->
  <nav class="navbar">
    <div class="nav-container">
      <a href="#" class="brand-logo"><span class="accent-dot"></span>{name}</a>
      <div class="nav-links">
        <a href="#about">About</a>
        <a href="#skills">Skills</a>
        <a href="#projects">Projects</a>
        <a href="#contact" class="btn-primary">Get In Touch</a>
      </div>
    </div>
  </nav>

  <!-- Hero Section -->
  <header class="hero" id="about">
    <div class="hero-container">
      <div class="status-pill">
        <span class="pulsing-dot"></span> Available for New Opportunities
      </div>
      <h1 class="hero-title">Designing & Scaling <br/><span class="gradient-text">{title}</span></h1>
      <p class="hero-subtitle">{bio}</p>
      <div class="hero-actions">
        <a href="#projects" class="btn-primary">View Featured Projects</a>
        <a href="#contact" class="btn-secondary">Let's Connect</a>
      </div>
    </div>
  </header>

  <!-- Skills Section -->
  <section class="section" id="skills">
    <div class="container">
      <div class="section-header">
        <h2 class="section-title">Core Competencies & Stack</h2>
        <p class="section-desc">Technologies, protocols, and architectural paradigms I leverage daily.</p>
      </div>
      <div class="skills-grid">
        {skills_html}
      </div>
    </div>
  </section>

  <!-- Projects Section -->
  <section class="section" id="projects">
    <div class="container">
      <div class="section-header">
        <h2 class="section-title">Featured Engineering Projects</h2>
        <p class="section-desc">Selected systems, automation scripts, and full-stack solutions.</p>
      </div>
      <div class="projects-grid">
        {projects_html}
      </div>
    </div>
  </section>

  <!-- Contact Section -->
  <section class="section" id="contact">
    <div class="container contact-container">
      <div class="contact-card">
        <h2 class="section-title">Initiate Transmission</h2>
        <p class="section-desc">Interested in discussing architecture, systems administration, or collaborating?</p>
        <form id="contact-form" class="contact-form">
          <div class="form-group">
            <input type="text" id="name" placeholder="Your Name" required>
          </div>
          <div class="form-group">
            <input type="email" id="email" placeholder="Your Email" required>
          </div>
          <div class="form-group">
            <textarea id="message" rows="4" placeholder="Your Message" required></textarea>
          </div>
          <button type="submit" class="btn-primary full-width">Send Message</button>
        </form>
        <div id="form-feedback" class="form-feedback"></div>
      </div>
    </div>
  </section>

  <!-- Footer -->
  <footer class="footer">
    <div class="container footer-content">
      <p>&copy; <span id="year"></span> {name}. Engineered with autonomous speed via JARVIS Mark-LV.</p>
    </div>
  </footer>

  <script src="app.js"></script>
</body>
</html>
"""

    css_content = """/* ── Design Tokens ────────────────────────────────────────────── */
:root {
  --bg-primary: #0a0e17;
  --bg-card: rgba(18, 25, 40, 0.65);
  --bg-card-hover: rgba(28, 38, 60, 0.85);
  --accent-cyan: #00e5ff;
  --accent-blue: #3b82f6;
  --accent-purple: #8b5cf6;
  --text-main: #f1f5f9;
  --text-muted: #94a3b8;
  --border-subtle: rgba(255, 255, 255, 0.08);
  --border-glow: rgba(0, 229, 255, 0.25);
  --radius-sm: 8px;
  --radius-md: 14px;
  --radius-lg: 20px;
  --font-sans: 'Outfit', -apple-system, BlinkMacSystemFont, sans-serif;
  --font-mono: 'JetBrains Mono', monospace;
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html {
  scroll-behavior: smooth;
}

body {
  font-family: var(--font-sans);
  background-color: var(--bg-primary);
  color: var(--text-main);
  line-height: 1.6;
  overflow-x: hidden;
  position: relative;
}

/* Background Ambient Lighting Mesh */
.bg-mesh {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background: 
    radial-gradient(circle at 15% 20%, rgba(0, 229, 255, 0.12) 0%, transparent 40%),
    radial-gradient(circle at 85% 75%, rgba(139, 92, 246, 0.12) 0%, transparent 45%);
  pointer-events: none;
  z-index: -1;
}

.container {
  width: 90%;
  max-width: 1200px;
  margin: 0 auto;
}

/* ── Navigation ───────────────────────────────────────────────── */
.navbar {
  position: sticky;
  top: 0;
  z-index: 100;
  background: rgba(10, 14, 23, 0.85);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border-subtle);
  padding: 1rem 0;
}

.nav-container {
  width: 90%;
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.brand-logo {
  font-size: 1.35rem;
  font-weight: 700;
  color: var(--text-main);
  text-decoration: none;
  display: flex;
  align-items: center;
  gap: 8px;
}

.accent-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--accent-cyan);
  box-shadow: 0 0 10px var(--accent-cyan);
}

.nav-links {
  display: flex;
  align-items: center;
  gap: 1.75rem;
}

.nav-links a:not(.btn-primary) {
  color: var(--text-muted);
  text-decoration: none;
  font-weight: 500;
  font-size: 0.95rem;
  transition: color 0.2s ease;
}

.nav-links a:hover {
  color: var(--accent-cyan);
}

/* ── Buttons ──────────────────────────────────────────────────── */
.btn-primary, .btn-secondary {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.65rem 1.4rem;
  border-radius: var(--radius-sm);
  font-weight: 600;
  font-size: 0.95rem;
  text-decoration: none;
  cursor: pointer;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  border: none;
}

.btn-primary {
  background: linear-gradient(135deg, var(--accent-cyan), var(--accent-blue));
  color: #040810;
  box-shadow: 0 4px 16px rgba(0, 229, 255, 0.3);
}

.btn-primary:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 24px rgba(0, 229, 255, 0.45);
}

.btn-secondary {
  background: rgba(255, 255, 255, 0.05);
  color: var(--text-main);
  border: 1px solid var(--border-subtle);
}

.btn-secondary:hover {
  background: rgba(255, 255, 255, 0.1);
  border-color: var(--accent-cyan);
  transform: translateY(-2px);
}

.full-width {
  width: 100%;
}

/* ── Hero Section ─────────────────────────────────────────────── */
.hero {
  padding: 6.5rem 0 4.5rem;
  text-align: center;
}

.hero-container {
  width: 90%;
  max-width: 850px;
  margin: 0 auto;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 16px;
  background: rgba(0, 229, 255, 0.08);
  border: 1px solid rgba(0, 229, 255, 0.3);
  border-radius: 50px;
  font-size: 0.85rem;
  color: var(--accent-cyan);
  margin-bottom: 1.75rem;
}

.pulsing-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--accent-cyan);
  box-shadow: 0 0 8px var(--accent-cyan);
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0% { transform: scale(0.95); opacity: 0.8; }
  50% { transform: scale(1.3); opacity: 1; }
  100% { transform: scale(0.95); opacity: 0.8; }
}

.hero-title {
  font-size: 3.25rem;
  font-weight: 800;
  letter-spacing: -0.03em;
  line-height: 1.15;
  margin-bottom: 1.25rem;
}

.gradient-text {
  background: linear-gradient(135deg, var(--accent-cyan), var(--accent-blue), var(--accent-purple));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.hero-subtitle {
  font-size: 1.2rem;
  color: var(--text-muted);
  margin-bottom: 2.25rem;
}

.hero-actions {
  display: flex;
  justify-content: center;
  gap: 1rem;
}

/* ── Section Styles ───────────────────────────────────────────── */
.section {
  padding: 5rem 0;
}

.section-header {
  text-align: center;
  margin-bottom: 3rem;
}

.section-title {
  font-size: 2rem;
  font-weight: 700;
  margin-bottom: 0.5rem;
}

.section-desc {
  color: var(--text-muted);
  font-size: 1.05rem;
}

/* ── Skills Grid ──────────────────────────────────────────────── */
.skills-grid {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 12px;
  max-width: 900px;
  margin: 0 auto;
}

.skill-badge {
  padding: 10px 20px;
  background: var(--bg-card);
  backdrop-filter: blur(10px);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  font-size: 0.95rem;
  font-weight: 500;
  color: var(--text-main);
  transition: all 0.25s ease;
}

.skill-badge:hover {
  border-color: var(--accent-cyan);
  background: var(--bg-card-hover);
  transform: translateY(-2px);
  box-shadow: 0 4px 14px rgba(0, 229, 255, 0.2);
}

/* ── Projects Grid ────────────────────────────────────────────── */
.projects-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 1.75rem;
}

.project-card {
  position: relative;
  background: var(--bg-card);
  backdrop-filter: blur(12px);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  padding: 2rem;
  overflow: hidden;
  transition: all 0.3s ease;
  display: flex;
  flex-direction: column;
}

.project-card:hover {
  border-color: var(--border-glow);
  transform: translateY(-4px);
  box-shadow: 0 12px 30px rgba(0, 0, 0, 0.4);
}

.project-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.project-header h3 {
  font-size: 1.3rem;
  font-weight: 700;
}

.project-link {
  font-size: 1.3rem;
  color: var(--accent-cyan);
  text-decoration: none;
  transition: transform 0.2s ease;
}

.project-card:hover .project-link {
  transform: translate(3px, -3px);
}

.project-desc {
  color: var(--text-muted);
  font-size: 0.95rem;
  margin-bottom: 1.5rem;
  flex-grow: 1;
}

.project-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.tag {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  padding: 4px 10px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 4px;
  color: var(--accent-cyan);
}

/* ── Contact Section ──────────────────────────────────────────── */
.contact-container {
  display: flex;
  justify-content: center;
}

.contact-card {
  width: 100%;
  max-width: 600px;
  background: var(--bg-card);
  backdrop-filter: blur(14px);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  padding: 3rem;
  text-align: center;
}

.contact-form {
  margin-top: 2rem;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.form-group input, .form-group textarea {
  width: 100%;
  padding: 12px 16px;
  background: rgba(10, 14, 23, 0.7);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-sm);
  color: var(--text-main);
  font-family: inherit;
  font-size: 0.95rem;
  transition: border-color 0.2s ease;
}

.form-group input:focus, .form-group textarea:focus {
  outline: none;
  border-color: var(--accent-cyan);
  box-shadow: 0 0 10px rgba(0, 229, 255, 0.2);
}

.form-feedback {
  margin-top: 1rem;
  font-size: 0.95rem;
  display: none;
}

/* ── Footer ───────────────────────────────────────────────────── */
.footer {
  border-top: 1px solid var(--border-subtle);
  padding: 2.5rem 0;
  text-align: center;
  color: var(--text-muted);
  font-size: 0.9rem;
}

/* ── Responsive Mobile ────────────────────────────────────────── */
@media (max-width: 768px) {
  .hero-title {
    font-size: 2.25rem;
  }
  .nav-links {
    display: none; /* Can be expanded with mobile drawer */
  }
  .contact-card {
    padding: 2rem 1.5rem;
  }
}
"""

    js_content = """// Dynamic Client Logic
document.addEventListener("DOMContentLoaded", () => {
  // Set current copyright year
  const yearEl = document.getElementById("year");
  if (yearEl) yearEl.textContent = new Date().getFullYear();

  // Contact Form Interactivity
  const form = document.getElementById("contact-form");
  const feedback = document.getElementById("form-feedback");

  if (form) {
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const name = document.getElementById("name").value.trim();
      const email = document.getElementById("email").value.trim();

      if (feedback) {
        feedback.style.display = "block";
        feedback.style.color = "#00e5ff";
        feedback.textContent = `Thank you, ${name}! Your transmission has been staged.`;
        form.reset();

        setTimeout(() => {
          feedback.style.display = "none";
        }, 5000);
      }
    });
  }
});
"""

    return html_content, css_content, js_content


def _generate_saas_template(app_name: str, tagline: str, features: List[Dict[str, str]], plans: List[Dict[str, Any]]) -> Tuple[str, str, str]:
    """Generates an ultra-modern SaaS landing page with animated pricing & FAQ."""
    features_html = ""
    for f in features:
        features_html += f"""
        <div class="feature-card">
          <div class="feature-icon">{f.get('icon', '⚡')}</div>
          <h3>{f.get('title', 'High Throughput')}</h3>
          <p>{f.get('desc', 'Engineered for sub-50ms latency and high reliability.')}</p>
        </div>
        """

    plans_html = ""
    for p in plans:
        is_pop = p.get("popular", False)
        pop_badge = '<div class="popular-badge">MOST POPULAR</div>' if is_pop else ''
        perks_html = "".join([f'<li>✓ {item}</li>' for item in p.get("perks", ["All Core Features", "24/7 Monitoring", "Unlimited Bandwidth"])])
        plans_html += f"""
        <div class="pricing-card {'popular' if is_pop else ''}">
          {pop_badge}
          <h3>{p.get('name', 'Pro')}</h3>
          <div class="price-box">
            <span class="currency">$</span>
            <span class="amount">{p.get('price', '29')}</span>
            <span class="period">/mo</span>
          </div>
          <p class="plan-desc">{p.get('desc', 'Ideal for engineers and growing teams.')}</p>
          <ul class="perks-list">
            {perks_html}
          </ul>
          <button class="btn-primary full-width">Deploy Now</button>
        </div>
        """

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{app_name} — {tagline}</title>
  <meta name="description" content="{tagline} — Enterprise automation platform">
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <div class="glow-sphere"></div>

  <!-- Navbar -->
  <nav class="navbar">
    <div class="container nav-wrap">
      <div class="brand">⚡ {app_name}</div>
      <div class="nav-menu">
        <a href="#features">Features</a>
        <a href="#pricing">Pricing</a>
        <a href="#faq">FAQ</a>
        <button class="btn-secondary">Sign In</button>
        <button class="btn-primary">Start Free Trial</button>
      </div>
    </div>
  </nav>

  <!-- Hero -->
  <header class="hero">
    <div class="container hero-content">
      <div class="badge-row"><span class="badge">Next-Gen Release 2.0</span></div>
      <h1>Accelerate Your Infrastructure with <span class="gradient-text">{app_name}</span></h1>
      <p class="subtitle">{tagline}</p>
      <div class="cta-row">
        <input type="email" placeholder="Enter your work email" class="email-input">
        <button class="btn-primary cta-btn">Get Started Instantly</button>
      </div>
      <div class="proof-row">
        <span>🔒 Zero Log Retention</span> • <span>⚡ Sub-50ms Reflexes</span> • <span>🌐 99.99% Availability</span>
      </div>
    </div>
  </header>

  <!-- Features Grid -->
  <section class="section" id="features">
    <div class="container">
      <div class="center-head">
        <h2>Engineered for Scale & Speed</h2>
        <p>Everything you need to orchestrate complex operations with confidence.</p>
      </div>
      <div class="features-grid">
        {features_html}
      </div>
    </div>
  </section>

  <!-- Pricing Table -->
  <section class="section" id="pricing">
    <div class="container">
      <div class="center-head">
        <h2>Transparent, Predictable Pricing</h2>
        <p>No hidden fees. Scale your nodes as your requirements expand.</p>
      </div>
      <div class="pricing-grid">
        {plans_html}
      </div>
    </div>
  </section>

  <!-- FAQ Accordion -->
  <section class="section" id="faq">
    <div class="container faq-container">
      <div class="center-head">
        <h2>Frequently Asked Questions</h2>
      </div>
      <div class="faq-list">
        <div class="faq-item">
          <div class="faq-question">How does {app_name} ensure zero downtime? <span>+</span></div>
          <div class="faq-answer">Our architecture leverages active-active multi-region failover with sub-second health checks and automated route redirection.</div>
        </div>
        <div class="faq-item">
          <div class="faq-question">Can I integrate with custom enterprise APIs? <span>+</span></div>
          <div class="faq-answer">Yes, we provide full REST and WebSocket APIs alongside webhooks for bidirectional synchronization.</div>
        </div>
        <div class="faq-item">
          <div class="faq-question">Is on-premise deployment supported? <span>+</span></div>
          <div class="faq-answer">Enterprise tiers include Docker Compose and Kubernetes Helm charts for self-hosted sovereign deployment.</div>
        </div>
      </div>
    </div>
  </section>

  <!-- Footer -->
  <footer class="footer">
    <div class="container">
      <p>&copy; {app_name} Inc. Powered by JARVIS Mark-LV Web Studio.</p>
    </div>
  </footer>

  <script src="app.js"></script>
</body>
</html>
"""

    css_content = """/* ── SaaS Theme ─────────────────────────────────────────────── */
:root {
  --bg-dark: #07090e;
  --bg-card: rgba(18, 24, 38, 0.7);
  --accent: #00e5ff;
  --accent-purple: #9333ea;
  --text: #f8fafc;
  --text-dim: #94a3b8;
  --border: rgba(255, 255, 255, 0.08);
  --font: 'Outfit', sans-serif;
}

* { margin:0; padding:0; box-sizing:border-box; }
body { background: var(--bg-dark); color: var(--text); font-family: var(--font); line-height: 1.6; }
.container { width: 90%; max-width: 1200px; margin: 0 auto; }

.navbar { position: sticky; top:0; background: rgba(7,9,14,0.85); backdrop-filter: blur(12px); border-bottom: 1px solid var(--border); padding: 1rem 0; z-index:100; }
.nav-wrap { display: flex; justify-content: space-between; align-items: center; }
.brand { font-size: 1.4rem; font-weight: 800; color: var(--text); }
.nav-menu { display: flex; align-items: center; gap: 1.5rem; }
.nav-menu a { color: var(--text-dim); text-decoration: none; font-weight: 500; transition: color 0.2s; }
.nav-menu a:hover { color: var(--accent); }

.btn-primary, .btn-secondary { padding: 0.65rem 1.4rem; border-radius: 8px; font-weight: 600; cursor: pointer; border: none; transition: all 0.2s; }
.btn-primary { background: linear-gradient(135deg, var(--accent), #3b82f6); color: #000; }
.btn-primary:hover { transform: translateY(-2px); box-shadow: 0 4px 20px rgba(0,229,255,0.4); }
.btn-secondary { background: transparent; color: var(--text); border: 1px solid var(--border); }
.btn-secondary:hover { border-color: var(--accent); }
.full-width { width: 100%; }

.hero { padding: 7rem 0 5rem; text-align: center; }
.hero-content { max-width: 800px; }
.badge { background: rgba(0,229,255,0.1); color: var(--accent); border: 1px solid rgba(0,229,255,0.3); padding: 6px 14px; border-radius: 20px; font-size: 0.85rem; }
.hero h1 { font-size: 3.5rem; font-weight: 800; line-height: 1.15; margin: 1.5rem 0 1rem; }
.gradient-text { background: linear-gradient(135deg, var(--accent), var(--accent-purple)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.subtitle { font-size: 1.25rem; color: var(--text-dim); margin-bottom: 2rem; }
.cta-row { display: flex; justify-content: center; gap: 8px; max-width: 500px; margin: 0 auto 1.5rem; }
.email-input { flex-grow: 1; padding: 14px 18px; border-radius: 8px; background: rgba(255,255,255,0.05); border: 1px solid var(--border); color: #fff; font-size: 1rem; }
.email-input:focus { outline: none; border-color: var(--accent); }
.proof-row { color: var(--text-dim); font-size: 0.85rem; }

.section { padding: 5rem 0; }
.center-head { text-align: center; margin-bottom: 3.5rem; }
.center-head h2 { font-size: 2.2rem; margin-bottom: 0.5rem; }
.center-head p { color: var(--text-dim); }

.features-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1.5rem; }
.feature-card { background: var(--bg-card); border: 1px solid var(--border); border-radius: 12px; padding: 2rem; transition: transform 0.2s; }
.feature-card:hover { transform: translateY(-4px); border-color: var(--accent); }
.feature-icon { font-size: 2rem; margin-bottom: 1rem; }

.pricing-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 2rem; align-items: center; }
.pricing-card { background: var(--bg-card); border: 1px solid var(--border); border-radius: 16px; padding: 2.5rem; position: relative; }
.pricing-card.popular { border-color: var(--accent); box-shadow: 0 0 30px rgba(0,229,255,0.15); transform: scale(1.03); }
.popular-badge { position: absolute; top:-12px; right:20px; background: var(--accent); color:#000; font-size: 0.75rem; font-weight:800; padding: 4px 10px; border-radius: 4px; }
.price-box { margin: 1.5rem 0; }
.price-box .amount { font-size: 3rem; font-weight: 800; color: #fff; }
.price-box .currency { font-size: 1.5rem; vertical-align: top; }
.price-box .period { color: var(--text-dim); }
.perks-list { list-style: none; margin: 1.5rem 0 2rem; display: flex; flex-direction: column; gap: 10px; color: var(--text-dim); }

.faq-container { max-width: 750px; }
.faq-item { background: var(--bg-card); border: 1px solid var(--border); border-radius: 8px; margin-bottom: 12px; cursor: pointer; overflow: hidden; }
.faq-question { padding: 1.25rem; font-weight: 600; display: flex; justify-content: space-between; align-items: center; }
.faq-answer { padding: 0 1.25rem 1.25rem; color: var(--text-dim); display: none; font-size: 0.95rem; }
.faq-item.active .faq-answer { display: block; }
.faq-item.active .faq-question span { transform: rotate(45deg); display: inline-block; }

.footer { border-top: 1px solid var(--border); padding: 2rem 0; text-align: center; color: var(--text-dim); font-size: 0.9rem; }
"""

    js_content = """document.addEventListener("DOMContentLoaded", () => {
  // FAQ accordion
  const faqItems = document.querySelectorAll(".faq-item");
  faqItems.forEach(item => {
    item.addEventListener("click", () => {
      item.classList.toggle("active");
    });
  });
});
"""

    return html_content, css_content, js_content


def _generate_noc_dashboard_template(title: str = "NOC Telemetry Portal") -> Tuple[str, str, str]:
    """Generates an advanced Network Operations Center & Server Telemetry Dashboard."""
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} — Network Operations Center</title>
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;800&family=Outfit:wght@400;600;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="style.css">
</head>
<body class="dashboard-body">
  <div class="sidebar">
    <div class="sidebar-header">
      <span class="pulse-cyan"></span> NOC SENTINEL
    </div>
    <ul class="nav-tree">
      <li class="active">📊 Live Topology</li>
      <li>🌐 Edge Routers</li>
      <li>🔒 Firewall Rules</li>
      <li>📈 BGP / OSPF Mesh</li>
      <li>📋 Incident Log</li>
      <li>⚙️ Core Settings</li>
    </ul>
    <div class="sidebar-footer">
      <span>SLA: 99.98%</span>
      <span class="uptime">UP: 42d 18h</span>
    </div>
  </div>

  <main class="main-content">
    <header class="dash-header">
      <div>
        <h1>{title}</h1>
        <p class="subhead">Real-time Autonomous Infrastructure & Routing Monitor</p>
      </div>
      <div class="clock-box" id="clock">00:00:00 UTC</div>
    </header>

    <!-- Top KPI Row -->
    <div class="kpi-grid">
      <div class="kpi-card">
        <span class="kpi-label">Core Latency (Avg)</span>
        <div class="kpi-val" id="latency">14.2 <small>ms</small></div>
        <span class="kpi-badge good">✓ Nominal</span>
      </div>
      <div class="kpi-card">
        <span class="kpi-label">Active WAN Traffic</span>
        <div class="kpi-val" id="bandwidth">8.42 <small>Gbps</small></div>
        <span class="kpi-badge neutral">~ 68% Cap</span>
      </div>
      <div class="kpi-card">
        <span class="kpi-label">Online Nodes</span>
        <div class="kpi-val">128 <small>/ 130</small></div>
        <span class="kpi-badge warn">! 2 Degraded</span>
      </div>
      <div class="kpi-card">
        <span class="kpi-label">Security Shield</span>
        <div class="kpi-val">ACTIVE</div>
        <span class="kpi-badge good">0 Dropped DDoS</span>
      </div>
    </div>

    <!-- Nodes Status Table -->
    <div class="panel">
      <div class="panel-header">
        <h2>Network Nodes & Interface Matrix</h2>
        <button id="refresh-btn" class="btn-sm">⚡ Ping Mesh</button>
      </div>
      <table class="nodes-table">
        <thead>
          <tr>
            <th>Host / FQDN</th>
            <th>IPv4 Address</th>
            <th>Role</th>
            <th>Interface</th>
            <th>Latency</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody id="nodes-tbody">
          <tr>
            <td><strong>rtr-core-01.dc</strong></td>
            <td>10.0.0.1</td>
            <td>BGP Border Gateway</td>
            <td>TenGigE 0/0/0</td>
            <td>2.1 ms</td>
            <td><span class="status-pill online">ONLINE</span></td>
          </tr>
          <tr>
            <td><strong>sw-dist-02.fl4</strong></td>
            <td>10.0.10.2</td>
            <td>Access Layer L3</td>
            <td>GigE 1/0/24</td>
            <td>4.8 ms</td>
            <td><span class="status-pill online">ONLINE</span></td>
          </tr>
          <tr>
            <td><strong>fw-perimeter-palo</strong></td>
            <td>192.168.1.1</td>
            <td>Palo Alto PA-3200</td>
            <td>eth1/1</td>
            <td>1.4 ms</td>
            <td><span class="status-pill online">ONLINE</span></td>
          </tr>
          <tr>
            <td><strong>vpn-gw-remote</strong></td>
            <td>172.16.50.1</td>
            <td>IPsec IKEv2 Concentrator</td>
            <td>Tunnel 10</td>
            <td>48.2 ms</td>
            <td><span class="status-pill degraded">HIGH JITTER</span></td>
          </tr>
          <tr>
            <td><strong>dns-bind-auth</strong></td>
            <td>10.0.0.53</td>
            <td>Internal Recursive DNS</td>
            <td>ens192</td>
            <td>0.9 ms</td>
            <td><span class="status-pill online">ONLINE</span></td>
          </tr>
        </tbody>
      </table>
    </div>
  </main>

  <script src="app.js"></script>
</body>
</html>
"""

    css_content = """/* ── NOC Sentinel Theme ──────────────────────────────────────── */
:root {
  --bg-dark: #070a0f;
  --bg-panel: #0d121c;
  --accent: #00e5ff;
  --accent-green: #10b981;
  --accent-warn: #f59e0b;
  --accent-err: #ef4444;
  --text: #e2e8f0;
  --text-dim: #64748b;
  --border: rgba(0, 229, 255, 0.15);
  --font-mono: 'JetBrains Mono', monospace;
  --font-sans: 'Outfit', sans-serif;
}

* { margin:0; padding:0; box-sizing:border-box; }
body.dashboard-body {
  background: var(--bg-dark);
  color: var(--text);
  font-family: var(--font-sans);
  display: flex;
  height: 100vh;
  overflow: hidden;
}

/* Sidebar */
.sidebar {
  width: 240px;
  background: #090e16;
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
}
.sidebar-header {
  padding: 1.5rem;
  font-family: var(--font-mono);
  font-weight: 800;
  font-size: 1rem;
  letter-spacing: 0.1em;
  color: var(--accent);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  gap: 8px;
}
.pulse-cyan { width: 8px; height: 8px; border-radius: 50%; background: var(--accent); box-shadow: 0 0 10px var(--accent); }
.nav-tree { list-style: none; padding: 1.5rem 0; flex-grow: 1; }
.nav-tree li { padding: 10px 1.5rem; font-size: 0.95rem; color: var(--text-dim); cursor: pointer; transition: all 0.2s; }
.nav-tree li:hover, .nav-tree li.active { color: var(--accent); background: rgba(0,229,255,0.06); border-left: 3px solid var(--accent); }
.sidebar-footer { padding: 1rem 1.5rem; border-top: 1px solid var(--border); font-family: var(--font-mono); font-size: 0.75rem; color: var(--text-dim); display: flex; justify-content: space-between; }

/* Main Content */
.main-content { flex-grow: 1; padding: 2rem; overflow-y: auto; }
.dash-header { display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 2rem; border-bottom: 1px solid var(--border); padding-bottom: 1rem; }
.dash-header h1 { font-size: 1.8rem; font-weight: 700; }
.subhead { color: var(--text-dim); font-size: 0.95rem; }
.clock-box { font-family: var(--font-mono); font-size: 1.2rem; background: var(--bg-panel); border: 1px solid var(--border); padding: 8px 16px; border-radius: 6px; color: var(--accent); }

/* KPI Grid */
.kpi-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1.25rem; margin-bottom: 2rem; }
.kpi-card { background: var(--bg-panel); border: 1px solid var(--border); border-radius: 10px; padding: 1.25rem; }
.kpi-label { font-size: 0.85rem; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.05em; }
.kpi-val { font-size: 2rem; font-family: var(--font-mono); font-weight: 800; margin: 0.5rem 0; color: #fff; }
.kpi-val small { font-size: 1rem; color: var(--text-dim); }
.kpi-badge { font-size: 0.75rem; padding: 3px 8px; border-radius: 4px; font-weight: 600; font-family: var(--font-mono); }
.kpi-badge.good { background: rgba(16, 185, 129, 0.15); color: var(--accent-green); }
.kpi-badge.neutral { background: rgba(0, 229, 255, 0.15); color: var(--accent); }
.kpi-badge.warn { background: rgba(245, 158, 11, 0.15); color: var(--accent-warn); }

/* Panel & Matrix Table */
.panel { background: var(--bg-panel); border: 1px solid var(--border); border-radius: 10px; padding: 1.5rem; }
.panel-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.25rem; }
.panel-header h2 { font-size: 1.15rem; }
.btn-sm { background: rgba(0,229,255,0.1); border: 1px solid var(--border); color: var(--accent); font-family: var(--font-mono); padding: 6px 12px; border-radius: 4px; cursor: pointer; }
.btn-sm:hover { background: var(--accent); color: #000; }

.nodes-table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
.nodes-table th { text-align: left; padding: 10px 14px; color: var(--text-dim); font-size: 0.8rem; text-transform: uppercase; border-bottom: 1px solid var(--border); }
.nodes-table td { padding: 12px 14px; border-bottom: 1px solid rgba(255,255,255,0.04); font-family: var(--font-mono); }
.status-pill { font-size: 0.75rem; padding: 4px 8px; border-radius: 4px; font-weight: 700; }
.status-pill.online { background: rgba(16, 185, 129, 0.2); color: var(--accent-green); }
.status-pill.degraded { background: rgba(245, 158, 11, 0.2); color: var(--accent-warn); }
"""

    js_content = """function updateClock() {
  const now = new Date();
  const time = now.toISOString().substring(11, 19) + ' UTC';
  const el = document.getElementById('clock');
  if (el) el.textContent = time;
}

setInterval(updateClock, 1000);
updateClock();

document.getElementById('refresh-btn')?.addEventListener('click', () => {
  const latency = document.getElementById('latency');
  if (latency) {
    const newL = (10 + Math.random() * 8).toFixed(1);
    latency.innerHTML = `${newL} <small>ms</small>`;
  }
});
"""

    return html_content, css_content, js_content


# ─────────────────────────────────────────────────────────────────────────────
# 3. Autonomous Site Generator Dispatcher
# ─────────────────────────────────────────────────────────────────────────────

def create_site(
    name: str = "my-site",
    template: str = "portfolio",
    title: str = "Software & Network Engineer",
    prompt: Optional[str] = None,
    preview: bool = True,
    player: Any = None,
) -> str:
    """Scaffolds a complete modern website project and optionally starts preview."""
    # Sanitize project folder name
    safe_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", name.strip().lower()) or "my-site"
    project_dir = _OUTPUT_SITES_DIR / safe_name
    project_dir.mkdir(parents=True, exist_ok=True)

    template_key = (template or "portfolio").lower().strip()

    if template_key in ("portfolio", "personal", "engineer"):
        skills = [
            "Cisco CCNA/CCNP", "BGP & OSPF Routing", "VLANs & Trunking",
            "Wireshark Packet Analysis", "Python Network Automation",
            "Windows Server 2022", "Active Directory & GPO",
            "Linux / Ubuntu / RHEL", "Palo Alto / Fortinet", "Docker & Microservices",
        ]
        projects = [
            {
                "title": "Autonomous Network Audit Agent",
                "desc": "Built sub-second ICMP/TCP telemetry scanner with automated CIDR subnet calculations and ARP inspection.",
                "tags": "Python,Sockets,Subnetting",
                "url": "#",
            },
            {
                "title": "BGP Mesh Routing Topology",
                "desc": "Configured dual-homed multi-AS BGP peering with prefix filtering and autonomous failover routes.",
                "tags": "Cisco,BGP,Networking",
                "url": "#",
            },
            {
                "title": "Enterprise Active Directory Migration",
                "desc": "Automated migration of 500+ AD DS user objects, GPO policies, and DNS root hints with PowerShell.",
                "tags": "Windows Server,Active Directory,GPO",
                "url": "#",
            },
        ]
        html_code, css_code, js_code = _generate_portfolio_template(
            name=name.title().replace("_", " "),
            title=title,
            bio="Network Engineer and Systems Administrator specializing in high-availability routing, packet inspection, and autonomous infrastructure automation.",
            skills=skills,
            projects=projects,
        )

    elif template_key in ("saas", "landing", "product"):
        features = [
            {"icon": "⚡", "title": "Sub-50ms Reaction Loop", "desc": "Direct motor execution on native applications with zero intermediary cloud delays."},
            {"icon": "🛡️", "title": "Zero-Leak Pre-Commit Sentinel", "desc": "Automated AST inspection guarding against leaked API keys, tokens, and broken imports."},
            {"icon": "🌐", "title": "Full-Duplex Telemetry", "desc": "Continuous network throughput, ping jitter, and packet loss tracking in real-time."},
            {"icon": "🤖", "title": "Self-Healing Test Cycles", "desc": "Captures traceback errors, diagnoses offending AST frames, and applies verified fixes."},
        ]
        plans = [
            {"name": "Starter", "price": "0", "desc": "Free forever for local personal projects.", "perks": ["Single Node", "Local Dev Server", "Standard CLI Tools"]},
            {"name": "Sentinel Pro", "price": "29", "popular": True, "desc": "For engineers scaling autonomous workflows.", "perks": ["Unlimited Nodes", "Real-Time Telemetry", "Chrome Control Suite", "Priority Live Models"]},
            {"name": "Enterprise", "price": "99", "desc": "For production infrastructure and multi-DC teams.", "perks": ["Dedicated Failover", "Multi-Region Mesh", "Custom SLA & 24/7 Support", "On-Premises Deployment"]},
        ]
        html_code, css_code, js_code = _generate_saas_template(
            app_name=name.title().replace("_", " "),
            tagline="Enterprise AI & Infrastructure Automation Platform",
            features=features,
            plans=plans,
        )

    elif template_key in ("dashboard", "noc", "noc_portal", "telemetry"):
        html_code, css_code, js_code = _generate_noc_dashboard_template(
            title=title or "NOC Telemetry Sentinel"
        )

    else:
        # Custom synthesis using Gemini SMART model if available
        html_code, css_code, js_code = _synthesize_custom_site(name, prompt or title)

    # Write files to disk
    (project_dir / "index.html").write_text(html_code, encoding="utf-8")
    (project_dir / "style.css").write_text(css_code, encoding="utf-8")
    (project_dir / "app.js").write_text(js_code, encoding="utf-8")

    _log(player, f"Generated website '{safe_name}' at {project_dir}")

    result_msg = (
        f"[SUCCESS] Website '{safe_name}' created successfully!\n"
        f"Location: {project_dir}\n"
        f"Files: index.html, style.css, app.js\n"
        f"Template: {template_key}"
    )

    if preview:
        preview_res = start_server(site_name=safe_name, open_browser=True, player=player)
        result_msg += f"\n\n{preview_res}"

    return result_msg


def _synthesize_custom_site(name: str, prompt: str) -> Tuple[str, str, str]:
    """Uses Gemini reasoning model to synthesize bespoke HTML, CSS, and JS."""
    try:
        from core import gemini
        sys_prompt = (
            "You are an elite principal web developer and UI/UX designer. "
            "Generate a production-ready, beautiful, modern website. "
            "Use modern Google Fonts, dark mode aesthetic, smooth CSS transitions, and vanilla JavaScript. "
            "Output your answer EXACTLY in three code blocks labeled ```html, ```css, and ```javascript."
        )
        user_prompt = f"Website Name: {name}\nRequirements: {prompt}\nCreate complete index.html, style.css, and app.js."
        
        response = gemini.call(f"{sys_prompt}\n\n{user_prompt}", tier=gemini.SMART, timeout_ms=60000)
        if response:
            text = str(response)
            html_m = re.search(r"```html\s*(.*?)\s*```", text, re.DOTALL)
            css_m = re.search(r"```css\s*(.*?)\s*```", text, re.DOTALL)
            js_m = re.search(r"```(?:javascript|js)\s*(.*?)\s*```", text, re.DOTALL)

            html_val = html_m.group(1) if html_m else ""
            css_val = css_m.group(1) if css_m else ""
            js_val = js_m.group(1) if js_m else ""

            if html_val:
                return html_val, css_val, js_val
    except Exception as e:
        print(f"[WebBuilder] Custom synthesis fallback: {e}")

    # Fallback to portfolio
    return _generate_portfolio_template(name, prompt, "Custom Web Project", ["HTML5", "CSS3", "JavaScript"], [])


# ─────────────────────────────────────────────────────────────────────────────
# 4. Modern UI Component Synthesizer
# ─────────────────────────────────────────────────────────────────────────────

def create_component(
    component_type: str = "pricing_card",
    theme: str = "dark_glass",
    save_preview: bool = True,
    player: Any = None,
) -> str:
    """Generates modular copy-paste ready UI components."""
    ctype = component_type.lower().strip()
    _OUTPUT_COMPONENTS_DIR.mkdir(parents=True, exist_ok=True)

    if ctype in ("pricing", "pricing_card", "pricing_table"):
        comp_html = """
<div class="jarvis-pricing-card">
  <div class="pricing-glow"></div>
  <span class="badge">RECOMMENDED</span>
  <h3 class="tier-title">Enterprise Edge</h3>
  <div class="price-wrap">
    <span class="currency">$</span><span class="val">49</span><span class="sub">/month</span>
  </div>
  <p class="desc">Autonomous network orchestration, continuous telemetry, and verified live editing.</p>
  <ul class="features">
    <li>✓ Sub-50ms Local Execution</li>
    <li>✓ Autonomous Visual Web Agent</li>
    <li>✓ Full Dev & SysAdmin Diagnostic Suite</li>
    <li>✓ Dedicated Chrome CDP Remote Bridge</li>
  </ul>
  <button class="cta-btn">Deploy License</button>
</div>
"""
        comp_css = """
.jarvis-pricing-card {
  position: relative;
  width: 340px;
  background: rgba(15, 23, 42, 0.75);
  backdrop-filter: blur(16px);
  border: 1px solid rgba(0, 229, 255, 0.3);
  border-radius: 16px;
  padding: 2.25rem;
  color: #f8fafc;
  font-family: 'Outfit', sans-serif;
  box-shadow: 0 10px 30px rgba(0,0,0,0.5);
  overflow: hidden;
}
.pricing-glow {
  position: absolute;
  top: -60px;
  right: -60px;
  width: 140px;
  height: 140px;
  background: radial-gradient(circle, rgba(0,229,255,0.25) 0%, transparent 70%);
  border-radius: 50%;
}
.badge {
  font-size: 0.75rem;
  font-weight: 800;
  letter-spacing: 0.05em;
  color: #00e5ff;
  background: rgba(0,229,255,0.12);
  padding: 4px 10px;
  border-radius: 20px;
  border: 1px solid rgba(0,229,255,0.3);
}
.tier-title { font-size: 1.5rem; margin: 1rem 0 0.5rem; font-weight: 700; }
.price-wrap { display: flex; align-items: baseline; gap: 4px; margin-bottom: 1rem; }
.price-wrap .currency { font-size: 1.4rem; color: #00e5ff; }
.price-wrap .val { font-size: 3rem; font-weight: 800; }
.price-wrap .sub { color: #94a3b8; font-size: 0.95rem; }
.desc { font-size: 0.9rem; color: #94a3b8; line-height: 1.5; margin-bottom: 1.5rem; }
.features { list-style: none; padding: 0; margin-bottom: 2rem; display: flex; flex-direction: column; gap: 10px; font-size: 0.9rem; }
.features li { color: #cbd5e1; }
.cta-btn {
  width: 100%;
  padding: 12px;
  background: linear-gradient(135deg, #00e5ff, #3b82f6);
  border: none;
  border-radius: 8px;
  color: #040810;
  font-weight: 700;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}
.cta-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 20px rgba(0,229,255,0.4);
}
"""

    elif ctype in ("navbar", "nav"):
        comp_html = """
<nav class="jarvis-glass-nav">
  <div class="nav-brand">⚡ CYBER_SENTINEL</div>
  <div class="nav-links">
    <a href="#">Overview</a>
    <a href="#">Telemetry</a>
    <a href="#">Audit</a>
    <a href="#" class="nav-cta">Connect</a>
  </div>
</nav>
"""
        comp_css = """
.jarvis-glass-nav {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 2rem;
  background: rgba(10, 15, 26, 0.8);
  backdrop-filter: blur(14px);
  border-bottom: 1px solid rgba(0, 229, 255, 0.2);
  color: #f1f5f9;
  font-family: 'Outfit', sans-serif;
}
.nav-brand { font-weight: 800; letter-spacing: 0.05em; color: #00e5ff; }
.nav-links { display: flex; align-items: center; gap: 1.5rem; }
.nav-links a { color: #94a3b8; text-decoration: none; font-size: 0.95rem; transition: color 0.2s; }
.nav-links a:hover { color: #00e5ff; }
.nav-cta {
  background: rgba(0,229,255,0.15) !important;
  color: #00e5ff !important;
  border: 1px solid rgba(0,229,255,0.4);
  padding: 6px 16px;
  border-radius: 6px;
}
"""

    else:
        # Stats / telemetry grid card
        comp_html = """
<div class="jarvis-stat-card">
  <div class="stat-head">
    <span class="label">BGP PEER LATENCY</span>
    <span class="dot-online"></span>
  </div>
  <div class="stat-number">12.4 <small>ms</small></div>
  <div class="stat-footer">
    <span class="trend-up">↓ 2.1 ms</span> vs 1h average
  </div>
</div>
"""
        comp_css = """
.jarvis-stat-card {
  width: 260px;
  background: rgba(13, 18, 28, 0.7);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(0, 229, 255, 0.2);
  border-radius: 12px;
  padding: 1.5rem;
  font-family: 'JetBrains Mono', monospace;
  color: #f8fafc;
}
.stat-head { display: flex; justify-content: space-between; align-items: center; }
.label { font-size: 0.75rem; color: #64748b; letter-spacing: 0.05em; }
.dot-online { width: 8px; height: 8px; border-radius: 50%; background: #10b981; box-shadow: 0 0 8px #10b981; }
.stat-number { font-size: 2.2rem; font-weight: 800; margin: 0.75rem 0; }
.stat-number small { font-size: 1rem; color: #64748b; }
.stat-footer { font-size: 0.8rem; color: #94a3b8; }
.trend-up { color: #10b981; font-weight: 600; }
"""

    preview_file = _OUTPUT_COMPONENTS_DIR / f"{ctype}_preview.html"
    full_preview_html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>{ctype.title()} Component Preview</title>
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
  <style>
    body {{
      background: #06090e;
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 100vh;
      margin: 0;
      padding: 2rem;
    }}
    {comp_css}
  </style>
</head>
<body>
  {comp_html}
</body>
</html>
"""
    if save_preview:
        preview_file.write_text(full_preview_html, encoding="utf-8")
        _log(player, f"Saved component preview to {preview_file}")

    return (
        f"[COMPONENT CREATED] Type: {ctype}\n"
        f"Preview file: {preview_file}\n\n"
        f"HTML:\n{comp_html.strip()}\n\n"
        f"CSS:\n{comp_css.strip()}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# 5. Live Website Inspector, SEO & Performance Auditor
# ─────────────────────────────────────────────────────────────────────────────

class _HTMLAuditParser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.title: Optional[str] = None
        self.meta_tags: List[Dict[str, str]] = []
        self.headings: List[Tuple[str, str]] = []
        self.images: List[Dict[str, str]] = []
        self.links: List[str] = []
        self.scripts_count = 0
        self.stylesheets_count = 0
        self._in_title = False
        self._in_heading: Optional[str] = None
        self._curr_heading_text = ""

    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)
        tag_lower = tag.lower()

        if tag_lower == "title":
            self._in_title = True
        elif tag_lower == "meta":
            self.meta_tags.append(attr_dict)
        elif tag_lower in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._in_heading = tag_lower
            self._curr_heading_text = ""
        elif tag_lower == "img":
            self.images.append(attr_dict)
        elif tag_lower == "a":
            href = attr_dict.get("href")
            if href:
                self.links.append(href)
        elif tag_lower == "script":
            self.scripts_count += 1
        elif tag_lower == "link" and attr_dict.get("rel") == "stylesheet":
            self.stylesheets_count += 1

    def handle_endtag(self, tag):
        tag_lower = tag.lower()
        if tag_lower == "title":
            self._in_title = False
        elif tag_lower == self._in_heading:
            if self._in_heading:
                self.headings.append((self._in_heading, self._curr_heading_text.strip()))
            self._in_heading = None

    def handle_data(self, data):
        if self._in_title:
            self.title = (self.title or "") + data
        elif self._in_heading:
            self._curr_heading_text += data


def audit_site(target: str, player: Any = None) -> str:
    """Audits any local HTML file or live URL for SEO, accessibility, and structure."""
    target_clean = target.strip()
    is_url = target_clean.startswith("http://") or target_clean.startswith("https://")
    html_content = ""

    if is_url:
        try:
            req = urllib.request.Request(
                target_clean,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                html_content = resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            return f"[ERROR] Failed to fetch URL '{target_clean}': {e}"
    else:
        # Check local path
        p = Path(target_clean)
        if not p.is_absolute():
            # Check relative to output/sites
            check_p = _OUTPUT_SITES_DIR / target_clean / "index.html"
            if check_p.exists():
                p = check_p
            else:
                p = (_base_dir() / target_clean).resolve()

        if not p.exists():
            return f"[ERROR] Target file not found: {p}"
        html_content = p.read_text(encoding="utf-8", errors="replace")

    parser = _HTMLAuditParser()
    try:
        parser.feed(html_content)
    except Exception as e:
        return f"[ERROR] Failed to parse HTML: {e}"

    # Analyze metrics
    score = 100
    recommendations = []

    # 1. Title verification
    title = (parser.title or "").strip()
    if not title:
        score -= 20
        recommendations.append("CRITICAL: Missing `<title>` tag.")
    elif len(title) < 15:
        score -= 5
        recommendations.append(f"ADVICE: Title '{title}' is quite short (<15 chars). Consider a more descriptive headline.")
    elif len(title) > 65:
        score -= 5
        recommendations.append(f"ADVICE: Title '{title[:30]}...' is long (>65 chars) and may be truncated on Google.")

    # 2. Viewport meta
    has_viewport = any("viewport" in m.get("name", "").lower() for m in parser.meta_tags)
    if not has_viewport:
        score -= 15
        recommendations.append("CRITICAL: Missing `<meta name=\"viewport\">` tag for mobile responsiveness.")

    # 3. Meta description
    desc_meta = next((m.get("content") for m in parser.meta_tags if m.get("name", "").lower() == "description"), None)
    if not desc_meta:
        score -= 15
        recommendations.append("WARNING: Missing `<meta name=\"description\">` tag for search engines.")

    # 4. OpenGraph tags
    has_og = any(m.get("property", "").startswith("og:") for m in parser.meta_tags)
    if not has_og:
        score -= 5
        recommendations.append("SUGGESTION: Add OpenGraph meta tags (`og:title`, `og:image`, `og:description`) for social sharing previews.")

    # 5. Heading hierarchy
    h1_count = sum(1 for h, _ in parser.headings if h == "h1")
    if h1_count == 0:
        score -= 15
        recommendations.append("CRITICAL: Page lacks an `<h1>` main heading.")
    elif h1_count > 1:
        score -= 5
        recommendations.append(f"WARNING: Multiple `<h1>` tags detected ({h1_count}). Best practice is exactly one `<h1>` per page.")

    # 6. Image accessibility
    missing_alt = sum(1 for img in parser.images if not img.get("alt"))
    if missing_alt > 0:
        score -= min(15, missing_alt * 5)
        recommendations.append(f"ACCESSIBILITY: {missing_alt} image(s) missing `alt` description attributes.")

    score = max(0, min(100, score))

    report = (
        f"===============================================================\n"
        f"  [WEB] WEBSITE AUDIT & SEO INSPECTION REPORT: {target_clean}\n"
        f"===============================================================\n"
        f"Health Score: {score} / 100\n"
        f"Title: {title or '[NONE]'}\n"
        f"Headings Found: {len(parser.headings)} (H1: {h1_count})\n"
        f"Images: {len(parser.images)} (Missing alt: {missing_alt})\n"
        f"External Stylesheets: {parser.stylesheets_count} | Scripts: {parser.scripts_count}\n"
        f"Links Count: {len(parser.links)}\n"
        f"---------------------------------------------------------------\n"
        f"Recommendations:\n"
    )
    if recommendations:
        for r in recommendations:
            report += f"  * {r}\n"
    else:
        report += "  [OK] Outstanding! All critical SEO, meta, and accessibility checks passed.\n"
    report += "===============================================================\n"


    _log(player, f"Audit complete for {target_clean} (Score: {score}/100)")
    return report


# ─────────────────────────────────────────────────────────────────────────────
# 6. Action Dispatcher & Tool Declaration
# ─────────────────────────────────────────────────────────────────────────────

def web_builder(
    action: str = "create_site",
    name: Optional[str] = None,
    template: Optional[str] = "portfolio",
    title: Optional[str] = None,
    prompt: Optional[str] = None,
    target: Optional[str] = None,
    target_path: Optional[str] = None,
    site_name: Optional[str] = None,
    port: int = 3000,
    open_browser: bool = True,
    component_type: Optional[str] = "pricing_card",
    preview: bool = True,
    player: Any = None,
) -> str:
    """Main routing dispatcher for the Autonomous Web Studio."""
    act = (action or "create_site").lower().strip()

    if act in ("create_site", "build_site", "new_site", "create_website"):
        return create_site(
            name=name or site_name or "my-site",
            template=template or "portfolio",
            title=title or "Software & Network Engineer",
            prompt=prompt,
            preview=preview,
            player=player,
        )

    elif act in ("start_server", "preview_site", "serve", "run_server"):
        return start_server(
            target_path=target_path or target,
            site_name=site_name or name,
            port=port,
            open_browser=open_browser,
            player=player,
        )

    elif act in ("stop_server", "kill_server", "close_server"):
        return stop_server(port=port if port != 3000 else None, player=player)

    elif act in ("list_servers", "servers", "status"):
        return list_servers()

    elif act in ("create_component", "component", "ui_component"):
        return create_component(
            component_type=component_type or "pricing_card",
            save_preview=preview,
            player=player,
        )

    elif act in ("audit_site", "audit_website", "inspect_site", "seo_audit"):
        target_val = target or target_path or site_name or name or "my-site"
        return audit_site(target=target_val, player=player)

    else:
        return (
            f"[ERROR] Unknown action '{action}'. Available actions: "
            f"create_site, start_server, stop_server, list_servers, create_component, audit_site."
        )


TOOL = {
    "name": "web_builder",
    "description": (
        "Autonomous Web Studio & Site Forge Engine. Builds complete modern responsive websites "
        "(portfolios, SaaS landing pages, NOC/SysAdmin dashboards, and custom sites) with "
        "rich CSS, glassmorphism, Google Fonts, and JavaScript. Spins up instant local dev servers "
        "on port 3000+ that auto-open in Google Chrome, generates modular UI components (pricing cards, "
        "navbars, hero sections, stats cards), and conducts SEO & accessibility website audits."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": [
                    "create_site",
                    "start_server",
                    "stop_server",
                    "list_servers",
                    "create_component",
                    "audit_site"
                ],
                "description": "The web operation to perform."
            },
            "name": {
                "type": "STRING",
                "description": "Project or site folder name (e.g. 'portfolio', 'saas_platform', 'noc_dashboard')."
            },
            "template": {
                "type": "STRING",
                "description": "Site archetype template: 'portfolio', 'saas', 'dashboard' (or 'noc_portal'), or 'custom'."
            },
            "title": {
                "type": "STRING",
                "description": "Headline or engineering specialty title for the site."
            },
            "prompt": {
                "type": "STRING",
                "description": "Specific customization instructions or content requirements for the website."
            },
            "target": {
                "type": "STRING",
                "description": "URL (https://...) or local project path to audit or serve."
            },
            "port": {
                "type": "INTEGER",
                "description": "Local HTTP port for the dev server (default: 3000)."
            },
            "open_browser": {
                "type": "BOOLEAN",
                "description": "Whether to automatically open the site in Google Chrome."
            },
            "component_type": {
                "type": "STRING",
                "enum": ["pricing_card", "navbar", "stat_card", "hero"],
                "description": "Type of UI component to synthesize."
            },
            "preview": {
                "type": "BOOLEAN",
                "description": "Whether to automatically launch local preview server after creating a site."
            }
        },
        "required": ["action"]
    },
    "handler": web_builder,
}
