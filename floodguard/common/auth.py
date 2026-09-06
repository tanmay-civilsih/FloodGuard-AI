"""Operator-scoped authorization for mutation endpoints in the local pilot API.

Configure FLOODGUARD_OPERATORS_JSON with subject -> {token_sha256, roles}.
Only digests belong in configuration; bearer tokens must never be logged or stored
in the registry. Missing/invalid configuration disables writes, not public QA reads.
This is scoped operator authentication, not proof of human presence or survey validity.
"""

from __future__ import annotations

import hashlib
import json
import re
import secrets
from dataclasses import dataclass

from fastapi import HTTPException, Request

from floodguard.common.config import Settings

ROLES = frozenset({"reviewer", "operator"})


@dataclass(frozen=True, slots=True)
class Operator:
    subject: str
    roles: frozenset[str]


def _accounts() -> list[tuple[Operator, str]]:
    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        values: dict[str, object] = {}
        for key, value in pairs:
            if key in values:
                raise ValueError("duplicate operator configuration key")
            values[key] = value
        return values

    try:
        raw = json.loads(Settings().operators_json, object_pairs_hook=unique)
        if not isinstance(raw, dict) or not 1 <= len(raw) <= 32:
            raise ValueError("configure 1 to 32 operators")
        accounts: list[tuple[Operator, str]] = []
        digests: set[str] = set()
        for subject, record in raw.items():
            if not isinstance(subject, str) or not 2 <= len(subject.strip()) <= 200:
                raise ValueError("invalid operator subject")
            if subject != subject.strip() or not isinstance(record, dict):
                raise ValueError("invalid operator record")
            if set(record) != {"token_sha256", "roles"}:
                raise ValueError("unexpected operator fields")
            digest, roles = record["token_sha256"], record["roles"]
            if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
                raise ValueError("invalid operator token digest")
            if digest in digests:
                raise ValueError("operator tokens must be unique")
            if (
                not isinstance(roles, list) or not roles
                or any(not isinstance(role, str) or role not in ROLES for role in roles)
            ):
                raise ValueError("invalid operator roles")
            digests.add(digest)
            accounts.append((Operator(subject, frozenset(roles)), digest))
        return accounts
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=503,
            detail="Writes are disabled: configure operator credentials on the server"
        ) from exc


def authenticate(authorization: str | None, *, role: str) -> Operator:
    accounts = _accounts()
    scheme, separator, token = (authorization or "").partition(" ")
    if (
        scheme.lower() != "bearer" or not separator or not 32 <= len(token) <= 1024
        or not token.isascii() or any(character.isspace() for character in token)
    ):
        raise HTTPException(status_code=401, detail="Valid bearer credentials required",
                            headers={"WWW-Authenticate": "Bearer"})
    digest = hashlib.sha256(token.encode("ascii")).hexdigest()
    matched = None
    for account, expected in accounts:
        if secrets.compare_digest(digest, expected):
            matched = account
    if matched is None:
        raise HTTPException(status_code=401, detail="Valid bearer credentials required",
                            headers={"WWW-Authenticate": "Bearer"})
    if role not in matched.roles:
        raise HTTPException(status_code=403, detail="Operator is not authorized for this action")
    return matched


async def require_write_access(request: Request) -> None:
    """Application-wide write guard; review identity must match the server's subject."""
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    path = request.url.path.rstrip("/")
    review = path.startswith("/reconstruction/maps/") and path.endswith("/reviews")
    operator = authenticate(request.headers.get("Authorization"),
                            role="reviewer" if review else "operator")
    request.state.operator = operator
    if review:
        try:
            payload = await request.json()
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Review requires a JSON object") from exc
        if not isinstance(payload, dict) or payload.get("reviewer") != operator.subject:
            raise HTTPException(status_code=403,
                                detail="Reviewer must match the authenticated operator subject")
