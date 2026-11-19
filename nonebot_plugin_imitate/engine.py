"""Markov 生成与文本过滤（纯函数，不 import NoneBot）。

算法：字符级 2 阶 Markov 链（``ORDER`` 默认 2，``\\0`` 起点、``\\1`` 终点），
只排除与语料完全相同的句子。学习期与发送期共用一套「拦截正则」（默认 URL/
域名）；发送前多候选重试，命中拦截就换下一个候选。

所有随机源可注入（``rng`` 或 ``seed``），便于固定种子测试。
"""

from __future__ import annotations

import random
import re
from collections.abc import Iterable

COMMAND_PREFIXES = ("/", "／", "!", "！", ".", "。")
_CQ_MARKER = "[CQ:"
_START = "\0"
_END = "\1"

MODES = ("replay", "markov", "mixed")


def compile_patterns(patterns: Iterable[str]) -> tuple[re.Pattern[str], ...]:
    """编译拦截正则；非法正则直接忽略，不让配置错误拖垮插件。"""
    compiled: list[re.Pattern[str]] = []
    for pattern in patterns:
        try:
            compiled.append(re.compile(pattern))
        except re.error:
            continue
    return tuple(compiled)


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def passes_block_patterns(text: str, patterns: Iterable[re.Pattern[str]]) -> bool:
    """True 表示文本没命中拦截规则，可以学习/发送。"""
    return not any(pattern.search(text) for pattern in patterns)


def should_learn(
    text: str,
    *,
    min_len: int = 2,
    max_len: int = 80,
    patterns: Iterable[re.Pattern[str]] = (),
) -> bool:
    """Markov 模式的学习过滤：长度、命令前缀、纯数字、CQ 片段、URL。"""
    text = clean_text(text)
    if not (min_len <= len(text) <= max_len):
        return False
    if text.startswith(COMMAND_PREFIXES):
        return False
    if text.isdigit():
        return False
    if _CQ_MARKER in text:
        return False
    return passes_block_patterns(text, patterns)


def build_chain(corpus: Iterable[str], order: int = 2) -> dict[str, list[str]]:
    """把语料切成 ``前缀 -> 后继字符`` 的映射。"""
    order = max(1, int(order))
    chain: dict[str, list[str]] = {}
    for text in corpus:
        text = clean_text(text)
        if not text:
            continue
        padded = _START * order + text + _END
        for i in range(len(padded) - order):
            prefix = padded[i : i + order]
            chain.setdefault(prefix, []).append(padded[i + order])
    return chain


def generate_markov(
    corpus: Iterable[str],
    *,
    order: int = 2,
    min_len: int = 2,
    max_generate_len: int = 20,
    patterns: Iterable[re.Pattern[str]] = (),
    rng: random.Random | None = None,
    seed: int | None = None,
    attempts: int = 20,
    max_candidates: int = 5,
) -> str | None:
    """从语料生成一句 2~max_generate_len 字的句子；失败返回 None。"""
    corpus_list = [clean_text(text) for text in corpus]
    corpus_list = [text for text in corpus_list if text]
    if len(corpus_list) < 2:
        return None

    order = max(1, int(order))
    chain = build_chain(corpus_list, order)
    if not chain:
        return None

    corpus_set = set(corpus_list)
    random_source = rng if rng is not None else random.Random(seed)

    for _ in range(max(1, int(max_candidates))):
        for _ in range(max(1, int(attempts))):
            prefix = _START * order
            output: list[str] = []
            for _ in range(max(1, int(max_generate_len))):
                candidates = chain.get(prefix)
                if not candidates:
                    break
                next_char = random_source.choice(candidates)
                if next_char == _END:
                    break
                output.append(next_char)
                prefix = (prefix + next_char)[-order:]

            sentence = clean_text("".join(output))
            if not (min_len <= len(sentence) <= max_generate_len):
                continue
            if sentence in corpus_set:
                continue
            if not passes_block_patterns(sentence, patterns):
                continue
            return sentence

    return None


def pick_replay(
    corpus: Iterable[str], *, rng: random.Random | None = None, seed: int | None = None
) -> str | None:
    """从「该用户最近 N 条短消息」里随机挑一条复读。"""
    items = [text for text in corpus if isinstance(text, str) and text]
    if not items:
        return None
    random_source = rng if rng is not None else random.Random(seed)
    return random_source.choice(items)


def generate_reply(
    mode: str,
    *,
    user_corpus: Iterable[str] = (),
    group_corpus: Iterable[str] = (),
    order: int = 2,
    min_len: int = 2,
    max_generate_len: int = 20,
    patterns: Iterable[re.Pattern[str]] = (),
    min_corpus: int = 1,
    attempts: int = 20,
    max_candidates: int = 5,
    rng: random.Random | None = None,
    seed: int | None = None,
) -> str | None:
    """按模式生成一句要发的话；没有可用语料时返回 None。"""
    mode = (mode or "replay").strip().lower()
    if mode not in MODES:
        mode = "replay"
    user_items = [text for text in user_corpus if isinstance(text, str) and text]
    group_items = [text for text in group_corpus if isinstance(text, str) and text]

    if mode == "replay":
        return pick_replay(user_items, rng=rng, seed=seed)

    sentence: str | None = None
    if len(group_items) >= max(1, int(min_corpus)):
        sentence = generate_markov(
            group_items,
            order=order,
            min_len=min_len,
            max_generate_len=max_generate_len,
            patterns=patterns,
            rng=rng,
            seed=seed,
            attempts=attempts,
            max_candidates=max_candidates,
        )
    if sentence is None and mode == "mixed":
        return pick_replay(user_items, rng=rng, seed=seed)
    return sentence


__all__ = [
    "COMMAND_PREFIXES",
    "build_chain",
    "clean_text",
    "compile_patterns",
    "generate_markov",
    "generate_reply",
    "passes_block_patterns",
    "pick_replay",
    "should_learn",
]
