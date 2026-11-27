# 本机可跑的 Jev 替代：本地决策模型选型

> 日期：2026-11-25 · 仓库：cijian（只调研，未安装、未改代码） · 类别：overview · 状态：**已在本机实测，未接入生产**

## 一句话

Jev 本体跑不了本地（闭源、无权重、无自托管）；但 **M2 / 8GB 完全跑得动 Jev 兼容的开源决策模型**。
首推 `Ollaya + laya:multilingual`（322M / 683MB，中文可用，CPU 即可）；想更快可试 `largha:150m`（144M，Apple GPU via MLX，但只有 512 token 上下文）。
**最大风险不是硬件，而是 zero-shot 准确率与校准**——2026-11-25 用 65 条真实微信实测：8 类意图 50.8%、noul 门禁接近随机，**不足以替代现有正则**。

## 实测结果（2026-11-25，本机）

代码与完整报告：<https://github.com/xuxun22/local-decision-bench>（private）。

- 数据：`wecom_messages` 中 80 条入站 text，去重后 65 条；单标注者，无对话上下文。
- 环境：M2 / 8GB / macOS 26.5.2；Ollaya 0.18.0；`laya:multilingual` 在 Mac 上实际走 **MLX/Metal fp32**（server log `engine=mlx`），不是文档写的 ONNX CPU。
- 8 类意图（paper/checkin/schedule/weather/memory/action/meta_dev/chitchat）：
  - `laya:multilingual` **50.8%**（95% CI 38.5–63.1），macro-F1 0.526；weather 4/4、schedule F1 0.67、checkin 0.52；memory/action/meta_dev/paper 只有 0.29–0.53。
  - `largha:150m` 38.5% / 0.421；更快但 action 全灭、memory 召回 1/11。
  - 手写关键词基线 87.7%（同数据、in-sample 上界，不是泛化估计）→ **零样本模型没打赢领域规则**。
- 两个 noul 门禁都不合格：
  - paper_related AUC 0.675（只有 6 个正例，CI 0.32–0.97）；0.5 阈值只 recall 0.17。
  - write_request AUC **0.540**（CI 0.37–0.70，等于瞎猜）；最佳 F1 阈值 0.003，等于全放行。
- 延迟与内存（3 问/请求）：p50 111ms / p95 136ms；单问 p50 26ms / p95 37ms；冷加载 6.7s；phys_footprint 2.3GB（峰值 2.57GB）；模型 683MB。默认 5 分钟 keep-alive 卸载后首问 ~0.7s，生产要调大或预热。
- prompt 消融：中文选项**描述**很关键（50.8%），只给标签名 30.8%，英文标签 21.5%；把 noul 换成 choice 或加 true/false 也救不了门禁。

结论：**运行时完全可行，准确率/校准不可行**。保留正则第一道；模型最多做「非状态性、正则未命中」的 fallback，并用 200+ 条带上下文的标注重新评测、重拟合温度。状态性操作绝不交给它。

## 为什么不是「随便下个模型」

- Jev 是 TypeSafe 托管服务，无开源权重、无自托管/VPC 方案（见 [jev-evaluation](jev-evaluation.md)）。
- 决策模型不是聊天模型：一次 forward 输出每个选项的概率，需要专用 readout / tokenizer。现有 `llama-server 0.9.0` 只能跑普通 GGUF 聊天模型，**不能**直接加载这类权重。
- 需要 Jev 兼容运行时。`Ollaya`（Apache-2.0，Rust 单二进制，1.5k star）把 `/v1/systemone`、`/v1/decisions`、`/v1/models` 做到与 `typesafe-sdk 0.7.1` 线级一致，现有客户端只改 base URL 即可。

## 本机边界（2026-11-25）

Apple M2（8 核 CPU / 10 核 GPU）、8GB 统一内存、macOS 26.5.2、可用磁盘约 64GB、已装 `llama-server 0.9.0`（未装 Ollama / LM Studio）。

