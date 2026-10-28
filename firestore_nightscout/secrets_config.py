"""Load firestore_nightscout/secrets.toml.

The file is a small subset of TOML: sections, comments, quoted strings, and
integers. That keeps the reader on the Python standard library.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent
SECRETS_PATH = ROOT / "secrets.toml"


def load_secrets(path: Path = SECRETS_PATH) -> dict:
    """Return {section: {key: value}}. Missing file is an error with the next step."""
    if not path.is_file():
        raise SystemExit(
            f"Missing {path.name}. Copy secrets.example.toml to secrets.toml and see README.md."
        )

    data: dict[str, dict] = {}
    section: str | None = None
    for line_number, raw in enumerate(path.read_text().splitlines(), start=1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip()
            data.setdefault(section, {})
            continue
        if section is None or "=" not in line:
            raise SystemExit(f"{path.name}:{line_number}: expected key = value under a [section]")
        key, raw_value = line.split("=", 1)
        data[section][key.strip()] = _parse_value(raw_value.strip())
    return data


def require(secrets: dict, section: str, key: str) -> str:
    """A non-empty string setting, or an error that names the key to fill in."""
    value = secrets.get(section, {}).get(key, "")
    if not isinstance(value, str) or not value.strip():
        raise SystemExit(f"secrets.toml [{section}] {key} is empty. See README.md.")
    return value


def key_path(secrets: dict) -> Path:
    """The service-account JSON path, relative to this directory unless absolute."""
    raw = require(secrets, "gcp", "service_account_key_file")
    path = Path(raw)
    if not path.is_absolute():
        path = ROOT / path
    return path


def set_string(path: Path, key: str, value: str) -> None:
    """Replace one top-level assignment, leaving comments and other keys alone."""
    lines = path.read_text().splitlines(keepends=True)
    prefix = f"{key}="
    prefix_spaced = f"{key} "
    found = False
    updated: list[str] = []
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith(prefix) or stripped.startswith(prefix_spaced):
            indent = line[: len(line) - len(stripped)]
            newline = "\n" if line.endswith("\n") else ""
            updated.append(f'{indent}{key} = "{value}"{newline}')
            found = True
        else:
            updated.append(line)
    if not found:
        raise SystemExit(f"{path.name} has no {key} assignment to fill in.")
    path.write_text("".join(updated))


def _parse_value(raw: str):
    if len(raw) >= 2 and raw[0] == '"' and raw[-1] == '"':
        return raw[1:-1]
    if raw.isdigit():
        return int(raw)
    return raw
