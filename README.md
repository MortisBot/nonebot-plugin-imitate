# nonebot-plugin-imitate

> 同系列插件与部署/架构文档：[`MortisBot/qqbot-plugins`](https://github.com/MortisBot/qqbot-plugins)（索引与文档仓）

QQ 群「模仿」插件：随机复读群友说过的话，或用语料训练字符级 Markov 链生成新句子。
默认**关闭**，只在白名单群里学习/发言，语料仅保存在本地 SQLite。

## 两种模式

| 模式 | 行为 |
|---|---|
| `replay`（默认） | 随机复读该用户最近 ≤ `IMITATE_MAX_RECORDS` 条短文本。行为规格复刻自 [koishi-plugin-imitate](https://www.npmjs.com/package/koishi-plugin-imitate) 2.0.6（MIT），**是行为复刻，不是代码拷贝**。 |
| `markov` | 用群语料训练字符级 2 阶 Markov 链生成新句子；语料不足 `IMITATE_MIN_CORPUS` 条时只学习、不生成。 |
| `mixed` | 语料够用 Markov，不够回退 replay。 |

学习语料按群隔离：A 群说过的话不会被拿到 B 群复读。

## 安装

```bash
nb plugin install nonebot-plugin-imitate
```

或在源码目录里开发安装：

```bash
uv venv .venv --python 3.13
uv pip install -e ".[dev]"
```

## 配置

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `IMITATE_ENABLED` | `0` | 总开关；默认关闭 |
| `IMITATE_GROUPS` | 空 | 允许学习/发言的群，逗号/空格分隔；**空 = 不生效** |
| `IMITATE_MODE` | `replay` | `replay` / `markov` / `mixed` |
| `IMITATE_DB_PATH` | `data/imitate/imitate.db` | 本地 SQLite 路径 |
| `IMITATE_PROBABILITY` | `0.02` | 每条可学习消息触发模仿的概率，0–1 |
| `IMITATE_MAX_LENGTH` | `20` | replay 学习/复读的最大长度（JS 字符数，emoji 计 2） |
| `IMITATE_MAX_RECORDS` | `100` | replay 每个用户保留的最近语料条数 |
| `IMITATE_MIN_CORPUS` | `500` | markov 出句的最低群语料条数 |
| `IMITATE_ORDER` | `2` | Markov 阶数，1–4 |
| `IMITATE_MAX_CORPUS_FETCH` | `5000` | 训练时最多读多少条群语料 |
| `IMITATE_MAX_ROWS_PER_GROUP` | `5000` | 每群语料行数上限（超出裁剪最旧） |
| `IMITATE_MIN_TEXT_LEN` | `2` | markov 学习/出句的最小长度 |
| `IMITATE_MAX_TEXT_LEN` | `80` | markov 学习的最大长度 |
| `IMITATE_MAX_GENERATE_LEN` | `20` | markov 出句的最大长度 |
| `IMITATE_DETECT_ROBOTS` | `1` | 用 `is_robot` 跳过 QQ 官方机器人 |
| `IMITATE_ROBOT_CACHE_TTL` | `3600` | 机器人标记缓存秒数 |
| `IMITATE_BOT_QQS` | 空 | 额外跳过的机器人/账号，逗号分隔 |
| `IMITATE_BLOCK_PATTERNS` | URL/域名两条正则 | 学习与发送共用的拦截正则，`;` 分隔 |
| `IMITATE_COOLDOWN_SECONDS` | `0` | 同群自动模仿的最短间隔 |
| `IMITATE_DEDUPE` | `1` | 同群相同文本只学一次 |
| `IMITATE_TARGET_ARG` | `1` | `1` 时 `模仿 <uid>` / `@某人` 生效；`0` 复刻上游「参数被忽略」的老行为 |

示例：

```bash
IMITATE_ENABLED=1
IMITATE_GROUPS=<群号>
IMITATE_MODE=replay
IMITATE_PROBABILITY=0.02
```

## 命令

| 命令 | 作用 |
|---|---|
| `模仿` | 模仿发送者自己 |
| `模仿 <uid>` | 模仿指定用户（`IMITATE_TARGET_ARG=1`） |
| `模仿 @某人` | 同上，用 at 指定 |

命令与自动模仿都只在 `IMITATE_GROUPS` 白名单群生效，且不需要 @bot。语料为空时
命令不回话（与上游一致），不会发送「学不到」之类的提示。

## 隐私与合规（请自行评估）

- 只保存 **群号 / 用户号 / 文本 / 时间戳** 四类字段到本地 `IMITATE_DB_PATH`，
  不保存图片、引用、文件、语音。
- 默认关闭；开启后请自行确认群规、成员知情与所在地法律/平台条款是否允许把群聊
  文本用于复读和 Markov 训练。维护者不提供任何合规担保。
- 拦截正则默认屏蔽 URL/域名；仍建议按群调整 `IMITATE_BLOCK_PATTERNS`。
- 想彻底清空：停服后删除 `IMITATE_DB_PATH` 指向的 `.db`（含 `-wal` / `-shm`）。

## 维护模式

- 一键停用：`IMITATE_ENABLED=0`（默认）。插件不响应任何消息、不学习、不建库。
- 只停某些群：把它们从 `IMITATE_GROUPS` 移除，或临时清空白名单（空 = 不生效）。
- 换模式：改 `IMITATE_MODE` 后重启；已有语料两种模式共用，不需要迁移。
- 语料膨胀：调小 `IMITATE_MAX_ROWS_PER_GROUP` / `IMITATE_MAX_RECORDS`，插件会在
  写入时按上限裁剪。

## 与上游实现的差异

- 删除了上游的隐藏命令、管理命令、`测试` 必触发后门与迁移脚本。
- 白名单语义从「空 = 全部群」收紧为「空 = 不生效」。
- 默认修正 `模仿 <uid>` 参数（上游 2.0.6 会忽略参数）。
- Markov 引擎来自另一套自研实现，与 replay 共用同一份语料表。

## 测试

```bash
uv venv .venv --python 3.13
uv pip install -e ".[dev]"
uv run pytest -q
```

测试不连 QQ、不发消息：覆盖学习过滤/去重/门槛、replay 抽取、固定 seed 的
Markov、模式切换、URL/机器人过滤、DB 容错和命令解析。

## License

MIT。第三方来源与许可见仓库根目录 `THIRD_PARTY_NOTICES.md`。
