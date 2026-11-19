"""Koishi 文本/消息语义的 Python 复刻（纯标准库）。

为什么需要它：复读模式的语料是「Koishi 里的 message.content」，即元素序列化后
的字符串（文本会做 Satori 转义、非文本元素变成标签）；学习前还会用
``content.replace(/<[^>]+>/g, '')`` 剥掉标签。长度判定用的是 JS ``String.length``
（UTF-16 code unit 数），emoji 会按 2 个字符计。

本模块不依赖 NoneBot，可离线单测。
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

Segment = tuple[str, dict]

_TAG_RE = re.compile(r"<[^>]+>")


def satori_escape(source: str) -> str:
    """复刻 Satori 的非 inline 转义：``& < >``。"""
    return (
        (source or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def js_length(source: str) -> int:
    """JS ``String.prototype.length``（UTF-16 code unit 数）。"""
    return len((source or "").encode("utf-16-le")) // 2


def _seg_qq(data: dict) -> str:
    value = data.get("qq", data.get("id", ""))
    return "" if value is None else str(value)


def serialize_segment(segment: Segment) -> str:
    """把单个 ``(type, data)`` 元素序列化成 Koishi 风格字符串。"""
    seg_type, data = segment
    if seg_type == "text":
        return satori_escape(str(data.get("text", "")))
    if seg_type == "at":
        qq = _seg_qq(data)
        name = data.get("name")
        if name:
            return f'<at id="{qq}" name="{satori_escape(str(name))}"/>'
        return f'<at id="{qq}"/>'
    if seg_type in {"img", "image"}:
        src = data.get("src", data.get("file", ""))
        return f'<img src="{satori_escape(str(src))}"/>'
    if seg_type == "face":
        return f'<face id="{satori_escape(str(data.get("id", "")))}"/>'
    if seg_type in {"reply", "quote"}:
        return ""
    return f"<{seg_type}/>"


def full_content(segments: Sequence[Segment]) -> str:
    """``session.content``：所有元素序列化后拼接（含标签，不 strip）。"""
    return "".join(serialize_segment(seg) for seg in segments)


def stripped_content(segments: Sequence[Segment]) -> str:
    """自动学习用的 content：等价于 ``strip_tags(full_content(...))``。"""
    parts: list[str] = []
    for seg_type, data in segments:
        if seg_type == "text":
            parts.append(satori_escape(str(data.get("text", ""))))
    return "".join(parts)


def strip_tags(content: str) -> str:
    """等价 JS ``content.replace(/<[^>]+>/g, '')``。"""
    return _TAG_RE.sub("", content or "")


def segments_from_onebot_message(message: Iterable) -> list[Segment]:
    """把 NoneBot v11 ``Message`` 转成 ``(type, data)`` 列表。"""
    result: list[Segment] = []
    for seg in message:
        seg_type = getattr(seg, "type", None)
        data = getattr(seg, "data", None)
        if seg_type is None:
            continue
        result.append((str(seg_type), dict(data or {})))
    return result


__all__ = [
    "Segment",
    "full_content",
    "js_length",
    "satori_escape",
    "segments_from_onebot_message",
    "serialize_segment",
    "strip_tags",
    "stripped_content",
]
