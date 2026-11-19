"""Markov 引擎、固定 seed、模式切换与学习过滤。"""

from __future__ import annotations

import random

from nonebot_plugin_imitate import engine

CORPUS = [
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


def test_clean_text():
    assert engine.clean_text("  a \n b  ") == "a b"
    assert engine.clean_text(None) == ""


def test_should_learn_filters():
    patterns = engine.compile_patterns(
        [
            r"(?:https?://|www\.)\S+",
            r"\b[\w-]+\.(?:com|cn|net|org|io|me|top|xyz|cc)\b",
        ]
    )
    assert engine.should_learn("你好啊", patterns=patterns) is True
    assert engine.should_learn("哈哈", patterns=patterns) is True
    assert engine.should_learn("/help", patterns=patterns) is False
    assert engine.should_learn("！帮助", patterns=patterns) is False
    assert engine.should_learn("看 http://a.com", patterns=patterns) is False
    assert engine.should_learn("www.example.com", patterns=patterns) is False
    assert engine.should_learn("a.xyz", patterns=patterns) is False
    assert engine.should_learn("12345", patterns=patterns) is False
    assert engine.should_learn("啊" * 81, patterns=patterns) is False
    assert engine.should_learn("啊", patterns=patterns) is False
    assert engine.should_learn("[CQ:face,id=1]", patterns=patterns) is False


def test_compile_patterns_ignores_invalid():
    patterns = engine.compile_patterns(["(", r"\d+"])
    assert len(patterns) == 1
    assert engine.passes_block_patterns("abc", patterns) is True
    assert engine.passes_block_patterns("a1", patterns) is False


def test_build_chain():
    chain = engine.build_chain(["ab"], order=2)
    assert chain["\0\0"] == ["a"]
    assert chain["\0a"] == ["b"]
    assert chain["ab"] == ["\1"]
    chain1 = engine.build_chain(["ab"], order=1)
    assert chain1["\0"] == ["a"]
    assert engine.build_chain([], order=2) == {}


def test_generate_markov_is_seeded():
    first = engine.generate_markov(CORPUS, seed=1, attempts=50, max_candidates=10)
    second = engine.generate_markov(CORPUS, seed=1, attempts=50, max_candidates=10)
    assert isinstance(first, str)
    assert first == second
    assert 2 <= len(first) <= 20
    assert first not in CORPUS


def test_generate_markov_rng_argument():
    rng = random.Random(7)
    first = engine.generate_markov(CORPUS, rng=rng)
    assert first is not None
    assert engine.generate_markov(CORPUS, seed=7) == first


def test_generate_markov_insufficient_corpus():
    assert engine.generate_markov(["你好"], seed=1) is None
    assert engine.generate_markov([], seed=1) is None


def test_generate_markov_blocked():
    patterns = engine.compile_patterns(["."])
    assert engine.generate_markov(CORPUS, patterns=patterns, seed=2) is None


def test_generate_markov_order3():
    sentence = engine.generate_markov(CORPUS, order=3, seed=3, attempts=50)
    assert sentence is None or 2 <= len(sentence) <= 20


def test_pick_replay():
    assert engine.pick_replay([]) is None
    assert engine.pick_replay(["a", "b"], seed=1) in {"a", "b"}
    assert engine.pick_replay(["a", "b"], seed=1) == engine.pick_replay(["a", "b"], seed=1)


def test_generate_reply_replay():
    reply = engine.generate_reply("replay", user_corpus=["a", "b", "c"], seed=1)
    assert reply in {"a", "b", "c"}
    assert engine.generate_reply("replay", user_corpus=[], seed=1) is None


def test_generate_reply_markov_threshold():
    assert (
        engine.generate_reply(
            "markov", group_corpus=CORPUS[:3], min_corpus=10, seed=1
        )
        is None
    )
    reply = engine.generate_reply(
        "markov", group_corpus=CORPUS, min_corpus=5, seed=1, attempts=50
    )
    assert isinstance(reply, str)


def test_generate_reply_mixed_falls_back_to_replay():
    # 拦截正则挡住所有 Markov 候选 -> mixed 回退 replay
    patterns = engine.compile_patterns(["."])
    reply = engine.generate_reply(
        "mixed",
        user_corpus=["备用句子"],
        group_corpus=CORPUS,
        min_corpus=3,
        patterns=patterns,
        seed=1,
    )
    assert reply == "备用句子"


def test_generate_reply_unknown_mode_is_replay():
    reply = engine.generate_reply("banana", user_corpus=["x"], seed=1)
    assert reply == "x"


def test_generate_reply_markov_does_not_fall_back():
    assert (
        engine.generate_reply(
            "markov", user_corpus=["备用"], group_corpus=["太少"], min_corpus=5
        )
        is None
    )
