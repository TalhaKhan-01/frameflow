"""Load secrets from the environment or ~/.config/frameflow/secrets.env. Values are never printed."""
import os
from pathlib import Path

SECRETS_FILE = Path(os.environ.get("FRAMEFLOW_SECRETS", "~/.config/frameflow/secrets.env")).expanduser()


def get(name):
    if os.environ.get(name):
        return os.environ[name]
    if SECRETS_FILE.exists():
        for line in SECRETS_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                if key.strip() == name and value.strip():
                    return value.strip()
    raise SystemExit(f"{name} is not set (environment or {SECRETS_FILE})")
