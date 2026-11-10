# cijian · 此间 · 需求与设计文档仓

> 「人间有味是清欢，此心安处是吾乡。」

**此间**（whereami.cn）—— 记录所学，收藏生活。

本仓**只存需求与设计文档 + 仓库自动化脚本，不含业务代码**（ADR-006）。业务代码分散在独立 GitHub 仓，各自配置 CI/CD。

## 仓库拓扑

| 仓库 | 职责 | 部署 |
|---|---|---|
| `cijian`（本仓） | 需求 / 架构 / 契约文档 + 建仓自动化 | — |
| `cijian-site` | 站点：公开内容（所学/生活/关于）+ 登录后打印工作台 | Vercel → whereami.cn |
| `cijian-api` | 单口令登录、文件收发（TTL 临时存储）、打印任务调度 | 腾讯云服务器 |
| `cijian-agent` | 任务守护进程：纯出站拉取任务 → 执行（打印）→ 上报 | 每个打印机地点一台 |
| `cijian-mp` | 微信小程序：相册/聊天文件 → 家里打印机 | 微信（个人主体） |
| `cijian-family-wiki` | 家庭记忆 Wiki（**私有内容仓**，非代码）：Agent 维护，API 零 wiki 原文 | GitHub private + agent 本地克隆 |

## 目录

```
docs/
├── 00-execution-plan.md     执行计划（阶段 / 里程碑 / 验收）
├── 01-vision.md             站点定位
├── 02-prd-print.md          打印功能 PRD
├── 03-architecture.md       架构（组件 / 时序 / 任务状态机）
├── 04-api-contract.md       API 契约 v1（site ↔ api ↔ agent）
├── 05-data-model.md         SQLite 模式 / 文件存储 / TTL 策略
├── 06-security.md           鉴权 / 密钥 / 传输 / 上传安全
├── 07-deploy-cicd.md        各仓部署与 CI/CD 手册
├── 09-miniprogram-plan.md   微信小程序支持计划（M-mp-1~3 已实现）
├── 10-checkin-plan.md       每日打卡（投递即打卡，M-C1~C5）
├── 11-checkin-usage.md      打卡使用说明
├── 12-shine-plan.md         看见闪光 · 产品与 UX（AI 执行见 13）
├── 13-ai-agent-plan.md      Agent AI 任务平面 + 家庭 Wiki 记忆层
├── adr/                     架构决策记录 ADR-001 ~ 009
├── llmwiki/                 # 开发经验维基（LLM 维护，Karpathy 模式）
│   ├── SKILL.md               # skill 定义（已装到 ~/.config/opencode/skill/llmwiki/）
│   ├── index.md · log.md      # 条目目录 + 时间线
│   └── pages/                 # 总览 / 部署实录 / 打印管线 / 踩坑记录
├── repos.yaml               代码仓清单（建仓脚本的数据源）
├── scaffold/                各仓最小骨架（README + CI，无业务逻辑）
├── scripts/bootstrap-repos.sh 按 repos.yaml 自动建仓并推送
```

## 建仓（一次性）

```bash
gh auth login                    # 前提：GitHub CLI 已登录
./scripts/bootstrap-repos.sh     # 建仓 + 推骨架 + 并入暂存的站点代码
```

随后按 `docs/07-deploy-cicd.md` 为各仓接线（Vercel 导入 / SSH secrets / 各地点安装 agent）。

## 里程碑状态

- [x] Phase 1 · 文档仓改造 + 全套文档
- [x] Phase 2 · bootstrap 建三个代码仓
- [x] M1 鉴权 · [x] M2 上传+任务(API) · [x] M3 打印闭环 · [ ] M4 状态页(前端) · [x] M5 运维收尾(API)
- [x] 初始部署（api 上线 + 本机 agent 常驻 + E2E 出纸，2026-10-21/22）
- [x] M-C1~C4 每日打卡（api/agent/网页/小程序，2026-11-05/06）；M-C5 试运行中
- [ ] **进行中：看见闪光 + Agent AI 任务平面**（M-S1/M-B1 文档阶段 → M-B0 spike → M-B1..B5 实施 → M-B6 试运行；见 docs/12、13）

## 写文档的规矩

- 改接口先改 `04-api-contract.md`，改数据先改 `05-data-model.md`，然后才是代码
- 新的架构取舍 → 新增一条 ADR（一页纸：背景 / 决策 / 后果）
- **开发/测试中踩的坑 → 沉淀进 `llmwiki/`**（OpenCode skill `llmwiki` 会引导：开工先查、解决必记）
- 里程碑完成 → 在 `00-execution-plan.md §4` 打 ✔ 并在代码仓合入
