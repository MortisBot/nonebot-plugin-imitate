<div align="center">

# nonebot-plugin-imitate

_✨ 随机复读 + 2 阶 Markov 群聊模仿 ✨_

[![LICENSE](https://img.shields.io/github/license/MortisBot/nonebot-plugin-imitate.svg)](./LICENSE)
[![pypi](https://img.shields.io/pypi/v/nonebot-plugin-imitate.svg)](https://pypi.python.org/pypi/nonebot-plugin-imitate)
![python](https://img.shields.io/badge/python-3.10+-blue.svg)

</div>

## 📖 介绍

学习群消息并模仿：默认随机复读该用户的短消息，可切换为字符级 2 阶 Markov 生成。默认**完全关闭**、按群白名单生效，语料只存本地 SQLite。

> `replay` 模式的行为规格来自 koishi-plugin-imitate 2.0.6（MIT），是行为复刻而非代码拷贝。

## 💿 安装

<details open>
<summary>使用 nb-cli 安装</summary>

在 NoneBot2 项目根目录下执行：

```bash
nb plugin install nonebot-plugin-imitate --upgrade
```

国内网络可换镜像源：

```bash
nb plugin install nonebot-plugin-imitate --upgrade -i "https://pypi.tuna.tsinghua.edu.cn/simple"
```

</details>

<details>
<summary>使用包管理器安装</summary>

在 NoneBot2 项目根目录下执行其一：

```bash
uv add nonebot-plugin-imitate
# 或
pdm add nonebot-plugin-imitate
# 或
poetry add nonebot-plugin-imitate
```

直接装仓库主分支（PyPI 包发布前可用）：

```bash
uv add git+https://github.com/MortisBot/nonebot-plugin-imitate@main
```

然后在 `pyproject.toml` 的 `[tool.nonebot]` 中追加：

```toml
plugins = ["nonebot_plugin_imitate"]
```

</details>

## ⚙️ 配置

在 NoneBot2 项目的 `.env` 中配置（配置项即环境变量名，大写）：

| 配置项 | 必填 | 默认值 | 说明 |
|:---:|:---:|:---:|:---|
| `IMITATE_ENABLED` | 是 | `false` | 总开关 |
| `IMITATE_MODE` | 否 | `replay` | `replay` / `markov` / `mixed` |
| `IMITATE_GROUPS` | 是 | 空 | 生效群号，逗号分隔（空 = 不生效） |
| `IMITATE_PROB` | 否 | `0.02` | replay 自动触发概率 |
| `IMITATE_MAX_RECORDS` | 否 | `100` | 每人保留语料条数 |
| `IMITATE_MIN_CORPUS` | 否 | `500` | markov 开始生成的最小语料量 |
| `IMITATE_DB_PATH` | 否 | `data/imitate/imitate.db` | 本地 SQLite 路径 |

## 🎉 使用

| 命令 | 权限 | 需要 @ | 范围 | 说明 |
|:---:|:---:|:---:|:---:|:---|
| `模仿` | 群员 | 否 | 群聊 | 随机复读一条该用户的短消息 |
| `模仿 @某人` | 群员 | 否 | 群聊 | 复读指定用户 |
| `模仿 <QQ号>` | 群员 | 否 | 群聊 | 同上 |

## 🔌 适配器

OneBot v11（`supported_adapters={"~onebot.v11"}`）。语料仅写入本地 SQLite；删除 `IMITATE_DB_PATH` 即可清空。

## 📄 License

[MIT](./LICENSE) · 维护模式（best-effort，无 SLA）
