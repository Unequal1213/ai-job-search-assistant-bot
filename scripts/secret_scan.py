"""Conservative current-tree secret-pattern scan with masked findings."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

PATTERNS = {
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "github_token": re.compile(r"\b(?:ghp|github_pat)_[A-Za-z0-9_]{20,}\b"),
    "telegram_token": re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{30,}\b"),
    "generic_api_key": re.compile(
        r"(?i)\b(?:api[_-]?key|secret[_-]?key)\s*[:=]\s*['\"]?[A-Za-z0-9_-]{20,}"
    ),
}

TEXT_SUFFIXES = {
    "",
    ".ini",
    ".in",
    ".md",
    ".py",
    ".toml",
    ".txt",
    ".yml",
    ".yaml",
}


def tracked_files() -> list[Path]:
    """Return tracked and untracked non-ignored project paths."""
    output = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        check=True,
        capture_output=True,
    ).stdout
    return [Path(item.decode()) for item in output.split(b"\0") if item]


def main() -> int:
    """Report category and path only; never echo a matching value."""
    findings: list[tuple[str, Path]] = []
    for path in tracked_files():
        if path.name == ".env" or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for category, pattern in PATTERNS.items():
            if pattern.search(content):
                findings.append((category, path))

    for category, path in findings:
        print(f"potential_{category}: {path} (value masked)")
    if findings:
        return 1
    print("No current-tree secret patterns found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
