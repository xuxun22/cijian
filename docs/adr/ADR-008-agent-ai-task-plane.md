# ADR-008 · Agent AI 任务平面：AI 执行全部下沉到 agent

日期：2026-11-11 · 状态：已接受（用户选定）

## 背景

「看见闪光」需要 AI（分析观察、维护成长记忆）。原方案（docs/12 §5）由 cijian-api 直连 LLM，
简单但有三 个问题：api 是公网暴露面却持有模型 key 与 AI 产物；无多步任务能力（wiki 维护/回顾/lint）；
无法复用为将来的编程/图片任务平面。用户明确要求：**AI 必须由 agent 领任务执行，
且任何 AI 产物必须经 agent 封装后才能给到 API**。

## 决策

- **API 只做队列与账本**：新表 `ai_tasks / ai_task_events / ai_artifacts`（派发/租约/心跳/重试/审计），
  **不直连任何模型**（`CIJIAN_AI_MODE=inline` 仅作开发开关，默认关）。
- **agent 新增 `ai` 能力线程**（与 checkin 同为 BACKGROUND，非 claim 型打印任务）：
  长轮询 `POST /api/agents/ai/tasks/claim`（无任务挂起 ≤25s）→ 执行 → 20s 心跳续租 → 报果。
  仍纯出站（ADR-001 不破）。
- **MVP 唯一 runner = spawn `opencode`**（`opencode run --standalone --model … --agent … --format json --auto`），
  两个专用 profile：`shine-analyze`（只读只出 JSON）/ `shine-wiki`（edit 限工作区、禁 bash/webfetch）。
  direct 直连与 deepagents 列为 Phase 3 备选。
- **prompt 归 agent 所有**（`cijian_agent/ai/prompts/`，带版本号）；任务 payload 只带 `prompt_version`。
- **链式编排在 API**：analyze 成功落库的同一事务入队 `shine.wiki.ingest`；删除条目入队 `shine.wiki.redact`。
- **多 agent 并发**：claim 原子 CAS，analyze 随机器数横向扩容；`shine.wiki.*`/`shine.review.*` 标记
  `serialized` 全局串行（同类型同时只有一单在跑），git `pull --rebase` + push 重试兜底。
- **能力按配置上报**（`printers.ai_capabilities`）：没配 wiki deploy key 的机器只报 `shine.analyze`。

## 备选与否决

- **API 直连 LLM（原 12 号方案）**：快、简单，但暴露面持有模型凭证与 AI 产物，且无法长任务/多步。
- **API 直连为主、agent 为辅**：两套执行路径，记忆类任务仍要 agent，维护成本翻倍。
- **全部 deepagents**：需先装 venv，启动更重，首期不确定因素多。

## 后果

- ✅ 公网暴露面（api）不持有模型 key、不产 AI 内容、不见家庭记忆
- ✅ 一个任务平面通吃现在（闪光）与将来（code/image，容器沙箱）
- ✅ agent 挂了不丢数据：条目照存、任务排队，上线自动补
- ⚠️ analyze 延迟从 ~3s 升到 p50 8~15s（opencode 启动 + agent 循环）——用异步 UI（202 + 轮询）承接
- ⚠️ agent 机器需装 opencode 并登录模型；家庭 AI 可用性 = 家里设备在线率
