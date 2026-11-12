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
| P3 ✅ | 已完成：`reminders` 表 + 每分钟扫描（事件前提醒 + 08:00 汇总）、对话动作（`<reminder>` / `<memory>` 结构化块）、wiki `family/assistant/{profile,preferences}.md` + `notes/YYYY-MM.md`、日程上下文注入、Hermes 记忆整理成档案与习惯 | 对话里说「记一下」→ 到点微信收到；问忌口/复查能答对 |
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
