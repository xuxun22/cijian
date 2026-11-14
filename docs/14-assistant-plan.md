# 14 · 此间助手（个人助手）方案

> 状态：方案定稿，P0 实施中
> 决策日期：2026-11-12
> 相关：`docs/13-ai-agent-plan.md`（AI 执行面）、`docs/06-security.md`（密钥清单）

## 1. 目标

把现在跑在旧服务器上的 Hermes 个人助手，替换成 cijian 原生的助手：

- **入口是微信会话**，家人零安装
- **内容页是小程序**，微信卡片点开直达
- **大脑是 opencode**，本机常驻
- **记忆是 wiki**，与「看见闪光」共用同一个仓库

## 2. 已确认的决策

| 项 | 决定 |
|---|---|
| 应用名 | **此间助手** |
| 主入口 | 微信会话（企业微信自建应用 + 微信插件） |
| 内容页 | 小程序（闪光 / 时间线 / 日报归档） |
| 长回复 | 超过 20 秒先回「收到，我想一下」，再补正式回复 |
| 日报内容源 | 沿用 Hermes 的 `fetch.py` / `fetch_industry.py` |
| 群聊 | 不做，只做 1:1 |
| AI 执行 | 只走 opencode；API 永不调用 LLM |
| 记忆仓库 | `xuxun22/cijian-family-wiki`，助手记忆在 `family/assistant/**` |

## 3. 链路

```
家人微信 ──①发消息──> 企业微信(自建应用) ──②回调──> cijian-api
                                                     │
                                                     │③入队 chat.reply
                                                     ▼
                                               opencode (Mac mini)
                                                     │④生成回复 / 写 wiki
                                                     ▼
家人微信 <──⑥送达── 企业微信 <──⑤message/send── cijian-api
```

API 只做四件事：**验签解密、去重入库、派发任务、发送消息**。不生成任何内容。

## 4. 通道事实（已实测）

| 方向 | 手段 | 限制 |
|---|---|---|
| 收 | 回调 URL + AES | **必须按 32 字节块剥填充**（Node 默认 16 字节会 `bad decrypt`） |
| 发文本 | `message/send` text | 2048 字节 |
| 发卡片 | textcard | 微信内可跳转 |
| 发图文 | news | 微信内正常，带缩略图 |
| 发图片 | `media/upload` → `media_id` | **不能内联 base64**；素材 3 天过期 |
| ~~markdown~~ | 禁用 | 微信显示「暂不支持此消息类型」 |
| 频控 | 20 条/分钟/应用 | 超限需要排队 |

回调约束：企业微信等 5 秒，超时会重试（最多 3 次）。所以必须**先回 `success`，再异步处理**。

## 5. 数据模型

```sql
-- 收到与发出的消息（去重 + 审计）
CREATE TABLE wecom_messages (
  id            TEXT PRIMARY KEY,
  direction     TEXT NOT NULL,          -- in | out
  msg_id        TEXT UNIQUE,            -- 企业微信 MsgId，入站去重
  from_user     TEXT,                   -- 入站 UserID
  to_user       TEXT,                   -- 出站 UserID
  msg_type      TEXT NOT NULL,          -- text | image | event | ...
  content       TEXT,                   -- 文本；图片存 media_id
  media_id      TEXT,
  task_id       TEXT,                   -- 关联的 AI 任务
  created_at    TEXT NOT NULL
);

-- 身份映射：企业微信 UserID ↔ 家庭成员
CREATE TABLE wecom_users (
  user_id       TEXT PRIMARY KEY,       -- 企业微信 UserID
  name          TEXT NOT NULL,          -- 显示名
  role          TEXT,                   -- dad | mom | child | other
  wiki_slug     TEXT,                   -- family/people/<slug>.md
  active        INTEGER NOT NULL DEFAULT 1,
  created_at    TEXT NOT NULL
);

-- 定时任务
CREATE TABLE schedules (
  id            TEXT PRIMARY KEY,
  name          TEXT NOT NULL,
  spec_kind     TEXT NOT NULL,          -- daily | weekly | every
  spec_value    TEXT NOT NULL,          -- "08:07" | "1 08:37" | "30m"
  task_type     TEXT NOT NULL,
  payload       TEXT NOT NULL,
  timezone      TEXT NOT NULL DEFAULT 'Asia/Shanghai',
  enabled       INTEGER NOT NULL DEFAULT 1,
  last_run_at   TEXT,
  next_run_at   TEXT,
  created_at    TEXT NOT NULL
);
```

## 6. 任务类型

