# Harness 规则：改动的「完成定义」

> 2026-10-22 · 类别：howto · 仓库：全部 · 状态：现行
> 本页是 cijian 全部代码改动的强制关卡。SKILL.md 已内置此清单（OpenCode skill `llmwiki`），
> agent 提交前必须逐条执行；CI 是最终防线，红了必须修，禁止绕过或放宽。

## 一、每仓校验命令（全绿才准 push）

| 仓库 | 必跑命令 | 覆盖内容 |
|---|---|---|
| cijian-api | `npm run typecheck && npm test && npm run build` | tsc 严格类型 · 15 项集成测试（登录/上传/闭环/重试/租约/签名URL） · 产物构建 |
| cijian-site | `npm run build` | Astro 全站构建（含打印工作台）零错误 |
| cijian-agent | `python3 -m compileall -q cijian_agent && ruff check cijian_agent` | 语法 + lint（ruff 规则见 pyproject） |
| cijian（文档） | 目视核对 `llmwiki/index.md`、`log.md` 与 docs 交叉引用一致 | 无 CI，靠 agent 自查 |

push 之后：`gh run list -R xuxun22/<repo> --limit 1` 必须 success；
cijian-api 推 main 后 5 分钟内服务器自拉取部署 → 抽查 `https://api.whereami.cn/api/health`。

## 二、类型与 lint 规则

- **api**：`tsc --noEmit` strict 全开，零错误才算过。
  - node:sqlite 参数类型是 `SQLInputValue`——查询结果字段（unknown）传参前必须显式
    `String()/Number()` 转换（坑已记录：gotcha-node-sqlite）。
- **agent**：`ruff check`（line-length 100，target py310）；禁止未使用 import；
  禁止裸 `except:`（用 `except Exception` 并注明兜底原因）。
- **site**：Vite/Astro 构建器检查；模板内插值一律过 `esc()`，禁止未转义 HTML。

## 三、产品层判定

### 用户友好

1. **任何 >1 秒的等待必须有可见反馈**：进度条 / 状态徽标 / 提示文案，三选一。
   （教训：上传无进度条被用户直接吐槽；打印卡「已接受」无中间态。）
2. **错误文案 = 人话 + 可操作**：写原因和下一步（"口令不正确，再想想"、"文件已过期，请重新上传"），
   禁止只堆状态码；统一结构 `{error:{code,message}}`，前端展示 message。
3. **可容忍的失败要优雅降级**：打印机离线允许排队提交但必须显著提示；重复提交做 3 秒防抖。
4. **任务状态可追溯**：状态变化必须写 `job_events`（含 source），前端点行可看时间线。

### 风格统一

5. **纸·墨·朱砂设计令牌**：颜色只用 `--paper/--card/--ink/--ink-soft/--ink-faint/--cinnabar/--line`，
   禁止硬编码色值；正文宋体（--serif），辅助信息 sans；圆角/阴影沿用现有变量。
6. **中文优先**：用户可见文案一律简体中文、口语化但不轻佻；代码注释中文优先。
7. **布局沿用既有模式**：列表页 `list-head`、文章 `article-title`、卡片 `life-card/print-drop`，
   新页面优先复用，不自造轮子。

### 产品语义

8. **契约先行**：接口/状态机改动先改 `docs/04`、`docs/05`，再动代码（api↔agent↔site 三处同步）。
9. **私有页面一律 `noindex`**（Base 的 noindex prop）；公开页面才可被收录。
10. **安全红线**：密钥/明文口令永不入 git（含 llmwiki）；文件只进 TTL 临时区；
    上传必须 magic bytes 校验；登录/上传必须限速。
11. **打印防重打优先级最高**：拿不到租约确认（report 返回 False）就绝不提交 CUPS。
12. **CD 契约**：cijian-api 推 main 即上线（服务器 5 分钟 timer 自拉取）——推 main 前必须
    本地全绿；agent/site 无自动部署，更新走各自流程（launchd 重启 / Vercel 自动）。

## 四、enforce 接线（谁在真正校验）

| 规则 | 校验点 |
|---|---|
| api 类型 + 集成测试 | GitHub Actions `CI`（setup-node 24 → typecheck → test → build） |
| site 构建 | GitHub Actions `CI`（npm ci → build） |
| agent 语法 + lint | GitHub Actions `CI`（ruff check + compileall） |
| 产品判定 1–12 | OpenCode skill `llmwiki`（本页 + HOME 清单，agent 开工/收工强制走查） |
| 部署健康 | 服务器 `cijian-deploy.timer`（5min 拉取）+ api healthcheck（compose） |
