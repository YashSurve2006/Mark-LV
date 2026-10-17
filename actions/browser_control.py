
from __future__ import annotations

import asyncio
import concurrent.futures
import json
import os
import platform
import shutil
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path
from typing import Optional

for _stream in ("stdout", "stderr"):
    try:
        _s = getattr(sys, _stream, None)
        if _s is not None and hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from playwright.async_api import (
    async_playwright,
    BrowserContext,
    Page,
    Playwright,
    TimeoutError as PlaywrightTimeout,
)
_OS = platform.system()   # "Windows" | "Darwin" | "Linux"

_ALIASES: dict[str, str] = {
    "google chrome":   "chrome",
    "google-chrome":   "chrome",
    "microsoft edge":  "edge",
    "ms edge":         "edge",
    "msedge":          "edge",
    "mozilla firefox": "firefox",
    "opera gx":        "operagx",
    "opera_gx":        "operagx",
}

try:
    import psutil
    _PSUTIL = True
except ImportError:
    _PSUTIL = False


def _is_browser_process_running(browser: str) -> bool:
    if not _PSUTIL:
        return False
    try:
        name = _ALIASES.get(browser.lower().strip(), browser.lower().strip())
        patterns = {
            "chrome": ["chrome.exe", "google-chrome", "chrome"],
            "edge": ["msedge.exe", "microsoft-edge", "msedge"],
            "firefox": ["firefox.exe", "firefox"],
            "opera": ["opera.exe", "opera"],
            "operagx": ["opera.exe", "opera_gx"],
            "brave": ["brave.exe", "brave"],
            "vivaldi": ["vivaldi.exe", "vivaldi"],
        }
        pats = patterns.get(name, [f"{name}.exe", name])
        for p in psutil.process_iter(['name']):
            p_name = (p.info['name'] or '').lower()
            if any(pat == p_name or p_name.startswith(pat) for pat in pats):
                return True
    except Exception:
        pass
    return False


def _normalize_url(url: str) -> str:
    """
    Bare words like "instagram" → "https://instagram.com"
    Domains like "instagram.com" → "https://instagram.com"
    Full URLs pass through unchanged.
    """
    url = url.strip()
    if not url:
        return "about:blank"
    if "://" in url:
        return url
    # No dot at all → assume .com  (e.g. "instagram" → "instagram.com")
    if "." not in url:
        url = url + ".com"
    return "https://" + url


