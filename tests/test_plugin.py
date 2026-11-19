"""插件装配：metadata、规则、学习过滤、replay/markov 出句、uid 参数、DB 容错。"""

from __future__ import annotations

import dataclasses
import time

import nonebot_plugin_imitate as plugin
import pytest
from nonebot.adapters.onebot.v11 import GroupMessageEvent, Message, MessageSegment
from nonebot_plugin_imitate import behavior, engine, robots, store

SELF = 10000
GROUP = 10000
USER = 10001

PHRASES = [
    "今天天气真不错",
    "机厅人好多啊",
    "晚上一起吃点什么",
    "明天还来打舞萌吗",
    "这谱面也太难了",
    "我刚刚到家",
    "有人出勤吗",
    "群里有人吗",
    "先去排卡吧",
    "人太多了等一会儿",
    "奶茶喝不喝",
    "地铁上人挤人",
    "困死了想睡觉",
    "再打一把就撤",
    "这歌我打不动",
    "我先去洗个手",
]


def make_event(
    text: str = "你好呀",
    *,
    group_id: int = GROUP,
    user_id: int = USER,
    at: bool = False,
) -> GroupMessageEvent:
    segments = (
        [MessageSegment.at(SELF), MessageSegment.text(" " + text)]
        if at
        else [MessageSegment.text(text)]
    )
    message = Message(segments)
    return GroupMessageEvent.model_validate(
        {
            "time": int(time.time()),
            "self_id": SELF,
            "post_type": "message",
            "sub_type": "normal",
            "user_id": user_id,
            "message_id": 123456,
            "message_type": "group",
            "message": message,
            "original_message": message,
            "raw_message": text,
            "font": 0,
            "sender": {"user_id": user_id, "nickname": "tester"},
            "group_id": group_id,
            "to_me": at,
        }
    )


@pytest.fixture
def patched(monkeypatch, cfg):
    monkeypatch.setattr(plugin, "CFG", cfg)
    monkeypatch.setattr(plugin, "PATTERNS", engine.compile_patterns(cfg.block_patterns))
    monkeypatch.setattr(plugin, "ROBOT_CACHE", robots.RobotCache(cfg.robot_cache_ttl))
    monkeypatch.setattr(plugin, "_db_state", None)
    store.init_db(cfg.db_path)
    return cfg


def _set_cfg(monkeypatch, cfg, **changes):
    new_cfg = dataclasses.replace(cfg, **changes)
    monkeypatch.setattr(plugin, "CFG", new_cfg)
    return new_cfg


def test_metadata():
    meta = plugin.__plugin_meta__
    assert meta.name == "imitate"
    assert meta.supported_adapters == {"~onebot.v11"}
    assert "模仿" in meta.usage


def test_matchers_registered():
    assert plugin.auto_matcher is not None
    assert plugin.command_matcher is not None
    assert plugin.auto_matcher.priority == 99
    assert plugin.command_matcher.priority == 5


def test_rule_command(monkeypatch, patched, fake_bot):
    bot = fake_bot()
    # 命令不要求 @bot
    assert plugin._rule_command(make_event("模仿"), bot) is True
    assert plugin._rule_command(make_event("模仿", at=True), bot) is True
    assert plugin._rule_command(make_event("你好"), bot) is False
    assert plugin._rule_command(make_event("模仿", group_id=10002), bot) is False
    _set_cfg(monkeypatch, patched, enabled=False)
    assert plugin._rule_command(make_event("模仿"), bot) is False


def test_rule_auto(monkeypatch, patched, fake_bot):
    bot = fake_bot()
    assert plugin._rule_auto(make_event(), bot) is True
    _set_cfg(monkeypatch, patched, enabled=False)
    assert plugin._rule_auto(make_event(), bot) is False


def test_group_allowed(monkeypatch, patched):
    assert plugin._group_allowed(GROUP) is True
    assert plugin._group_allowed(10002) is False
    _set_cfg(monkeypatch, patched, groups=frozenset())
    assert plugin._group_allowed(GROUP) is False


def test_ignored_user(monkeypatch, patched, fake_bot):
    bot = fake_bot()
    assert plugin._is_ignored_user(make_event(user_id=SELF), bot) is True
    assert plugin._is_ignored_user(make_event(user_id=USER), bot) is False
    _set_cfg(monkeypatch, patched, bot_qqs=frozenset({10002}))
    assert plugin._is_ignored_user(make_event(user_id=10002), bot) is True


async def test_learn_records(patched, fake_bot):
    reply = await plugin._learn(make_event("你好呀"), fake_bot())
    assert reply is None  # probability=0
    assert store.count_corpus(patched.db_path, GROUP) == 1
    assert store.fetch_user_corpus(patched.db_path, GROUP, USER) == ["你好呀"]


async def test_learn_dedupes(patched, fake_bot):
    bot = fake_bot()
    await plugin._learn(make_event("复读测试"), bot)
    await plugin._learn(make_event("复读测试", user_id=10002), bot)
    assert store.count_corpus(patched.db_path, GROUP) == 1


async def test_learn_skips_url(patched, fake_bot):
    await plugin._learn(make_event("看 http://a.com"), fake_bot())
    await plugin._learn(make_event("www.example.com"), fake_bot())
    assert store.count_corpus(patched.db_path, GROUP) == 0


