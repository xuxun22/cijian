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
├── adr/                     架构决策记录 ADR-001 ~ 007
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

## 写文档的规矩

- 改接口先改 `04-api-contract.md`，改数据先改 `05-data-model.md`，然后才是代码
- 新的架构取舍 → 新增一条 ADR（一页纸：背景 / 决策 / 后果）
- **开发/测试中踩的坑 → 沉淀进 `llmwiki/`**（OpenCode skill `llmwiki` 会引导：开工先查、解决必记）
- 里程碑完成 → 在 `00-execution-plan.md §4` 打 ✔ 并在代码仓合入