def _user_agent() -> str:
    if _OS == "Windows":
        return (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    if _OS == "Darwin":
        return (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    return (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )


def _real_profile_dir(browser: str) -> str:
    home  = Path.home()
    local = os.environ.get("LOCALAPPDATA", "")
    roam  = os.environ.get("APPDATA", "")

    candidates: list[Path] = []

    if _OS == "Windows":
        m = {
            "chrome":   [Path(local) / "Google"          / "Chrome"          / "User Data"],
            "edge":     [Path(local) / "Microsoft"        / "Edge"            / "User Data"],
            "brave":    [Path(local) / "BraveSoftware"    / "Brave-Browser"   / "User Data"],
            "vivaldi":  [Path(local) / "Vivaldi"          / "User Data"],
            "opera":    [Path(roam)  / "Opera Software"   / "Opera Stable",
                         Path(local) / "Opera Software"   / "Opera Stable"],
            "operagx":  [Path(roam)  / "Opera Software"   / "Opera GX Stable",
                         Path(local) / "Opera Software"   / "Opera GX Stable"],
        }
        candidates = m.get(browser, [])

    elif _OS == "Darwin":
        lib = home / "Library" / "Application Support"
        m = {
            "chrome":   [lib / "Google"             / "Chrome"],
            "edge":     [lib / "Microsoft Edge"],
            "brave":    [lib / "BraveSoftware"       / "Brave-Browser"],
            "vivaldi":  [lib / "Vivaldi"],
            "opera":    [lib / "com.operasoftware.Opera"],
            "operagx":  [lib / "com.operasoftware.OperaGX"],
        }
        candidates = m.get(browser, [])

    elif _OS == "Linux":
        cfg = home / ".config"
        m = {
            "chrome":   [cfg / "google-chrome", cfg / "chromium"],
            "edge":     [cfg / "microsoft-edge"],
            "brave":    [cfg / "BraveSoftware" / "Brave-Browser"],
            "vivaldi":  [cfg / "vivaldi"],
            "opera":    [cfg / "opera"],
            "operagx":  [cfg / "opera-gx"],
        }
        candidates = m.get(browser, [])

    for p in candidates:
        if p.exists():
            print(f"[Browser] ✅ Real profile found for {browser}: {p}")
            return str(p)

    fallback = home / ".jarvis_profiles" / browser
    fallback.mkdir(parents=True, exist_ok=True)
    print(f"[Browser] ⚠️  Real profile not found for {browser}, using: {fallback}")
    return str(fallback)

def _firefox_profile_dir() -> Optional[str]:
    home = Path.home()

    if _OS == "Windows":
        base = Path(os.environ.get("APPDATA", "")) / "Mozilla" / "Firefox"
    elif _OS == "Darwin":
        base = home / "Library" / "Application Support" / "Firefox"
    else:
        base = home / ".mozilla" / "firefox"

    ini = base / "profiles.ini"
    if not ini.exists():
        return None

    current: dict[str, str] = {}
    default_path: Optional[str] = None

    for line in ini.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if line.startswith("["):
            p = current.get("Path", "")
            if p and current.get("Default") == "1":
                is_rel = current.get("IsRelative", "1") == "1"
                default_path = str(base / p) if is_rel else p
            current = {}
        elif "=" in line:
            k, _, v = line.partition("=")
            current[k.strip()] = v.strip()

    p = current.get("Path", "")
    if p and current.get("Default") == "1":
        is_rel = current.get("IsRelative", "1") == "1"
        default_path = str(base / p) if is_rel else p

    if default_path and Path(default_path).exists():
        print(f"[Browser] Firefox real profile: {default_path}")
        return default_path
    return None

def _find_opera_windows() -> Optional[str]:
    local  = os.environ.get("LOCALAPPDATA", "")
    prog   = os.environ.get("PROGRAMFILES", "")
    prog86 = os.environ.get("PROGRAMFILES(X86)", "")

    candidates = [
        Path(local)  / "Programs" / "Opera"    / "opera.exe",
        Path(local)  / "Programs" / "Opera GX" / "opera.exe",
        Path(prog)   / "Opera"    / "opera.exe",
        Path(prog86) / "Opera"    / "opera.exe",
    ]
    for p in candidates:
        if p.exists():
            print(f"[Browser] Opera found at: {p}")
            return str(p)

    try:
        import winreg
        keys = [
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\opera.exe",
            r"SOFTWARE\Clients\StartMenuInternet\OperaStable\shell\open\command",
            r"SOFTWARE\Clients\StartMenuInternet\OperaGXStable\shell\open\command",
            r"SOFTWARE\Clients\StartMenuInternet\opera\shell\open\command",
        ]
        for key_path in keys:
            for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                try:
                    k   = winreg.OpenKey(hive, key_path)
                    val = winreg.QueryValue(k, None)
                    winreg.CloseKey(k)
                    exe = val.strip().strip('"').split('"')[0].split(" --")[0].strip()
                    if exe and Path(exe).exists():
                        print(f"[Browser] Opera found via registry: {exe}")
                        return exe
                except Exception:
                    continue
    except Exception:
        pass

    return shutil.which("opera") or None

def _find_exe_windows(prog_name: str) -> Optional[str]:
    try:
        import winreg
        paths_to_try = [
            rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{prog_name}.exe",
            rf"SOFTWARE\Clients\StartMenuInternet\{prog_name}\shell\open\command",
        ]
        for key_path in paths_to_try:
            for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                try:
                    k   = winreg.OpenKey(hive, key_path)
                    val = winreg.QueryValue(k, None)
                    winreg.CloseKey(k)
                    exe = val.strip().strip('"').split('"')[0].split(" --")[0].strip()
                    if exe and Path(exe).exists():
                        return exe
                except Exception:
                    continue
    except Exception:
        pass
    return None

_BROWSER_SPECS: dict[str, dict] = {
    "Windows": {
        "chrome":   {"engine": "chromium", "channel": "chrome",  "bins": []},
        "edge":     {"engine": "chromium", "channel": "msedge",  "bins": []},
        "firefox":  {"engine": "firefox",  "channel": None,      "bins": ["firefox.exe"]},
        "opera":    {"engine": "chromium", "channel": None,      "bins": ["opera.exe"],  "special": "opera_windows"},
        "operagx":  {"engine": "chromium", "channel": None,      "bins": [],             "special": "opera_windows"},
        "brave":    {"engine": "chromium", "channel": None,      "bins": ["brave.exe"]},
        "vivaldi":  {"engine": "chromium", "channel": None,      "bins": ["vivaldi.exe"]},
        "safari":   None,
    },
    "Darwin": {
        "chrome":   {"engine": "chromium", "channel": "chrome",  "bins": []},
        "edge":     {"engine": "chromium", "channel": "msedge",  "bins": ["microsoft-edge"]},
        "firefox":  {"engine": "firefox",  "channel": None,      "bins": ["firefox"]},
        "opera":    {"engine": "chromium", "channel": None,      "bins": ["opera"]},
        "operagx":  {"engine": "chromium", "channel": None,      "bins": ["opera"]},
        "brave":    {"engine": "chromium", "channel": None,      "bins": ["brave browser", "brave"]},
        "vivaldi":  {"engine": "chromium", "channel": None,      "bins": ["vivaldi"]},
        "safari":   {"engine": "webkit",   "channel": None,      "bins": []},
    },
    "Linux": {
        "chrome":   {"engine": "chromium", "channel": None,
                     "bins": ["google-chrome", "google-chrome-stable", "chromium-browser", "chromium"]},
        "edge":     {"engine": "chromium", "channel": None,
                     "bins": ["microsoft-edge", "microsoft-edge-stable"]},
        "firefox":  {"engine": "firefox",  "channel": None, "bins": ["firefox"]},
        "opera":    {"engine": "chromium", "channel": None, "bins": ["opera", "opera-stable"]},
        "operagx":  {"engine": "chromium", "channel": None, "bins": ["opera", "opera-stable"]},
        "brave":    {"engine": "chromium", "channel": None, "bins": ["brave-browser", "brave"]},
        "vivaldi":  {"engine": "chromium", "channel": None, "bins": ["vivaldi-stable", "vivaldi"]},
        "safari":   None,
    },
}

_ALIASES: dict[str, str] = {
    "google chrome":   "chrome",
    "google-chrome":   "chrome",
    "microsoft edge":  "edge",
    "ms edge":         "edge",
    "msedge":          "edge",
    "mozilla firefox": "firefox",
    "opera gx":        "operagx",
    "opera_gx":        "operagx",
}


def _resolve_browser(name: str) -> dict | None:
    name   = _ALIASES.get(name.lower().strip(), name.lower().strip())
    os_map = _BROWSER_SPECS.get(_OS, {})
    spec   = os_map.get(name)
    if spec is None:
        return None

    engine  = spec["engine"]
    channel = spec.get("channel")
    bins    = spec.get("bins", [])
    exe     = None

    if spec.get("special") == "opera_windows":
        exe = _find_opera_windows()
        if not exe:
            print(f"[Browser] ⚠️  Opera executable not found on Windows.")
        return {"engine": engine, "exe": exe, "channel": channel}

    for b in bins:
        found = shutil.which(b)
        if found:
            exe = found
            break

    if not exe and _OS == "Darwin":
        app_names = {
            "chrome":  ["Google Chrome.app"],
            "edge":    ["Microsoft Edge.app"],
            "firefox": ["Firefox.app"],
            "opera":   ["Opera.app", "Opera GX.app"],
            "brave":   ["Brave Browser.app"],
            "vivaldi": ["Vivaldi.app"],
        }
        for app in app_names.get(name, []):
            app_dir = Path("/Applications") / app / "Contents" / "MacOS"
            if app_dir.exists():
                found_bins = list(app_dir.iterdir())
                if found_bins:
                    exe = str(found_bins[0])
                    break

    if not exe and _OS == "Windows" and not channel:
        exe = _find_exe_windows(name)

    return {"engine": engine, "exe": exe, "channel": channel}


def _detect_default_browser() -> str:
    try:
        if _OS == "Windows":
            import winreg
            k = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\Shell\Associations"
                r"\UrlAssociations\http\UserChoice",
            )
            prog_id = winreg.QueryValueEx(k, "ProgId")[0].lower()
            winreg.CloseKey(k)
            for kw in ("edge", "firefox", "opera", "brave", "vivaldi", "chrome"):
                if kw in prog_id:
                    return kw
        elif _OS == "Darwin":
            out = subprocess.run(
                ["defaults", "read",
                 "com.apple.LaunchServices/com.apple.launchservices.secure",
                 "LSHandlers"],
                capture_output=True, text=True, timeout=5,
            ).stdout.lower()
            for kw in ("firefox", "opera", "brave", "vivaldi", "safari", "chrome", "edge"):
                if kw in out:
                    return kw
        elif _OS == "Linux":
            out = subprocess.run(
                ["xdg-settings", "get", "default-web-browser"],
                capture_output=True, text=True, timeout=5,
            ).stdout.lower()
            for kw in ("firefox", "opera", "brave", "vivaldi", "chrome", "edge"):
                if kw in out:
                    return kw
    except Exception:
        pass
    return "chrome"


_SEARCH_ENGINES: dict[str, str] = {
    "google":     "https://www.google.com/search?q=",
    "bing":       "https://www.bing.com/search?q=",
    "duckduckgo": "https://duckduckgo.com/?q=",
    "yandex":     "https://yandex.com/search/?text=",
}

_MAC_APP_NAMES: dict[str, str] = {
    "chrome":  "Google Chrome",
    "edge":    "Microsoft Edge",
    "firefox": "Firefox",
    "opera":   "Opera",
    "operagx": "Opera GX",
    "brave":   "Brave Browser",
    "vivaldi": "Vivaldi",
    "safari":  "Safari",
}

# Windows registry lookup names for browsers whose spec has no explicit binary
_WIN_EXE_HINTS: dict[str, str] = {"chrome": "chrome", "edge": "msedge"}


def _open_native(url: str, browser_name: Optional[str]) -> str:
    """
    Opens the user's REAL browser normally — with their own profile,
    logged-in accounts and extensions. No automation attaches, so an
    about:blank tab or a blank profile NEVER shows up.
    If url is empty the browser starts with no URL (its own start page /
    session restore) — exactly as if the user had opened it themselves.
    Works on all three of Windows / macOS / Linux.
    """
    url = _normalize_url(url) if url and url.strip() else ""
    if url == "about:blank":
        url = ""

    name = None
    if browser_name:
        name = _ALIASES.get(browser_name.lower().strip(), browser_name.lower().strip())
    elif not url:
        # No URL → only a window will open; needs the default browser's exe
        name = _detect_default_browser()

    # Specific browser → launch its own executable, exactly like the user would.
    if name:
        if _OS == "Darwin":
            app = _MAC_APP_NAMES.get(name)
            if app:
                cmd = ["open", "-a", app] + ([url] if url else [])
                try:
                    subprocess.run(cmd, check=True, timeout=10)
                    return f"Opened in {name}: {url}" if url else f"Opened {name}."
                except Exception as e:
                    print(f"[Browser] 'open -a {app}' failed ({e}), trying binary…")

        spec = _resolve_browser(name)
        exe  = spec.get("exe") if spec else None
        if not exe and _OS == "Windows":
            if name in ("opera", "operagx"):
                exe = _find_opera_windows()
            else:
                exe = _find_exe_windows(_WIN_EXE_HINTS.get(name, name))
        if exe:
            try:
                subprocess.Popen(
                    [exe, url] if url else [exe],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                return f"Opened in {name}: {url}" if url else f"Opened {name}."
            except Exception as e:
                print(f"[Browser] Native launch failed for {name}: {e}")
        print(f"[Browser] '{name}' not found — falling back to default browser.")

    if not url:
        return "Could not find a browser to open."

    # Default browser via the OS — exactly like the user clicking a link.
    try:
        if _OS == "Windows":
            os.startfile(url)                       # ShellExecute → default browser
        elif _OS == "Darwin":
            subprocess.run(["open", url], check=True, timeout=10)
        else:
            subprocess.Popen(
                ["xdg-open", url],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        return f"Opened in your default browser: {url}"
    except Exception:
        try:
            if webbrowser.open(url):
                return f"Opened in your default browser: {url}"
        except Exception:
            pass
        return f"Could not open a browser for: {url}"


def _find_active_cdp_port(browser_name: str = "chrome") -> int | None:
    b = _ALIASES.get(browser_name.lower().strip(), browser_name.lower().strip())
    candidates = []
    local = os.environ.get("LOCALAPPDATA", "")
    home = Path.home()
    if _OS == "Windows":
        if b == "chrome":
            candidates.append(Path(local) / "Google" / "Chrome" / "User Data" / "DevToolsActivePort")
        elif b == "edge":
            candidates.append(Path(local) / "Microsoft" / "Edge" / "User Data" / "DevToolsActivePort")
        elif b == "brave":
            candidates.append(Path(local) / "BraveSoftware" / "Brave-Browser" / "User Data" / "DevToolsActivePort")
    elif _OS == "Darwin":
        if b == "chrome":
            candidates.append(home / "Library" / "Application Support" / "Google" / "Chrome" / "DevToolsActivePort")
    elif _OS == "Linux":
        if b == "chrome":
            candidates.append(home / ".config" / "google-chrome" / "DevToolsActivePort")

    for p in candidates:
        try:
            if p.exists():
                lines = p.read_text(encoding="utf-8", errors="ignore").strip().splitlines()
                if lines and lines[0].strip().isdigit():
                    port = int(lines[0].strip())
                    if 1 <= port <= 65535:
                        return port
        except Exception:
            pass
    return None


class _BrowserSession:
    """
    A full session for one browser instance.
    All browsers open on the real profile via launch_persistent_context.
    """

    def __init__(self, browser_name: str):
        self.browser_name    = browser_name
        self._spec           = _resolve_browser(browser_name)
        self._is_cdp: bool   = False
        self._is_native_mode: bool = False
        self._browser        = None

        self._loop:    asyncio.AbstractEventLoop | None = None
        self._thread:  threading.Thread | None          = None
        self._ready    = threading.Event()

        self._pw:      Playwright     | None = None
        self._context: BrowserContext | None = None
        self._page:    Page           | None = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self._run_loop,
            daemon=True,
            name=f"BrowserThread-{self.browser_name}",
        )
        self._thread.start()
        self._ready.wait(timeout=20)

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._async_init())
        self._ready.set()
        self._loop.run_forever()

    async def _async_init(self):
        self._pw = await async_playwright().start()

    def run(self, coro, timeout: int = 60) -> str:
        if not self._loop:
            raise RuntimeError(f"Session for '{self.browser_name}' not started.")
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=timeout)

    def close(self):
        if self._loop:
            asyncio.run_coroutine_threadsafe(self._async_close(), self._loop).result(10)

    async def _async_close(self):
        if self._context:
            try:
                await self._context.close()
            except Exception:
                pass
        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass
        if self._pw:
            try:
                await self._pw.stop()
            except Exception:
                pass
        self._context = self._page = self._browser = None
        self._is_cdp = False
        self._is_native_mode = False

    async def _adopt_page(self) -> Page:
        """
        launch_persistent_context already opens a starting tab.
        Instead of opening a new blank tab (about:blank), it adopts that tab —
        so the user never sees an extra blank tab.
        """
        await asyncio.sleep(0.3)
        pages = self._context.pages
        return pages[0] if pages else await self._context.new_page()

    async def _launch(self):
        """
        Launches or attaches to the browser with the real user profile.
        If Chrome/Chromium is already running, it connects over CDP (if available)
        or activates Native Tab Control to operate directly on the user's real tabs,
        pages, and Google accounts — NEVER spawning an isolated blank profile.
        """
        if self._context is not None or self._is_native_mode:
            return

        if self._spec is None:
            raise RuntimeError(
                f"'{self.browser_name}' is not supported on this platform ({_OS})."
            )

        engine_name = self._spec["engine"]
        exe         = self._spec["exe"]
        channel     = self._spec["channel"]
        engine_obj  = getattr(self._pw, engine_name)

        # 1. CDP Check: If browser is running with remote debugging (dynamic or port 9222 / 9223), attach!
        if engine_name == "chromium":
            ports = [9222, 9223]
            active_port = _find_active_cdp_port(self.browser_name)
            if active_port and active_port not in ports:
                ports.insert(0, active_port)
            for port in ports:
                try:
                    self._browser = await engine_obj.connect_over_cdp(f"http://127.0.0.1:{port}", timeout=2000)
                    if self._browser.contexts:
                        self._context = self._browser.contexts[0]
                        pages = self._context.pages
                        self._page = pages[-1] if pages else await self._context.new_page()
                        self._is_cdp = True
                        print(f"[Browser] [CDP] Connected over CDP to running {self.browser_name} (port {port}) with {len(pages)} open tabs!")
                        return
                except Exception:
                    pass

        # 2. If the user's browser is already running:
        # NEVER open an isolated .jarvis_profiles window that lacks their Google accounts.
        # Switch immediately to Native Tab Control so we work on THEIR real tabs!
        if _is_browser_process_running(self.browser_name):
            print(f"[Browser] [Native] Your {self.browser_name} is already open -- using Native Tab Control on your real tabs & accounts!")
            self._is_native_mode = True
            return

        # 3. Firefox:
        if engine_name == "firefox":
            profile = _firefox_profile_dir() or str(
                Path.home() / ".jarvis_profiles" / "firefox"
            )
            kwargs: dict = {
                "headless":    False,
                "slow_mo":     0,
                "viewport":    None,
                "no_viewport": True,
                "timeout":     25_000,
            }
            if exe:
                kwargs["executable_path"] = exe
            try:
                self._context = await engine_obj.launch_persistent_context(profile, **kwargs)
            except Exception as e:
                print(f"[Browser] Firefox real profile failed ({e}), using JARVIS profile")
                jarvis = str(Path.home() / ".jarvis_profiles" / "firefox_jarvis")
                Path(jarvis).mkdir(parents=True, exist_ok=True)
                self._context = await engine_obj.launch_persistent_context(jarvis, **kwargs)

            self._page = await self._adopt_page()
            print(f"[Browser] [OK] Firefox launched")
            return

        # 4. WebKit / Safari:
        if engine_name == "webkit":
            safari_profile = str(Path.home() / ".jarvis_profiles" / "safari")
            Path(safari_profile).mkdir(parents=True, exist_ok=True)
            kwargs = {
                "headless":    False,
                "slow_mo":     0,
                "viewport":    None,
                "no_viewport": True,
                "timeout":     25_000,
            }
            self._context = await engine_obj.launch_persistent_context(safari_profile, **kwargs)
            self._page = await self._adopt_page()
            print(f"[Browser] [OK] Safari launched")
            return

        # 5. Chromium with real profile (when browser is not already running)
        profile = _real_profile_dir(self.browser_name)

        kwargs = {
            "headless":    False,
            "slow_mo":     0,
            "viewport":    None,
            "no_viewport": True,
            "timeout":     25_000,
            "args": [
                "--start-maximized",
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--disable-default-apps",
                "--no-default-browser-check",
            ],
        }

        if exe:
            kwargs["executable_path"] = exe
        elif channel:
            kwargs["channel"] = channel

        label = (
            f"{self.browser_name}"
            + (f"/{channel}" if channel else "")
            + (f" @ {exe}" if exe else "")
        )

        try:
            self._context = await engine_obj.launch_persistent_context(profile, **kwargs)
            self._page = await self._adopt_page()
            print(f"[Browser] [OK] Launched [{label}] profile={profile}")
            return
        except Exception as e:
            print(f"[Browser] [WARN] Real profile failed for {label}: {e}")
            self._is_native_mode = True
            print(f"[Browser] [Native] Using Native Tab Control for {self.browser_name}")
            return


    async def _get_page(self) -> Page | None:
        await self._launch()
        if self._is_native_mode:
            return None
        # If somehow page got closed, open a fresh one
        if self._page is None or self._page.is_closed():
            self._page = await self._context.new_page()
            await asyncio.sleep(0.2)
        return self._page

    async def go_to(self, url: str) -> str:
        await self._launch()
        if self._is_native_mode:
            from actions.computer_control import _chrome_navigate, _focus_window
            _focus_window(self.browser_name)
            return _chrome_navigate(url)

        url      = _normalize_url(url)
        page     = await self._get_page()
        prev_url = page.url

        async def _do_goto(p: Page) -> str:
            """Attempt navigation and return the resulting URL (may still be blank)."""
            try:
                await p.goto(url, wait_until="domcontentloaded", timeout=30_000)
                await asyncio.sleep(0.3)
            except PlaywrightTimeout:
                pass   # page may have partially loaded — check URL below
            except Exception as e:
                print(f"[Browser] goto exception (non-fatal): {e}")
            return p.url

        result_url = await _do_goto(page)

        if result_url in ("about:blank", "", None, prev_url) and prev_url in ("about:blank", "", None):
            print(f"[Browser] Still blank after goto — retrying on new tab: {url}")
            try:
                new_page   = await self._context.new_page()
                self._page = new_page
                result_url = await _do_goto(new_page)
            except Exception as e:
                print(f"[Browser] New-tab retry failed: {e}")

        if result_url and result_url not in ("about:blank", "", None):
            return f"Opened: {result_url}"
        return f"Could not open: {url}"

    async def search(self, query: str, engine: str = "google") -> str:
        await self._launch()
        if self._is_native_mode:
            from actions.computer_control import _chrome_search
            return _chrome_search(query)
        base = _SEARCH_ENGINES.get(engine.lower(), _SEARCH_ENGINES["google"])
        return await self.go_to(base + query.replace(" ", "+"))

    async def click(self, selector: str = None, text: str = None) -> str:
        await self._launch()
        if self._is_native_mode:
            from actions.computer_control import _chrome_click
            return _chrome_click(text or selector or "")
        page = await self._get_page()
        try:
            if text:
                await page.get_by_text(text, exact=False).first.click(timeout=8_000)
                return f"Clicked text: '{text}'"
            if selector:
                await page.click(selector, timeout=8_000)
                return f"Clicked selector: {selector}"
            return "No selector or text provided."
        except PlaywrightTimeout:
            return "Element not found (timeout)."
        except Exception as e:
            return f"Click error: {e}"

    async def type_text(self, selector: str = None, text: str = "",
                        clear_first: bool = True) -> str:
        await self._launch()
        if self._is_native_mode:
            from actions.computer_control import _chrome_type_in
            return _chrome_type_in(selector or "", text, clear_first=clear_first)
        page = await self._get_page()
        try:
            el = page.locator(selector).first if selector else page.locator(":focus")
            if clear_first:
                await el.clear()
            await el.type(text, delay=50)
            return "Text typed."
        except Exception as e:
            return f"Type error: {e}"

    async def scroll(self, direction: str = "down", amount: int = 500) -> str:
        await self._launch()
        if self._is_native_mode:
            from actions.computer_control import _scroll, _focus_window
            _focus_window(self.browser_name)
            clicks = max(1, amount // 100)
            return _scroll(direction=direction, amount=clicks)
        page = await self._get_page()
        try:
            y = amount if direction == "down" else -amount
            await page.mouse.wheel(0, y)
            return f"Scrolled {direction}."
        except Exception as e:
            return f"Scroll error: {e}"

    async def press(self, key: str) -> str:
        await self._launch()
        if self._is_native_mode:
            from actions.computer_control import _press, _focus_window
            _focus_window(self.browser_name)
            return _press(key)
        page = await self._get_page()
        try:
            await page.keyboard.press(key)
            return f"Pressed: {key}"
        except Exception as e:
            return f"Key error: {e}"

    async def get_text(self) -> str:
        await self._launch()
        if self._is_native_mode:
            from actions.computer_control import _chrome_get_page_text
            return _chrome_get_page_text()
        page = await self._get_page()
        try:
            text = await page.inner_text("body")
            return text[:4_000]
        except Exception as e:
            return f"Could not get page text: {e}"

    async def get_url(self) -> str:
        await self._launch()
        if self._is_native_mode:
            from actions.computer_control import _chrome_get_url
            return _chrome_get_url()
        page = await self._get_page()
        return page.url

    async def fill_form(self, fields: dict) -> str:
        await self._launch()
        if self._is_native_mode:
            from actions.computer_control import _chrome_type_in
            results = []
            for field, val in fields.items():
                r = _chrome_type_in(field, str(val))
                results.append(r)
            return "Form filled: " + ", ".join(results)
        page    = await self._get_page()
        results = []
        for selector, value in fields.items():
            try:
                el = page.locator(selector).first
                await el.clear()
                await el.type(str(value), delay=40)
                results.append(f"✓ {selector}")
            except Exception as e:
                results.append(f"✗ {selector}: {e}")
        return "Form filled: " + ", ".join(results)

    async def smart_click(self, description: str) -> str:
        await self._launch()
        if self._is_native_mode:
            from actions.computer_control import _chrome_click
            return _chrome_click(description)
        page = await self._get_page()
        for role in ("button", "link", "searchbox", "textbox", "menuitem", "tab"):
            try:
                loc = page.get_by_role(role, name=description)
                if await loc.count() > 0:
                    await loc.first.click(timeout=5_000)
                    return f"Clicked ({role}): '{description}'"
            except Exception:
                pass
        for attempt in (
            lambda: page.get_by_text(description, exact=False).first.click(timeout=5_000),
            lambda: page.get_by_placeholder(description, exact=False).first.click(timeout=5_000),
            lambda: page.locator(
                f'[alt*="{description}" i],[title*="{description}" i],'
                f'[aria-label*="{description}" i]'
            ).first.click(timeout=5_000),
        ):
            try:
                await attempt()
                return f"Clicked: '{description}'"
            except Exception:
                pass
        return f"Could not find element: '{description}'"

    async def smart_type(self, description: str, text: str) -> str:
        await self._launch()
        if self._is_native_mode:
            from actions.computer_control import _chrome_type_in
            return _chrome_type_in(description, text)
        page = await self._get_page()
        candidates = [
            ("placeholder", page.get_by_placeholder(description, exact=False)),
            ("label",       page.get_by_label(description, exact=False)),
            ("role",        page.get_by_role("textbox", name=description)),
            ("searchbox",   page.get_by_role("searchbox")),
            ("combobox",    page.get_by_role("combobox", name=description)),
        ]
        for method, loc in candidates:
            try:
                el = loc.first
                if await el.count() == 0:
                    continue
                await el.clear()
                await el.type(text, delay=50)
                return f"Typed into ({method}): '{description}'"
            except Exception:
                continue
        return f"Could not find input: '{description}'"

    async def new_tab(self, url: str = "") -> str:
        await self._launch()
        if self._is_native_mode:
            from actions.computer_control import _chrome_new_tab
            return _chrome_new_tab(url)
        page = await self._get_page()
        ctx  = page.context
        new  = await ctx.new_page()
        self._page = new
        if url:
            return await self.go_to(url)
        return "New tab opened."

    async def close_tab(self) -> str:
        await self._launch()
        if self._is_native_mode:
            from actions.computer_control import _chrome_close_tab
            return _chrome_close_tab()
        page = self._page
        if page and not page.is_closed():
            ctx   = page.context
            await page.close()
            pages = ctx.pages
            self._page = pages[-1] if pages else None
            return "Tab closed."
        return "No active tab to close."

    async def switch_tab(self, target: str = "next") -> str:
        await self._launch()
        if self._is_native_mode:
            from actions.computer_control import _chrome_switch_tab
            return _chrome_switch_tab(target)
        if self._context:
            pages = self._context.pages
            if pages:
                t = str(target or "next").lower().strip()
                if t.isdigit() and 1 <= int(t) <= len(pages):
                    self._page = pages[int(t) - 1]
                    await self._page.bring_to_front()
                    return f"Switched to tab {t}: {self._page.url}"
                idx = pages.index(self._page) if self._page in pages else 0
                step = -1 if t in ("prev", "previous") else 1
                next_idx = (idx + step) % len(pages)
                self._page = pages[next_idx]
                await self._page.bring_to_front()
                return f"Switched to tab {next_idx + 1}: {self._page.url}"
        return "No tabs to switch."

    async def screenshot(self, path: str = None) -> str:
        await self._launch()
        if self._is_native_mode:
            from actions.computer_control import _screenshot
            return _screenshot(path)
        page = await self._get_page()
        try:
            save_path = path or str(Path.home() / "Desktop" / "jarvis_screenshot.png")
            await page.screenshot(path=save_path, full_page=False)
            return f"Screenshot saved: {save_path}"
        except Exception as e:
            return f"Screenshot error: {e}"

    async def back(self) -> str:
        await self._launch()
        if self._is_native_mode:
            from actions.computer_control import _hotkey, _focus_window
            _focus_window(self.browser_name)
            return _hotkey("alt", "left")
        page = await self._get_page()
        try:
            await page.go_back(timeout=10_000)
            return f"Navigated back: {page.url}"
        except Exception as e:
            return f"Back error: {e}"

    async def forward(self) -> str:
        await self._launch()
        if self._is_native_mode:
            from actions.computer_control import _hotkey, _focus_window
            _focus_window(self.browser_name)
            return _hotkey("alt", "right")
        page = await self._get_page()
        try:
            await page.go_forward(timeout=10_000)
            return f"Navigated forward: {page.url}"
        except Exception as e:
            return f"Forward error: {e}"

    async def reload(self, hard: bool = False) -> str:
        await self._launch()
        if self._is_native_mode:
            from actions.computer_control import _chrome_reload
            return _chrome_reload(hard)
        page = await self._get_page()
        try:
            await page.reload(timeout=15_000)
            return f"Page reloaded: {page.url}"
        except Exception as e:
            return f"Reload error: {e}"

    async def list_tabs(self) -> str:
        await self._launch()
        if self._is_native_mode:
            from actions.computer_control import _chrome_list_tabs
            return _chrome_list_tabs()
        if self._context:
            pages = self._context.pages
            if pages:
                lines = []
                for i, p in enumerate(pages):
                    active = " (active)" if p == self._page else ""
                    try:
                        title = await p.title()
                    except Exception:
                        title = ""
                    lines.append(f"  [{i+1}] {p.url} ({title}){active}")
                return f"Open tabs ({len(pages)}):\n" + "\n".join(lines)
        return "No open tabs."

    async def zoom(self, factor: str = "reset") -> str:
        await self._launch()
        if self._is_native_mode:
            from actions.computer_control import _chrome_zoom
            return _chrome_zoom(factor)
        page = await self._get_page()
        f = str(factor or "reset").lower().strip()
        if f in ("in", "+", "zoom_in"):
            await page.keyboard.press("Control+=")
            return "Zoomed in."
        elif f in ("out", "-", "zoom_out"):
            await page.keyboard.press("Control+-")
            return "Zoomed out."
        else:
            await page.keyboard.press("Control+0")
            return "Reset zoom."

    async def find_text(self, query: str) -> str:
        await self._launch()
        if self._is_native_mode:
            from actions.computer_control import _chrome_find
            return _chrome_find(query)
        page = await self._get_page()
        await page.keyboard.press("Control+f")
        if query:
            await page.keyboard.type(query)
            await page.keyboard.press("Enter")
        return f"Searched for '{query}' on page."

    async def duplicate_tab(self) -> str:
        await self._launch()
        if self._is_native_mode:
            from actions.computer_control import _chrome_duplicate_tab
            return _chrome_duplicate_tab()
        page = await self._get_page()
        url = page.url
        return await self.new_tab(url)

    async def history(self) -> str:
        await self._launch()
        if self._is_native_mode:
            from actions.computer_control import _chrome_history
            return _chrome_history()
        return await self.go_to("chrome://history" if self.browser_name == "chrome" else "about:history")

    async def downloads(self) -> str:
        await self._launch()
        if self._is_native_mode:
            from actions.computer_control import _chrome_downloads
            return _chrome_downloads()
        return await self.go_to("chrome://downloads" if self.browser_name == "chrome" else "about:downloads")

    async def bookmarks(self) -> str:
        await self._launch()
        if self._is_native_mode:
            from actions.computer_control import _chrome_bookmarks
            return _chrome_bookmarks()
        return await self.go_to("chrome://bookmarks" if self.browser_name == "chrome" else "about:bookmarks")

    async def evaluate_script(self, script: str) -> str:
        await self._launch()
        if self._is_native_mode:
            return "Script evaluation requires automation/CDP session. Start Chrome with 'launch_debug'."
        page = await self._get_page()
        try:
            res = await page.evaluate(script)
            return f"Script result: {res}"
        except Exception as e:
            return f"Script evaluation failed: {e}"

    async def hover(self, selector: str = None, text: str = None) -> str:
        """Hover over an element to reveal tooltips, submenus, or dropdown overlays."""
        await self._launch()
        page = await self._get_page()
        try:
            if text:
                el = page.get_by_text(text, exact=False).first
            elif selector:
                el = page.locator(selector).first
            else:
                return "No selector or text provided for hover."
            await el.scroll_into_view_if_needed(timeout=5_000)
            await el.hover(timeout=6_000)
            return f"Hovered over '{text or selector}'."
        except Exception as e:
            return f"Hover error: {e}"

    async def right_click(self, selector: str = None, text: str = None) -> str:
        """Right-click an element to open a context menu."""
        await self._launch()
        page = await self._get_page()
        try:
            if text:
                el = page.get_by_text(text, exact=False).first
            elif selector:
                el = page.locator(selector).first
            else:
                return "No selector or text provided for right_click."
            await el.click(button="right", timeout=6_000)
            return f"Right-clicked '{text or selector}'."
        except Exception as e:
            return f"Right-click error: {e}"

    async def double_click(self, selector: str = None, text: str = None) -> str:
        """Double-click an element (e.g. to open a file or enter edit mode)."""
        await self._launch()
        page = await self._get_page()
        try:
            if text:
                el = page.get_by_text(text, exact=False).first
            elif selector:
                el = page.locator(selector).first
            else:
                return "No selector or text provided for double_click."
            await el.dblclick(timeout=6_000)
            return f"Double-clicked '{text or selector}'."
        except Exception as e:
            return f"Double-click error: {e}"

    async def drag_and_drop(self, source: str, target: str) -> str:
        """Drag element matching `source` selector to element matching `target` selector."""
        await self._launch()
        page = await self._get_page()
        try:
            src = page.locator(source).first
            tgt = page.locator(target).first
            await src.drag_to(tgt, timeout=10_000)
            return f"Dragged '{source}' to '{target}'."
        except Exception as e:
            return f"Drag-and-drop error: {e}"

    async def select_option(self, selector: str, value: str) -> str:
        """Select an <option> inside a <select> dropdown by value, label, or index."""
        await self._launch()
        page = await self._get_page()
        try:
            el = page.locator(selector).first
            # Try value, then label
            try:
                await el.select_option(value=value, timeout=5_000)
                return f"Selected option value='{value}' in '{selector}'."
            except Exception:
                await el.select_option(label=value, timeout=5_000)
                return f"Selected option label='{value}' in '{selector}'."
        except Exception as e:
            return f"Select option error: {e}"

    async def get_cookies(self) -> str:
        """Return all cookies for the current page as a formatted list."""
        await self._launch()
        page = await self._get_page()
        try:
            cookies = await page.context.cookies()
            if not cookies:
                return "No cookies found."
            lines = [f"  {c['name']}={c['value'][:40]}{'...' if len(c['value'])>40 else ''} (domain={c.get('domain','?')})" for c in cookies[:30]]
            return f"Cookies ({len(cookies)}):\n" + "\n".join(lines)
        except Exception as e:
            return f"Get cookies error: {e}"

    async def clear_cookies(self) -> str:
        """Clear all cookies for the current browser context."""
        await self._launch()
        page = await self._get_page()
        try:
            await page.context.clear_cookies()
            return "All cookies cleared."
        except Exception as e:
            return f"Clear cookies error: {e}"

    async def get_local_storage(self, key: str = None) -> str:
        """Read localStorage from the current page. Pass key for a single value, or omit for all."""
        await self._launch()
        page = await self._get_page()
        try:
            if key:
                val = await page.evaluate(f"() => localStorage.getItem({json.dumps(key)})")
                return f"localStorage['{key}'] = {val}"
            data = await page.evaluate("() => { const o={}; for(let i=0;i<localStorage.length;i++){const k=localStorage.key(i);o[k]=localStorage.getItem(k);} return o; }")
            if not data:
                return "localStorage is empty."
            lines = [f"  {k}: {str(v)[:60]}" for k, v in list(data.items())[:20]]
            return f"localStorage ({len(data)} keys):\n" + "\n".join(lines)
        except Exception as e:
            return f"Get localStorage error: {e}"

    async def set_local_storage(self, key: str, value: str) -> str:
        """Write a key-value pair into the page's localStorage."""
        await self._launch()
        page = await self._get_page()
        try:
            await page.evaluate(f"() => localStorage.setItem({json.dumps(key)}, {json.dumps(value)})")
            return f"localStorage['{key}'] set to '{value[:60]}'"
        except Exception as e:
            return f"Set localStorage error: {e}"

    async def get_all_links(self) -> str:
        """Extract all visible hyperlinks on the current page."""
        await self._launch()
        page = await self._get_page()
        try:
            links = await page.evaluate(
                """() => Array.from(document.querySelectorAll('a[href]'))
                   .filter(a => a.offsetParent !== null)
                   .map(a => ({text: (a.innerText||a.href).trim().slice(0,80), href: a.href}))
                   .slice(0, 50)"""
            )
            if not links:
                return "No visible links found on page."
            lines = [f"  [{i+1}] {l['text']} -> {l['href'][:80]}" for i, l in enumerate(links)]
            return f"Links ({len(links)}):\n" + "\n".join(lines)
        except Exception as e:
            return f"Get links error: {e}"

    async def get_page_title(self) -> str:
        """Return the current page's title tag."""
        await self._launch()
        page = await self._get_page()
        try:
            return f"Page title: {await page.title()}"
        except Exception as e:
            return f"Get title error: {e}"

    async def wait_for_navigation(self, timeout: float = 15.0) -> str:
        """Wait until the page URL changes or a navigation event fires."""
        await self._launch()
        page = await self._get_page()
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=int(timeout * 1_000))
            return f"Navigation complete: {page.url}"
        except Exception as e:
            return f"Wait for navigation error: {e}"

    async def accept_dialog(self, accept: bool = True, prompt_text: str = "") -> str:
        """Accept or dismiss the next browser dialog (alert/confirm/prompt)."""
        await self._launch()
        page = await self._get_page()
        handled = []
        def _handler(dialog):
            asyncio.ensure_future(
                dialog.accept(prompt_text) if accept else dialog.dismiss()
            )
            handled.append(dialog.type)
        page.once("dialog", _handler)
        await asyncio.sleep(3.0)  # Give time for dialog to fire
        if handled:
            action = "Accepted" if accept else "Dismissed"
            return f"{action} {handled[0]} dialog."
        return "No dialog appeared within 3 seconds."

    async def highlight_element(self, selector: str, duration_ms: int = 2000) -> str:
        """Flash a bright outline on an element so the user can see what JARVIS is targeting."""
        await self._launch()
        page = await self._get_page()
        try:
            await page.evaluate(
                f"""(args) => {{
                    const el = document.querySelector(args.sel);
                    if (!el) return;
                    const prev = el.style.outline;
                    el.style.outline = '3px solid #00E5FF';
                    el.style.boxShadow = '0 0 12px #00E5FF';
                    setTimeout(() => {{ el.style.outline=prev; el.style.boxShadow=''; }}, args.ms);
                }}""",
                {"sel": selector, "ms": duration_ms},
            )
            return f"Highlighted '{selector}' for {duration_ms}ms."
        except Exception as e:
            return f"Highlight error: {e}"

    async def close_browser(self) -> str:
        await self._async_close()
        return f"{self.browser_name} closed."

