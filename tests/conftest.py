"""pytest 公共夹具：先 nonebot.init()，清空 IMITATE_* 环境变量，假 Bot。"""

from __future__ import annotations

import os
from dataclasses import replace

import nonebot
import pytest

nonebot.init()

_ENV_PREFIX = "IMITATE_"


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch):
    for key in list(os.environ):
        if key.startswith(_ENV_PREFIX):
            monkeypatch.delenv(key, raising=False)
    yield


@pytest.fixture
def cfg(tmp_path):
    """启用、仅群 10000、新库、低门槛的测试配置。"""
    from nonebot_plugin_imitate.config import load_config

    return replace(
        load_config(),
        enabled=True,
        groups=frozenset({10000}),
        db_path=str(tmp_path / "imitate.db"),
        probability=0.0,
        min_corpus=5,
        max_rows_per_group=100,
    )


class FakeBot:
    self_id = "10000"

    def __init__(self, responses: dict[str, object] | None = None) -> None:
        self.responses = dict(responses or {})
        self.calls: list[tuple[str, dict]] = []

    async def call_api(self, api: str, **kwargs):
        self.calls.append((api, kwargs))
        value = self.responses.get(api)
        if isinstance(value, BaseException):
            raise value
        return value


@pytest.fixture
def fake_bot():
    def _make(responses: dict[str, object] | None = None) -> FakeBot:
        return FakeBot(responses)

    return _make
