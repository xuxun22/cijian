# gotcha：自动切模型只覆盖 chat，dev 编码通道仍吃免费额度

> 日期：2026-11-27 · 仓库：cijian-agent / cijian-api · 类别：gotcha · 状态：**已修（2026-11-27）**

## 症状

同一个 dev 任务 `dt_2b318707e6348925` 的 execute 阶段，2026-11-27 12:33 和 12:43 两次失败：

```
cijian_agent.ai.runner.RunnerError: opencode exit 1：provider.free-limit:
Free usage limit reached. Connect a provider or subscribe to OpenCode Go to keep going, or switch models.
```

12:43 爸爸在微信里明确说「切到 deepseek/deepseek-flash 模型接着改」，3 秒后仍然报同一个错。
任务看板显示失败，工作区里已经留下失败前的部分改动。

## 根因

1. **11-20 的自动切模型只加在 `AiWorker._chat`**（commit `3e9eacd`）：
   `worker.py:935-941` catch `RunnerError`，命中 `MODEL_QUOTA_RE` 后换 `cfg.ai_review_model` 重试。
2. **dev 的 plan/execute 完全没有兜底**：`_dev_plan`（`worker.py:1023-1027`）和
   `_dev_execute`（`worker.py:1099-1103`）直接调 `runner.run_dev`，没有 try/except。
3. **cijian 项目的 dev 模型仍是免费档**：`repos.json` 的 `cijian` 没有 `model` 字段，
   `agent.env` 也没有 `CIJIAN_AI_DEV_MODEL` / `CIJIAN_AI_PLAN_MODEL`
   → 落到默认 `opencode/deepseek-v4.1-flash-free`。
   只有 `get` 项目在 `repos.json` 里写了 `"model": "deepseek/deepseek-flash"`。
4. **「切到 xxx 模型」没有传递通道**：dev task payload、API `enqueueExecute`、
   MCP `dev_continue` 都没有 `model` 字段；这句话只是作为 `message` 传给了同一个免费模型。
5. **免费池按账号共享**：12:05、12:11 两次 plan（239s / 255s，`steps: 40`）先消耗额度，
   12:33 的 execute（`steps: 200`）跑到一半撞顶；12:43 重试时额度已空，3 秒即失败。

## 关键证据

```
2026-11-27 12:05:07  dev.task at_f716... 完成 239425ms
2026-11-27 12:11:56  dev.task at_eaed... 完成 255078ms
2026-11-27 12:33:26  dev.task at_7bd... 开始
2026-11-27 12:35:15  ERROR ... provider.free-limit
2026-11-27 12:43:26  chat.reply「切到 deepseek/deepseek-flash 模型接着改」
2026-11-27 12:43:36  dev.task at_d2c... 又开始（同一个 dev_task_id）
2026-11-27 12:43:39  ERROR ... provider.free-limit（3 秒）
```

不是重启没生效：agent 进程 2026-11-25 07:55:28 启动，HEAD 是 07:55:05 的 `bf92362`，
11-20 的 fallback commit 已经在运行代码里，只是没覆盖 dev。

## 修法（2026-11-27 已实施）

确认后的策略：

- **plan**：`zai-coding-plan/glm-5.4` → `opencode/deepseek-v4.1-flash-free` → `deepseek/deepseek-flash`
- **dev**：`opencode/deepseek-v4.1-flash-free` → `deepseek/deepseek-flash`
- 每日看见 / 技能回顾：`ai_review_model` → `ai_model`（z.ai 额度满时落 deepseek）

落地：

- `cijian_agent/config.py` 新增 `ai_plan_fallbacks` / `ai_dev_fallbacks`，
  可用 `CIJIAN_AI_PLAN_FALLBACKS` / `CIJIAN_AI_DEV_FALLBACKS`（逗号分隔）覆盖；
  `ai_plan_model` 默认改为 `zai-coding-plan/glm-5.4`。
- `cijian_agent/ai/worker.py` 新增 `model_chain()` + `_run_with_quota_fallback()`；
  `_dev_plan` / `_dev_execute` 都走模型链，返回体带 `model` 字段，API 的 `ai_tasks.model` 能看出实际用了谁。
- execute 换模型重试时追加 `DEV_QUOTA_RETRY_NOTE`：先 `git status` / `git diff` 看上一轮残留，
  再继续，避免重复改。
- `MODEL_QUOTA_RE` 增加 `provider.rate-limit` 和中文「使用上限/额度/限额」；zhipuai 的限流错误就是这种形状。
- 记忆回顾的 agent 名从 `memory-review` 改为 `assistant-memory-review`，与
  `prompts/assistant-memory-review.md` 对齐；之前每天 23:30 报「缺少 prompt」。
- 测试：新增 `tests/test_dev_models.py`（模型链、免费/付费切换、plan 三级兜底、execute 重试提示），
  并给记忆回顾加了 prompt 名断言；全量 219 项通过，ruff 通过。

**仍未做（P2）**：dev task / MCP `dev_continue` 还没有显式 `model` 参数；
对话里说「切到 xxx 模型」仍不会改变 dev 模型，需要单独设计。

**当前额度**：免费池 15:30 实测仍满（`retryAfter` 约 17h）；z.ai/zhipuai GLM 周额度
`2026-11-27 22:50:23` 重置；deepseek 付费档实测可用。所以今天 plan 会先撞 GLM，再撞免费，
最后落到 deepseek；22:50 之后 plan 才会真正用上 GLM-5.4。

## 今天这个任务的现状

工作区：`~/.local/share/cijian-agent/ai/dev/dt_2b318707e6348925`
分支：`assistant/dt_2b318707e6348925`

`cijian-api` 里已有失败前的未提交改动：

```
M src/errors.ts
M src/services/checkin.ts
```

不要 discard；重启 agent 后用 `dev_continue` 续改，新模型会先看 diff 再继续。

## 预防

- 新增任何「自动兜底」能力时，按任务类型列出覆盖矩阵，别只测主路径。
- 免费模型可以先试，但 `steps: 200` 的编码任务必须有付费兜底，不能裸跑免费模型。
- 主模型和兜底模型要按「当前实际配置」验证，不要只看默认值；coding plan 同名 provider 可能共享额度。
