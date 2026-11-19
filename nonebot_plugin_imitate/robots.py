"""QQ 官方机器人识别（带 TTL 缓存，不 import NoneBot）。

群成员信息里的 ``is_robot`` 是 NapCat 对 QQ 官方机器人的标记；查询失败按
「不是机器人」处理，避免影响正常学习。
"""

from __future__ import annotations

import logging
import time
from collections import OrderedDict

logger = logging.getLogger(__name__)


class RobotCache:
    """``group_id:user_id -> is_robot`` 的小型 TTL/LRU 缓存。"""

    def __init__(self, ttl: float, max_size: int = 2048) -> None:
        self.ttl = float(ttl)
        self.max_size = max(16, int(max_size))
        self._data: OrderedDict[str, tuple[float, bool]] = OrderedDict()

    def get(self, key: str) -> bool | None:
        hit = self._data.get(key)
        if hit is None:
            return None
        created_at, value = hit
        if time.monotonic() - created_at > self.ttl:
            self._data.pop(key, None)
            return None
        return value

    def put(self, key: str, value: bool) -> None:
        self._data[key] = (time.monotonic(), bool(value))
        self._data.move_to_end(key)
        while len(self._data) > self.max_size:
            self._data.popitem(last=False)

    def clear(self) -> None:
        self._data.clear()


async def is_official_robot(
    bot,
    group_id: int,
    user_id: int,
    cache: RobotCache,
) -> bool:
    """查询群成员是否为 QQ 官方机器人；结果写缓存。"""
    key = f"{group_id}:{user_id}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    try:
        info = await bot.call_api(
            "get_group_member_info",
            group_id=int(group_id),
            user_id=int(user_id),
            no_cache=False,
        )
    except Exception as exc:  # noqa: BLE001 - 查询失败按非机器人处理
        logger.debug(
            "[imitate] get_group_member_info failed user=%s: %s", user_id, exc
        )
        return False

    is_robot = bool(info.get("is_robot")) if isinstance(info, dict) else False
    cache.put(key, is_robot)
    return is_robot


__all__ = ["RobotCache", "is_official_robot"]
