# gotcha：opencode 免费模型是共享额度，压测后连对话一起挂

> 更新：2026-11-20 · 仓库：cijian-agent · 类别：gotcha · 状态：现行
>
> **2026-11-27 补正**：本文 11-20 段说的「主 z.ai、兜底 deepseek」已在 11-22 延迟优化时互换
> （主对话 = `deepseek/deepseek-flash`，`ai_review_model` = `zai-coding-plan/glm-5.3-flash`）。
> 更关键的是，自动切模型最初只覆盖 `_chat`；dev 的 plan/execute 没有兜底，2026-11-27 因此失败两次。
> 当天已补上通用模型链（plan: glm-5.4→free→deepseek；dev: free→deepseek），
> 每日看见/技能回顾也会从 `ai_review_model` 落到 `ai_model`。
> 见 [gotcha-dev-quota-fallback-gap](gotcha-dev-quota-fallback-gap.md)。

## 症状（2026-11-20 新增：付费 coding plan 的周/月限额）

微信查询又收到「这次没想好，等下再问我一次」，`ai_tasks.last_error`：

```
RunnerError: opencode exit 1：provider.quota: Weekly/Monthly Limit Exhausted.
Your limit will reset at 2026-11-20 22:50:23
```

这次不是免费档，是 `zai-coding-plan/glm-5.3-flash` 的**周/月额度**打满（coding plan 按账号共享，
所有 z.ai 模型一起不可用）。备份模型 `deepseek/deepseek-flash`（技能回顾用的）同时正常。

**已改成自动兜底**：`AiWorker._chat` 捕获 `provider.quota|free-limit|usage limit` 错误后，
本次对话自动换 `ai_review_model`（默认 `deepseek/deepseek-flash`）重试，不再把兜底文案发给家人。
实测：主模型 429 立刻返回 → 切 deepseek → 1.7s 正常答「ok」。额度恢复后下次对话自动回到主模型（无需重启）。

## 症状（2026-11-18 新增）

对话模型还在免费档时，微信问天气会收到兜底文案「**这次没想好，等下再问我一次**」——这不是搜索坏了，
是 `provider.free-limit`：agent 日志里 7 秒内两次 `opencode exit 1`，模型进程根本没起来，搜索更没机会跑。
判断方法：grep agent 的 err 日志看有没有 `Free usage limit reached`；有就是额度，别去查插件/提示词。

## 症状（2026-11-15 原始）

连续跑几次 `opencode run` 之后，所有 `opencode/*-free` 模型统一报：

```json
{"type":"error","error":{"type":"provider.quota","message":"Free usage limit reached. Free models work in OpenCode (https://opencode.ai); subscribe to OpenCode Go to keep going","status":429}}
```

对话模型（`opencode/mimo-v2.6-flash-free`）和编码模型（`opencode/deepseek-v4.1-flash-free`）一起不可用。
更迷惑的是：**子进程 exit 1，stderr 却是空的**，worker 日志只剩 `opencode exit 1：`。

## 根因

1. 免费档是同一个账号/额度池，用量跨模型共享；短时间多次调用（例如反复调试 prompt）会直接打满。
2. provider 错误只写在 **stdout 的 JSON 事件流**里，`stderr` 没内容；`runner` 原来只读 stderr，报错信息就丢了。

## 解法（2026-11-18 对话模型已切付费）

- 对话模型 2026-11-18 起改为 `zai-coding-plan/glm-5.3-flash`（`~/.config/cijian/agent.env` 的 `CIJIAN_AI_MODEL` + `launchctl kickstart` 重启），不再吃免费额度。

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
- 主对话模型与兜底模型不要选同一家（2026-11-20 起主 z.ai、兜底 deepseek），一家的额度打满不影响家人对话。

## 症状（2026-11-20 视觉识别）：周额度也会打满

错题本第 2 步联调时，`zai-coding-plan/glm-5.3-flash` 报：

```
provider.quota: Weekly/Monthly Limit Exhausted. Your limit will reset at 2026-11-20 22:50:23
```

同日备选也不可用：`google/gemini-3.8-flash` → `provider.no-route`（未配置该 provider 路由）；
`opencode/nemotron-3.5-super-vl-free` → `provider.free-limit`（免费池共享，早已打满）。

**结论**：视觉识别模型必须提前确认可用性；周额度按 provider 重置（不是按天），
联调大任务前先跑一张图的最小调用。`CIJIAN_PAPERS_VISION_MODEL` 可单独指定，
默认跟 `CIJIAN_AI_MODEL`；额度打满时不要反复重试（每次都会消耗一点并拖慢排障）。
