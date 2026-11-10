# ADR-009 · 家庭 Wiki 记忆层：私有 GitHub 仓，API 零 wiki 原文

日期：2026-11-11 · 状态：已接受（用户选定）

## 背景

「让孩子真的在成长」需要**累积的记忆**而不是每次从零推理。模式参考 Karpathy《LLM Wiki》
（raw sources / wiki / schema 三层，ingest·query·lint）。同时用户划定硬边界：
**API 是公网暴露面，不得存任何家庭记忆原文；AI 产出必须经 agent 封装后才能给到 API。**

## 决策

- **三层落地**：
  - raw sources（不可变）= `shine_entries`（API）+ checkin 记录；
  - wiki（AI 维护）= 私有仓 `github.com:xuxun22/cijian-family-wiki`，markdown + `growth.json`；
  - schema = wiki 仓内 `AGENTS.md`（证据规则/禁令/ingest·review·lint 工作流，人 + AI 共同进化）。
- **权威副本只在私有 GitHub 仓 + agent 本地克隆**；**API 不建 `wiki_pages`/`wiki_commits`，无任何 wiki 端点**。
- **agent 封装后发布视图**（`shine_views` 表，每孩子每类一条，`commit_count` 单调防回退）：
  - `growth`：成长页渲染所需的一切（维度卡/证据引用/置信度/回顾/AI 摘要）；
  - `analyze_context`：给 analyze 任务的口吻偏好摘要（≤500 字），让无 wiki 克隆的机器也能带家庭语气。
- **证据纪律**：每句关于孩子的话必须带 `[E:sh_xxx]`；5 维度（思考/情绪/行为/关系/坚持）只有
  trend/confidence/counter_evidence，**不打分**；判定线 = ≥3 次独立观察、跨 ≥2 场景、持续 ≥3 周、
  非成人指令驱动，达不到就明写「还不能判断」。
- **记忆增删改全经 agent**：删除条目 → `shine.wiki.redact` 任务（移除引用 → push → 重发视图）。
- **凭证**：SSH deploy key（仅该仓写权限）只存 agent 机 `~/.config/cijian/wiki_deploy_key`（600），
  不入仓不入 api；api 服务器无 GitHub 凭证。
- 「越来越聪明」= wiki 累积 + `family/preferences.md` 学家长口吻，**不做任何模型训练**。

## 备选与否决

- **API 存 wiki 全量镜像**（原 13 号草案）：网页读起来最简单，但违反内容边界——暴露面躺着完整家庭画像。
- **只存 API（无 GitHub）**：少一份历史，且违背「记忆属家庭」的所有权表达。
- **向量库/RAG**：家庭规模（<1MB、几百页内）`index.md` + grep 足够（Karpathy 原判断）。

## 后果

- ✅ API 被攻破的最坏情况：拿到条目与任务记录，拿不到任何累积记忆画像
- ✅ 完整 git 历史免费；家人可用 Obsidian 直接读 wiki（App 只看编译产物，正是该模式本意）
- ✅ 记忆可随家庭迁移/导出（仓就是你的）
- ⚠️ GitHub 仓丢失则 API 无法恢复 wiki（视图≠备份）——仓开 snapshot，agent 本地克隆仍在
- ⚠️ 成长页数据有延迟（ingest 异步），且依赖 wiki 写者机器在线（首期 = 家里 Mac mini）
