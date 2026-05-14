import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import FrozenSet, Optional, Tuple


@dataclass(frozen=True)
class Settings:
    profile: str
    token: str
    admin_ids: FrozenSet[int]
    control_mode: str
    service: str
    log_file: str
    mc_port: int
    rcon_host: str
    rcon_port: int
    rcon_password: Optional[str]
    backup_paths: Tuple[str, ...]
    backup_dir: str
    backup_keep: int
    monitor_interval: int
    start_timeout: int
    stop_timeout: int
    max_log_mb: int
    project_root: Path


PROFILE_ALIASES = {
    "develop": "dev",
    "development": "dev",
    "local": "dev",
    "main": "prod",
    "master": "prod",
    "production": "prod",
}


def _required_env(values, name):
    value = values.get(name)
    if not value:
        raise RuntimeError("Не задана переменная окружения {}".format(name))
    return value


def _normalize_profile(profile):
    value = (profile or "").strip().lower()
    if not value:
        return None
    return PROFILE_ALIASES.get(value, value)


def _profile_from_git_branch(project_root):
    try:
        process = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(project_root),
            text=True,
            capture_output=True,
            timeout=3,
        )
    except Exception:
        return None

    if process.returncode != 0:
        return None

    branch = process.stdout.strip()
    if branch in ("master", "main"):
        return "prod"
    if branch in ("dev", "develop", "development"):
        return "dev"
    return None


def _strip_env_value(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def _load_env_file(path):
    values = {}
    if not path or not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue

        values[key] = _strip_env_value(value)

    return values


def _parse_admin_ids(value):
    try:
        return frozenset(int(item.strip()) for item in value.split(",") if item.strip())
    except ValueError as exc:
        raise RuntimeError("ADMIN_IDS должен содержать числовые Telegram ID через запятую") from exc


def _resolve_path(value, project_root):
    path = Path(value).expanduser()
    if path.is_absolute():
        return str(path)
    return str((project_root / path).resolve())


def _resolve_paths(value, project_root):
    return tuple(_resolve_path(item.strip(), project_root) for item in value.split(",") if item.strip())


def _load_profile_env(profile, env_file, project_root):
    if env_file:
        path = Path(env_file).expanduser()
        if not path.is_absolute():
            path = project_root / path
        file_values = _load_env_file(path)
        detected = _normalize_profile(profile)
        detected = detected or _normalize_profile(os.environ.get("BOT_PROFILE"))
        detected = detected or _normalize_profile(file_values.get("BOT_PROFILE"))
        detected = detected or _profile_from_git_branch(project_root)
        detected = detected or "prod"
        return detected, _merge_env_values(file_values)

    base_values = _load_env_file(project_root / ".env")

    detected = _normalize_profile(profile)
    detected = detected or _normalize_profile(os.environ.get("BOT_PROFILE"))
    detected = detected or _normalize_profile(base_values.get("BOT_PROFILE"))
    detected = detected or _profile_from_git_branch(project_root)
    detected = detected or "prod"

    profile_values = _load_env_file(project_root / ".env.{}".format(detected))
    values = {}
    values.update(base_values)
    values.update(profile_values)
    return detected, _merge_env_values(values)


def _merge_env_values(file_values):
    values = dict(file_values)
    values.update(os.environ)
    return values


def _control_mode(profile, values):
    value = values.get("MC_CONTROL_MODE")
    if value:
        value = value.strip().lower()
    else:
        value = "mock" if profile == "dev" else "systemd"

    if value not in ("systemd", "mock"):
        raise RuntimeError("MC_CONTROL_MODE должен быть systemd или mock")
    return value


def load_settings(profile=None, env_file=None, project_root=None):
    root = Path(project_root or Path.cwd()).resolve()
    profile, values = _load_profile_env(profile, env_file, root)
    profile = _normalize_profile(profile)

    return Settings(
        profile=profile,
        token=_required_env(values, "BOT_TOKEN"),
        admin_ids=_parse_admin_ids(_required_env(values, "ADMIN_IDS")),
        control_mode=_control_mode(profile, values),
        service=values.get("MC_SERVICE", "minecraft.service"),
        log_file=_resolve_path(values.get("MC_LATEST_LOG", "/root/server/logs/latest.log"), root),
        mc_port=int(values.get("MC_PORT", "25565")),
        rcon_host=values.get("MC_RCON_HOST", "127.0.0.1"),
        rcon_port=int(values.get("MC_RCON_PORT", "25575")),
        rcon_password=values.get("MC_RCON_PASSWORD"),
        backup_paths=_resolve_paths(values.get("MC_BACKUP_PATHS", "/root/server/world"), root),
        backup_dir=_resolve_path(values.get("MC_BACKUP_DIR", "backups"), root),
        backup_keep=int(values.get("MC_BACKUP_KEEP", "5")),
        monitor_interval=int(values.get("MC_MONITOR_INTERVAL", "30")),
        start_timeout=int(values.get("MC_START_TIMEOUT", "180")),
        stop_timeout=int(values.get("MC_STOP_TIMEOUT", "180")),
        max_log_mb=int(values.get("MAX_LOG_SEND_MB", "45")),
        project_root=root,
    )
