"""imitate —— 随机复读 / Markov 群消息模仿（OneBot v11，默认关闭）。

两种模式：

* ``replay``（默认）：随机复读该用户最近 ≤ ``IMITATE_MAX_RECORDS`` 条短消息。
  行为规格复刻自 koishi-plugin-imitate 2.0.6（MIT），不是代码拷贝。
* ``markov``：用群语料训练字符级 2 阶 Markov 链生成新句子，语料不足
  ``IMITATE_MIN_CORPUS`` 条时只学习不发言。
* ``mixed``：语料够用 Markov，不够回退 replay。

命令：``模仿`` / ``模仿 <uid>`` / ``模仿 @某人``（``IMITATE_TARGET_ARG=1`` 时
uid 参数生效；默认已修正上游「参数被忽略」的问题）。

安全默认：``IMITATE_ENABLED=0``、``IMITATE_GROUPS`` 为空——什么都不做。
学习与自动发送都只发生在白名单群里；不注册任何隐藏/删库/必触发后门命令。
"""

from __future__ import annotations

import asyncio
import random
import time

from nonebot import logger, on_message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, MessageEvent
from nonebot.plugin import PluginMetadata
from nonebot.rule import Rule

from . import behavior, engine, robots, store
from . import text as text_mod
from .config import ImitateConfig, load_config

__plugin_meta__ = PluginMetadata(
    name="imitate",
    description=(
        "学习群消息并模仿：默认随机复读该用户的短消息，可切换为字符级 Markov；"
        "默认关闭、按群白名单，语料只存本地 SQLite。"
    ),
    usage="模仿\n模仿 <uid>\n模仿 @某人",
    type="application",
    homepage="https://github.com/MortisBot/nonebot-plugin-imitate",
    supported_adapters={"~onebot.v11"},
)

CFG: ImitateConfig = load_config()
PATTERNS = engine.compile_patterns(CFG.block_patterns)
ROBOT_CACHE = robots.RobotCache(CFG.robot_cache_ttl)

_db_state: bool | None = None
_last_sent: dict[int, float] = {}
_insert_counts: dict[int, int] = {}


def _db_ready() -> bool:
    global _db_state
    if _db_state is None:
        _db_state = store.try_init_db(CFG.db_path)
    return _db_state


def _segments(event: MessageEvent):
    """优先用 adapter 处理前的原始消息，对齐 Koishi ``session.content``。"""
    message = getattr(event, "original_message", None)
    if message is None:
        message = event.get_message()
    return text_mod.segments_from_onebot_message(message)


def _group_allowed(group_id: object) -> bool:
    return behavior.group_allowed(group_id, CFG.groups)


def _is_ignored_user(event: MessageEvent, bot: Bot) -> bool:
    user_id = str(event.user_id)
    if user_id == str(bot.self_id):
        return True
    try:
        return int(user_id) in CFG.bot_qqs
    except ValueError:
        return False


def _cooldown_ok(group_id: int) -> bool:
    if CFG.cooldown_seconds <= 0:
        return True
    last = _last_sent.get(group_id)
    if last is None:  # 从未发过：立即放行（不依赖 monotonic 的起点）
        return True
    return time.monotonic() - last >= CFG.cooldown_seconds


def _rule_auto(event: MessageEvent, bot: Bot) -> bool:
    return CFG.enabled and isinstance(event, GroupMessageEvent)


def _rule_command(event: MessageEvent, bot: Bot) -> bool:
    if not CFG.enabled or not isinstance(event, GroupMessageEvent):
        return False
    if not _group_allowed(event.group_id):
        return False
    return (
        behavior.parse_command(
            _segments(event), behavior.COMMANDS, str(bot.self_id)
        )
        is not None
    )


auto_matcher = on_message(rule=Rule(_rule_auto), priority=99, block=False)
command_matcher = on_message(rule=Rule(_rule_command), priority=5, block=True)


async def _generate(
    group_id: int, user_id: int, *, user_corpus: list[str] | None = None
) -> str | None:
    """按当前模式生成一句回复；任何异常都降级为 None。"""
    if not _db_ready():
        return None
    try:
        if user_corpus is None and CFG.mode in {"replay", "mixed"}:
            user_corpus = await asyncio.to_thread(
                store.fetch_user_corpus,
                CFG.db_path,
                group_id,
                user_id,
                CFG.max_records,
            )
        group_corpus: list[str] = []
        if CFG.mode in {"markov", "mixed"}:
            group_corpus = await asyncio.to_thread(
                store.fetch_group_corpus,
                CFG.db_path,
                group_id,
                CFG.max_corpus_fetch,
            )
        return await asyncio.to_thread(
            engine.generate_reply,
            CFG.mode,
            user_corpus=user_corpus or [],
            group_corpus=group_corpus,
            order=CFG.order,
            min_len=CFG.min_text_len,
            max_generate_len=CFG.max_generate_len,
            patterns=PATTERNS,
            min_corpus=CFG.min_corpus,
        )
    except Exception:  # noqa: BLE001 - 生成失败不能影响聊天
        logger.exception(
            "[imitate] 生成失败 group={} user={}", group_id, user_id
        )
        return None


