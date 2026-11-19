"""复读模式的行为逻辑（复刻 koishi-plugin-imitate 2.0.6 的可见行为）。

参考的是 2.0.6 的**行为规格**而非代码：自动学习短消息、按概率随机复读该用户
之前说过的一句话。来源与许可见 README / THIRD_PARTY_NOTICES。

本模块是纯函数，不 import NoneBot：
- :func:`plan_message` 对应「学习 + 是否触发复读」的一次决策；
- :func:`parse_command` 复刻 Koishi 的命令 token 化（含 ``@bot`` 前缀与
  ``ignore-space`` 的边界行为）；
- :func:`group_allowed` 是群白名单判定。

安全默认：白名单为空时**不允许任何群**（上游 Koishi 插件是空=全部群；这里刻意
收紧，避免开启总开关后在全部分群里说话）。
"""

from __future__ import annotations

import random
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass

try:  # 包内导入（NoneBot 插件加载）
    from . import text as _text
except ImportError:  # 脚本/单测时把插件目录加入 sys.path 后直接 import
    import text as _text  # type: ignore[no-redef]

Segment = _text.Segment
COMMANDS = ("模仿",)

# utils.js: isQQNumber 的判定
_QQ_RE = re.compile(r"^\d+$")
_LEADING_ZERO_RE = re.compile(r"^0\d+$")
_AT_STR_RE = re.compile(r'<at id="(\d+)"')


@dataclass(frozen=True, slots=True)
class Plan:
    """一条群消息的处理计划。"""

    record: bool
    trigger: bool
    reply: str | None


def plan_message(
    content: str,
    pre_corpus: Sequence[str],
    *,
    prob: float = 0.02,
    max_length: int = 20,
    rng: Callable[[], float] = random.random,
    chooser: Callable[[Sequence[str]], str] = random.choice,
) -> Plan:
    """决定是否记录本条消息、是否复读，以及复读哪一句。

    ``pre_corpus`` 必须是**本条消息入库之前**的语料：上游插件在学习与回复之间
    读库，所以刚说的这句不会立刻被自己复读。
    """
    record = bool(content) and _text.js_length(content) <= max_length
    trigger = rng() < prob
    reply: str | None = None
    if trigger and pre_corpus:
        reply = chooser(pre_corpus)
    return Plan(record=record, trigger=trigger, reply=reply)


# ---------------------------------------------------------------------------
# 命令解析（复刻 Koishi core 的 token 化 + commands/ignore-space 组合行为）
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CommandMatch:
    name: str
    tail: str = ""
    at_ids: tuple[str, ...] = ()


def _seg_qq(data: dict) -> str:
    value = data.get("qq", data.get("id", ""))
    return "" if value is None else str(value)


def parse_command(
    segments: Sequence[Segment],
    candidates: Sequence[str],
    self_id: str,
    *,
    allow_attached: frozenset[str] = frozenset(),
) -> CommandMatch | None:
    """按 Koishi 语义判定消息是否触发了候选命令之一。

    规则：
    1. 开头允许一个 ``@bot``；开头 ``@别人``（或 @bot 之后再 @别人）不解析。
    2. 命令名后必须是边界（空白/消息结束）；``allow_attached`` 里的命令允许
       紧跟内容（``什么是yyds``）。
    3. 命令名后紧跟非 text 元素时（如 ``模仿@某人``），仍视为命令。
    4. 命令名允许前导空白。
    """
    if not segments:
        return None
    index = 0
    saw_at = False
    while index < len(segments) and segments[index][0] == "at":
        qq = _seg_qq(segments[index][1])
        if not saw_at and qq == str(self_id):
            saw_at = True
            index += 1
            continue
        return None
    if index >= len(segments) or segments[index][0] != "text":
        return None
    raw_text = str(segments[index][1].get("text", ""))
    content = raw_text.lstrip()
    if not content:
        return None
    tail_segments = list(segments[index + 1 :])

    for name in sorted(candidates, key=len, reverse=True):
        if not content.startswith(name):
            continue
        rest = content[len(name) :]
        if rest and not rest[0].isspace() and name not in allow_attached:
            continue
        at_ids: list[str] = []
        tail_parts: list[str] = []
        if rest:
            tail_parts.append(rest)
        for seg_type, data in tail_segments:
            if seg_type == "at":
                qq = _seg_qq(data)
                if qq:
                    at_ids.append(qq)
            elif seg_type == "text":
                tail_parts.append(str(data.get("text", "")))
        return CommandMatch(name=name, tail="".join(tail_parts), at_ids=tuple(at_ids))
    return None


def is_qq_number(value: str | None) -> bool:
    """utils.js: isQQNumber（至少 5 位、非 0 开头）。"""
    if not isinstance(value, str):
        return False
    if len(value) < 5:
        return False
    if _LEADING_ZERO_RE.match(value):
        return False
    return bool(_QQ_RE.match(value))


def get_target_id(at_ids: Sequence[str], tail: str) -> str | None:
    """utils.js: getTargetId（at 元素或纯数字 QQ 号；其余返回 None）。"""
    raw: str | None = None
    if at_ids:
        raw = str(at_ids[0])
    else:
        stripped = (tail or "").strip()
        if stripped:
            raw = stripped.split()[0]
    if not raw:
        return None
    match = _AT_STR_RE.search(raw)
    if match:
        return match.group(1)
    if raw.startswith("<at"):
        return None
    if is_qq_number(raw):
        return raw
    return None


def group_allowed(group_id: object, groups: frozenset[int]) -> bool:
    """群白名单；空集合 = 不允许任何群（安全默认）。"""
    if not groups:
        return False
    try:
        return int(str(group_id)) in groups
    except (TypeError, ValueError):
        return False


__all__ = [
    "COMMANDS",
    "CommandMatch",
    "Plan",
    "get_target_id",
    "group_allowed",
    "is_qq_number",
    "parse_command",
    "plan_message",
]
