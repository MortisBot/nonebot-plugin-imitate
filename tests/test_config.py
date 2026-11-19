"""配置默认值、模式解析、边界钳制与安全默认。"""

from __future__ import annotations

import dataclasses

import pytest
from nonebot_plugin_imitate.config import (
    DEFAULT_DB_PATH,
    ImitateConfig,
    load_config,
    parse_mode,
)


def test_defaults_are_safe():
    cfg = load_config()
    assert cfg.enabled is False
    assert cfg.groups == frozenset()
    assert cfg.mode == "replay"
    assert cfg.db_path == DEFAULT_DB_PATH == "data/imitate/imitate.db"
    assert cfg.probability == 0.02
    assert cfg.max_length == 20
    assert cfg.max_records == 100
    assert cfg.min_corpus == 500
    assert cfg.order == 2
    assert cfg.detect_robots is True
    assert cfg.bot_qqs == frozenset()
    assert cfg.dedupe is True
    assert cfg.target_arg is True
    assert cfg.cooldown_seconds == 0.0
    assert len(cfg.block_patterns) == 2


def test_empty_config_denies_groups():
    cfg = ImitateConfig()
    assert cfg.groups == frozenset()
    assert cfg.enabled is False


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("replay", "replay"),
        ("markov", "markov"),
        ("mixed", "mixed"),
        ("MARKOV", "markov"),
        (" unknown ", "replay"),
        ("", "replay"),
        (None, "replay"),
    ],
)
def test_parse_mode(value, expected):
    assert parse_mode(value) == expected


def test_env_overrides(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setenv("IMITATE_ENABLED", "1")
    monkeypatch.setenv("IMITATE_GROUPS", "10000，10001；10002")
    monkeypatch.setenv("IMITATE_MODE", "markov")
    monkeypatch.setenv("IMITATE_DB_PATH", str(tmp_path / "x.db"))
    monkeypatch.setenv("IMITATE_PROBABILITY", "0.5")
    monkeypatch.setenv("IMITATE_MAX_LENGTH", "12")
    monkeypatch.setenv("IMITATE_MAX_RECORDS", "30")
    monkeypatch.setenv("IMITATE_MIN_CORPUS", "20")
    monkeypatch.setenv("IMITATE_ORDER", "3")
    monkeypatch.setenv("IMITATE_MIN_TEXT_LEN", "1")
    monkeypatch.setenv("IMITATE_MAX_TEXT_LEN", "40")
    monkeypatch.setenv("IMITATE_MAX_GENERATE_LEN", "10")
    monkeypatch.setenv("IMITATE_BOT_QQS", "10002,10003")
    monkeypatch.setenv("IMITATE_DEDUPE", "0")
    monkeypatch.setenv("IMITATE_TARGET_ARG", "0")
    monkeypatch.setenv("IMITATE_DETECT_ROBOTS", "0")
    monkeypatch.setenv("IMITATE_COOLDOWN_SECONDS", "7")

    cfg = load_config()
    assert cfg.enabled is True
    assert cfg.groups == frozenset({10000, 10001, 10002})
    assert cfg.mode == "markov"
    assert cfg.db_path == str(tmp_path / "x.db")
    assert cfg.probability == 0.5
    assert cfg.max_length == 12
    assert cfg.max_records == 30
    assert cfg.min_corpus == 20
    assert cfg.order == 3
    assert cfg.min_text_len == 1
    assert cfg.max_text_len == 40
    assert cfg.max_generate_len == 10
    assert cfg.bot_qqs == frozenset({10002, 10003})
    assert cfg.dedupe is False
    assert cfg.target_arg is False
    assert cfg.detect_robots is False
    assert cfg.cooldown_seconds == 7.0


def test_clamps(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("IMITATE_PROBABILITY", "9")
    monkeypatch.setenv("IMITATE_ORDER", "99")
    monkeypatch.setenv("IMITATE_MIN_CORPUS", "0")
    monkeypatch.setenv("IMITATE_MAX_LENGTH", "0")
    monkeypatch.setenv("IMITATE_MAX_RECORDS", "-5")
    monkeypatch.setenv("IMITATE_ROBOT_CACHE_TTL", "0")
    monkeypatch.setenv("IMITATE_COOLDOWN_SECONDS", "-3")
    monkeypatch.setenv("IMITATE_MAX_TEXT_LEN", "1")
    monkeypatch.setenv("IMITATE_MIN_TEXT_LEN", "5")
    cfg = load_config()
    assert cfg.probability == 1.0
    assert cfg.order == 4
    assert cfg.min_corpus == 1
    assert cfg.max_length == 1
    assert cfg.max_records == 1
    assert cfg.robot_cache_ttl == 1.0
    assert cfg.cooldown_seconds == 0.0
    # max_text_len 不小于 min_text_len
    assert cfg.max_text_len >= cfg.min_text_len == 5
    assert cfg.max_corpus_fetch >= cfg.min_corpus
    assert cfg.max_generate_len >= cfg.min_text_len


def test_invalid_values_fall_back(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("IMITATE_PROBABILITY", "not-a-number")
    monkeypatch.setenv("IMITATE_MODE", "banana")
    monkeypatch.setenv("IMITATE_ENABLED", "maybe")
    monkeypatch.setenv("IMITATE_GROUPS", "abc,0,10000")
    cfg = load_config()
    assert cfg.probability == 0.02
    assert cfg.mode == "replay"
    assert cfg.enabled is False
    assert cfg.groups == frozenset({10000})


def test_block_patterns_default_and_override(monkeypatch: pytest.MonkeyPatch):
    cfg = load_config()
    assert any("http" in pattern for pattern in cfg.block_patterns)
    assert any("com" in pattern for pattern in cfg.block_patterns)
    monkeypatch.setenv("IMITATE_BLOCK_PATTERNS", "foo;bar")
    assert load_config().block_patterns == ("foo", "bar")
    monkeypatch.setenv("IMITATE_BLOCK_PATTERNS", " ")
    assert load_config().block_patterns == cfg.block_patterns


def test_config_is_frozen(cfg):
    with pytest.raises(dataclasses.FrozenInstanceError):
        cfg.mode = "markov"  # type: ignore[misc]
