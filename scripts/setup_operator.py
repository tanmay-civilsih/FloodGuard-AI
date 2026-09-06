"""Create/rotate one local operator without storing its plaintext bearer token."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import tempfile
from pathlib import Path

KEY = "FLOODGUARD_OPERATORS_JSON"


def configure(env_file: Path, subject: str, *, rotate: bool = False) -> str:
    if re.fullmatch(r"[A-Za-z0-9_.@ -]{2,200}", subject) is None or subject != subject.strip():
        raise ValueError("Use a 2-200 character subject with letters, digits, spaces, . _ @ or -")
    original = env_file.read_text(encoding="utf-8") if env_file.exists() else ""
    lines = original.splitlines()
    matches = [index for index, line in enumerate(lines) if line.startswith(KEY + "=")]
    if len(matches) > 1:
        raise ValueError("Duplicate operator configuration; no changes were made")
    accounts: dict[str, object] = {}
    if matches:
        value = lines[matches[0]].split("=", 1)[1].strip().strip("'")
        if value:
            accounts = json.loads(value)
        if not isinstance(accounts, dict):
            raise ValueError("Existing operator configuration must be a JSON object")
    if subject in accounts and not rotate:
        raise ValueError("Operator already exists. Use its token, or explicitly pass --rotate")
    token = secrets.token_urlsafe(48)
    accounts[subject] = {
        "token_sha256": hashlib.sha256(token.encode("ascii")).hexdigest(),
        "roles": ["reviewer", "operator"],
    }
    setting = KEY + "='" + json.dumps(accounts, separators=(",", ":")) + "'"
    if matches:
        lines[matches[0]] = setting
    else:
        lines.append(setting)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=env_file.parent,
                                         prefix=".env-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write("\n".join(lines) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, env_file)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return token


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject", default="local-operator")
    parser.add_argument("--rotate", action="store_true")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    args = parser.parse_args()
    try:
        token = configure(args.env_file, args.subject, rotate=args.rotate)
    except (ValueError, OSError) as exc:
        raise SystemExit(str(exc)) from exc
    print(f"Operator subject: {args.subject}")
    print(f"Bearer token (shown once): {token}")
    print("Keep this token private. Enter it in the QA operator form; do not share it in logs.")
    print("Recreate the API container so Docker Compose loads the updated configuration.")


if __name__ == "__main__":
    main()
