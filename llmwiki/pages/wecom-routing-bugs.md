# 微信入口误触发与错题本流程 bug（已修）

> 日期：2026-11-25 · 仓库：cijian-api / cijian-agent · 类别：gotcha · 状态：**已修**（Jev 调研的副产物；修法与回归见末尾「修复记录」）

复现方式：A 组走真实 `/api/wecom/callback`（临时库 + 假企微客户端，仓外脚本）；
B 组直接跑 `cijian-api` 的解析函数；C 组直接 import `cijian_agent.ai.worker` 的正则常量。**没碰生产数据。**

## A. 错题本流程（cijian-api）

### A1 随图说明永远进不了 `paper.ingest`（payload.note 恒为空）

- **症状**：家长发照片前/后配一句「三年级口算」，识别任务里 `note` 是 undefined，归属只能靠卷面姓名/年级。
  （维基 11-22 记的「随图文字进管线」修复在线上不生效，只在单测里过。）
- **根因**：`recentPaperNotes`（`src/services/paper.ts`）只取 `task_id IS NULL OR task_id = ''` 的文本；
  但回调里落到 `chat.reply` 的文本一律带对话任务 id（`src/routes/wecom.ts` 的 `record('in', { taskId })`）。
  说明文字不是意图 → 必走 chat → 必有 task_id → 永远不算 note。单测 `insertText` 直接插 NULL task_id，所以测不出。
- **建议修法**：note 是否已消费改用独立标记（新列如 `note_task_id`，或单独一张表），别复用 `task_id`；
  新列的 ALTER 放 `migrate()` 第一条（见 [gotcha-migrate-order](gotcha-migrate-order.md)）。
- **预防**：解析/筛选函数的单测必须走回调入口造数据，至少补一条「文本经回调入库后再被收集」的用例。

### A2 对话消费照片后，自动分流仍把同一张图入队 `paper.ingest`

- **症状**：发图 → 8 秒内跟一句「这道题怎么做」→ 对话带图回答；批次到期后**又**入队一次 `paper.ingest`
  （`source=wecom-auto`，日志「照片自动分流：… 1 张」）→ 家长再收到一份试卷预览或「不像试卷」引导。
- **根因**：`consumePhotoForChat` 删 `paper_intake` 行表示「已消费、错题本不再处理」，但没删 `photo_batches` 行；
  `createPhotoBatchLoop` 的兜底登记 `recentPaperImages` 把「没有 intake 行」当成「预下载没来得及登记」，重新抢占并入队。
  测试只断言消费那一刻 intake 行没了（`test/wecom.test.ts`「图后跟文字」、`test/paper.test.ts`「对话消费照片」），没跑批次 tick。
- **建议修法**：消费时不要删行，改成打标记（如 `paper_intake.task_id='chat'`）：`recentPaperImages` 看到「已登记」不再抢占，
  `pendingPaperImages`（`task_id=''`）自然排除；不要直接删批次（多页卷里其余页还要走错题本）。
- **预防**：「删行=已处理」这类隐式状态最怕别处用 NOT EXISTS 兜底；测试要跑到下游那一步（批次 tick）再断言。

## B. 解析函数误判（cijian-api）

### B1 `parseDailyFeedback`（`src/services/shineDaily.ts`）：负面反应记成 bright

- 「他不开心」「今天很不高兴」→ `{reaction: bright}`，回执是「收到，他笑了。」；「不继续说了」→ `more`。
- 根因：子串匹配，`开心` 命中 `不开心`、`高兴` 命中 `不高兴`、`继续说` 命中 `不继续说了`。
- 「还行」「挺好的」「没意思」→ `null`（落对话，反馈不落库）。
- 建议：先判否定式再判肯定式；这是纯 bug，不用等 Jev。

### B2 `parsePaperSheet`（`src/services/paper.ts`）：闲聊触发出复习卷

- 「孩子今天复习完了」「我复习一下英语」「今天复习了没」→ 命中 → 入队 `paper.sheet`
  （LLM 出变式 + Chrome PDF + 企微文件消息，几十秒、无确认）。
- 根因：`ask = /复习/ && (有孩子名 || /(出|来|做|今天|该|一下)/)`，「今天」「一下」太宽。
- 建议：只认明确说法（复习卷 / 复习错题 / 错题复习 / 出…复习），或生成前加一句确认。

### B3 `parsePaperQuery`（`src/services/paper.ts`）：非查询句被当成查错题

- 「把错题记下来」「这些错题下次再看」「错题本是什么」→ 命中 → 回一份错题清单。
- 根因：查询语气词表里有单字 `下`、`查`、`几`（「把错题记下来」命中 `下`，「错题本是什么」命中 `什么`）；
  另一面，「奶茶最近哪些题错了」「奶茶今天口算错了几道」「奶茶的错题多不多」这类真查询反而漏。
- 建议：语气词至少两字；漏的走 Jev 或对话工具兜底。

## C. agent worker 正则层（`cijian_agent/ai/worker.py`）