async def test_learn_skips_long_replay_text(patched, fake_bot):
    await plugin._learn(make_event("啊" * 21), fake_bot())
    assert store.count_corpus(patched.db_path, GROUP) == 0


async def test_learn_skips_other_group(patched, fake_bot):
    await plugin._learn(make_event("你好呀", group_id=10002), fake_bot())
    assert store.count_corpus(patched.db_path, 10002) == 0


async def test_learn_skips_self_and_bots(monkeypatch, patched, fake_bot):
    bot = fake_bot()
    await plugin._learn(make_event("我自己", user_id=SELF), bot)
    _set_cfg(monkeypatch, patched, bot_qqs=frozenset({10002}))
    await plugin._learn(make_event("别的机器人", user_id=10002), bot)
    assert store.count_corpus(patched.db_path, GROUP) == 0


async def test_learn_skips_official_robot(patched, fake_bot):
    bot = fake_bot({"get_group_member_info": {"is_robot": True}})
    await plugin._learn(make_event("官方机器人"), bot)
    assert store.count_corpus(patched.db_path, GROUP) == 0
    assert bot.calls[0][0] == "get_group_member_info"


async def test_learn_does_not_reply_with_current_message(patched, monkeypatch, fake_bot):
    _set_cfg(monkeypatch, patched, probability=1.0)
    reply = await plugin._learn(make_event("第一句话"), fake_bot())
    assert reply is None
    assert store.count_corpus(patched.db_path, GROUP) == 1


async def test_learn_replays_history(patched, monkeypatch, fake_bot):
    store.add_corpus(patched.db_path, GROUP, USER, "旧句子", 1000.0)
    _set_cfg(monkeypatch, patched, probability=1.0)
    reply = await plugin._learn(make_event("新句子"), fake_bot())
    assert reply == "旧句子"
    assert store.count_corpus(patched.db_path, GROUP) == 2


async def test_learn_markov_records_without_replay(patched, monkeypatch, fake_bot):
    _set_cfg(monkeypatch, patched, mode="markov", probability=0.0)
    reply = await plugin._learn(make_event("今天天气真不错"), fake_bot())
    assert reply is None
    assert store.count_corpus(patched.db_path, GROUP) == 1


async def test_generate_replay(patched, monkeypatch):
    store.add_corpus(patched.db_path, GROUP, USER, "甲", 1.0)
    store.add_corpus(patched.db_path, GROUP, USER, "乙", 2.0)
    reply = await plugin._generate(GROUP, USER)
    assert reply in {"甲", "乙"}


async def test_generate_markov(patched, monkeypatch):
    _set_cfg(monkeypatch, patched, mode="markov", min_corpus=3)
    for index, phrase in enumerate(PHRASES):
        store.add_corpus(patched.db_path, GROUP, USER, phrase, float(index))
    reply = await plugin._generate(GROUP, USER)
    assert reply is None or isinstance(reply, str)


async def test_generate_mixed_falls_back(patched, monkeypatch):
    _set_cfg(monkeypatch, patched, mode="mixed", min_corpus=3)
    monkeypatch.setattr(plugin, "PATTERNS", engine.compile_patterns(["."]))
    store.add_corpus(patched.db_path, GROUP, USER, "备用句子", 1.0)
    for index, phrase in enumerate(PHRASES):
        store.add_corpus(patched.db_path, GROUP, 10002, phrase, float(index))
    reply = await plugin._generate(GROUP, USER)
    assert reply == "备用句子"


def test_resolve_target(monkeypatch, patched):
    match = behavior.CommandMatch(name="模仿", tail=" 10002")
    assert plugin._resolve_target(match, USER) == 10002
    at_match = behavior.CommandMatch(name="模仿", tail="", at_ids=("10003",))
    assert plugin._resolve_target(at_match, USER) == 10003
    bad = behavior.CommandMatch(name="模仿", tail=" abc")
    assert plugin._resolve_target(bad, USER) == USER
    _set_cfg(monkeypatch, patched, target_arg=False)
    assert plugin._resolve_target(match, USER) == USER


def test_db_ready_lazy(monkeypatch, cfg, tmp_path):
    db_path = tmp_path / "lazy" / "imitate.db"
    monkeypatch.setattr(plugin, "CFG", dataclasses.replace(cfg, db_path=str(db_path)))
    monkeypatch.setattr(plugin, "_db_state", None)
    assert plugin._db_ready() is True
    assert db_path.is_file()


def test_db_ready_failure(monkeypatch, cfg, tmp_path):
    monkeypatch.setattr(plugin, "CFG", dataclasses.replace(cfg, db_path=str(tmp_path)))
    monkeypatch.setattr(plugin, "_db_state", None)
    assert plugin._db_ready() is False


def test_cooldown(monkeypatch, patched):
    _set_cfg(monkeypatch, patched, cooldown_seconds=60)
    plugin._last_sent.clear()
    try:
        assert plugin._cooldown_ok(GROUP) is True
        plugin._last_sent[GROUP] = time.monotonic()
        assert plugin._cooldown_ok(GROUP) is False
    finally:
        plugin._last_sent.clear()
    _set_cfg(monkeypatch, patched, cooldown_seconds=0)
    assert plugin._cooldown_ok(GROUP) is True
