"""imitate 统一存储层（标准库 sqlite3，不 import NoneBot）。

表结构：

    corpus(id INTEGER PRIMARY KEY, group_id TEXT, user_id TEXT, content TEXT,
           created_at REAL)               群消息短文本语料
    meta(key TEXT PRIMARY KEY, value TEXT) schema_version 等元信息

索引 ``(group_id, created_at)`` 与 ``(group_id, content)`` 分别服务「按群取最近
语料」与「同群文本去重」。语料按群隔离：A 群的句子不会被拿去在 B 群复读。
"""

from __future__ import annotations

import logging
import sqlite3
import time
from pathlib import Path

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "1"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS corpus (
    id INTEGER PRIMARY KEY,
    group_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

_INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_imitate_corpus_group_time "
    "ON corpus(group_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_imitate_corpus_group_content "
    "ON corpus(group_id, content)",
)


def _connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=10.0)
    conn.execute("PRAGMA busy_timeout = 10000")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def init_db(db_path: str | Path) -> None:
    """建表/索引并写入 schema_version（幂等）。"""
    conn = _connect(db_path)
    try:
        conn.executescript(_SCHEMA)
        for statement in _INDEXES:
            conn.execute(statement)
        conn.execute(
            "INSERT OR IGNORE INTO meta(key, value) VALUES(?, ?)",
            ("schema_version", SCHEMA_VERSION),
        )
        conn.commit()
    finally:
        conn.close()


def try_init_db(db_path: str | Path) -> bool:
    """初始化数据库；失败只记日志并返回 False（插件降级为不学习）。"""
    try:
        init_db(db_path)
        return True
    except Exception:  # noqa: BLE001 - 数据库不可用时不能拖垮 bot
        logger.warning(
            "[imitate] 初始化数据库失败 path=%s", db_path, exc_info=True
        )
        return False


def _exists(conn: sqlite3.Connection, group_id: str, content: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM corpus WHERE group_id = ? AND content = ? LIMIT 1",
        (group_id, content),
    ).fetchone()
    return row is not None


def add_corpus(
    db_path: str | Path,
    group_id: object,
    user_id: object,
    content: str,
    created_at: float | None = None,
    dedupe: bool = True,
) -> bool:
    """写入一条语料；``dedupe=True`` 时同群同文本只保留一行。"""
    content = str(content)
    if not content:
        return False
    conn = _connect(db_path)
    try:
        if dedupe and _exists(conn, str(group_id), content):
            return False
        conn.execute(
            "INSERT INTO corpus(group_id, user_id, content, created_at) "
            "VALUES(?, ?, ?, ?)",
            (
                str(group_id),
                str(user_id),
                content,
                float(created_at if created_at is not None else time.time()),
            ),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def count_corpus(db_path: str | Path, group_id: object) -> int:
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM corpus WHERE group_id = ?", (str(group_id),)
        ).fetchone()
        return int(row[0]) if row else 0
    finally:
        conn.close()


def count_user_corpus(
    db_path: str | Path, group_id: object, user_id: object
) -> int:
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM corpus WHERE group_id = ? AND user_id = ?",
            (str(group_id), str(user_id)),
        ).fetchone()
        return int(row[0]) if row else 0
    finally:
        conn.close()


def fetch_group_corpus(
    db_path: str | Path, group_id: object, limit: int = 5000
) -> list[str]:
    """取某群最近的语料（新的在前），供 Markov 训练。"""
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT content FROM corpus WHERE group_id = ? "
            "ORDER BY id DESC LIMIT ?",
            (str(group_id), max(1, int(limit))),
        ).fetchall()
        return [str(row[0]) for row in rows]
    finally:
        conn.close()


def fetch_user_corpus(
    db_path: str | Path,
    group_id: object,
    user_id: object,
    limit: int = 100,
) -> list[str]:
    """取某群某用户最近的短文本（新的在前），供 replay 随机抽取。"""
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT content FROM corpus WHERE group_id = ? AND user_id = ? "
            "ORDER BY created_at DESC, id DESC LIMIT ?",
            (str(group_id), str(user_id), max(1, int(limit))),
        ).fetchall()
        return [str(row[0]) for row in rows]
    finally:
        conn.close()


def prune_group(db_path: str | Path, group_id: object, max_rows: int) -> int:
    """每群只保留最近 max_rows 行，返回删除行数。"""
    gid = str(group_id)
    keep = max(1, int(max_rows))
    conn = _connect(db_path)
    try:
        cursor = conn.execute(
            "DELETE FROM corpus WHERE group_id = ? AND id NOT IN ("
            "SELECT id FROM corpus WHERE group_id = ? ORDER BY id DESC LIMIT ?"
            ")",
            (gid, gid, keep),
        )
        conn.commit()
        return int(cursor.rowcount)
    finally:
        conn.close()


def get_meta(
    db_path: str | Path, key: str, default: str | None = None
) -> str | None:
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT value FROM meta WHERE key = ?", (key,)
        ).fetchone()
        return str(row[0]) if row else default
    finally:
        conn.close()


def set_meta(db_path: str | Path, key: str, value: str) -> None:
    conn = _connect(db_path)
    try:
        conn.execute(
            "INSERT INTO meta(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )
        conn.commit()
    finally:
        conn.close()


__all__ = [
    "SCHEMA_VERSION",
    "add_corpus",
    "count_corpus",
    "count_user_corpus",
    "fetch_group_corpus",
    "fetch_user_corpus",
    "get_meta",
    "init_db",
    "prune_group",
    "set_meta",
    "try_init_db",
]