结论：**100M~2B 参数都可行**，决策模型 144M~322M 是最舒服的区间；4B 及以上不要碰（`decider:4b` 权重 8.4GB，且 CPU 峰值可到 21GB）。

## 候选对比

数据来自 Ollaya 模型页 / Ollaya Bench（2026-10 版）。延迟列原文是 RTX 5090 或 24 核 Threadripper 的 CPU，**不是 M2 实测**。

| 模型 | 参数 / 体积 | 峰值内存 | 语言 | 上下文 | macOS 跑法 | 5 问延迟（参考） | 结论 |
|---|---|---|---|---|---|---|---|
| `laya:multilingual` | 322M / 683MB | 1.9GB（CPU） | 100+，含中文 | 1024 | ONNX Runtime **CPU** | 516ms（24 核 CPU） | **首推**：中文 + 零样本 + 内存小 |
| `largha:150m` | 144M / 328MB | <1GB（估） | 100+，作者测过中英 | **512** | **Apple GPU（MLX）** | 339ms（CPU）/ 18ms（GPU） | 次推：最快最省，但上下文短，需 Ollaya ≥0.15 |
| `decima:small` | 122M / 510MB | 586MB | 100+ | 512 | ONNX CPU | 591ms | 备选：选项顺序不影响结果 |
| `decider:0.8b` | 0.75B / 1.5GB | 数 GB | **仅英文** | 32768 | ONNX CPU（慢） | 60ms（GPU） | 中文场景不适用 |
| `kev:0.8b` | 0.76B / 约 1.5GB | 数 GB | 仅英文 | 长 | ONNX CPU | 171ms（GPU 家族） | 中文不适用 |
| `decider:4b` / `winnow:e4b` | 4B 级 / 8GB+ | 超 8GB | 英文 | — | — | — | **不要** |

补充：

- Ollaya 在 macOS 上，**ONNX 模型（laya / decima / decider）走 CPU**，GGUF 模型才走 llama.cpp Metal；只有 `largha` 明确走 MLX / Apple GPU。
- 想要更低延迟，可以绕过 Ollaya，直接用 Python `laya` + PyTorch MPS：官方基准里 M1 Pro 上 `laya-multilingual` 单问短文本 fp32 **25.5ms**、5 问 56ms；M2 应同量级。代价是失去 Jev 兼容 HTTP 层，且要自己做超时/并发。
- 注意新版 `laya` Python 包默认引擎已换成 0.8B reader，跑经典编码器要显式指定 `convaiinnovations/laya-multilingual`（以安装版本的 README 为准）。

## 中文证据（别只看「支持 100+ 语言」）

- MASSIVE intent（20 选项，随机 = 0.05）：`laya:multilingual` **zh-CN 0.650 / zh-TW 0.610**（英文 0.710）。
- 中文业务场景（219 条 / 284 问）：voice routing 0.883、客服路由 0.640、紧急度 0.560、诈骗/营销 0.667、升级人工 0.550。
- 但 **typed-decisions 零样本只有 0.352，低于多数类基线 0.461**：它的强项是「短文本 + 少选项 + 模式化分类」，不是通用业务推理。`laya:typed-decisions`（0.766）是英文微调版，中文用不了。
- 选项顺序不稳：20 选项时英文 flip 23%、中文客服 28%；中文繁简改写 flip 12.8%。
- 校准：原版严重过自信，ECE 0.314 → 按题类/选项数拟合温度后 0.106；中文 `noul` 拟合温度 10.2，超过官方 clamp 上限 5。

⇒ 用法上：**选项压到 ≤20、每个 Choice 带「其他」、配一个伴生 Noul；中段概率不自动执行；在自己数据上重拟合温度。**

## 推荐落地

### A. Ollaya（首选，Jev 客户端零改动）

```bash
curl -fsSL https://ollaya.dev/install.sh | sh
ollaya pull laya:multilingual
ollaya serve                     # 默认 11435
# 冒烟
ollaya run laya:multilingual --preset triage "这个月被重复扣了两次钱，请退一笔。"
```