class _SessionRegistry:
    """Manages all active browser sessions."""

    def __init__(self):
        self._sessions:        dict[str, _BrowserSession] = {}
        self._active_browser:  str                        = ""
        self._lock             = threading.Lock()
        self._last_native_url: str                        = ""

    def has(self, browser_name: str | None = None) -> bool:
        """Is there an active automation session for this browser (or any)?"""
        with self._lock:
            if not browser_name:
                return bool(self._sessions)
            name = _ALIASES.get(browser_name.lower().strip(), browser_name.lower().strip())
            return name in self._sessions

    def note_native_url(self, url: str) -> None:
        self._last_native_url = url

    def pop_native_url(self) -> str:
        """Returns the last natively-opened URL once (consumed to avoid repeats)."""
        url, self._last_native_url = self._last_native_url, ""
        return url

    def _get_or_create(self, browser_name: str) -> _BrowserSession:
        with self._lock:
            if browser_name not in self._sessions:
                sess = _BrowserSession(browser_name)
                sess.start()
                self._sessions[browser_name] = sess
                print(f"[Registry] New session: {browser_name}")
            return self._sessions[browser_name]

    def get(self, browser_name: str | None = None) -> _BrowserSession:
        if not browser_name:
            browser_name = self._active_browser or _detect_default_browser()
        browser_name = _ALIASES.get(browser_name.lower().strip(), browser_name.lower().strip())
        sess = self._get_or_create(browser_name)
        self._active_browser = browser_name
        return sess

    def switch(self, browser_name: str) -> str:
        browser_name = _ALIASES.get(browser_name.lower().strip(), browser_name.lower().strip())
        self._get_or_create(browser_name)
        self._active_browser = browser_name
        return f"Active browser -> {browser_name}"

    def close_one(self, browser_name: str) -> str:
        with self._lock:
            sess = self._sessions.pop(browser_name, None)
        if sess:
            sess.close()
            if self._active_browser == browser_name:
                self._active_browser = ""
            return f"{browser_name} closed."
        return f"No active session for: {browser_name}"

    def close_all(self) -> str:
        with self._lock:
            names    = list(self._sessions.keys())
            sessions = list(self._sessions.values())
            self._sessions.clear()
            self._active_browser = ""
        for s in sessions:
            try:
                s.close()
            except Exception:
                pass
        return "All browsers closed: " + (", ".join(names) if names else "none")

    def list_sessions(self) -> str:
        with self._lock:
            if not self._sessions:
                return "No active browser sessions."
            lines = []
            for name in self._sessions:
                marker = " <- active" if name == self._active_browser else ""
                lines.append(f"  • {name}{marker}")
            return "Open browsers:\n" + "\n".join(lines)


