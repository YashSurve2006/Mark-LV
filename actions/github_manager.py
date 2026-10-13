"""
actions/github_manager.py — Seamless GitHub Account Integration for JARVIS.

Integrates user Yash Surve's GitHub account (YashSurve2006).
Provides full API and Git automation for repositories, commits, issues, PRs,
code pushing, cloning, and notifications.
"""

from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Optional

API_BASE = "https://api.github.com"
CONFIG_FILE = Path(__file__).resolve().parent.parent / "config" / "api_keys.json"


def _log(msg: str, player=None) -> None:
    print(f"[GitHub] {msg}")
    if player and hasattr(player, "write_log"):
        try:
            player.write_log(f"GITHUB: {msg}")
        except Exception:
            pass


def _get_credentials() -> tuple[str, str, str]:
    """Resolves GitHub token, username, and user email with fallback chaining:
    1. config/api_keys.json
    2. Environment variables GITHUB_TOKEN / GH_TOKEN
    3. Windows Git Credential Manager (git credential fill)
    """
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
    username = os.environ.get("GITHUB_USER") or ""
    email = os.environ.get("GITHUB_EMAIL") or ""

    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if not token:
                token = data.get("github_token", "").strip()
            if not username:
                username = data.get("github_username", "").strip()
        except Exception:
            pass

    if not token or not username:
        try:
            res = subprocess.run(
                ["git", "credential", "fill"],
                input="protocol=https\nhost=github.com\n\n",
                capture_output=True,
                text=True,
                timeout=5,
            )
            for line in res.stdout.splitlines():
                if line.startswith("username=") and not username:
                    username = line.split("=", 1)[1].strip()
                elif line.startswith("password=") and not token:
                    token = line.split("=", 1)[1].strip()
        except Exception:
            pass

    if not email:
        try:
            res = subprocess.run(
                ["git", "config", "--global", "user.email"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            email = res.stdout.strip()
        except Exception:
            pass

    if not username:
        username = "YashSurve2006"

    return token, username, email


def _api_request(
    endpoint: str,
    method: str = "GET",
    data: Optional[dict] = None,
    token: str = "",
) -> tuple[int, Any]:
    """Dispatches an authenticated HTTP request to GitHub API."""
    if not token:
        token, _, _ = _get_credentials()

    url = endpoint if endpoint.startswith("http") else f"{API_BASE}{endpoint}"
    payload = json.dumps(data).encode("utf-8") if data is not None else None

    req = urllib.request.Request(url, data=payload, method=method)
    req.add_header("User-Agent", "JARVIS-Mark-LV")
    req.add_header("Accept", "application/vnd.github.v3+json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    if payload:
        req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            status = resp.status
            body = resp.read().decode("utf-8")
            if not body.strip():
                return status, {}
            return status, json.loads(body)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        try:
            err_json = json.loads(err_body)
            msg = err_json.get("message", err_body)
        except Exception:
            msg = err_body or str(e)
        return e.code, {"error": msg}
    except Exception as e:
        return 500, {"error": str(e)}


def get_profile(player=None) -> str:
    """Fetch GitHub user profile details."""
    token, default_user, _ = _get_credentials()
    if not token:
        return "Sir, no GitHub token is configured. Please provide your personal access token."

    code, data = _api_request("/user", token=token)
    if code != 200:
        return f"Unable to fetch GitHub profile: {data.get('error', 'Unknown error')} (Code {code})"

    login = data.get("login", default_user)
    name = data.get("name", login)
    public_repos = data.get("public_repos", 0)
    total_private_repos = data.get("total_private_repos", 0)
    followers = data.get("followers", 0)
    bio = data.get("bio") or "No bio set"
    html_url = data.get("html_url", f"https://github.com/{login}")

    _log(f"Profile: {login} ({name}) with {public_repos} public repos", player)
    return (
        f"**GitHub Profile for {name} (@{login})**:\n"
        f"• Profile URL: {html_url}\n"
        f"• Public Repositories: {public_repos}\n"
        f"• Private Repositories: {total_private_repos}\n"
        f"• Followers: {followers}\n"
        f"• Bio: {bio}"
    )


def list_repos(
    visibility: str = "all",
    sort: str = "updated",
    limit: int = 15,
    player=None,
) -> str:
    """Lists repositories for the authenticated user."""
    token, login, _ = _get_credentials()
    if not token:
        return "Sir, no GitHub token is configured."

    query = urllib.parse.urlencode({"visibility": visibility, "sort": sort, "per_page": min(100, limit)})
    code, data = _api_request(f"/user/repos?{query}", token=token)
    if code != 200:
        return f"Error listing repositories: {data.get('error', 'Unknown error')}"

    if not isinstance(data, list) or not data:
        return "You have no repositories matching the query, sir."

    lines = [f"**Your GitHub Repositories ({len(data)} displayed, sorted by {sort})**:"]
    for idx, r in enumerate(data[:limit], 1):
        name = r.get("name", "untitled")
        is_private = "🔒 Private" if r.get("private") else "🌐 Public"
        stars = r.get("stargazers_count", 0)
        lang = r.get("language") or "General"
        desc = (r.get("description") or "No description")[:60]
        url = r.get("html_url", "")
        lines.append(f"{idx}. **{name}** [{is_private} | {lang} | ⭐{stars}]\n   {desc}\n   <{url}>")

    _log(f"Listed {len(data[:limit])} repositories", player)
    return "\n".join(lines)


def get_repo(repo_name: str, player=None) -> str:
    """Fetch details about a specific repository."""
    token, username, _ = _get_credentials()
    if "/" not in repo_name:
        full_name = f"{username}/{repo_name.strip()}"
    else:
        full_name = repo_name.strip()

    code, r = _api_request(f"/repos/{full_name}", token=token)
    if code != 200:
        return f"Could not find repository '{full_name}': {r.get('error', 'Not found')}"

    name = r.get("name")
    is_private = "Private" if r.get("private") else "Public"
    desc = r.get("description") or "No description provided"
    branch = r.get("default_branch", "main")
    stars = r.get("stargazers_count", 0)
    forks = r.get("forks_count", 0)
    open_issues = r.get("open_issues_count", 0)
    clone_url = r.get("clone_url", "")
    html_url = r.get("html_url", "")
    updated = (r.get("updated_at") or "")[:10]

    _log(f"Details retrieved for repository {full_name}", player)
    return (
        f"**Repository: {full_name}** ({is_private})\n"
        f"• Description: {desc}\n"
        f"• Default Branch: `{branch}`\n"
        f"• Stars: {stars} | Forks: {forks} | Open Issues/PRs: {open_issues}\n"
        f"• Last Updated: {updated}\n"
        f"• Web URL: {html_url}\n"
        f"• Clone URL: `{clone_url}`"
    )


def create_repo(
    repo_name: str,
    description: str = "",
    private: bool = False,
    auto_init: bool = True,
    player=None,
) -> str:
    """Creates a new repository under the user's GitHub account."""
    token, username, _ = _get_credentials()
    payload = {
        "name": repo_name.strip(),
        "description": description.strip(),
        "private": bool(private),
        "auto_init": bool(auto_init),
    }

    _log(f"Creating repository '{repo_name}' (private={private})...", player)
    code, res = _api_request("/user/repos", method="POST", data=payload, token=token)
    if code in (200, 201):
        html_url = res.get("html_url", f"https://github.com/{username}/{repo_name}")
        clone_url = res.get("clone_url", "")
        _log(f"Repository created: {html_url}", player)
        return (
            f"Successfully created GitHub repository **{repo_name}**, sir.\n"
            f"• Visibility: {'Private 🔒' if private else 'Public 🌐'}\n"
            f"• URL: {html_url}\n"
            f"• Clone command: `git clone {clone_url}`"
        )
    return f"Failed to create repository '{repo_name}': {res.get('error', 'Error creating repo')}"


def list_issues(repo_name: str, state: str = "open", limit: int = 10, player=None) -> str:
    """Lists issues for a repository."""
    token, username, _ = _get_credentials()
    full_name = repo_name if "/" in repo_name else f"{username}/{repo_name.strip()}"
    code, issues = _api_request(f"/repos/{full_name}/issues?state={state}&per_page={limit}", token=token)
    if code != 200:
        return f"Error retrieving issues for '{full_name}': {issues.get('error', 'Failed')}"

    if not isinstance(issues, list) or not issues:
        return f"No {state} issues found for '{full_name}', sir."

    lines = [f"**{state.capitalize()} Issues in {full_name}**:"]
    for i in issues[:limit]:
        # Filter out pull requests which GitHub also includes under /issues
        if "pull_request" in i:
            continue
        num = i.get("number")
        title = i.get("title", "Untitled")
        author = i.get("user", {}).get("login", "unknown")
        url = i.get("html_url", "")
        lines.append(f"• #{num}: **{title}** (by @{author})\n  <{url}>")

    _log(f"Found {len(lines)-1} issues in {full_name}", player)
    return "\n".join(lines)


def create_issue(repo_name: str, title: str, body: str = "", labels: list = None, player=None) -> str:
    """Creates a new issue in a repository."""
    token, username, _ = _get_credentials()
    full_name = repo_name if "/" in repo_name else f"{username}/{repo_name.strip()}"
    payload = {"title": title.strip(), "body": body.strip(), "labels": labels or []}

    code, res = _api_request(f"/repos/{full_name}/issues", method="POST", data=payload, token=token)
    if code in (200, 201):
        num = res.get("number")
        url = res.get("html_url", "")
        _log(f"Created issue #{num} in {full_name}", player)
        return f"Created Issue #{num} in **{full_name}**: '{title}'\nLink: {url}"
    return f"Failed to create issue in '{full_name}': {res.get('error', 'Failed')}"


def list_prs(repo_name: str, state: str = "open", limit: int = 10, player=None) -> str:
    """Lists pull requests for a repository."""
    token, username, _ = _get_credentials()
    full_name = repo_name if "/" in repo_name else f"{username}/{repo_name.strip()}"
    code, prs = _api_request(f"/repos/{full_name}/pulls?state={state}&per_page={limit}", token=token)
    if code != 200:
        return f"Error retrieving PRs for '{full_name}': {prs.get('error', 'Failed')}"

    if not isinstance(prs, list) or not prs:
        return f"No {state} pull requests found in '{full_name}', sir."

    lines = [f"**{state.capitalize()} Pull Requests in {full_name}**:"]
    for pr in prs[:limit]:
        num = pr.get("number")
        title = pr.get("title")
        author = pr.get("user", {}).get("login", "unknown")
        head = pr.get("head", {}).get("ref", "")
        base = pr.get("base", {}).get("ref", "")
        url = pr.get("html_url", "")
        lines.append(f"• PR #{num}: **{title}** (`{head}` → `{base}`) by @{author}\n  <{url}>")

    _log(f"Retrieved {len(prs[:limit])} PRs for {full_name}", player)
    return "\n".join(lines)


def create_pr(
    repo_name: str,
    title: str,
    head: str,
    base: str = "main",
    body: str = "",
    player=None,
) -> str:
    """Opens a new pull request."""
    token, username, _ = _get_credentials()
    full_name = repo_name if "/" in repo_name else f"{username}/{repo_name.strip()}"
    payload = {"title": title.strip(), "head": head.strip(), "base": base.strip(), "body": body.strip()}

    code, res = _api_request(f"/repos/{full_name}/pulls", method="POST", data=payload, token=token)
    if code in (200, 201):
        num = res.get("number")
        url = res.get("html_url", "")
        _log(f"Opened PR #{num} on {full_name}", player)
        return f"Pull Request #{num} created on **{full_name}**: '{title}'\nLink: {url}"
    return f"Failed to open PR on '{full_name}': {res.get('error', 'Failed')}"


def list_commits(repo_name: str, limit: int = 5, player=None) -> str:
    """Lists recent commits on a repository."""
    token, username, _ = _get_credentials()
    full_name = repo_name if "/" in repo_name else f"{username}/{repo_name.strip()}"
    code, commits = _api_request(f"/repos/{full_name}/commits?per_page={limit}", token=token)
    if code != 200:
        return f"Error fetching commits for '{full_name}': {commits.get('error', 'Failed')}"

    if not isinstance(commits, list) or not commits:
        return f"No commits found in '{full_name}', sir."

    lines = [f"**Recent Commits in {full_name}**:"]
    for c in commits[:limit]:
        sha = c.get("sha", "")[:7]
        msg = (c.get("commit", {}).get("message") or "").splitlines()[0][:70]
        author = c.get("commit", {}).get("author", {}).get("name") or "unknown"
        date = (c.get("commit", {}).get("author", {}).get("date") or "")[:10]
        lines.append(f"• `{sha}`: {msg} (by {author} on {date})")

    _log(f"Listed commits for {full_name}", player)
    return "\n".join(lines)


def get_notifications(unread_only: bool = True, player=None) -> str:
    """Checks user notifications on GitHub."""
    token, _, _ = _get_credentials()
    q = "all=false" if unread_only else "all=true"
    code, notifs = _api_request(f"/notifications?{q}&per_page=10", token=token)
    if code != 200:
        return f"Could not fetch notifications: {notifs.get('error', 'Failed')}"

    if not isinstance(notifs, list) or not notifs:
        return "You have no unread GitHub notifications, sir."

    lines = [f"**Your GitHub Notifications ({len(notifs)} unread)**:"]
    for n in notifs[:10]:
        subject = n.get("subject", {}).get("title", "Update")
        stype = n.get("subject", {}).get("type", "Item")
        repo = n.get("repository", {}).get("full_name", "")
        lines.append(f"• [{stype}] **{repo}**: {subject}")

    _log(f"Checked notifications ({len(notifs)} items)", player)
    return "\n".join(lines)


def clone_repo(repo_name: str, dest_dir: str = "", player=None) -> str:
    """Clones a GitHub repository to the local filesystem."""
    token, username, _ = _get_credentials()
    full_name = repo_name if "/" in repo_name else f"{username}/{repo_name.strip()}"
    bare_name = full_name.split("/")[-1]

    target = Path(dest_dir).resolve() if dest_dir else Path.cwd() / bare_name
    if target.exists() and any(target.iterdir()):
        return f"Target directory '{target}' already exists and is not empty, sir."

    clone_url = f"https://github.com/{full_name}.git"
    _log(f"Cloning {clone_url} into {target}...", player)
    try:
        res = subprocess.run(
            ["git", "clone", clone_url, str(target)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if res.returncode == 0:
            _log(f"Cloned successfully to {target}", player)
            return f"Successfully cloned **{full_name}** to `{target}`, sir."
        return f"Failed to clone repository: {res.stderr or res.stdout}"
    except Exception as e:
        return f"Error executing git clone: {e}"


def push_to_github(
    repo_name: str,
    local_dir: str = "",
    commit_message: str = "Update via JARVIS",
    branch: str = "main",
    private: bool = False,
    player=None,
) -> str:
    """Initializes and pushes a local project folder to GitHub.

    If the repository does not exist on GitHub, it automatically creates it.
    Uses authenticated git credential helper or token for seamless push.
    """
    token, username, email = _get_credentials()
    if not token:
        return "Sir, no GitHub token is configured. Cannot push."

    path = Path(local_dir).resolve() if local_dir else Path.cwd()
    if not path.exists():
        return f"Local directory '{path}' does not exist, sir."

    repo_slug = repo_name.strip().split("/")[-1]
    full_repo = f"{username}/{repo_slug}"

    _log(f"Starting GitHub push for '{repo_slug}' from '{path}'...", player)

    # 1. Check if repo exists on GitHub; if not, create it
    code, rinfo = _api_request(f"/repos/{full_repo}", token=token)
    if code != 200:
        _log(f"Repository '{full_repo}' does not exist. Creating it on GitHub...", player)
        create_res = create_repo(repo_slug, description=f"Project {repo_slug}", private=private, auto_init=False, player=player)
        if "Failed" in create_res:
            return f"Could not create repository on GitHub: {create_res}"

    # 2. Check or initialize local git repository
    def _run_git(cmd: list[str]) -> tuple[int, str, str]:
        p = subprocess.run(cmd, cwd=str(path), capture_output=True, text=True, timeout=40)
        return p.returncode, p.stdout.strip(), p.stderr.strip()

    git_dir = path / ".git"
    if not git_dir.exists():
        rc, _, err = _run_git(["git", "init"])
        if rc != 0:
            return f"Failed to initialize git repository: {err}"

    # Configure user name/email locally if not set
    _run_git(["git", "config", "user.name", "Yash Surve"])
    _run_git(["git", "config", "user.email", email or "yashsurve2019@gmail.com"])

    # 3. Add and commit files
    _run_git(["git", "add", "."])
    rc, out, err = _run_git(["git", "commit", "-m", commit_message])
    # Note: commit might return rc!=0 if nothing changed (working tree clean)

    # 4. Configure remote URL (injecting token safely for push)
    remote_url = f"https://{token}@github.com/{full_repo}.git"
    clean_url = f"https://github.com/{full_repo}.git"

    # Check existing origin
    rc, remotes, _ = _run_git(["git", "remote"])
    if "origin" in remotes.split():
        _run_git(["git", "remote", "set-url", "origin", remote_url])
    else:
        _run_git(["git", "remote", "add", "origin", remote_url])

    # 5. Push to branch
    _run_git(["git", "branch", "-M", branch])
    rc, out, err = _run_git(["git", "push", "-u", "origin", branch])

    # Reset origin to clean url without embedded token for security
    _run_git(["git", "remote", "set-url", "origin", clean_url])

    if rc == 0:
        html_url = f"https://github.com/{full_repo}"
        _log(f"Pushed code successfully to {html_url}", player)
        return (
            f"🚀 **Successfully pushed project to GitHub!**\n"
            f"• Repository: **{full_repo}**\n"
            f"• Branch: `{branch}`\n"
            f"• Commit: \"{commit_message}\"\n"
            f"• Web URL: {html_url}"
        )
    else:
        return f"Git push failed: {err or out}"


def search_repos(query: str, limit: int = 5, player=None) -> str:
    """Searches GitHub for repositories."""
    token, _, _ = _get_credentials()
    q = urllib.parse.quote(query.strip())
    code, res = _api_request(f"/search/repositories?q={q}&per_page={limit}", token=token)
    if code != 200:
        return f"Search failed: {res.get('error', 'Failed')}"

    items = res.get("items", [])
    if not items:
        return f"No GitHub repositories found matching '{query}', sir."

    lines = [f"**GitHub Search Results for '{query}'**:"]
    for r in items[:limit]:
        fn = r.get("full_name")
        stars = r.get("stargazers_count", 0)
        desc = (r.get("description") or "No description")[:60]
        url = r.get("html_url", "")
        lines.append(f"• **{fn}** (⭐{stars})\n  {desc}\n  <{url}>")

    _log(f"Search found {len(items[:limit])} items", player)
    return "\n".join(lines)


# ── Action Router ─────────────────────────────────────────────────────────────

def github_action(parameters: dict, player=None, **kwargs) -> str:
    """Master entrypoint for GitHub tool dispatch."""
    p = parameters or {}
    action = (p.get("action") or "").strip().lower()

    if action in ("get_profile", "profile", "whoami"):
        return get_profile(player=player)

    elif action in ("list_repos", "repos", "repositories"):
        vis = p.get("visibility", "all")
        sort = p.get("sort", "updated")
        lim = int(p.get("limit", 15))
        return list_repos(visibility=vis, sort=sort, limit=lim, player=player)

    elif action in ("get_repo", "repo_info"):
        repo = p.get("repo_name", "") or p.get("name", "")
        if not repo:
            return "Please provide the name of the repository, sir."
        return get_repo(repo_name=repo, player=player)

    elif action in ("create_repo", "new_repo"):
        repo = p.get("repo_name", "") or p.get("name", "")
        if not repo:
            return "Please provide a name for the new repository, sir."
        desc = p.get("description", "")
        priv = bool(p.get("private", False))
        auto = bool(p.get("auto_init", True))
        return create_repo(repo_name=repo, description=desc, private=priv, auto_init=auto, player=player)

    elif action in ("list_issues", "issues"):
        repo = p.get("repo_name", "") or p.get("name", "")
        if not repo:
            return "Please specify which repository's issues to view, sir."
        state = p.get("state", "open")
        lim = int(p.get("limit", 10))
        return list_issues(repo_name=repo, state=state, limit=lim, player=player)

    elif action in ("create_issue", "new_issue"):
        repo = p.get("repo_name", "") or p.get("name", "")
        title = p.get("title", "")
        if not repo or not title:
            return "Please specify both repository name and issue title, sir."
        body = p.get("body", "")
        labels = p.get("labels") or []
        return create_issue(repo_name=repo, title=title, body=body, labels=labels, player=player)

    elif action in ("list_prs", "prs", "pull_requests"):
        repo = p.get("repo_name", "") or p.get("name", "")
        if not repo:
            return "Please specify the repository to check pull requests for, sir."
        state = p.get("state", "open")
        lim = int(p.get("limit", 10))
        return list_prs(repo_name=repo, state=state, limit=lim, player=player)

    elif action in ("create_pr", "new_pr"):
        repo = p.get("repo_name", "") or p.get("name", "")
        title = p.get("title", "")
        head = p.get("head", "")
        base = p.get("base", "main")
        body = p.get("body", "")
        if not repo or not title or not head:
            return "Please provide repository, PR title, and head branch, sir."
        return create_pr(repo_name=repo, title=title, head=head, base=base, body=body, player=player)

    elif action in ("list_commits", "commits", "history"):
        repo = p.get("repo_name", "") or p.get("name", "")
        if not repo:
            return "Please specify which repository's commits to view, sir."
        lim = int(p.get("limit", 5))
        return list_commits(repo_name=repo, limit=lim, player=player)

    elif action in ("get_notifications", "notifications", "alerts"):
        unread = p.get("unread_only", True)
        return get_notifications(unread_only=unread, player=player)

    elif action in ("clone_repo", "clone"):
        repo = p.get("repo_name", "") or p.get("name", "")
        dest = p.get("dest_dir", "") or p.get("path", "")
        if not repo:
            return "Please specify the repository to clone, sir."
        return clone_repo(repo_name=repo, dest_dir=dest, player=player)

    elif action in ("push_to_github", "push", "publish"):
        repo = p.get("repo_name", "") or p.get("name", "")
        if not repo:
            return "Please provide a name for the repository to push to, sir."
        loc = p.get("local_dir", "") or p.get("path", "")
        msg = p.get("commit_message", "Update via JARVIS")
        branch = p.get("branch", "main")
        priv = bool(p.get("private", False))
        return push_to_github(
            repo_name=repo,
            local_dir=loc,
            commit_message=msg,
            branch=branch,
            private=priv,
            player=player,
        )

    elif action in ("search_repos", "search"):
        query = p.get("query", "")
        if not query:
            return "Please specify a search term, sir."
        lim = int(p.get("limit", 5))
        return search_repos(query=query, limit=lim, player=player)

    else:
        # Default fallback: show summary status of GitHub connection
        return get_profile(player=player)


# ── Tool declaration (auto-discovered by core/action_loader.py) ──────────────
TOOL = {
    "name": "github_manager",
    "description": (
        "Integrated GitHub management for user Yash Surve (YashSurve2006). "
        "Allows listing repositories, viewing repo details and commit logs, "
        "creating new repositories, cloning repositories locally, automated "
        "pushing of local projects to GitHub, managing issues and pull requests, "
        "checking unread notifications, and searching repositories."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": (
                    "get_profile | list_repos | get_repo | create_repo | clone_repo | "
                    "push_to_github | list_issues | create_issue | list_prs | create_pr | "
                    "list_commits | get_notifications | search_repos"
                ),
            },
            "repo_name": {
                "type": "STRING",
                "description": "Name of the repository (e.g. 'smart-campus-hub' or 'YashSurve2006/smart-campus-hub')",
            },
            "description": {
                "type": "STRING",
                "description": "Description for new repository or issue",
            },
            "private": {
                "type": "BOOLEAN",
                "description": "True for private repository, False for public (default False)",
            },
            "title": {
                "type": "STRING",
                "description": "Title for issue or pull request",
            },
            "body": {
                "type": "STRING",
                "description": "Body text for issue or pull request",
            },
            "head": {
                "type": "STRING",
                "description": "Head branch for pull request (e.g. 'feature-branch')",
            },
            "base": {
                "type": "STRING",
                "description": "Base branch for pull request (default 'main')",
            },
            "local_dir": {
                "type": "STRING",
                "description": "Local directory path to push or clone to",
            },
            "commit_message": {
                "type": "STRING",
                "description": "Commit message for push_to_github",
            },
            "visibility": {
                "type": "STRING",
                "description": "Visibility filter for list_repos: all | public | private",
            },
            "sort": {
                "type": "STRING",
                "description": "Sort order for list_repos: updated | created | pushed | full_name",
            },
            "state": {
                "type": "STRING",
                "description": "State filter for issues/PRs: open | closed | all",
            },
            "limit": {
                "type": "INTEGER",
                "description": "Maximum number of items to return (default 10-15)",
            },
            "query": {
                "type": "STRING",
                "description": "Search query for search_repos",
            },
        },
        "required": ["action"],
    },
    "handler": github_action,
}
