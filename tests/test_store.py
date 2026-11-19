"""统一存储：schema/索引、去重、按群隔离、recent 排序、裁剪、DB 容错。"""

from __future__ import annotations

import sqlite3
import time

from nonebot_plugin_imitate import store


def _indexes(db) -> set[str]:
    conn = sqlite3.connect(str(db))
    try:
        rows = conn.execute("PRAGMA index_list('corpus')").fetchall()
    finally:
        conn.close()
    return {str(row[1]) for row in rows}


def _columns(db) -> list[str]:
    conn = sqlite3.connect(str(db))
    try:
        rows = conn.execute("PRAGMA table_info('corpus')").fetchall()
    finally:
        conn.close()
    return [str(row[1]) for row in rows]


def test_schema_and_indexes(tmp_path):
    db = tmp_path / "imitate.db"
    store.init_db(db)
    assert db.is_file()
    assert _columns(db) == ["id", "group_id", "user_id", "content", "created_at"]
    indexes = _indexes(db)
    assert "idx_imitate_corpus_group_time" in indexes
    assert "idx_imitate_corpus_group_content" in indexes
    assert store.get_meta(db, "schema_version") == store.SCHEMA_VERSION == "1"


def test_init_is_idempotent(tmp_path):
    db = tmp_path / "nested" / "imitate.db"
    store.init_db(db)
    store.init_db(db)
    assert store.add_corpus(db, 10000, 10001, "你好呀", 1000.0) is True


def test_add_corpus_dedupe(tmp_path):
    db = tmp_path / "imitate.db"
    store.init_db(db)
    assert store.add_corpus(db, 10000, 10001, "复读测试", 1000.0) is True
    # 同群同文本只入一行
    assert store.add_corpus(db, 10000, 10002, "复读测试", 1001.0) is False
    assert store.count_corpus(db, 10000) == 1
    # 关掉去重可重复写入
    assert store.add_corpus(db, 10000, 10002, "复读测试", 1002.0, dedupe=False) is True
    assert store.count_corpus(db, 10000) == 2
    # 空文本不写
    assert store.add_corpus(db, 10000, 10001, "", 1003.0) is False


def test_corpus_is_group_scoped(tmp_path):
    db = tmp_path / "imitate.db"
    store.init_db(db)
    store.add_corpus(db, 10000, 10001, "同一句话", 1.0)
    store.add_corpus(db, 10001, 10001, "同一句话", 2.0)
    assert store.count_corpus(db, 10000) == 1
    assert store.count_corpus(db, 10001) == 1
    assert store.fetch_user_corpus(db, 10000, 10001) == ["同一句话"]
    assert store.fetch_user_corpus(db, 10002, 10001) == []


def test_fetch_orders_recent_first(tmp_path):
    db = tmp_path / "imitate.db"
    store.init_db(db)
    now = time.time()
    for index in range(5):
        store.add_corpus(db, 10000, 10001, f"m{index}", now + index)
    assert store.fetch_group_corpus(db, 10000, 3) == ["m4", "m3", "m2"]
    assert store.fetch_user_corpus(db, 10000, 10001, 2) == ["m4", "m3"]
    assert store.fetch_user_corpus(db, 10000, 10002, 2) == []


def test_counts(tmp_path):
    db = tmp_path / "imitate.db"
    store.init_db(db)
    store.add_corpus(db, 10000, 10001, "a")
    store.add_corpus(db, 10000, 10001, "b")
    store.add_corpus(db, 10000, 10002, "c")
    assert store.count_corpus(db, 10000) == 3
    assert store.count_user_corpus(db, 10000, 10001) == 2
    assert store.count_user_corpus(db, 10000, 10002) == 1
    assert store.count_user_corpus(db, 10000, 10003) == 0


def test_prune_group(tmp_path):
    db = tmp_path / "imitate.db"
    store.init_db(db)
    for index in range(5):
        store.add_corpus(db, 10000, 10001, f"m{index}")
    store.add_corpus(db, 10001, 10001, "other")
    removed = store.prune_group(db, 10000, 2)
    assert removed == 3
    assert store.count_corpus(db, 10000) == 2
    assert store.count_corpus(db, 10001) == 1
    assert store.fetch_group_corpus(db, 10000) == ["m4", "m3"]


def test_meta_roundtrip(tmp_path):
    db = tmp_path / "imitate.db"
    store.init_db(db)
    assert store.get_meta(db, "missing") is None
    assert store.get_meta(db, "missing", "fallback") == "fallback"
    store.set_meta(db, "maintenance", "1")
    assert store.get_meta(db, "maintenance") == "1"
    store.set_meta(db, "maintenance", "0")
    assert store.get_meta(db, "maintenance") == "0"


def test_try_init_db_failure(tmp_path):
    # 传目录：sqlite 打不开，返回 False 而不是抛错
    assert store.try_init_db(tmp_path) is False


def test_try_init_db_corrupt_file(tmp_path):
    db = tmp_path / "corrupt.db"
    db.write_bytes(b"this is not a sqlite database" * 100)
    assert store.try_init_db(db) is False


def test_try_init_db_success(tmp_path):
    assert store.try_init_db(tmp_path / "ok.db") is True


def test_write_error_propagates(tmp_path):
    # 父路径是文件时，底层异常应抛出，交给插件 handler 兜底
    parent = tmp_path / "blocker"
    parent.write_text("x")
    try:
        store.add_corpus(parent / "db.sqlite", 10000, 10001, "hi")
    except (sqlite3.OperationalError, NotADirectoryError, OSError):
        pass
    else:  # pragma: no cover
        raise AssertionError("不可写路径应抛错")
