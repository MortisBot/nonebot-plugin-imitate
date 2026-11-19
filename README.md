# nonebot-plugin-imitate

让机器人学会群友说话——但默认**完全关闭**。

## 三种模式

| `IMITATE_MODE` | 行为 |
|:---:|:---|
| `replay`（默认） | 从该用户最近的短消息里随机复读一条 |
| `markov` | 用本群语料训练 2 阶字符级 Markov 链生成新句子 |
| `mixed` | 语料够用时走 Markov，不够回退 replay |

> `replay` 的行为规格来自 koishi-plugin-imitate 2.0.6（MIT），是行为复刻而非代码拷贝。

## 安装

```bash
nb plugin install nonebot-plugin-imitate
```

或手动 `pip install nonebot-plugin-imitate`，并在 `pyproject.toml` 中启用 `nonebot_plugin_imitate`。

## 配置（最小示例）

```dotenv
IMITATE_ENABLED=true
IMITATE_MODE=replay
IMITATE_GROUPS=123456789,987654321
IMITATE_PROB=0.02
```

| 变量 | 默认 | 说明 |
|:---:|:---:|:---|
| `IMITATE_ENABLED` | `false` | 总开关 |
| `IMITATE_GROUPS` | 空 | 生效群；空 = 不生效 |
| `IMITATE_PROB` | `0.02` | replay 自动触发概率 |
| `IMITATE_MAX_RECORDS` | `100` | 每人保留语料条数 |
| `IMITATE_MIN_CORPUS` | `500` | markov 开始生成的最小语料量 |
| `IMITATE_DB_PATH` | `data/imitate/imitate.db` | 本地 SQLite |

## 指令

- `模仿`
- `模仿 @某人`
- `模仿 <QQ号>`

语料只写入本地 SQLite；删除 `IMITATE_DB_PATH` 即可清空。

## License

[MIT](./LICENSE) · 维护模式（best-effort）
