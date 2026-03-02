"""Configuration files and utilities for Mini-SWE-Core.

Config search order:
1. Direct path (if absolute or exists)
2. {workdir}/configs/{name}.yaml  <-- Portable priority
3. MINI_CONFIG_DIR env var
4. Built-in config directory
5. Built-in extra config directory
"""

import os
from pathlib import Path
from typing import Optional

builtin_config_dir = Path(__file__).parent

# Safe mode fallback config (used when no config file is found)
SAFE_MODE_CONFIG = {
    "model": {
        "model_class": "litellm",
        "model_name": "gpt-4o-mini",
        "cost_tracking": "ignore_errors",
    },
    "environment": {
        "timeout": 60,
    },
    "agent": {
        "mode": "confirm",
        "cost_limit": 1.0,
        "step_limit": 20,
    },
}


def get_config_path(config_spec: str | Path, workdir: Optional[Path] = None) -> Path:
    """Get the path to a config file.

    Search order:
    1. Absolute path or relative path that exists
    2. {workdir}/configs/{config_spec}.yaml  <-- Portable priority
    3. MINI_CONFIG_DIR env variable directory
    4. Built-in config directory (package)
    5. Built-in extra config directory

    Args:
        config_spec: Config file name or path (e.g., "live" or "live.yaml" or "/path/to/config.yaml")
        workdir: Optional workdir override. If None, uses get_workdir() from minisweagent.

    Returns:
        Path to the config file

    Raises:
        FileNotFoundError: If config file is not found in any location
    """
    config_spec = Path(config_spec)

    # Add .yaml suffix if not present
    if config_spec.suffix != ".yaml":
        config_spec = config_spec.with_suffix(".yaml")

    # Determine workdir
    if workdir is None:
        from minisweagent import get_config_dir
        local_config_dir = get_config_dir()
    else:
        local_config_dir = Path(workdir) / ".miniswe" / "configs"

    # Build candidate list
    candidates = [
        Path(config_spec),                                      # 1. Direct path
        local_config_dir / config_spec.name,                    # 2. ./configs/ (PORTABLE)
        Path(os.getenv("MINI_CONFIG_DIR", ".")) / config_spec,  # 3. Env var
        builtin_config_dir / config_spec.name,                  # 4. Built-in
        builtin_config_dir / "extra" / config_spec.name,        # 5. Built-in extra
    ]

    # Also check legacy env var for backward compatibility
    legacy_config_dir = os.getenv("MSWEA_CONFIG_DIR")
    if legacy_config_dir:
        candidates.insert(3, Path(legacy_config_dir) / config_spec)

    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()

    raise FileNotFoundError(
        f"Config not found: {config_spec}\n"
        f"Searched locations:\n" + "\n".join(f"  - {c}" for c in candidates)
    )


def get_profile_path(profile_name: str, workdir: Optional[Path] = None) -> Path:
    """Get config path for a named profile.

    This is a convenience function for the --profile CLI argument.

    Example:
        --profile live  ->  ./configs/live.yaml

    Args:
        profile_name: Profile name without extension (e.g., "live", "dev", "default")
        workdir: Optional workdir override

    Returns:
        Path to the profile config file
    """
    return get_config_path(profile_name, workdir=workdir)


def load_config(config_spec: str | Path, workdir: Optional[Path] = None, safe_mode: bool = True) -> dict:
    """Load a config file as a dictionary.

    Args:
        config_spec: Config file name or path
        workdir: Optional workdir override
        safe_mode: If True, return SAFE_MODE_CONFIG on error instead of raising

    Returns:
        Config dictionary
    """
    import yaml

    try:
        config_path = get_config_path(config_spec, workdir=workdir)
        return yaml.safe_load(config_path.read_text()) or {}
    except FileNotFoundError:
        if safe_mode:
            return SAFE_MODE_CONFIG.copy()
        raise


def load_profile(profile_name: str, workdir: Optional[Path] = None, safe_mode: bool = True) -> dict:
    """Load a profile config as a dictionary.

    Args:
        profile_name: Profile name (e.g., "live", "dev")
        workdir: Optional workdir override
        safe_mode: If True, return SAFE_MODE_CONFIG on error

    Returns:
        Config dictionary
    """
    return load_config(profile_name, workdir=workdir, safe_mode=safe_mode)


__all__ = [
    "builtin_config_dir",
    "get_config_path",
    "get_profile_path",
    "load_config",
    "load_profile",
    "SAFE_MODE_CONFIG",
]
