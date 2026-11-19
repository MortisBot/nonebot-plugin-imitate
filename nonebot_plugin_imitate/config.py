"""imitate 配置（纯标准库，便于离线测试）。

所有配置项来自 ``IMITATE_*`` 环境变量；非法值回退默认值。默认
``IMITATE_ENABLED=0``、``IMITATE_GROUPS`` 为空，即**不学习、不回复任何群**。

模式：

* ``replay``（默认）：随机复读该用户最近的短消息（koishi-plugin-imitate 2.0.6 行为）。
* ``markov``：用群语料训练字符级 Markov 链生成新句子。
* ``mixed``：语料够就 Markov，不够再回退 replay。
"""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_DB_PATH = "data/imitate/imitate.db"
DEFAULT_MODE = "replay"
MODES = ("replay", "markov", "mixed")
DEFAULT_BLOCK_PATTERNS = (
    r"(?:https?://|www\.)\S+",
    r"\b[\w-]+\.(?:com|cn|net|org|io|me|top|xyz|cc)\b",
)


def _env(name: str, default: str = "") -> str:
    value = os.environ.get(name)
    return default if value is None else value.strip()


_TRUE_VALUES = {"1", "true", "yes", "y", "on", "enable", "enabled"}
_FALSE_VALUES = {"0", "false", "no", "n", "off", "disable", "disabled"}


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    text = raw.strip().lower()
    if text in _TRUE_VALUES:
        return True
    if text in _FALSE_VALUES:
        return False
    return default


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw.strip())
    except ValueError:
        return default


def _env_int_set(name: str) -> frozenset[int]:
    raw = os.environ.get(name, "")
    result: set[int] = set()
    for part in (
        raw.replace("，", " ")
        .replace("；", " ")
        .replace(",", " ")
        .replace(";", " ")
        .split()
    ):
        try:
            value = int(part)
        except ValueError:
            continue
        if value > 0:
            result.add(value)
    return frozenset(result)


def _env_patterns(name: str) -> tuple[str, ...]:
    raw = os.environ.get(name, "")
    patterns = tuple(part.strip() for part in raw.split(";") if part.strip())
    return patterns or DEFAULT_BLOCK_PATTERNS


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def parse_mode(value: object) -> str:
    text = str(value or "").strip().lower()
    return text if text in MODES else DEFAULT_MODE


@dataclass(frozen=True, slots=True)
class ImitateConfig:
    enabled: bool = False
    groups: frozenset[int] = frozenset()
    mode: str = DEFAULT_MODE
    db_path: str = DEFAULT_DB_PATH
    probability: float = 0.02
    max_length: int = 20
    max_records: int = 100
    min_corpus: int = 500
    order: int = 2
    max_corpus_fetch: int = 5000
    max_rows_per_group: int = 5000
    min_text_len: int = 2
    max_text_len: int = 80
    max_generate_len: int = 20
    detect_robots: bool = True
    robot_cache_ttl: float = 3600.0
    bot_qqs: frozenset[int] = frozenset()
    block_patterns: tuple[str, ...] = DEFAULT_BLOCK_PATTERNS
    cooldown_seconds: float = 0.0
    dedupe: bool = True
    target_arg: bool = True


def load_config() -> ImitateConfig:
    min_text_len = max(1, _env_int("IMITATE_MIN_TEXT_LEN", 2))
    max_text_len = max(min_text_len, _env_int("IMITATE_MAX_TEXT_LEN", 80))
    min_corpus = max(1, _env_int("IMITATE_MIN_CORPUS", 500))
    return ImitateConfig(
        enabled=_env_bool("IMITATE_ENABLED", False),
        groups=_env_int_set("IMITATE_GROUPS"),
        mode=parse_mode(_env("IMITATE_MODE", DEFAULT_MODE)),
        db_path=_env("IMITATE_DB_PATH", DEFAULT_DB_PATH) or DEFAULT_DB_PATH,
        probability=_clamp(
            _env_float("IMITATE_PROBABILITY", 0.02), 0.0, 1.0
        ),
        max_length=max(1, _env_int("IMITATE_MAX_LENGTH", 20)),
        max_records=max(1, _env_int("IMITATE_MAX_RECORDS", 100)),
        min_corpus=min_corpus,
        order=max(1, min(4, _env_int("IMITATE_ORDER", 2))),
        max_corpus_fetch=max(
            min_corpus, _env_int("IMITATE_MAX_CORPUS_FETCH", 5000)
        ),
        max_rows_per_group=max(
            min_corpus, _env_int("IMITATE_MAX_ROWS_PER_GROUP", 5000)
        ),
        min_text_len=min_text_len,
        max_text_len=max_text_len,
        max_generate_len=max(
            min_text_len, _env_int("IMITATE_MAX_GENERATE_LEN", 20)
        ),
        detect_robots=_env_bool("IMITATE_DETECT_ROBOTS", True),
        robot_cache_ttl=max(
            1.0, _env_float("IMITATE_ROBOT_CACHE_TTL", 3600.0)
        ),
        bot_qqs=_env_int_set("IMITATE_BOT_QQS"),
        block_patterns=_env_patterns("IMITATE_BLOCK_PATTERNS"),
        cooldown_seconds=max(
            0.0, _env_float("IMITATE_COOLDOWN_SECONDS", 0.0)
        ),
        dedupe=_env_bool("IMITATE_DEDUPE", True),
        target_arg=_env_bool("IMITATE_TARGET_ARG", True),
    )


__all__ = [
    "DEFAULT_BLOCK_PATTERNS",
    "DEFAULT_DB_PATH",
    "DEFAULT_MODE",
    "ImitateConfig",
    "MODES",
    "load_config",
    "parse_mode",
]
