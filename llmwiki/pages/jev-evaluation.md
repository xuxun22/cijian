# Jev（TypeSafe System One 判别模型）适用性调研

> 日期：2026-11-25 · 仓库：cijian-api / cijian-agent（只调研，未改代码） · 类别：overview · 状态：**调研结论，未实施**（是否引入由爸爸定）

## 是什么

Jev = TypeSafe AI 2026-09-15 发布的「System One 模型」：**不生成文本**。一次请求 = `state`（字符串/JSON）
+ 若干 `questions`，并行返回带概率的类型化答案。`POST https://api.typesafe.ai/v1/systemone`，
当前 `jev-1.14.0`（别名 `jev-latest` 会漂移，要钉版本号）。

| 原语 | 问法 | 返回 |
|---|---|---|
| Choice | 多选一（≤255 项） | `choice` + 每项概率 + `confidence` |
| Score | 有序量表打分 | `score`（加权平均）+ 分布 + `confidence` |
| Noul | 是非题 | `noul` ∈ [0,1]（无 confidence） |
| Box | 图里某物在哪 | 四边比例（**预览版**） |

- 价格 $0.042/MTok 输入、输出免费；上下文 64k/请求、32k/单问题；官方延迟 70~500ms（美西测得）。
- SDK：Python `typesafe-sdk`、JS/TS `@typesafe-ai/sdk`（Node ≥22）。HTTP 就一个 POST，
  agent 侧 stdlib `urllib`、api 侧全局 `fetch` 都够，不必引依赖。
- 图片：要带 `TypeSafe-Danger-Zone-Images: true`，官方标注 "Dreamer-ready"（未达生产标准）；
  PNG/JPEG、每边 280~1568px。音频/视频不支持。

## 官方短板（docs.typesafe.ai → Model jaggedness）

字面理解、不会算术/计数、日期比较不可靠、多跳推理掉准、大段无关上下文掉准、
内容里的指令会影响判断（注入）、选项顺序偏置、不能生成文本（抽取要先 regex/LLM 列候选再让它选）。

## 网络实测（2026-11-25，决定性约束）

| 发起方 | 结果 |
|---|---|
| Mac mini（家里出口，cf-ray `HKG`） | `api.typesafe.ai`、`console.typesafe.ai` 均 **451** `Typesafe is not available in your region.` |
| 腾讯云 api 服务器（美国，cf-ray `SJC`） | **403 `Must supply an API key`** = 可达；tcp 3ms / TLS 30ms / 整次 ~80ms（未带 key，不含推理） |

⇒ **agent（Mac mini）不能直连**，只能从 `cijian-api` 侧调；agent 侧要用得经 api 中转（仿 agent 专用端点走 X-Agent-Key）。
注册、建 key、Playground 所在的 console 在家里网络同样 451。

