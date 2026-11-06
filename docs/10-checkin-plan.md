# 10 · 每日打卡工具计划（通用打卡引擎）

> 目标：工具箱**第二件工具**（第一件是打印）。「打卡项目是配置不是代码」，阅读/二胡只是两条配置；
> 核心体验是**投递即打卡**——手机录完练习视频/录音 AirDrop 给 Mac mini，全自动完成指派、记录、归档、可回看。
>
> - 日期：2026-11-05 · 状态：✅ 设计已确认，开工
> - 调研背景（钉钉读/写路线为何搁置）：[research/dingtalk-reading-checkin.md](./research/dingtalk-reading-checkin.md)
> - 契约与数据模型增补：[04-api-contract.md](./04-api-contract.md) §v1.4、[05-data-model.md](./05-data-model.md)

---

## 1. 一句话与核心体验

孩子练完 → 手机录视频/录音 → AirDrop 给 Mac mini → **约 1 分钟内**当天对应项目的卡自动点亮，家长打开网页/小程序看到的是结果，而不是待填的表单。

家长在 UI 里的角色是**例外处理者 + 事后补充者**：

| 动作 | 频率 | 在哪做 |
|---|---|---|
| 什么都不做（自动完成） | 常态 | — |
| 待指派媒体一键挂到某项目 | AI 判不了时 | 网页/小程序 |
| 改派（AI 判错时纠正） | 偶发 | 网页/小程序 |
| 补字段（书名页码/曲目遍数，触发归档文件改名） | 每天 10 秒 | 网页/小程序 |
| 在线回看当天/近 7 天的练习媒体 | 随意 | 网页/小程序 |
| 看统计（连续天数、累计时长） | 随意 | 网页/小程序 |

## 2. 与钉钉的关系（沿袭调研结论）

| 决策 | 结论 |
|---|---|
| 读老师布置的作业 | **搁置**（DWS CLI 卡在学校组织授权，家长无法自行开通）。引擎 schema 保留休眠字段 `dingtalk_rules`，将来学校放行后「加配置即接入」，不改代码 |
| 自动提交作业 | **不做**（个人无官方 API 通道，RPA 成本高）。本系统的价值 = 把视频归档好、命好名、备好字段文案，家长在钉钉里手动提交只需 30 秒 |

## 3. 用户故事

| # | 故事 | 要点 |
|---|---|---|
| US-C1 | **投递即打卡**：AirDrop 媒体 → 自动指派项目 → 自动生成当日记录 → 状态变绿 | 见 §4.1 管线 |
| US-C2 | **在线回看**：任意一天的卡点开 → 媒体列表 → 直接播放（近 7 天云端预览；更早显示「已转本地归档」） | 见 §4.4 |
| US-1 | **建/改/停项目**：名称、应打日、媒体偏好、字段模板、分类提示语——新增跳绳/口算零代码 | 配置界面 MVP 仅网页（低频） |
| US-2 | **补字段**：给自动生成的记录补「书名/页码」「曲目/遍数」 | 触发归档文件重命名（§4.5） |
| US-3 | **待指派/改派/忽略**：AI 判不了的挂到对的项目；判错的一键改派；误投进 Downloads 的忽略 | 同一个 `assign` 端点 |
| US-4 | **补卡改卡**：改字段、改日期；「无媒体手动补卡」Phase 2 视试运行情况 | — |
| US-5 | **统计**：连续天数（streak）、近 N 天完成格、累计练习时长 | streak 口径见 §4.6 |
| US-6 | **扩展**：新项目 = 一条配置；钉钉双通道休眠字段已留 | — |

## 4. 关键设计

### 4.1 投递即打卡管线

```
手机录视频/录音 ──AirDrop──▶ Mac mini ~/Downloads
                               │ agent checkin 线程，30s 一轮：
                               │   过滤：mp4/mov/m4v/m4a/mp3/wav + 连续两轮大小稳定
                               │         + ffprobe 可解析 + 时长 ≥ 60s（垃圾过滤，非练习时长判定）
                               │   ffprobe → type/duration/size/sha256
                               │   抽 3×12s 片段 → whisper.cpp 分类（§4.3）
                               ▼
             POST /api/agents/checkin/media（元数据 + 分类结果）
                               │ api 指派（§4.2）→ upsert 当日记录 → 挂媒体
                               ▼
             响应 {assigned, archive_name} ──▶ agent 重命名入 归档/<yyyy-mm>/
                               │                    （未指派 → holding，等 assign）
                               ▼
             agent 异步：ffmpeg 转码预览（§4.4）→ POST …/media/:id/content
                               ▼
             网页/小程序：今日卡绿、可回看、可补字段
```

