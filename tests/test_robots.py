"""QQ 官方机器人识别与 TTL 缓存。"""

from __future__ import annotations

import time

from nonebot_plugin_imitate import robots


def test_cache_ttl_and_eviction():
    cache = robots.RobotCache(ttl=60, max_size=16)
    assert cache.get("10000:10001") is None
    cache.put("10000:10001", True)
    assert cache.get("10000:10001") is True
    cache.put("10000:10001", False)
    assert cache.get("10000:10001") is False

    short = robots.RobotCache(ttl=0.001, max_size=16)
    short.put("10000:10001", True)
    time.sleep(0.01)
    assert short.get("10000:10001") is None

    small = robots.RobotCache(ttl=60, max_size=16)
    for index in range(40):
        small.put(f"1:{index}", True)
    assert len(small._data) == 16
    assert small.get("1:0") is None
    assert small.get("1:39") is True

    small.clear()
    assert small.get("1:39") is None


async def test_is_official_robot_cached(fake_bot):
    bot = fake_bot({"get_group_member_info": {"is_robot": True}})
    cache = robots.RobotCache(ttl=60)
    assert await robots.is_official_robot(bot, 10000, 10001, cache) is True
    assert await robots.is_official_robot(bot, 10000, 10001, cache) is True
    assert len(bot.calls) == 1


async def test_is_official_robot_human(fake_bot):
    bot = fake_bot({"get_group_member_info": {"is_robot": False}})
    cache = robots.RobotCache(ttl=60)
    assert await robots.is_official_robot(bot, 10000, 10001, cache) is False


async def test_is_official_robot_api_failure(fake_bot):
    bot = fake_bot({"get_group_member_info": RuntimeError("down")})
    cache = robots.RobotCache(ttl=60)
    assert await robots.is_official_robot(bot, 10000, 10001, cache) is False
    # 失败不写缓存，下次还会重试
    await robots.is_official_robot(bot, 10000, 10001, cache)
    assert len(bot.calls) == 2


async def test_is_official_robot_non_dict(fake_bot):
    bot = fake_bot({"get_group_member_info": "unexpected"})
    cache = robots.RobotCache(ttl=60)
    assert await robots.is_official_robot(bot, 10000, 10001, cache) is False
