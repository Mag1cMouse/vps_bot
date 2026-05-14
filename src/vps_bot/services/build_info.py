import html
import json
import subprocess
from pathlib import Path


def build_info_text(project_root):
    info = load_build_info(project_root)

    lines = ["<b>Версия бота</b>"]
    lines.append("Branch: <code>{}</code>".format(html.escape(info.get("branch") or "unknown")))
    lines.append("Commit: <code>{}</code>".format(html.escape(short_sha(info.get("sha")))))

    if info.get("built_at"):
        lines.append("Build time: <code>{}</code>".format(html.escape(info["built_at"])))
    if info.get("run_url"):
        lines.append("Actions: {}".format(html.escape(info["run_url"])))
    if info.get("source") == "git":
        lines.append("Source: <code>local git</code>")
    elif info.get("source") == "missing":
        lines.append("Source: <code>BUILD_INFO.json отсутствует</code>")

    return "\n".join(lines)


def load_build_info(project_root):
    root = Path(project_root)
    path = root / "BUILD_INFO.json"

    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except (OSError, json.JSONDecodeError):
            pass

    git_info = load_git_info(root)
    if git_info:
        git_info["source"] = "git"
        return git_info

    return {"branch": "unknown", "sha": "unknown", "source": "missing"}


def load_git_info(project_root):
    try:
        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(project_root),
            text=True,
            capture_output=True,
            timeout=3,
        )
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(project_root),
            text=True,
            capture_output=True,
            timeout=3,
        )
    except Exception:
        return None

    if branch.returncode != 0 or sha.returncode != 0:
        return None

    return {"branch": branch.stdout.strip(), "sha": sha.stdout.strip()}


def short_sha(value):
    value = value or "unknown"
    if value == "unknown":
        return value
    return value[:12]