复测（403=可达，451=被地区限制）：

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST https://api.typesafe.ai/v1/systemone -d '{}'
ssh ubuntu@100.78.101.104 'curl -s -o /dev/null -w "%{http_code}\n" -X POST https://api.typesafe.ai/v1/systemone -d "{}"'
```

## 项目里的现状（扫全部代码后的结论）

- cijian-api **零模型调用**（只排队/校验/投递）；cijian-agent 的模型调用只走 `opencode run`（12 处）+ `whisper-cli`（1 处）。没有直接调厂商、没有 embedding。
- 「做判断」的地方全是手写正则/阈值：api 侧 `routes/intents.ts` + `services/{paper,shineDaily,outing,checkin}.ts`；
  agent 侧 `ai/worker.py` 顶部一组正则。误判实例见 [wecom-routing-bugs](wecom-routing-bugs.md)。
- 测试：api 194 个 vitest 用例（CI 跑）；agent 202 个测试**不在 CI**（只 ruff + compileall），`checkin.py` 完全没有测试。

## 契合点（按性价比）

判定标准：**输入是乱文本、输出是有限选项**才适合；要生成文字 / 看图读题 / 算数 / 比日期的不适合。
以下都在 api 侧（可达 + 有 CI 护着）。

1. **出复习卷前的否决闸**（`parsePaperSheet`）：「孩子今天复习完了」「今天复习了没」会直接出卷（LLM + PDF + 企微文件）。
   正则仍当触发器（项目铁规：状态性操作不交给模型），Jev 只负责否决（Noul「对方是在要一份复习卷吗」）→ 落回 chat。
2. **错题查询路由**（`parsePaperQuery`）：正则两头都不准——真查询漏 4/8（构造句），闲聊误触 3 句。
   命中后让 Jev 复核，没命中让 Jev 兜底（Choice{查错题, 出复习卷, 其他} + 孩子 + 伴随 Noul）。
   漏了走对话模型：切 deepseek 后最近 9 条 p50 6.8s / p90 16s，11-23 出现过编答案。
3. **每日看见反馈**（`parseDailyFeedback`）：「不开心」被判成 bright 是纯 bug，**先修正则**；长尾再上 Jev
   Choice（说了/没说/换我说/五种反应/其他），state 带当天卡片原文。
4. **agent 侧（需中转，暂不做）**：`ai/worker.py` 正则层误伤不少（「我在改孩子的作业」→ 看板、「这个蛋糕谁做的」→ 身份话术），
   是 Jev 最典型的用途（有道中文技能路由 F1 0.717→0.947）；但要加 api 中转 + agent 测试不在 CI，先把正则修紧更划算。
   其中「批准/提交/算了」是状态操作，按规矩不能交给模型。

## 不适合 / 现在不需要

- vision 读卷/切题/判对错（要生成 + 高分辨率）、变式题、每日看见/出门建议/对话文案（生成）。
- whisper 音频分类（音频不支持）。`CIJIAN_CHECKIN_CLASSIFIER=llm` 是预留口但未实现；现在实质是「有人声/无人声」二分，
  需要人声的媒体项目只有一个，**Jev 暂无增益**——将来要分朗读/背诵/跟读时可用转写文本填这个口。
- 题数统计、口算 4 题=1 题、`answered ≥80%`、时间窗（算术/日期留给代码）。
- 破坏性/状态性确认（收/丢弃/纠错）——`intents.ts` 头注释的规矩，Jev 也不例外。
- 技能预选：cijian 侧没有选择逻辑（opencode 的模型按 id+description 自己挑），做了是新功能不是替代。

## 第三方证据（别只看官方 200x）

- **有道**（2026-10-17，中文，891 条）：技能路由逐技能 Noul 精确率 93.2% / 召回 96.2% / F1 0.947；
  单选 Choice F1 0.908；关键词 0.630；embedding 0.717。经验：给「何时触发」别给整份说明书（更差且贵 10 倍）；
  门槛用自己数据调；放在「错了还有第二道防线」的位置；分不清「引用的内容」和「要做的事」。
- **TDS**（Banking77 3080 条）：Jev 81.1% vs Qwen3-Coder 76.4%；**中段过度自信**（confidence 0.7~0.9 实际只对 53%）；
  没有「其他」选项时类外输入照样给 ≥0.99；级联到更弱的兜底模型反而更差。
- **arXiv 2609.37647**（37 数据集 34.6 万次）：粗粒度短文本很好，低资源语言/细粒度标签/量表打分明显变弱；
  是非题阈值需调。中文准确率须用自己的数据测。

## 若要做：落地约束

- **先修 [wecom-routing-bugs](wecom-routing-bugs.md) 里的纯 bug，再谈 Jev**——那几个 bug 的收益比接 Jev 直接。
- **先离线评测再上线**：从 `wecom_messages` 抽 100~200 条真实文本人工标注，在 api 服务器上批量跑（家里跑不了），
  看混淆矩阵再定门槛；门槛在留出集上定。
- 每个 Choice 带「其他/都不是」，并配一个伴随 Noul「这句话是不是冲着 X 来的」；中段概率不当自动执行。
- 微信回调只等 5 秒（`routes/wecom.ts` 头注释）：回调里的 Jev 调用超时 ≤1s，任何失败 **fail-open**
  落回现有路径（正则 → chat.reply）。
- 钉 `jev-1.14.0`，结果里记 `model` 字段；封装成一个模块（api：`services/jev.ts`），不散落 fetch。
- **隐私**：新增外部处理方（美国）。[privacy-iron-law](privacy-iron-law.md) 要求外部模型逐功能确认；
  零保留（ZDR）仅企业版；TypeSafe 隐私政策写明不面向 18 岁以下用户——`role=child` 的消息要不要送需爸爸拍板。
  经美国服务器调用是否符合 TypeSafe 使用条款，也需爸爸确认。
- **量级**：`cijian-agent.err.log` 里 chat.reply 共 132 条（p50 13.5s；11-22 切 deepseek 后 9 条 p50 6.8s），
  每天个位数到十几条——**省不了钱，价值只在误路由的延迟和鲁棒性**。

## 相关

- [wecom-routing-bugs](wecom-routing-bugs.md)（调研中复现的误触发与流程 bug）
- [assistant-architecture](assistant-architecture.md)（三层链路与 worker 兜底）
- [papers-pipeline](papers-pipeline.md)（意图路由登记表与 chat 工具兜底的由来）
- [wechat-reply-latency](wechat-reply-latency.md) / [opencode-latency-bench](opencode-latency-bench.md)（延迟拆解）
- [privacy-iron-law](privacy-iron-law.md)