| 类型 | 优先级 | 串行 | 用途 |
|---|---|---|---|
| `chat.reply` | 5 | 否 | 微信对话回复 |
| `digest.daily` | 60 | 是 | 每日 AI 日报（8:07） |
| `digest.weekly` | 70 | 是 | 产业专刊（周一 8:37） |
| `reminder.fire` | 20 | 否 | 日程提醒（每 30 分钟扫一次） |
| `assistant.wiki.write` | 40 | 是 | 记忆写入（与 shine wiki 共用串行队列） |

`assistant.wiki.write` 与 `shine.wiki.*` 一样进全局串行组。

## 7. 回复链路时序

1. 回调验签、解密
2. `MsgId` 去重（重复直接 `success`）
3. 写 `wecom_messages`
4. 立即返回 `success`
5. 20 秒计时器：到点未完成 → 发「收到，我想一下」
6. 入队 `chat.reply`，payload 含消息 id、文本、发送人、最近 6 轮上下文
7. agent 执行 opencode（profile `assistant-chat`，带 `family/assistant/**` 上下文）
8. 结果回写任务 → API 发送文本/卡片
9. 异步触发 `assistant.wiki.write`（有值得记的内容才写）

## 8. 定时任务

`services/scheduler.ts` 每 30 秒扫一次 `schedules`：

- `daily HH:MM` → 计算下一次
- `weekly D  HH:MM` → D 为 1–7
- `every 30m` → 间隔执行

到点生成 `ai_tasks`，由 agent 领取。**API 不执行内容生成。**

迁移 Hermes 的 5 个 job：

| Hermes | 新 |
|---|---|
| AI日报 8:07 | `digest.daily` 08:07 |
| 产业专刊 周一 8:37 | `digest.weekly` 1 08:37 |
| 投递重试 每 3 分钟 | 删除（API 内建重试） |
| 家庭日程 08:00 | `reminder.fire` 08:00 |
| 事件前提醒 每 5 分钟 | `reminder.fire` 每 30 分钟 |

## 9. 记忆

```
family/assistant/
  profile.md        # 助手对家庭的长期理解
  preferences.md    # 表达偏好、禁忌
  people/           # 每个成员一页
  threads/2026-11.md
  digest/2026-11-12.md
```

写入规则：

- 只写**可复用的结论**，不写流水账
- 每条记忆带来源（消息 id 或日期）
- 冲突时以新为准，旧条目追加 `~~删除线~~` 而不是直接删
- `assistant.wiki.write` 与 shine wiki 串行，避免 git 冲突

### 9.1 推送范围（谁收什么）

| 内容 | 范围 | 说明 |
|---|---|---|
| 家庭日程（08:00 汇总、事件前提醒） | 全家广播 | 接送、上课这类本来就该两人都知道 |
| AI 日报 / 产业专刊 | 定向订阅 | 只发订阅了这个栏目的人（`wecom_subscriptions`） |
| 对话问答 | 1:1 | 各聊各的，微信里互不可见；记忆与日程共用一份 |

- 新成员加入时默认**不订阅**任何新闻栏目，接入时当面问清楚要哪个栏目；不替别人改订阅。
- 对话里说「日报别发给我了」→ 只退订说话人自己的；日程提醒不受影响。


## 9.2 能力面（MCP，2026-11-12 落地）

助手不再靠 `<reminder>` 这类标签猜意图，所有动作都走 MCP 工具；工具只是 `/api/assistant/cap/*` 的薄封装。

| 工具 | 作用 |
|---|---|
| `printers` / `print_jobs` | 看打印机、看打印进度 |
| `print_preview` / `print_submit` | 两段式打印：先给摘要和 intent，用户明确说「打」才提交 |
| `checkin_today` / `checkin_records` / `checkin_stats` | 打卡三连 |
| `shine_recent` / `shine_growth` | 闪光时间线与长期视图 |
| `reminder_list` / `reminder_create` / `reminder_cancel` | 日程增删查 |
| `subscription_get` / `subscription_set` | 新闻栏目订阅（只改本人） |

安全模型：

- API 在入队 `chat.reply` 时签发一枚 **只代表说话人** 的令牌（`scope=assistant`，15 分钟），写进任务 payload。
- runner 把它和 API 地址注入 opencode 子进程环境；工作区 `opencode.json` 用 `{env:...}` 引用，**agent key 不下传**。
- 打印用第二枚令牌（`scope=print`，10 分钟），绑定 file/printer/参数与说话人；别人拿到也用不了。
- 令牌不能登录网页、不能领任务，只能调能力面。