- 记录日期以 **agent 本地日期**（`date` 字段上报）为准；api 侧「当日」统一按 **Asia/Shanghai**。
- 同项目同日多条媒体**求和累计**（20 分钟二胡分两段录是常态）。
- sha256 去重：7 天内重复上报返回已有 media（`duplicate: true`），agent 跳过。

### 4.2 项目指派（优先级）

| 优先级 | 规则 | 说明 |
|---|---|---|
| ① | **AI 分类**：`classifier.project_hint` 指向 active 项目且 `confidence ≥ 0.6` | 常态路径，见 §4.3 |
| ② | **唯一未完成**：当天恰有一个 active 项目尚无记录，且其 `media_type` 兼容（video≠audio） | 兜底 |
| ③ | **待指派**：进待指派区，家长一键 assign；>14 天未处理自动 `dismissed` | 误投的媒体也走忽略 |

改派 = 同一个 `assign` 端点把已挂媒体移到另一项目（目标日无记录则自动建）。**AI 永远可被一键纠正**，误指派的代价只是点一下。

### 4.3 AI 分类器（可插拔，`CIJIAN_CHECKIN_CLASSIFIER`）

| 值 | 机制 | 说明 |
|---|---|---|
| `asr`（默认） | **whisper.cpp 本地**：3 段片段转写 → 中文字符量 + no_speech_prob 判「人声/非人声」→ 按项目 `classifier_hint`（如 朗读=人声 / 二胡=器乐）匹配 | brew 装 whisper-cpp + ggml 模型（base ~148MB）；纯子进程调用，与 ffprobe/lp 同模式，不破坏 agent 零依赖原则；隐私不出家门；M 系芯片 3 段共 ~15s |
| `llm` | OpenAI 兼容多模态接口带片段 + 各项目 hint 直接问 | 更通用（未来「听不出区别」的项目），需 API key |
| `off` | 不分类，纯规则（§4.2 ②③） | 兜底 |

前置：Mac mini 为 M 系芯片（安装时确认；老 Intel 机降级 `llm`/`off`）。分类结果（方法/置信度/证据）随媒体入库，界面上可见「为什么归到这个项目」。

### 4.4 媒体回看（预览片上云 + 签名 URL 播放）

约束：视频本体在 Mac mini（几百 MB，不过云）；agent 纯出站；`<video>`/`wx.video` 发不了 Authorization 头。

```
agent: ffmpeg 转码预览 —— 视频 480p/H.264/~250kbps/faststart（长视频按 8MB 上限自动降码率，最低 100k）；音频转 AAC 64k（或原样 m4a）
  → POST /api/agents/checkin/media/:id/content（≤120MB，X-Agent-Key）
  → api 落盘 data/media/<yyyy-mm>/<media_id>.<ext>，preview_status → ready，
    preview_expires_at = now + 7 天
播放: GET /api/checkin/media/:id/url (JWT) → { url: "/media/<HMAC token>", expires_at }（12h 有效）
  → <video>/<wx.video> 直接播；GET /media/:token 支持 Range（seek）
```

- **原件永远留在 Mac mini 归档目录**（全质量无上限）；云端只有预览片，保留 **7 天**（每天约 75MB，稳态 ~0.5GB），sweeper 到期删文件置 `expired`，界面显示「已转本地归档」。
- token 复用 `FILE_URL_SECRET` 的 HMAC 签名模式，绑定 media_id + 过期时间，免 auth 头正是为了播放器组件。
- 码率/分辨率/保留天数为 api 配置项（env），数字可调。

### 4.5 归档命名（两段式，一个 rename 机制）

1. **投递时**：指派成功响应带 `archive_name`（模板默认 `{date}_{project}_{orig}`，如 `2026-11-05_二胡_IMG_1240.mp4`），agent 即刻重命名入归档，并回报确认。
2. **补字段后**：api 重算期望名（`2026-11-05_二胡_良宵x5.mp4`），agent 每 5 分钟 `GET /api/agents/checkin/renames` 拉差量执行，完成回报 `{archive_name, archive_path}` 入库（界面可显示归档位置）。

### 4.6 状态与统计口径

- 预览上传：agent 后台线程上传（失败指数退避），api 的 Node `requestTimeout` 放宽到 1 小时——默认 300s
  会切断跨洋慢速上传（2026-11-06 首条真实视频实测：6.7MB/14 分钟）。
