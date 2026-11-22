# opencode 各环节延迟基准：glm-5.3-flash 有 ~5s 固定首响应税

> 更新：2026-11-22 · 仓库：cijian-agent · 类别：howto · 状态：现行（Mac mini 实测）

## 结论（对话慢的归因，2026-11-22 实测）

| 环节 | glm-5.3-flash (zai) | deepseek-flash |
|---|---|---|
| opencode 纯启动+初始化（坏模型快速失败） | 0.72s | 0.72s |
| 真实 agent 环境（assistant-chat + 31 MCP）spawn→首事件 | **5.6s** | 1.4s |
| 「只输出 ok」端到端 | 5.6~6.6s（稳定） | 1.5~1.9s |
| 「写 200 字短文」端到端 | 5.8s | 11.8s |

- **opencode 启动不慢**：纯 0.7s；带全套 MCP 工具发现也只 ~1.4s（F2 对照：deepseek 带 MCP 1.45s）。
- **MCP 不是瓶颈**：glm 无 MCP 也要 7.3s，deepseek 带 MCP 只要 1.45s。
- **瓶颈 = zai-coding-plan 端点 glm-5.3-flash 的固定首响应延迟 ~5s**：连「只输出 ok」都稳定 5.6s+。
  它生成速度其实快（200 字总耗时与 ok 相当）；deepseek 反之：首响应快、长文本生成慢（~17 字/s）。
- 每轮工具调用都要重付首响应税 → 生产对话 13~19s = 5s(首轮) + 生成 + 5s(工具轮) + …
- 大文本 prompt（2.7k 字）与小图对单轮耗时影响可忽略（deepseek 均 ~1.5s）。

## 测量方法

```bash
# 纯启动：坏模型立即失败，耗时≈启动+初始化
time opencode run --standalone --format json --auto --model nonexistent/x "ok"
# 事件时间戳不可用于拆分推理（非流式，事件在结束时一次性 emit）——用对照实验拆变量
# 真实环境：cijian_agent.ai.runner.prepare_home + install_mcp + isolate_config 后
#   opencode run --standalone --agent assistant-chat --model <m> --format json --auto
```

（/tmp/opencode_bench.py：spawn→首事件 emit = wall - (now - 首事件 timestamp)。）

## 改进选项（按性价比）

1. **主对话模型切 deepseek/deepseek-flash**（`CIJIAN_AI_MODEL` 一行 + kickstart）：
   家庭对话多为短回复 + 工具轮，每轮省 ~4s；长文稍慢但占比低。chat_vision 已是 deepseek。
   **→ 2026-11-22 12:56 已切**（agent.env：主对话+看图 = deepseek/deepseek-flash；
   兜底+技能回顾 = zai-coding-plan/glm-5.3-flash，主/兜底不同家，glm 的固定税对后台任务无所谓）。
2. glm 换流式 runner：改动大（runner 拿 streaming 事件），收益与 1 重叠，暂缓。
3. 消息到达即预热 opencode 进程：复杂，先看 1 的效果。

## 预启动 opencode 实测（2026-11-22 晚）

结论：**技术上可行，但只省 ~0.7~1.1s/条**，不是当前主要瓶颈。三种跑法实测（同机、同一 home、
31 个 MCP 工具、deepseek-flash，交替跑消除漂移）：

| 跑法 | 「只输出 ok」 | 带图 | 说明 |
|---|---|---|---|
| 现状 `opencode run --standalone`（每任务新进程） | **1.5~1.9s** | 2.5~2.9s | 启动+MCP+CLI 全付 |
| `opencode run --server <url>`（预启服务 + CLI 客户端） | 0.9~1.0s | 2.4~3.1s | CLI 自身仍要 ~0.9s |
| HTTP API 直连预启服务（`/api/session` + `/api/session/{id}/prompt`） | **0.6~0.8s** | 1.9~2.6s | 最省，但要自己管会话/事件/中断 |

- 预启服务本身：boot 0.17s，RSS **275~400MB**（另加 MCP 子进程）；`opencode serve` 打印
  `server password`，鉴权是 **Basic `opencode:<password>`**（不是 Bearer）。
- 会话完成信号：**没有 `session.idle` 事件**，要听 `session.execution.succeeded/failed/interrupted`。
- 图片附件走 `files:[{uri:"file:///abs/path"}]`；传裸路径 400（`Invalid attachment URI`）。
- 配置热更：改 `opencode.json` 后必须显式 `POST /api/location/reload`（~40ms）；靠文件 watch
  自动重载会拖到 **4s**，不能依赖。
- 每任务能力令牌（`CIJIAN_CAP_TOKEN`）和 `CIJIAN_USER_TEXT` 是写在 MCP 配置 env 里的，
  预启服务下要「改配置 + reload」或改成 MCP 每次调用读上下文文件；并发两条任务会互相覆盖。

**为什么暂不做**：一条典型对话 5~10s，其中模型首轮 ~0.7s + 每个工具轮 ~1.5~2s + 可能的
search-retry 翻倍；预启动只能砍掉 ~1s 固定开销（~10~20%），却要引入会话生命周期、实验性 API、
令牌轮换、并发串行化、400MB 常驻。性价比低于「砍重试轮/工具轮」。若以后做，优先
`--server` 变体（改动小、保留 CLI 契约），不要直接上 HTTP API。

## 相关

- [wechat-reply-latency](wechat-reply-latency.md)（整体延迟拆解）
- [gotcha-opencode-free-quota](gotcha-opencode-free-quota.md)（模型额度与兜底）