迁移现有 Jev 客户端：

```bash
export TYPESAFE_BASE_URL=http://localhost:11435
export TYPESAFE_API_KEY=local              # 任意非空
export TYPESAFE_DEFAULT_MODEL=laya:multilingual
```

HTTP 直接验证（与 TypeSafe 同 wire format）：

```bash
curl http://localhost:11435/v1/systemone -H 'Authorization: Bearer local' -d '{
  "model": "laya:multilingual",
  "state": "孩子今天复习完了，别再出卷子了",
  "questions": {
    "wants_paper": {"type": "noul", "instructions": "对方是在要一份复习卷吗？"},
    "intent": {"type": "choice", "instructions": "这句话的意图是什么？",
      "criteria": ["要复习卷", "汇报进度", "其他"]}
  }
}'
```

### B. Python `laya` + MPS（要极限延迟 / 自己控制前后处理）

`pip install laya`，显式加载 `convaiinnovations/laya-multilingual`，`device="mps"`。
单问几十毫秒，适合塞进 api 进程内；但要自己实现超时、fail-open 和批量。

### C. 为什么不用现成的 llama.cpp

`llama-server` 适合生成式 GGUF；决策模型的选项打分头不在普通 GGUF 里（`decider`/`kev` 需要作者专用 readout 与 tokenizer）。除非只想要「聊天模型 + prompt 让它选」，那既慢又不校准，不建议。

## 上线前必须先做（沿用 jev-evaluation 的约束）

1. 从 `wecom_messages` 抽 **100~200 条真实文本人工标注**，跑混淆矩阵 + 覆盖率-准确率曲线，门槛在留出集上定。
2. 先修 [wecom-routing-bugs](wecom-routing-bugs.md) 的纯 bug——收益比接模型直接。
3. 每个调用 ≤1s 超时，任何失败 **fail-open** 回现有正则 / `chat.reply`（微信回调只等 5s）。
4. 用 `ollaya calibrate MODEL examples.jsonl --eval test.jsonl` 拟合温度，写进 Modelfile 的 `CALIBRATION`；否则概率不可当阈值用。
5. 先只放在「错了还有第二道防线」的位置（出卷否决闸、错题查询复核），不要接状态性操作。

## 对本项目的额外价值

- **隐私**：推理在本机，`role=child` 的文本不出机器，绕开美国处理方和 ZDR 问题（[privacy-iron-law](privacy-iron-law.md)）；只有首次 `pull` 权重需要联网。
- **451**：不再依赖 `api.typesafe.ai`，家里出口限制与腾讯云中转都不需要。
- **成本**：每天个位数到十几条 chat，省不了钱；价值在误路由的鲁棒性、延迟和隐私。

## 坑

- **不要把 benchmark 0.65 当业务准确率**：zero-shot typed-decisions 接近随机；必须自测。
- 上下文 512/1024 token 会截断，`/v1/systemone` 返回 `STATE_TRUNCATED`；微信长引用/多图说明要先裁剪。
- 选项 >20 明显掉（banking77 0.425，Jev 0.870）。
- 版本耦合：`largha` 需 Ollaya ≥0.15，`decider:4b` ≥0.7，`decider:2b-vision` ≥0.7.5；钉版本、记 `model` 字段。
- 模型页延迟是 5090 / 24 核 CPU 的数字，M2 8GB 必须自己测 p50/p95 和峰值内存。

## 相关

- [jev-evaluation](jev-evaluation.md)（Jev 本体调研、451、契合点）
- [wecom-routing-bugs](wecom-routing-bugs.md)（要替代的误路由）
- [privacy-iron-law](privacy-iron-law.md)（本地化依据）
- [assistant-architecture](assistant-architecture.md)（调用链路）
- 上游：<https://github.com/ollaya-dev/ollaya>、<https://ollaya.dev/library/laya>、<https://github.com/NandhaKishorM/laya/blob/main/BENCHMARKS.md>