打印跨两轮：`print_preview` 把摘要与凭条（10 分钟）暂存在 `app_state.print_intent:<本人>`，用户回「打」时 `print_submit` 不传凭条也能提交，用过即清。对话任务还带最近 6 条消息（`recent_chat`），让「先发摘要、再回打」接得上。

模型：`opencode/mimo-v2.6-flash-free`。原来的 deepseek-v4.1-flash 实测三次里只有一次真的调工具，会回「工具没连上」；mimo 连续两次都调，答复也更稳。

## 9.3 对话区与技能（P0，2026-11-13）

**工作目录**：对话不再用一次性临时目录，固定在 `~/.local/share/cijian-agent/ai/work/home/`。里面只有 agent profile 和 `opencode.json`，跑完不销毁；`opencode.json` 不再包含仓库路径。

**技能**：放在私有 wiki 仓 `family/assistant/skills/<id>/SKILL.md`，通过 `opencode.json` 的 `skills` 数组挂载，按 opencode 的渐进式方式加载（每步只给 id + 描述，正文按需加载）。

- id 一律 `family-` 前缀；`description` 一句话说明何时使用；
- 对话里通过 `skill_list / skill_read / skill_write / skill_delete` 四个 MCP 工具增删改，不需要 shell / 文件权限；
- 改完 worker 检测到 skills 目录变脏，串行 commit + push（`assistant: skills update`）；
- 全局 `~/.config/opencode/skills` 里的开发技能用 `skill` 权限挡在外面，只放 `family-*`。

**权限**：对话 agent 只保留 `cijian_*` 与 `family-*` 技能；去掉 read/glob/grep，`external_directory` 只允许技能目录。这从结构上消灭了「翻实现、讲权限」的行为。

**兜底**：身份/实现类短问题（「你是什么模型」「读一下 xxx.py」）在 worker 里直接给固定回答，不进模型。

**已知局限**：mimo 仍会偶尔把模型名说出来，所以依赖兜底；换更强的对话模型可以减掉这层补丁。

## 9.4 编码通道（P1，2026-11-14）

对话进程不写代码；要改代码走独立通道：**微信一句话 → 独立 worktree 里让模型改 → 人看 diff 决定提交**。

**流转**：
1. 对话里说「帮我改…」→ 助手调 `dev_task`，回一句「我去改，弄好了告你」；
2. worker 在 `~/.local/share/cijian-agent/ai/dev/<dt_id>/` 为白名单里每个仓库建 git worktree（分支 `assistant/<dt_id>`），用 `dev` agent（deepseek flash）改；
3. 改完 worker 自己跑检查（有 `typecheck` 跑 typecheck，否则 `npm test`），把「改了什么 + diff --stat + 检查结果」直接发微信；
4. 回「提交」→ `dev_submit`：worker 在有改动的仓库 commit（`assistant: <需求>`），保留分支、清掉 worktree；回「算了」→ `dev_discard`：连分支一起删；
5. 不满意可以继续说，`dev_continue` 沿用同一工作区和 opencode 会话接着改。

**项目白名单**：`~/.config/cijian/repos.json`（`{"root","repos"}`），人工编辑生效，微信里不审批新项目。

**dev agent 的权限**（`prompts/dev.md`）：deny `*` 起步，只放行——
- 工作区内的 read/edit/glob/grep；`external_directory` 全禁（读不到 `~/.ssh`、别的仓库）；
- shell 白名单：git 只读操作 + `git add/stash`、`npm install/ci/run/test`、`npx tsc/vitest/astro`、`pytest`、`ls/cat/head/tail/rg/find/wc/sed -n/mkdir -p`；
- 明确禁：`git commit`、`git push`、`sudo`、`rm -rf`、`curl`、`ssh`、`npm run dev/start`（后匹配优先）。

**对话区隔离**：chat 和 dev 的子进程 `XDG_CONFIG_HOME` 指到工作区内空目录，全局 `~/.config/opencode`（24 个开发技能、开发用 MCP）不再混进来；凭证在 `XDG_DATA_HOME`，不受影响。

**API**：`dev_tasks` 表（状态机 queued→running→done→committed/discarded）+ `/api/assistant/cap/dev*` 路由（投递/续改/提交/丢弃/查询，只能操作本人任务）+ ai_tasks 队列类型 `dev.task/dev.commit/dev.discard`（优先级仅次于对话，失败不自动重派）。完成与提交结果由 API 直接发微信，不经过对话模型。