_registry = _SessionRegistry()

def browser_control(
    parameters:    dict = None,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params  = parameters or {}
    action  = params.get("action", "").lower().strip()
    browser = params.get("browser", "").lower().strip() or None
    result  = "Unknown action."

    if action == "switch":
        target = browser or params.get("target", "").lower().strip()
        result = _registry.switch(target) if target else "Please specify a browser."
        _log(player, result)
        return result

    if action == "list_browsers":
        result = _registry.list_sessions()
        _log(player, result)
        return result

    if action == "close_all":
        result = _registry.close_all()
        _log(player, result)
        return result

    if action == "close":
        target = browser or _registry._active_browser
        result = _registry.close_one(target) if target else "No browser specified."
        _log(player, result)
        return result

    # ── Navigation is ALWAYS native ──────────────────────────────────────────
    # go_to / search / new_tab open the site in the user's own browser —
    # their own profile, logged-in accounts and start page; exactly as if the
    # user had opened it themselves. A controlled window with about:blank never
    # opens here. The only exception: if an automation flow is already running,
    # navigation continues in that window (so multi-step tasks aren't split).
    if action in ("go_to", "search", "new_tab"):
        if _registry.has(browser):
            sess = _registry.get(browser)
            try:
                if action == "search":
                    result = sess.run(sess.search(params.get("query", ""),
                                                  params.get("engine", "google")))
                elif action == "new_tab":
                    result = sess.run(sess.new_tab(params.get("url", "")))
                else:
                    result = sess.run(sess.go_to(params.get("url", "")))
            except concurrent.futures.TimeoutError:
                result = f"Browser action '{action}' timed out (60s)."
            except Exception as e:
                result = f"Browser error ({action}): {e}"
            _log(player, result)
            return result

        if action == "search":
            base    = _SEARCH_ENGINES.get(params.get("engine", "google").lower(),
                                          _SEARCH_ENGINES["google"])
            nav_url = base + params.get("query", "").replace(" ", "+")
        else:
            nav_url = params.get("url", "").strip()

        result = _open_native(nav_url, browser)
        if result.startswith("Opened") and nav_url:
            _registry.note_native_url(_normalize_url(nav_url))
        _log(player, result)
        return result

    # ── Interactive actions (click/type/read…) ───────────────────────────────
    # These require a physically controllable browser; the automation window
    # only opens here, and as soon as it opens it goes to the user's last
    # navigated page — it doesn't sit on a blank page.
    try:
        sess = _registry.get(browser)
    except Exception as e:
        result = f"Could not start browser session: {e}"
        _log(player, result)
        return result

    try:
        last = _registry.pop_native_url()
        if last:
            try:
                sess.run(sess.go_to(last))
            except Exception as e:
                print(f"[Browser] Could not resume last page ({last}): {e}")

        if action == "click":
            result = sess.run(sess.click(params.get("selector"), params.get("text")))
        elif action == "type":
            result = sess.run(sess.type_text(
                params.get("selector"), params.get("text", ""), params.get("clear_first", True)))
        elif action in ("goto_page", "pdf_page", "chrome_pdf_goto_page", "scroll_to_page"):
            from actions.computer_control import _chrome_pdf_goto_page
            result = _chrome_pdf_goto_page(params.get("page", params.get("page_number", 1)), params.get("relative_pages", None))
        elif action == "scroll":
            if params.get("page") is not None or params.get("page_number") is not None:
                from actions.computer_control import _chrome_pdf_goto_page
                result = _chrome_pdf_goto_page(params.get("page", params.get("page_number", 1)))
            else:
                result = sess.run(sess.scroll(params.get("direction", "down"), int(params.get("amount", 500))))
        elif action == "fill_form":
            result = sess.run(sess.fill_form(params.get("fields", {})))
        elif action == "smart_click":
            result = sess.run(sess.smart_click(params.get("description", "")))
        elif action == "smart_type":
            result = sess.run(sess.smart_type(params.get("description", ""), params.get("text", "")))
        elif action == "get_text":
            result = sess.run(sess.get_text())
        elif action == "get_url":
            result = sess.run(sess.get_url())
        elif action == "press":
            result = sess.run(sess.press(params.get("key", "Enter")))
        elif action == "close_tab":
            result = sess.run(sess.close_tab())
        elif action == "screenshot":
            result = sess.run(sess.screenshot(params.get("path")))
        elif action == "back":
            result = sess.run(sess.back())
        elif action == "forward":
            result = sess.run(sess.forward())
        elif action == "reload":
            result = sess.run(sess.reload(bool(params.get("hard", False))))
        elif action in ("fullscreen", "toggle_fullscreen"):
            result = sess.run(sess.press("F11"))
        elif action == "task_manager":
            from actions.computer_control import _chrome_task_manager
            result = _chrome_task_manager()
        elif action in ("print_pdf", "print"):
            from actions.computer_control import _chrome_print_pdf
            result = _chrome_print_pdf()
        elif action == "page_source":
            from actions.computer_control import _chrome_page_source
            result = _chrome_page_source()
        elif action == "clear_data":
            from actions.computer_control import _chrome_clear_data
            result = _chrome_clear_data()
        elif action == "switch_tab":
            target = params.get("target", params.get("tab", "next"))
            result = sess.run(sess.switch_tab(target))
        elif action in ("list_tabs", "get_tabs"):
            result = sess.run(sess.list_tabs())
        elif action in ("zoom", "zoom_in", "zoom_out", "zoom_reset"):
            factor = params.get("level", "in" if "in" in action else ("out" if "out" in action else "reset"))
            result = sess.run(sess.zoom(factor))
        elif action in ("find_text", "find_on_page"):
            result = sess.run(sess.find_text(params.get("query", params.get("text", ""))))
        elif action == "duplicate_tab":
            result = sess.run(sess.duplicate_tab())
        elif action == "history":
            result = sess.run(sess.history())
        elif action == "downloads":
            result = sess.run(sess.downloads())
        elif action == "bookmarks":
            result = sess.run(sess.bookmarks())
        elif action in ("evaluate", "evaluate_script", "execute_script"):
            result = sess.run(sess.evaluate_script(params.get("script", params.get("text", ""))))
        elif action in ("launch_debug", "enable_debugging"):
            from actions.computer_control import _chrome_launch_debug
            result = _chrome_launch_debug(int(params.get("port", 9222)))
        elif action == "hover":
            result = sess.run(sess.hover(params.get("selector"), params.get("text")))
        elif action == "right_click":
            result = sess.run(sess.right_click(params.get("selector"), params.get("text")))
        elif action == "double_click":
            result = sess.run(sess.double_click(params.get("selector"), params.get("text")))
        elif action == "drag_and_drop":
            result = sess.run(sess.drag_and_drop(params.get("source", ""), params.get("target", "")))
        elif action == "select_option":
            result = sess.run(sess.select_option(params.get("selector", ""), params.get("value", "")))
        elif action == "get_cookies":
            result = sess.run(sess.get_cookies())
        elif action == "clear_cookies":
            result = sess.run(sess.clear_cookies())
        elif action == "get_local_storage":
            result = sess.run(sess.get_local_storage(params.get("key")))
        elif action == "set_local_storage":
            result = sess.run(sess.set_local_storage(params.get("key", ""), params.get("value", "")))
        elif action == "get_all_links":
            result = sess.run(sess.get_all_links())
        elif action == "get_page_title":
            result = sess.run(sess.get_page_title())
        elif action == "wait_for_navigation":
            result = sess.run(sess.wait_for_navigation(float(params.get("timeout", 15.0))))
        elif action in ("accept_dialog", "dismiss_dialog"):
            accept = action == "accept_dialog"
            result = sess.run(sess.accept_dialog(accept, params.get("text", "")))
        elif action == "highlight_element":
            result = sess.run(sess.highlight_element(params.get("selector", ""), int(params.get("duration_ms", 2000))))
        else:
            result = f"Unknown browser action: '{action}'"

    except concurrent.futures.TimeoutError:
        result = f"Browser action '{action}' timed out (60s)."
    except Exception as e:
        result = f"Browser error ({action}): {e}"

    _log(player, result)
    return result


def _log(player, text: str):
    short = str(text)[:80]
    try:
        print(f"[Browser] {short}")
    except UnicodeEncodeError:
        try:
            print(f"[Browser] {short.encode('ascii', errors='replace').decode('ascii')}")
        except Exception:
            pass
    if player:
        try:
            player.write_log(f"[browser] {short[:60]}")
        except Exception:
            pass


# ── Tool declaration (auto-discovered by core/action_loader.py) ──────────────
TOOL = {
    "name": "browser_control",
    "description": (
        "Controls web browsers directly on the user's running tabs, profiles, and Google accounts. "
        "Use for: opening websites, new tabs, switching tabs, listing tabs, closing tabs, "
        "clicking, right-clicking, double-clicking, hovering, drag-and-drop, "
        "filling forms, selecting dropdown options, typing, scrolling, screenshots, "
        "navigation (back/forward/reload), zooming, searching on page, extracting text/links/title, "
        "history, downloads, bookmarks, cookies management, localStorage read/write, "
        "JavaScript evaluation, dialog handling, element highlighting, and advanced web automation. "
        "When the user has Chrome open, all actions work directly on THEIR open tabs without "
        "launching an empty guest window. "
        "Core navigation: go_to | search | new_tab | switch_tab | list_tabs | close_tab | duplicate_tab | back | forward | reload. "
        "Interaction: click | right_click | double_click | hover | drag_and_drop | type | fill_form | "
        "smart_click | smart_type | select_option | press | scroll. "
        "Inspection: get_text | get_url | get_page_title | get_all_links | screenshot | get_cookies | "
        "get_local_storage | page_source. "
        "Advanced: evaluate_script | set_local_storage | clear_cookies | accept_dialog | dismiss_dialog | "
        "highlight_element | wait_for_navigation | zoom | find_text | history | downloads | bookmarks | "
        "fullscreen | task_manager | print_pdf | clear_data | launch_debug | switch | list_browsers | close | close_all."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": (
                    "Navigation: go_to | search | new_tab | switch_tab | list_tabs | close_tab | duplicate_tab | back | forward | reload | goto_page. "
                    "Interaction: click | right_click | double_click | hover | drag_and_drop | type | fill_form | "
                    "smart_click | smart_type | select_option | press | scroll. "
                    "Inspection: get_text | get_url | get_page_title | get_all_links | screenshot | "
                    "get_cookies | get_local_storage | page_source. "
                    "Advanced: evaluate_script | set_local_storage | clear_cookies | accept_dialog | dismiss_dialog | "
                    "highlight_element | wait_for_navigation | zoom | find_text | history | downloads | bookmarks | "
                    "fullscreen | task_manager | print_pdf | clear_data | launch_debug | switch | list_browsers | close | close_all."
                )
            },
            "page": {
                "type": "INTEGER",
                "description": "Page number to navigate to for goto_page or PDF scroll."
            },
            "browser": {
                "type": "STRING",
                "description": "Target browser: chrome | edge | firefox | opera | operagx | brave | vivaldi | safari. Omit to use the currently active browser."
            },
            "url": {
                "type": "STRING",
                "description": "URL for go_to or new_tab."
            },
            "query": {
                "type": "STRING",
                "description": "Search query for search or find_text."
            },
            "target": {
                "type": "STRING",
                "description": "Target for switch_tab: next | prev | 1-9 | last | tab title keyword."
            },
            "engine": {
                "type": "STRING",
                "description": "Search engine: google | bing | duckduckgo | yandex (default: google)."
            },
            "selector": {
                "type": "STRING",
                "description": "CSS selector for click, hover, right_click, double_click, drag_and_drop, select_option, highlight_element."
            },
            "source": {
                "type": "STRING",
                "description": "CSS selector of the element to drag (for drag_and_drop)."
            },
            "target_selector": {
                "type": "STRING",
                "description": "CSS selector of the drop destination (for drag_and_drop — use 'target' param key)."
            },
            "value": {
                "type": "STRING",
                "description": "Option value or label for select_option. Also used for set_local_storage."
            },
            "key": {
                "type": "STRING",
                "description": "Key name for press action (e.g. Enter, Escape, Tab, F5, ArrowDown)."
            },
            "text": {
                "type": "STRING",
                "description": "Text content to match, type, or enter into a dialog prompt."
            },
            "description": {
                "type": "STRING",
                "description": "Natural language element description for smart_click / smart_type."
            },
            "level": {
                "type": "STRING",
                "description": "Zoom level: in | out | reset."
            },
            "script": {
                "type": "STRING",
                "description": "JavaScript expression to evaluate (evaluate_script)."
            },
            "direction": {
                "type": "STRING",
                "description": "Scroll direction: up | down."
            },
            "amount": {
                "type": "INTEGER",
                "description": "Scroll amount in pixels (default: 500)."
            },
            "path": {
                "type": "STRING",
                "description": "File path to save screenshot."
            },
            "clear_first": {
                "type": "BOOLEAN",
                "description": "Clear the field before typing (default: true)."
            },
            "hard": {
                "type": "BOOLEAN",
                "description": "Hard-refresh (Ctrl+Shift+R) instead of normal reload (default: false)."
            },
            "duration_ms": {
                "type": "INTEGER",
                "description": "Duration in milliseconds for highlight_element flash (default: 2000)."
            },
            "timeout": {
                "type": "NUMBER",
                "description": "Timeout in seconds for wait_for_navigation (default: 15)."
            },
            "fields": {
                "type": "OBJECT",
                "description": "Field map for fill_form: {\"css_selector\": \"value_to_type\"}."
            }
        },
        "required": ["action"]
    },
    "handler": browser_control,
}
