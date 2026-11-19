"""复读行为：学习/触发决策、命令解析、目标 uid 与群白名单。"""

from __future__ import annotations

import pytest
from nonebot_plugin_imitate import behavior

SELF_ID = "10000"


def seg(seg_type: str, **data):
    return (seg_type, data)


def _plan(content, pre, rng_value, prob=0.02, max_length=20, chooser=None):
    return behavior.plan_message(
        content,
        pre,
        prob=prob,
        max_length=max_length,
        rng=lambda: rng_value,
        chooser=chooser or (lambda items: items[0]),
    )


def test_plan_record_only():
    plan = _plan("你好", [], rng_value=0.99)
    assert (plan.record, plan.trigger, plan.reply) == (True, False, None)


def test_plan_probability_boundary():
    hit = _plan("你好", ["旧语料"], rng_value=0.019999)
    assert (hit.trigger, hit.reply) == (True, "旧语料")
    miss = _plan("你好", ["旧语料"], rng_value=0.02)
    assert (miss.trigger, miss.reply) == (False, None)


def test_plan_no_history_no_reply():
    plan = _plan("你好", [], rng_value=0.0)
    assert plan.trigger is True
    assert plan.reply is None


def test_plan_long_message_not_recorded():
    plan = _plan("这" * 21, ["旧"], rng_value=0.0)
    assert (plan.record, plan.trigger, plan.reply) == (False, True, "旧")
    assert _plan("这" * 20, ["旧"], rng_value=0.99).record is True


def test_plan_empty_content_can_trigger():
    plan = _plan("", ["旧"], rng_value=0.0)
    assert (plan.record, plan.trigger, plan.reply) == (False, True, "旧")


def test_plan_reply_comes_from_history():
    pre = ["第一条", "第二条"]
    plan = _plan("第三", pre, rng_value=0.0, chooser=lambda items: items[-1])
    assert plan.reply == "第二条"
    assert plan.reply not in pre[-1:] or plan.reply == pre[-1]


def test_plan_js_length_counts_emoji():
    # 10 个 emoji = JS 长度 20，刚好可记录
    assert _plan("😀" * 10, [], rng_value=0.99).record is True
    assert _plan("😀" * 11, [], rng_value=0.99).record is False


def test_parse_imitate():
    parse = behavior.parse_command
    match = parse([seg("text", text="模仿")], ("模仿",), SELF_ID)
    assert match is not None and match.name == "模仿"
    assert parse([seg("text", text=" 模仿")], ("模仿",), SELF_ID).name == "模仿"
    assert parse([seg("text", text="模仿 ")], ("模仿",), SELF_ID).name == "模仿"
    assert parse([seg("text", text="模仿 123456")], ("模仿",), SELF_ID).tail == " 123456"
    assert parse([seg("text", text="模仿xxx")], ("模仿",), SELF_ID) is None
    # @bot 前缀
    assert (
        parse([seg("at", qq=SELF_ID), seg("text", text=" 模仿")], ("模仿",), SELF_ID).name
        == "模仿"
    )
    # @别人 开头：Koishi 不解析命令
    assert parse([seg("at", qq="10001"), seg("text", text="模仿")], ("模仿",), SELF_ID) is None
    assert (
        parse(
            [seg("at", qq=SELF_ID), seg("at", qq="10001"), seg("text", text="模仿")],
            ("模仿",),
            SELF_ID,
        )
        is None
    )
    # 命令名后紧跟 at 元素（ignore-space 救回）
    assert parse([seg("text", text="模仿"), seg("at", qq="10001")], ("模仿",), SELF_ID).name == "模仿"
    # 图片开头不触发
    assert parse([seg("img", src="x"), seg("text", text="模仿")], ("模仿",), SELF_ID) is None


def test_parse_attached_content():
    parse = behavior.parse_command
    allowed = frozenset({"什么是"})
    assert parse([seg("text", text="什么是yyds")], ("什么是",), SELF_ID, allow_attached=allowed).tail == "yyds"
    assert parse([seg("text", text="什么是 yyds")], ("什么是",), SELF_ID, allow_attached=allowed).tail.strip() == "yyds"
    assert parse([seg("text", text="什么是x")], ("什么是",), SELF_ID) is None


def test_parse_longest_command_wins():
    match = behavior.parse_command(
        [seg("text", text="删除模仿")], behavior.COMMANDS + ("删除模仿",), SELF_ID
    )
    assert match.name == "删除模仿"


def test_parse_collects_at_ids():
    match = behavior.parse_command(
        [seg("text", text="模仿"), seg("at", qq="10001"), seg("text", text=" 你好")],
        ("模仿",),
        SELF_ID,
    )
    assert match.at_ids == ("10001",)
    assert match.tail == " 你好"


def test_get_target_id():
    get = behavior.get_target_id
    assert get(("123456789",), "") == "123456789"
    assert get((), " 123456789 你好") == "123456789"
    assert get((), "1234") is None
    assert get((), "0123456") is None
    assert get((), "abcdef") is None
    assert get((), "") is None
    assert behavior.is_qq_number("12345") is True
    assert behavior.is_qq_number("01234") is False
    assert behavior.is_qq_number("1234") is False
    assert behavior.is_qq_number(None) is False


def test_group_allowed_is_deny_by_default():
    assert behavior.group_allowed("10000", frozenset()) is False
    assert behavior.group_allowed("10000", frozenset({10000})) is True
    assert behavior.group_allowed("10001", frozenset({10000})) is False
    assert behavior.group_allowed(None, frozenset({10000})) is False


@pytest.mark.parametrize("bad", ["", "   ", "abc"])
def test_group_allowed_invalid(bad):
    assert behavior.group_allowed(bad, frozenset({10000})) is False