**实测**（2026-11-14）：API 直投、微信对话投递、续改、提交（分支留档）、丢弃（工作区+分支清理）、完成通知全链路通过；危险动作探测（push、读 `~/.zshrc`、读 `/etc/hosts`）全部被挡。

**已知局限**：
- mimo 偶发不调工具直接说「我去改」（1/5 概率，提示词已加约束，仍需观察）；
- deepseek flash 只适合小改动，大重构质量无保证（当初的取舍）；
- 每个人同时只有一个「最近」编码任务，新任务的结果没确认前，「提交」永远指向最近一条；
- 提交只到本地分支，不 push、不合 main——合并仍是人工做。

## 9.5 微信批准仓库 + 多轮续改（P2，2026-11-14）

**加仓库（两步，都是助手做）**：
1. 「把 xxx 也加到能改的范围」→ `repo_add` → 建 `repo_requests`（pending）→ 回「你回句批准，我就加进去」；
2. 「批准」（带不带名字都行）→ `repo_approve`（只有爸爸的角色能批）→ 入队 `dev.repo.add` → worker 校验 `~/work/<name>` 真的是 git 仓库后写进 `repos.json`，结果直接发微信。

只有本机 root 下真实存在的 git 仓库加得进来；加不进来会照实说（比如 cijian-hermes-import 只是普通目录）。

**小模型稳定性的两处兜底**（mimo 实测丢参数/拒绝调用）：
- 「批准」这类零参数动作在 worker 直接执行（`_repo_approve_reply`），没有在等的申请时才交回模型；
- 对方这条微信的原文（`CIJIAN_USER_TEXT`）注入 MCP 进程，`dev_task`/`dev_continue` 没带参数时拿它当需求。

**多轮续改**：
- `dev.task` 改为串行类型——同一时间只跑一个编码任务，续改/新任务排队，不会撞工作区；
- 「提交/算了」挑的是最近一条**改完了等人定**的（`GET /dev/latest?for=decide`），正在跑的不会被误伤；
- 会话丢了（换模型/清会话）续改也能接上：API 把上一轮 summary/diff 塞进 payload，worker 在无会话时注入提示词；
- 已提交的任务再要改，API 明确回「要再改就重新提一个」，对话侧照新需求开新任务。

**实测**：申请→批准（裸「批准」）→repos.json 落盘→在新仓库里连改两轮（diff 累积）→提交到分支→清理，全链路走通；坏路径（非 git 目录、非爸爸批准、没申请就批准）都有对应报错。

## 9.6 编码通道按项目划分 + 看板（P3，2026-11-14）

**为什么**：编码通道原来只有一套仓库白名单，以后会同时有多个项目（此间、别的系统），改动必须落到明确的项目上，不能谁都能改一堆无关仓库。

**白名单 v2**（`~/.config/cijian/repos.json`，仍由人工维护，微信里只能批仓库、不能建项目）：

```json
{
  "default": "cijian",
  "projects": {
    "cijian": { "root": "~/work", "repos": ["cijian", "cijian-api", "cijian-agent", "cijian-site", "cijian-mp"] }
  }
}
```

旧格式 `{"root","repos"}` 照旧可读（整个文件视为单个 `cijian` 项目），第一次加仓库时自动迁成 v2。

**项目如何落到任务上**：
- `dev_tasks.project` / `repo_requests.project`（`openDb` 里 ALTER 迁移）；`POST /dev`、`POST /dev/repos`、`/dev/:id/continue|accept|discard` 都带 project；
- 上下文里注入 `<可改的项目>cijian（没说就默认 cijian）</...>`；只有一个项目时没提项目就自动用它，多个项目时要求说清（MCP 侧 `CIJIAN_DEV_PROJECTS`/`CIJIAN_DEV_DEFAULT` 兜底）；
- worker 按项目取仓库建 worktree：`_project_repos(project)`，项目不存在就回「没有 X 这个项目，现在能改的有…」。

**看板**：`GET /dev/board?project=&days=14` → 按「在改 / 改完等确认 / 已提交 / 没改成」分组（本人的、近 14 天，时间转北京时间，标题截 40 字）。对话侧对应 `dev_board` 工具，以及 worker 的 `_board_reply` 兜底——小模型遇到清单类问题经常干脆不调工具，所以这类固定格式的问答由 worker 直接查 API 生成，稳定且省一次模型调用。

**「提交/算了」也走 worker 兜底**（`_decide_reply`）：一个词的确定指令不再依赖模型；挑「最近一条改完了等人定」的任务，已提交/在改/没改成各有各的回话；「算了」还要求最近聊过编码结果，避免别的语境被误伤。

