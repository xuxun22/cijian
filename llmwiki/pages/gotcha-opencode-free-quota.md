# gotcha：opencode 免费模型是共享额度，压测后连对话一起挂

> 更新：2026-11-15 · 仓库：cijian-agent · 类别：gotcha · 状态：现行

## 症状

连续跑几次 `opencode run` 之后，所有 `opencode/*-free` 模型统一报：

```json
{"type":"error","error":{"type":"provider.quota","message":"Free usage limit reached. Free models work in OpenCode (https://opencode.ai); subscribe to OpenCode Go to keep going","status":429}}
```

对话模型（`opencode/mimo-v2.6-flash-free`）和编码模型（`opencode/deepseek-v4.1-flash-free`）一起不可用。
更迷惑的是：**子进程 exit 1，stderr 却是空的**，worker 日志只剩 `opencode exit 1：`。

## 根因

1. 免费档是同一个账号/额度池，用量跨模型共享；短时间多次调用（例如反复调试 prompt）会直接打满。
2. provider 错误只写在 **stdout 的 JSON 事件流**里，`stderr` 没内容；`runner` 原来只读 stderr，报错信息就丢了。

## 解法

- 后台任务（技能回顾）不再用免费模型，默认走便宜的付费模型 `deepseek/deepseek-flash`（`Config.ai_review_model`，
  可用 `CIJIAN_AI_REVIEW_MODEL` 覆盖），把免费额度留给日常对话；
- `runner._exit_error()` 在 stderr 为空时解析 stdout 里的 `{"type":"error","error":{"type","message"}}`，
  日志里能直接看到 `provider.quota: Free usage limit reached`；
- 排查时先直接跑一条最小命令确认额度，而不是怀疑 prompt：

```bash
opencode run --standalone --format json --auto "只输出 ok" | tail -3
```

## 预防

- 调 prompt / 压测尽量用付费模型或本地模型，别连续消耗免费额度；
- 看到「失败但没错误信息」，先查 stdout 事件流，再看 stderr；
- 辅助任务（回顾、摘要、清理）默认独立模型，别和主对话抢资源。
