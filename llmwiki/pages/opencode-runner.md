# opencode runner 集成（M-B0 spike 实测）

- 日期：2026-11-11 · 仓库：cijian-agent（将实现）/ cijian（本文） · 类别：howto · 状态：有效

## 是什么

Agent 用 `opencode run` 作为 AI 任务执行器的全部实测事实（看见闪光 M-B0 spike）。
完整报告：`docs/research/mb0-spike-result.md`。

## 关键事实（实现时容易忘的）

- **JSON 契约**：`opencode run --standalone --format json --auto "<msg>"` 输出单行 JSON，
  模型文本在 `part.text`；`time.start/end`（ms epoch）可直接算耗时。
- **agent profile 目录是 `.opencode/agents/`（复数）**，不是 `.opencode/agent/`。
  frontmatter：`description/mode/model/permissions/steps`，**正文 = system prompt**。
- **权限规则有序，后匹配者胜**：先 `{action:"*", effect:deny}` 再放行 read/glob/grep。
- **`--standalone` 每次冷启 ~1.2s**，不依赖也不干扰常驻后台 service——任务级隔离就用它。
- **附图走 `--file <path>`**，无需手工 base64；模型能真实看到图（vision 生效）。
- **延迟**：完整 prompt + 5 few-shot，文字 6.4~8.5s、图片 ~10.6s（免费档 opencode/deepseek-v4.1-flash-free）。
- **deploy key 流程**：`gh repo create --private` → `ssh-keygen -f ~/.config/cijian/wiki_deploy_key`
  → `gh repo deploy-key add … --allow-write` → clone/push 用
  `GIT_SSH_COMMAND='ssh -i <key> -o IdentitiesOnly=yes'`。api 服务器**不需要**任何 GitHub 凭证。
- wiki 仓：`github.com:xuxun22/cijian-family-wiki`（PRIVATE），骨架 AGENTS.md/index.md/log.md 已种子。

## 症状 → 解法

- `--agent xxx` 报不存在 → 检查目录名是不是 `agents`；frontmatter 是否合法 YAML。
- 输出多了 Markdown 围栏 → system prompt 里要有「只输出 JSON，不要 Markdown，不要解释」。
- 想限制步数 → frontmatter `steps: N`（最后一步会收工具强制总结）。
