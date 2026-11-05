# 调研报告：钉钉「小学生每日打卡」自动化可行性（阅读 / 二胡 / 通用打卡）

> 调研日期：2026-11-05（2026-11-05 更新：扩展为通用打卡设计）
> 目标：① 通过 API 自动获取老师在钉钉布置的作业/打卡任务；② 自动上传小朋友的练习视频（阅读、二胡等）并提交；③ 打卡功能设计为通用引擎，可承载任意练习项目。

## 一、结论速览（TL;DR）

| 子问题 | 结论 | 可行路径 |
|---|---|---|
| 自动**获取**老师布置的作业/打卡任务 | ⏸️ 实测受阻，搁置 | 官方 DWS CLI 技术上可读 `EDU_HOMEWORK`/`EDU_CARD` 任务，但**组织授权需要学校管理员批准**（2026-11-05 实测确认），家长无法自行开通；引擎保留双通道设计，未来学校放行后加配置即接入 |
| 自动**提交**阅读视频到作业/打卡 | ❌ 官方 API 对个人基本不可用 | 旧版 EDU API 有完整的「提交作业/提交打卡」接口，但权限只对教育类 ISV 服务商（行业 TOP5 门槛）或学校组织内部应用开放，**家长身份拿不到权限** |
| 自动提交的替代方案 | ⚠️ 可行但重 | RPA/UI 自动化（Android 无障碍，社区有成熟先例）；或退而求其次：agent 准备好视频+文案，最后一步人工点提交（半自动） |

**一句话结论**：「读」能自动化，「写」对个人开发者没有官方通道；推荐做「自动获取作业 + 自动备好视频 + 半自动提交」的 MVP，全自动提交走闲置安卓手机 RPA 的进阶路线。

---

## 二、发现详情

### 2.1 旧版 EDU API：接口齐全，但个人拿不到权限

钉钉旧版服务端 API（`oapi.dingtalk.com/topapi/edu/...`）有一整套家校本/打卡接口：

| API | 功能 | 关键参数 |
|---|---|---|
| `dingtalk.oapi.edu.homework.query` | 查询作业详情 | 返回 hw_title、hw_content、hw_media(视频)、hw_photo、teacher_name、截止时间等 |
| `dingtalk.oapi.edu.homework.student.submit` | **学生提交作业** | media(视频)、photo、video(音频)、content、student_id、hw_id、class_id、biz_code |
| `dingtalk.oapi.edu.card.user.task.submit` | **提交打卡**（家长身份） | medias JSON 支持 `{"type":"video", data:{mediaUrl, videoDuration, videoFileName...}}`、card_task_id、content |
| `dingtalk.oapi.edu.card.task.submit` | 帮用户提交打卡 | card_type（如跳绳 jump）、metering_number、content |
| `dingtalk.oapi.edu.homework.create/update` | 老师布置/更新作业 | 教师侧 |
| 事件订阅 `events-edu-card-update` | 打卡任务变更推送 | 需应用订阅 |

**为什么用不了：**
- 这套 API 是给**教育行业 ISV 服务商**设计的（文档里的 `biz_code` 是 SONGSHU/KNOWBOX 等合作方）。接入要求：教育垂直领域 **TOP5**、有明确运营/商业规划、专门人力投入 —— 个人开发者不可能过审。
- 另一条路是**学校组织的企业内部应用**，但应用必须建在学校钉钉组织里，家长不是学校组织的管理员。
- 旧版服务端 API 已明确「**不再开放新能力**」，多个历史模块「未接入的不再支持新增接入」。

### 2.2 官方 DWS CLI（最现实的「读」路径）