- 练习时长门槛（min_duration）**不参与任何判定**（2026-11-05 决策）；ffprobe 时长仅用于统计展示「累计练习时长」。字段保留，逻辑不读。
- 今日卡三态：**未打（灰）/ 待指派（红点）/ 已完成（绿）**。
- streak = 以日历日连续的「完成」天数（完成 = 当日该项目至少一条 matched 媒体；当天未打不断历史，只是 streak 归零重算向后看）。

## 5. 对各仓的影响

| 仓 | 改动 | 里程碑 |
|---|---|---|
| cijian-api | 三张新表（幂等迁移）+ 站点侧 9 个端点 + agent 侧 4 个 + /media/:token(Range) + sweeper 两项清理 + vitest | M-C1 ✅ |
| cijian-agent | checkin 守护线程（扫描/ffprobe/whisper 分类/两段命名/预览转码上传/rename 轮询）+ 配置项 + install.sh；Mac mini 装 ffmpeg/whisper-cpp | M-C2 ✅ |
| cijian-site | 工具箱卡片 + `/tools/checkin`：状态板/待指派/补字段/统计/播放器 | M-C3 ✅ |
| cijian-mp | `pages/checkin`（今日/待认领/播放/字段/改派）+ `pages/checkin/projects`（项目管理）+ app.json tabBar + api.ts 扩展（PATCH/wx.video 播放） | M-C4 ✅ |
| cijian（本仓） | 本计划 + 04/05 增补 + research 归档 | ✅ |

## 6. 里程碑

| # | 内容 | 验收 |
|---|---|---|
| M-C1 ✅ | api 全部端点 + 测试 | vitest 全绿；curl 模拟 agent 上报 → 指派 → 记录生成 → 预览上传 → 签名 URL 可播（Range 生效） |
| M-C2 ✅ | agent 管线 | 真机：录音投 Downloads → 归档命名正确 → 预览上云；whisper 分类准确（阅读/二胡各试 3 次） |
| M-C3 ✅ | 网页 | 未登录不可见；状态板/待指派/补字段/播放/统计可用 |
| M-C4 ✅ | 小程序 | 同上网页口径 + 项目管理页；CI 类型检查 + 自动上传开发版；「设为体验版」需后台一键操作；播放需真机点一次 |
| M-C5 | 试运行一周 | 全家真实使用一周；统计待指派率（目标 <10%）；决定是否需要「无媒体手动补卡」 |

## 7. 决策记录（2026-11-05 确认）

| # | 决策点 | 结论 |
|---|---|---|
| 1 | 功能归属 | cijian 工具集第二件工具，**网页 + 小程序同时可用**，不建独立仓 |
| 2 | 打卡方式 | **投递即打卡**：所有打卡 = AirDrop 媒体到 agent 机器，自动扫描自动完成；无手动打卡表单 |
| 3 | 项目指派 | AI 分类（whisper.cpp 本地，默认）> 唯一未完成 > 待指派；永远可一键改派 |
| 4 | 在线回看 | **必须功能**：预览片上云（480p/250kbps，2026-11-06 因跨洋链路从 450k 下调）+ 签名 URL 播放；**云端只留 7 天**，原件 Mac mini 永久 |
| 5 | 练习时长 | **不设门槛**（min_duration 字段保留不启用），时长仅入统计 |
| 6 | 提醒 | 暂不做（Phase 2 再议通道） |
| 7 | 钉钉 | 读搁置（schema 留 `dingtalk_rules` 休眠字段）、自动提交不做 |
| 8 | 技术栈 | 完全跟随现有四仓（node:sqlite/Hono、Astro、原生小程序 TS、Python agent） |

## 8. 风险

| 风险 | 缓解 |
|---|---|
| whisper 误判（音乐段偶发幻觉文本） | 置信度阈值 + 3 段投票 + 界面一键改派；`classifier` 入库可追溯 |
| Downloads 误扫（家人下载的视频） | 扩展名 + ≥60s + 双轮稳定过滤；待指派区可忽略；14 天自动 dismissed |
| Mac mini 离线/挂了 | 打卡暂停但无数据丢失（投递物在 Downloads 等待）；今日卡显示 agent 离线（复用心跳） |
| 预览上传占用上行带宽 | 60–70MB/天，深夜或不限；失败下轮重试，不影响打卡主流程 |
| 7 天后想回看 | 原件在 Mac 归档目录（家庭共享/直连）；Phase 2 可选「按需重传预览」 |
