import hashlib
import json
from pathlib import Path

import pytest

from scripts.setup_operator import configure


def test_setup_keeps_other_settings_and_does_not_store_token(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("OTHER_SETTING=unchanged\n", encoding="utf-8")
    token = configure(env, "local-operator")
    result = env.read_text(encoding="utf-8")
    assert result.startswith("OTHER_SETTING=unchanged\n")
    assert token not in result
    assert hashlib.sha256(token.encode()).hexdigest() in result
    assert not list(tmp_path.glob(".env-*"))


def test_rotation_is_explicit_and_preserves_other_operators(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    old = configure(env, "first-operator")
    configure(env, "other-operator")
    before = env.read_text()
    with pytest.raises(ValueError, match="already exists"):
        configure(env, "first-operator")
    assert env.read_text() == before
    new = configure(env, "first-operator", rotate=True)
    assert new != old
    records = json.loads(env.read_text().split("=", 1)[1].strip().strip("'"))
    assert set(records) == {"first-operator", "other-operator"}
