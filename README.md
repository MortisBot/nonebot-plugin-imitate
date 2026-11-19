# nonebot-plugin-imitate

_✨ 学习群消息并模仿：默认随机复读群友短消息，可切换字符级 Markov 生成。 ✨_

<a href="./LICENSE"><img src="https://img.shields.io/github/license/MortisBot/nonebot-plugin-imitate.svg" alt="license"></a>
<a href="https://pypi.python.org/pypi/nonebot-plugin-imitate"><img src="https://img.shields.io/pypi/v/nonebot-plugin-imitate.svg" alt="pypi"></a>
<img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="python">

## 安装

在 NoneBot2 项目根目录下执行：

```bash
nb plugin install nonebot-plugin-imitate
```

或手动安装：

```bash
pip install nonebot-plugin-imitate
```

并在 `pyproject.toml` 的 `[tool.nonebot]` 中追加：

```toml
plugins = ["nonebot_plugin_imitate"]
```

## 配置

在 `.env` 中配置（环境变量名即配置项大写）：

| 配置项 | 必填 | 默认值 | 说明 |
|:---:|:---:|:---:|:---|
| `IMITATE_ENABLED` | 是 | `false` | 总开关 |
| `IMITATE_MODE` | 否 | `replay` | `replay` / `markov` / `mixed` |
| `IMITATE_GROUPS` | 是 | 空 | 生效群号，逗号分隔（空 = 不生效） |
| `IMITATE_PROB` | 否 | `0.02` | replay 自动触发概率 |
| `IMITATE_MAX_RECORDS` | 否 | `100` | 每人保留的语料条数 |
| `IMITATE_MIN_CORPUS` | 否 | `500` | markov 生成本群最小语料量 |
| `IMITATE_DB_PATH` | 否 | `data/imitate/imitate.db` | SQLite 路径 |

## 使用

| 命令 | 说明 |
|:---:|:---|
| `模仿` | 随机复读一条该用户的短消息 |
| `模仿 @某人` | 复读指定用户的短消息 |
| `模仿 <QQ号>` | 同上 |

默认关闭；开启后还会自动学习群消息并按概率自动模仿。语料只存本地 SQLite。

## 适配器

OneBot v11（`supported_adapters={"~onebot.v11"}`）。

## License

[MIT](./LICENSE)

> 维护模式：原项目已停止运营，本插件按 best-effort 维护，无 SLA。