**踩到的坑：能力工具在隔离配置下全丢**（本轮最大问题）
- 现象：微信里让它建个文件，回「现在交不出去」/「我建不了文件」，看板和直接 `opencode run` 都正常；
- 原因：对话子进程把 `XDG_CONFIG_HOME` 指到工作区内的空目录（隔离 24 个开发技能），而 `install_mcp` 只把 MCP 配置写到工作区根的 `opencode.json`——隔离后那份被忽略，26 个能力工具一个都没注册，模型手里只有 `skill`，于是把 `dev_task` 当技能调，报错后认输；
- 修法：`install_mcp` 同时写 `<workdir>/.xdg-config/opencode/opencode.json`；
- 教训：**「小模型不稳」要先排除工具根本没挂上**，别急着怪模型。另外模型会把工具名当技能名调（`skill dev_task`），提示词里写全名 `cijian_dev_task` 并明说「不是技能」。

**实测**：显式项目「cijian 项目帮我…」→ 落 `project=cijian` → 改完推送 → 看板三档 → 裸「提交」→ 提交到分支 → 已提交；不提项目「在 docs 下建个 …」→ 自动落 cijian；裸「算了」→ 丢弃 + 清工作区。

## 10. 小程序

新增/改造：

| 页面 | 作用 |
|---|---|
| `pages/assistant/assistant` | 助手会话（可选，主要看历史） |
| `pages/shine/shine` | 已有，卡片深链目标 |
| `pages/timeline/timeline` | 闪光时间线 |
| `pages/digest/digest` | 日报归档 |

微信卡片跳转：textcard 的 `url` 指向 H5（`whereami.cn`），H5 再引导进小程序；或用 `miniprogram_notice`（需小程序与主体绑定，P4 再验）。

## 11. 实施阶段

| 阶段 | 内容 | 验收 |
|---|---|---|
| P0 | 回调正式化、发送封装、去重入库、回执 | 微信发一句，2 秒内收到回执 |
| P1 | `chat.reply` 全链路 + 人格 | 能回答并引用 wiki |
| P2 | 调度器 + 日报/提醒 | 明早 8:07 自动收到日报 |
| P3 | 记忆写入 + Hermes 记忆迁移 | 记得住「周三有英语课」 |
| P3 ✅ | 已完成：`reminders` 表 + 每分钟扫描（事件前提醒 + 08:00 汇总）、对话动作、wiki `family/assistant/{profile,preferences}.md` + `notes/YYYY-MM.md`、日程上下文注入、Hermes 记忆整理成档案与习惯 | 对话里说「记一下」→ 到点微信收到；问忌口/复查能答对 |
| P3.5 ✅ | 能力面 MCP：14 个工具（打印/打卡/闪光/提醒/订阅），每任务一枚短令牌；旧标签解析保留作兜底 | 问「这周打卡几天」能答出真实数字；说「提醒我…」真能建；说「删掉那条」真能删 |
| P4 | 小程序归档页 + 深链 | 卡片点开落到对应页面 |
| P5 | 家人接入 + Secret 轮换 | 妈妈微信里能收发 |
| P6 | 下线 Hermes | 旧服务器 cron 全停 |

## 12. 安全

- `CIJIAN_WECOM_SECRET`、`CIJIAN_WECOM_AESKEY` 只放服务器 `cijian.env`，不提交
- 回调验签失败一律 401，不落库
- 入站消息按 `MsgId` 去重，防重放
- 出站白名单：只允许发给 `wecom_users` 里 active 的成员
- **P5 前轮换聊天里暴露过的 Secret**
- 日志不打印正文（只打 msg_id、长度、耗时）

## 13. 风险

| 风险 | 应对 |
|---|---|
| 微信插件偶发丢消息 | 保留 `wecom_messages`，可人工补发 |
| opencode 卡住 | 任务 120 秒租约 + 心跳；超时回「这次没想好」 |
| 企业微信回调重试造成重复回复 | MsgId 去重 + 任务 dedupe |
| Mac mini 休眠 | `caffeinate` 常驻；agent 掉线时回执降级为「稍后回你」 |
| 素材 3 天过期 | 图片只在发送时上传，不长期存 media_id |
| 兜底回执被误判为正式回复 | 回执用 `ack:<task_id>` 记账，正式回复仍按原 task_id 发送（有回归测试） |
| agent 重启时长轮询把任务吃掉 | 领取方断开即退回队列（`releaseAiTask`）+ 租约回收改为 30 秒 |
