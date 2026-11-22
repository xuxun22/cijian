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
2. glm 换流式 runner：改动大（runner 拿 streaming 事件），收益与 1 重叠，暂缓。
3. 消息到达即预热 opencode 进程：复杂，先看 1 的效果。

## 相关

- [wechat-reply-latency](wechat-reply-latency.md)（整体延迟拆解）
- [gotcha-opencode-free-quota](gotcha-opencode-free-quota.md)（模型额度与兜底）