[DingTalk-Real-AI/dingtalk-workspace-cli](https://github.com/DingTalk-Real-AI/dingtalk-workspace-cli)（`dws`）是钉钉**官方开源**的 CLI（3.9k stars，活跃维护），面向人和 AI agent：

- 家校作业会以 **`EDU_HOMEWORK`（家校本）/ `EDU_CARD`（打卡）** 类型出现在用户的待办任务里
- `dws todo task list --query-all`（底层 `query_all_task` / `query_multi_user_sub_tasks`）可以读到这些任务，**家长账号实测能拿到**（社区 issue 有人用于自己孩子的作业汇总）
- 还可以 `dws event consume user_todo_task_*` **实时监听**新作业下发
- 认证三层模型：OAuth 设备流登录（个人账号）→ 组织 CLI 访问授权（管理员）→ PAT 行为授权（scope 粒度）

**已知限制**（[issue #459](https://github.com/DingTalk-Real-AI/dingtalk-workspace-cli/issues/459)，2026-06 仍 open）：
- 任务 `content` 只有**纯文本**；老师插入的图片/worksheet 附件嵌在家校 Mini App 渲染层，API 不暴露
- 任务的 `redirectUrl` 是 `dingtalk://` deeplink，外部程序无法直接调起详情页
- DWS **没有**「提交家校本作业/打卡内容」的命令

**风险点**：DWS 需要组织开启 CLI 访问（管理员授权）。家长用自己所在组织的授权登录后，跨组织待办 `--query-all` 能否稳定读到学校班级的任务需要实测（issue 里有人成功，但不是官方承诺的能力）。

> **✅ 2026-11-05 实测结论**：家长账号 OAuth 登录走到组织授权一步被卡 —— 「CLI data access is not enabled for this organization」，需要提交申请由**学校组织管理员**批准，家长无法自行开通。**钉钉读取路线搁置**，待将来学校愿意开启 CLI 访问、或 DWS 开放个人级 edu 读取能力时再启用（引擎里的 `dingtalk_rules` 双通道设计保留，届时加配置即可接入）。

### 2.3 视频上传能力盘点

| 通道 | 能力 | 能否当「提交作业」用 |
|---|---|---|
| DWS `chat message send` | 可以给班级群发文件/视频消息（PAT scope `chat.message:send`） | ❌ 只是发群消息，老师在家校本里看不到，不算提交 |
| DWS `drive` | 上传文件到个人钉盘 | ❌ 同上 |
| 旧版 edu submit API | 真正写入家校本/打卡记录 | ❌ 权限拿不到（见 2.1） |
| 钉钉客户端手动提交 | 老师能在打卡任务里看到视频 | ✅ 唯一"官方认可"的提交方式 |

### 2.4 RPA / UI 自动化路线（社区成熟先例）

「自动提交」目前在社区的全部实践都是 **UI 自动化**，且都是考勤打卡场景（技术路线完全适用于家校打卡）：

- [AndroidCoderPeng/DailyTask (AutoDingding)](https://github.com/AndroidCoderPeng/AutoDingding)：1680 stars，Kotlin + Android 无障碍，**维护到 2026-05**，兼容 Android 8~16 / 鸿蒙 4
- [yqchilde/DingTalkClockIn](https://github.com/yqchilde/DingTalkClockIn)：基于 Hamibot 平台（免 root，远程/定时触发）
- [wjd-jax/android-attendance](https://github.com/wjd-jax/android-attendance)：Docker + USB ADB + 本地 OCR，隐私友好
- 还有 root/shell、chromedriver 模拟网页版等老方案

**套用到「上传阅读视频」**：需要一台常驻安卓设备（或模拟器）登录家长钉钉 → 定时唤起 → 打开班级群打卡任务 → 从相册选择指定视频 → 提交。技术上可行（无障碍可以遍历钉钉 WebView 控件），但：
- 钉钉版本更新可能导致控件结构变化，需要维护
- 上传视频属于多步交互（选文件、等待转码），脚本比「极速打卡」复杂一个量级
- 提交的是**真实阅读视频**，不是伪造记录，合规风险低；但全自动无人值守一旦出错（传错视频/重复提交）没有兜底

---

## 三、推荐方案（分阶段）

### MVP：半自动（推荐先做，1~2 周量级）

```
[DWS CLI 定时/事件监听] → 发现今日打卡任务（EDU_CARD/EDU_HOMEWORK）
        ↓
[Agent] 提醒家长+孩子："今天的XX打卡来了，要求是…… 截止时间……"
        ↓
[孩子] 用手机录练习视频（agent 可提供书单/曲目/计时等辅助）
        ↓
[Agent] 自动整理：视频重命名、写好打卡文案、放到相册指定目录
        ↓
[家长] 点开 deeplink/打卡入口，选视频，点提交（唯一的 manual step）
        ↓
[Agent] 定时核查任务状态变为「已完成」，否则再提醒
```

价值：家长每天只需 30 秒；习惯养成部分（提醒、书目/曲目、统计、存档）完全自动。

### 进阶：全自动提交（如果半自动不够）

- 路线 A：闲置安卓手机 + Android 无障碍脚本（参考 DailyTask/Hamibot），agent 通过推送指令触发「上传今日视频并提交」
- 路线 B：盯 DWS / 开放平台后续是否开放 edu 提交类能力（给 issue #459 点赞/订阅）

### 兜底：直接发班级群

如果老师不强求在打卡任务里提交，`dws chat message send` 发视频到班级群是全自动且官方 API 支持的 —— 可以和老师沟通确认接受哪种形式。

---

## 四、通用打卡引擎设计（阅读 / 二胡 / 未来任意项目）

> 核心思想：**「打卡项目」是配置，不是代码**。阅读、二胡只是两条不同的配置记录，引擎和流程管线完全复用；未来加跳绳、口算、英语跟读都是加一行配置。

### 4.1 数据模型

```
CheckInProject（打卡项目）
├── name            "每日阅读" / "二胡练习"
├── schedule        提醒时间（如 阅读每天 19:30，二胡 周一三五 20:15）
├── media_required  [video] / [video,audio] / [photo,text] …
├── min_duration    视频最短时长（二胡 20min、阅读 10min，防"假打卡"）
├── dingtalk_rules  钉钉任务路由规则（可选）：
│     { task_types: [EDU_CARD, EDU_HOMEWORK],
│       keywords_any: ["阅读","朗读","二胡","练习曲"] }
├── submit_policy   manual / group_chat / rpa / local_only
└── stats           连续天数、累计时长、周报

CheckInRecord（打卡记录）
├── project_id, date, media_files[]
├── source          dingtalk_task:<id> / self_scheduled
├── status          pending → recorded → submitted → verified
└── extra           书名+页码 / 练习曲目 等项目自由字段
```

### 4.2 任务来源：双通道适配器

| 通道 | 机制 | 适用 |
|---|---|---|
| A. 钉钉自动发现 | 轮询 `dws todo task list --query-all`（或事件监听），按 `dingtalk_rules` 的 taskType+关键词把任务路由进对应项目 | 老师在钉钉布置的阅读打卡 |
| B. 自设计划 | 本地重复日程，到点直接触发流程 | 课外二胡班、家庭自定的每日练习 |

两个通道产出统一的 `CheckInRecord`，后续流程不感知来源。二胡如果老师也在钉钉布置，只需给二胡项目加上 `dingtalk_rules`，立即升级为自动发现。

### 4.3 统一流程管线（对所有项目一致）

```
触发（定时 / 钉钉新任务）
  → 提醒（含任务要求摘要 + 项目专属内容：今日书目/练习曲目）
  → 录制（视频/音频，agent 提供计时器）
  → 校验（时长≥min_duration、文件大小、格式）
  → 整理（重命名 "2026-11-05_阅读_夏洛的网P32-45.mp4"、归档、生成文案）
  → 提交（按 submit_policy 分发）
  → 核查（钉钉任务状态轮询，未完成则升级提醒）
  → 记录（连续天数、周报推送给家长）
```

### 4.4 提交策略可插拔

| 策略 | 自动化程度 | 说明 |
|---|---|---|
| `manual` | 半自动 | agent 备好视频+文案+deeplink，家长最后点提交（MVP 默认） |
| `group_chat` | 全自动 | `dws chat message send` 发视频到班级群（需老师认可） |
| `rpa` | 全自动 | 闲置安卓机无障碍脚本真提交（进阶） |
| `local_only` | 全自动 | 纯家庭自设项目，本地存档+统计即可（二胡课外练习默认用这个） |

### 4.5 阅读 vs 二胡：只是配置差异

| 维度 | 每日阅读 | 二胡练习 |
|---|---|---|
| schedule | 每天 19:30 | 周一三五 20:15（或每天） |
| media | video + text(书名页码) | video + text(曲目/遍数) |
| min_duration | 10min | 20min |
| dingtalk_rules | 关键词「阅读/朗读」 | 关键词「二胡/练习曲」（若有） |
| submit_policy | manual | local_only 或 manual |

---

## 五、关键参考链接

- DWS CLI（官方）：https://github.com/DingTalk-Real-AI/dingtalk-workspace-cli
- 家校本/打卡任务 API 层限制：https://github.com/DingTalk-Real-AI/dingtalk-workspace-cli/issues/459
- 旧版提交作业 API（权限不可得，仅参考）：`dingtalk.oapi.edu.homework.student.submit`（developer.alibaba.com docs apiId=49894）
- 旧版提交打卡 API（同上）：`dingtalk.oapi.edu.card.user.task.submit`（apiId=52022）
- 教育服务商接入门槛：https://open.dingtalk.com/document/isvapp/dingtalk-education-application-service-provider-access-solution
- 新版待办查询（定向开放）：`POST /v1.0/todo/users/{unionId}/organizations/tasks/query`
- RPA 先例：https://github.com/AndroidCoderPeng/AutoDingding 、https://github.com/yqchilde/DingTalkClockIn 、https://github.com/wjd-jax/android-attendance
