"""Koishi 文本语义：Satori 转义、元素剥离、UTF-16 长度。"""

from __future__ import annotations

from nonebot.adapters.onebot.v11 import Message, MessageSegment
from nonebot_plugin_imitate import text as text_mod


def seg(seg_type: str, **data):
    return (seg_type, data)


def test_satori_escape():
    assert text_mod.satori_escape("&") == "&amp;"
    assert text_mod.satori_escape("<b>") == "&lt;b&gt;"
    assert text_mod.satori_escape("'") == "'"


def test_stripped_content():
    segments = [
        seg("at", qq="10000"),
        seg("text", text=" hi"),
        seg("img", src="http://x/y.png"),
        seg("text", text=" & "),
        seg("face", id="1"),
        seg("text", text="world"),
    ]
    assert text_mod.stripped_content(segments) == " hi &amp; world"
    # 序列化后剥标签等价于只拼文本段
    full = text_mod.full_content(segments)
    assert text_mod.strip_tags(full) == " hi &amp; world"


def test_js_length():
    assert text_mod.js_length("汉" * 20) == 20
    assert text_mod.js_length("😀") == 2
    assert text_mod.js_length("😀" * 10) == 20
    assert text_mod.js_length("") == 0


def test_serialize_segment():
    assert text_mod.serialize_segment(seg("at", qq="10000")) == '<at id="10000"/>'
    assert (
        text_mod.serialize_segment(seg("at", qq="10000", name="a&b"))
        == '<at id="10000" name="a&amp;b"/>'
    )
    assert (
        text_mod.serialize_segment(seg("image", file="x.png"))
        == '<img src="x.png"/>'
    )
    assert text_mod.serialize_segment(seg("face", id="1")) == '<face id="1"/>'
    assert text_mod.serialize_segment(seg("reply", id="1")) == ""
    assert text_mod.serialize_segment(seg("dice")) == "<dice/>"


def test_segments_from_onebot_message():
    message = Message(
        [
            MessageSegment.at("10000"),
            MessageSegment.text(" 模仿 "),
            MessageSegment.image("http://x/y.png"),
        ]
    )
    segments = text_mod.segments_from_onebot_message(message)
    assert segments[0] == ("at", {"qq": "10000"})
    assert segments[1] == ("text", {"text": " 模仿 "})
    assert segments[2][0] == "image"
