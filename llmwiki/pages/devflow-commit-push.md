# 「提交」的语义 = commit + push（规则分叉复盘）

> 日期：2026-11-22 · 仓库：cijian（skill/wiki） · 类别：gotcha + decision · 状态：现行

## 约定（爸爸定稿）

- **「提交」= `git commit` + `git push` 一起做**。没有单独的「推送」步骤，
  不要再回复「回『推送』我再推」。
- 提交后照常收尾：确认 CI 绿 → cijian-api 推 main 自动部署后抽查
  `https://api.whereami.cn/api/health` → 改了 agent 代码则 `launchctl kickstart -k` 重启。

## 症状

爸爸此前要求「提交 == git commit + git push」，但 AI 连续多次只 commit 不 push，
还问「回『推送』我再推」。

## 根因（两份 SKILL.md 分叉）

- 初始提交（10560b1）里同时存在**两份** skill：
  - `.opencode/skill/llmwiki/SKILL.md` —— **实际被 OpenCode 加载的唯一一份**；
  - `llmwiki/SKILL.md` —— 仓库里的拷贝，**从未被加载**，属死文件。
- 爸爸的旧要求（commit && push）写在**死文件**的步骤 4：
  `git add llmwiki && git commit && git push`。
- 2026-11-18 的 1e254ad 只改了生效文件，把步骤 4 改成
  「不要自行 commit/push……推送等『推送』」——**与爸爸要求相反**；
  `llmwiki/HOME.md` 同步改成「提交统一等爸爸回『提交』」，未说明含不含 push。
- 因此之后所有会话（包括本 AI）都按生效文件执行：提交=只 commit。
- 另外 `pages/devflow-push-main.md` 只记录了**微信 dev 通道**的「提交=合并+push+部署」，
  与交互式编码通道的语义没有放在一起，无法纠偏。

## 解法

- `.opencode/skill/llmwiki/SKILL.md` 步骤 4 改为「提交 = commit + push（含 CI/部署/agent 重启）」。
- `llmwiki/SKILL.md` 改为指针 stub：规则只改 `.opencode/...` 那份。
- `HOME.md` 工作流第 2 条补明「提交 = commit + push」并链接本页。
- `index.md` 登记本页。

## 预防

- **单一生效文件**：skill 规则只在 `.opencode/skill/llmwiki/SKILL.md` 维护；
  发现别处出现第二份 skill 文本，一律改成指针。
- 修改工作流语义时，先 grep 全仓 `提交|推送`，把 HOME.md、SKILL.md、相关 pages 一起对齐。
- 汇报里不要再出现「未推送，回『推送』」这类话术——直接按「提交」含 push 执行。

## 相关

- [devflow-push-main](devflow-push-main.md)：微信 dev 通道的「提交」= 合并 main + push + 部署（同一语义）
- [engineering-standards](engineering-standards.md)：提交前 Harness 检查清单
