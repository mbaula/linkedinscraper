"""
Configuration utilities.
"""
import json
import os
import re
from typing import Any, Dict, List, Optional

_ACTIVE_MARKER = "active_config.txt"


def get_project_root() -> str:
    """Repository root (parent of the utils package)."""
    return os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def _is_allowed_relative_config_path(root: str, rel: str) -> bool:
    """Reject path traversal; only config.json or configs/*.json."""
    if not rel or not isinstance(rel, str):
        return False
    rel = rel.strip().replace("\\", "/")
    if rel.startswith("/") or ".." in rel.split("/"):
        return False
    if rel == "config.json":
        return True
    if not rel.startswith("configs/"):
        return False
    rest = rel[len("configs/") :]
    if "/" in rest or not rest.endswith(".json"):
        return False
    if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*\.json$", rest):
        return False
    full = os.path.normpath(os.path.join(root, rel))
    root_norm = os.path.normpath(os.path.abspath(root))
    if not (full == root_norm or full.startswith(root_norm + os.sep)):
        return False
    return True


def get_active_config_relative_path() -> str:
    """Relative path from project root to the active config file."""
    root = get_project_root()
    marker = os.path.join(root, _ACTIVE_MARKER)
    default = "config.json"
    if not os.path.isfile(marker):
        return default
    try:
        with open(marker, "r", encoding="utf-8") as f:
            rel = f.read().strip().replace("\\", "/")
    except OSError:
        return default
    if not rel:
        return default
    if not _is_allowed_relative_config_path(root, rel):
        return default
    full = os.path.normpath(os.path.join(root, rel))
    if os.path.isfile(full):
        return rel
    return default


def get_active_config_path() -> str:
    """Absolute path to the active JSON config file."""
    root = get_project_root()
    rel = get_active_config_relative_path()
    return os.path.normpath(os.path.join(root, rel))


def set_active_config_relative_path(rel: str) -> str:
    """
    Persist active config as a path relative to project root.
    Returns the normalized relative path that was written.
    """
    root = get_project_root()
    rel = rel.strip().replace("\\", "/")
    if not _is_allowed_relative_config_path(root, rel):
        raise ValueError("Invalid or disallowed config path")
    full = os.path.normpath(os.path.join(root, rel))
    if not os.path.isfile(full):
        raise FileNotFoundError(f"Config file not found: {rel}")
    marker = os.path.join(root, _ACTIVE_MARKER)
    with open(marker, "w", encoding="utf-8") as f:
        f.write(rel + "\n")
    return rel


def load_config(file_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Load configuration from a JSON file.

    Args:
        file_name: Path to JSON. If None, loads the active config file.

    Returns:
        dict: Configuration dictionary
    """
    path = file_name if file_name is not None else get_active_config_path()
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def sanitize_profile_name(name: str) -> str:
    name = (name or "").strip()
    if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$", name):
        raise ValueError(
            "Profile name must start with a letter or number and contain only letters, numbers, underscores, and hyphens (max 64 chars)."
        )
    return name


def ensure_configs_dir() -> str:
    root = get_project_root()
    d = os.path.join(root, "configs")
    os.makedirs(d, exist_ok=True)
    return d


def list_config_profiles() -> List[Dict[str, Any]]:
    """Named profiles under configs/ plus root config.json if present."""
    root = get_project_root()
    active_rel = get_active_config_relative_path()
    profiles: List[Dict[str, Any]] = []

    default_path = os.path.join(root, "config.json")
    if os.path.isfile(default_path):
        profiles.append(
            {
                "name": "config.json (root)",
                "relative_path": "config.json",
                "active": active_rel == "config.json",
            }
        )

    cfg_dir = os.path.join(root, "configs")
    if os.path.isdir(cfg_dir):
        for fn in sorted(os.listdir(cfg_dir)):
            if not fn.endswith(".json"):
                continue
            fp = os.path.join(cfg_dir, fn)
            if not os.path.isfile(fp):
                continue
            rel = f"configs/{fn}".replace("\\", "/")
            profiles.append(
                {
                    "name": fn[: -len(".json")],
                    "relative_path": rel,
                    "active": rel == active_rel,
                }
            )
    return profiles


def save_profile_json(name: str, config_dict: Dict[str, Any]) -> str:
    """Write config_dict to configs/{name}.json. Returns relative path."""
    slug = sanitize_profile_name(name)
    ensure_configs_dir()
    root = get_project_root()
    rel = f"configs/{slug}.json".replace("\\", "/")
    full = os.path.join(root, "configs", f"{slug}.json")
    with open(full, "w", encoding="utf-8") as f:
        json.dump(config_dict, f, indent=4, ensure_ascii=False)
    return rel


def delete_profile_json(name: str) -> bool:
    """Remove configs/{name}.json. Returns True if a file was removed."""
    slug = sanitize_profile_name(name)
    root = get_project_root()
    full = os.path.join(root, "configs", f"{slug}.json")
    if not os.path.isfile(full):
        return False
    os.remove(full)
    return True