async def _learn(event: GroupMessageEvent, bot: Bot) -> str | None:
    """学习 + 概率触发；返回要发送的句子（不发送）。"""
    if not _db_ready():
        return None
    group_id = int(event.group_id)
    user_id = int(event.user_id)
    if _is_ignored_user(event, bot):
        return None
    if not _group_allowed(group_id):
        return None

    content = engine.clean_text(text_mod.stripped_content(_segments(event)))
    if not content:
        return None
    if not engine.passes_block_patterns(content, PATTERNS):
        return None
    if CFG.mode == "replay":
        if text_mod.js_length(content) > CFG.max_length:
            return None
    elif not engine.should_learn(
        content,
        min_len=CFG.min_text_len,
        max_len=CFG.max_text_len,
        patterns=PATTERNS,
    ):
        return None

    if CFG.detect_robots and await robots.is_official_robot(
        bot, group_id, user_id, ROBOT_CACHE
    ):
        return None

    pre_user: list[str] = []
    if CFG.mode in {"replay", "mixed"}:
        try:
            pre_user = await asyncio.to_thread(
                store.fetch_user_corpus,
                CFG.db_path,
                group_id,
                user_id,
                CFG.max_records,
            )
        except Exception:  # noqa: BLE001 - 读库失败就当没有历史
            logger.debug("[imitate] 读取用户语料失败 group={}", group_id)

    if CFG.mode == "replay":
        plan = behavior.plan_message(
            content,
            pre_user,
            prob=CFG.probability,
            max_length=CFG.max_length,
        )
        record, trigger, reply = plan.record, plan.trigger, plan.reply
    else:
        record = True
        trigger = random.random() < CFG.probability
        reply = None

    if record:
        try:
            inserted = await asyncio.to_thread(
                store.add_corpus,
                CFG.db_path,
                group_id,
                user_id,
                content,
                None,
                CFG.dedupe,
            )
        except Exception:  # noqa: BLE001 - 写库失败不能影响聊天
            logger.exception("[imitate] 写库失败 group={}", group_id)
            inserted = False
        if inserted:
            counter = _insert_counts.get(group_id, 0) + 1
            _insert_counts[group_id] = counter
            if counter % 50 == 0:
                try:
                    await asyncio.to_thread(
                        store.prune_group,
                        CFG.db_path,
                        group_id,
                        CFG.max_rows_per_group,
                    )
                except Exception:  # noqa: BLE001 - 清理失败下轮再说
                    logger.debug("[imitate] 清理语料失败 group={}", group_id)

    if not trigger or not _cooldown_ok(group_id):
        return None
    if reply is not None:
        return reply
    return await _generate(group_id, user_id, user_corpus=pre_user)


@auto_matcher.handle()
async def _handle_auto(event: GroupMessageEvent, bot: Bot) -> None:
    try:
        reply = await _learn(event, bot)
        if reply:
            await auto_matcher.send(reply)
            _last_sent[int(event.group_id)] = time.monotonic()
            logger.info(
                "[imitate] sent group={} mode={} len={}",
                event.group_id,
                CFG.mode,
                len(reply),
            )
    except Exception:  # noqa: BLE001 - handler 全兜底
        logger.exception(
            "[imitate] handler error group={} user={}",
            getattr(event, "group_id", "?"),
            getattr(event, "user_id", "?"),
        )


def _resolve_target(match: behavior.CommandMatch, fallback: int) -> int:
    """``IMITATE_TARGET_ARG=1`` 时用 at / uid 参数，否则模仿发送者本人。"""
    if not CFG.target_arg:
        return fallback
    target = behavior.get_target_id(match.at_ids, match.tail)
    if target is None:
        return fallback
    try:
        return int(target)
    except ValueError:
        return fallback


@command_matcher.handle()
async def _handle_command(event: GroupMessageEvent, bot: Bot) -> None:
    if not _group_allowed(event.group_id):
        return
    match = behavior.parse_command(
        _segments(event), behavior.COMMANDS, str(bot.self_id)
    )
    if match is None:
        return
    group_id = int(event.group_id)
    user_id = _resolve_target(match, int(event.user_id))
    reply = await _generate(group_id, user_id)
    if reply:
        await command_matcher.finish(reply)


__all__ = ["CFG", "auto_matcher", "command_matcher"]