| 输入 | 实际走向 | 原因 |
|---|---|---|
| 「我在改孩子的作业」「奶茶在改错题」 | 看板回复 | `BOARD_QUERY_RE` 含 `在改`，`BOARD_SKIP_RE` 没有作业/错题 |
| 「这个蛋糕谁做的」「哪个模型飞机好玩」 | 固定身份话术 | `CANNED_REPLIES` 的 `谁(做\|开发\|造)的`、`(哪个)模型` |
| 「保存」「保留」「要了」「留下」 | 接受提交 | `DECIDE_ACCEPT_RE`；`_decide_reply` 对 accept 只校验最近编码任务 `status=done`，**没有上下文校验**（discard 才有 `DECIDE_CONTEXT_RE`）——push-main 项目会合并+部署 |
| 「明天不对，是周四」 | 触发技能回顾 | `CORRECTION_RE` 含 `不对` |
| 「布丁今天读了多少分钟」 | 够条件触发联网重试 | `SEARCH_PUBLIC_RE` 含 `多少`，`SEARCH_SKIP_RE` 没有「读」 |

后两行只验证到「正则命中」，是否真触发还取决于模型回复；前两行同理还受长度门槛（≤60 / ≤30 字）限制。
agent 测试不在 CI（只跑 ruff + compileall），改这里必须手动 `python3 -m unittest discover -s tests`。

## 复现片段

```bash
cd ~/work/cijian-api && npx tsx -e "
import { parseDailyFeedback } from './src/services/shineDaily.ts';
console.log(parseDailyFeedback('他不开心'));   // {kind:'reaction', reaction:'bright', ...}"
cd ~/work/cijian-agent && python3 -c "
from cijian_agent.ai import worker as w
print(bool(w.BOARD_QUERY_RE.search('我在改孩子的作业')), bool(w.BOARD_SKIP_RE.search('我在改孩子的作业')))  # True False"
```

## 相关

- [jev-evaluation](jev-evaluation.md)（这些误判正是 Jev 的候选用途，但多数先修正则更划算）
- [papers-pipeline](papers-pipeline.md)（11-22 记的 note 修复、consumePhotoForChat 设计意图）
- [wechat-reply-latency](wechat-reply-latency.md)（P0 图片通路改造的原始方案）
- [gotcha-migrate-order](gotcha-migrate-order.md)

## 修复记录（2026-11-25）

### cijian-api

- **A1 随图说明**：`wecom_messages` 新增 `note_task_id TEXT`（ALTER 放在 `migrate()` 第一条，老库实测可补列）；
  `recentPaperNotes` 改看 `note_task_id`，`bindPaperNotes` 只写这一列，对话 `task_id` 不再被占用。
- **A2 照片重复入队**：`consumePhotoForChat` 不再删 `paper_intake` 行，改成 `task_id='chat'`；
  `recentPaperImages`（NOT EXISTS）与 `pendingPaperImages`（`task_id=''`）都自然跳过。
- **B1 反馈否定式**：`parseDailyFeedback` 先判否定（不开心/不高兴/没意思/不继续说了），再判肯定；
  补 `挺好的`→bright、`还行/就那样/一般`→neutral。
- **B2 复习卷误触**：`parsePaperSheet` 排除「复习完/复习过/复习了没/复习一下/复习什么/复习多久/复习得」；
  `ask` 只认点名孩子或「该/要/得/准备复习」。
- **B3 错题查询**：`parsePaperQuery` 去掉单字语气词（`下/查/几/什么`），问句只认两字以上或
  「错了什么/错了几道/哪些题错」这类完整问法；顺带补上「奶茶最近哪些题错了」等真查询。

### cijian-agent（`ai/worker.py`）

- `DECIDE_ACCEPT_RE` 拆出 `DECIDE_STRONG_ACCEPT_RE`：「提交」直接办；「保存/保留/要了/留下」必须
  `DECIDE_CONTEXT_RE` 命中最近对话（防日常「保存」误触发 push-main 合并+部署）。
- `BOARD_QUERY_RE` 的「在改/在弄」必须跟疑问词/语气词；`BOARD_SKIP_RE` 补 `作业/错题/学习`。
- `CANNED_REPLIES` 的身份问题要求「你/助手/机器人 + 谁做的」或「模型 + 跑/用/是/句尾」，
  「这个蛋糕谁做的」「哪个模型飞机好玩」不再命中。
- `CORRECTION_RE` 去掉裸「不对」，改为「你说得不对/这样不对」等针对做法的说法。
- `SEARCH_PUBLIC_RE` 去掉裸「多少」；`SEARCH_SKIP_RE` 补 `布丁/奶茶/分钟/小时/读了多少`。

### 回归测试（都过了）

- 回调入口级：`test/wecom.test.ts`「图前一句话（走 chat.reply）仍作为随图说明进 paper.ingest」
  （文本先到 → 照片 → 真实 batch tick → 断言 `payload.note`）。
- 下游 tick 级：`test/paper.test.ts`「对话消费后批次到期，不再把同一张图入队 paper.ingest」。
- 解析级：paper/shine-daily 新增误触发与否定式用例；agent `test_worker_replies.py` 新增
  canned/board/decide/correction/search 误伤用例。

> 注意：agent 测试不在 CI，改 `worker.py` 后必须手动 `python3 -m unittest discover -s tests`。
