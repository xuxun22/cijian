# 打印闭环：状态机、租约、防重打

> 2026-10-21 · 类别：howto · 仓库：cijian-api / cijian-agent · 状态：现行

## 状态机

```
queued → claimed → printing → done
   ▲        │(租约超时/失败且attempts<3 → 回 queued，30s 退避租约)
   │        ▼
   └──── failed(attempts≥3)      expired(文件24h过期且未开印)
```

## 关键机制（改动前必读）

1. **租约即退避**：`claim` 只领 `lease IS NULL OR lease <= now` 的任务。失败回 queued 时把
   lease 设为 now+30s —— 退避与"领取占用"复用同一字段。测试里模拟时间流逝 = 直接 UPDATE lease。
2. **attempts 在 claim 时 +1**，上限 3。sweeper 把 `queued AND attempts>=3` 置 failed。
3. **防重打**：agent 本地 `state.json` 记 `{current_job, phase, cups_job}`。重启恢复规则：
   - phase=submitted 且 CUPS 队列里还有 → **只等待，不重新提交**
   - phase≠submitted 且租约仍有效 → 重新走完整流程
   - 租约过期 → 清状态，服务端重派（服务端 attempts<3 才重派）
4. **上报 409 的含义**：租约过期或任务被重派 → agent 必须放弃本地副本。process() 里
   report('printing') 返回 False 时必须中止（不确认租约不打印）。
5. **CUPS 结果判定**：`lp` 非零退出 = 提交失败；任务离开 not-completed 队列 = 视为完成
   （CUPS 失败任务同样移出队列且历史保留因机而异，明细不强校验）。
6. **照片默认 fit-to-page**：手机大图按原始尺寸打印会被 CUPS 拆成多页（实测一张照片打到第 5 页
   还在打）。图片类任务加 `-o fit-to-page` 单页输出；若驱动不吃 `-o` 导致 lp 失败，自动去掉
   可选项重试一次。
7. **打印超时默认 30 分钟**（CIJIAN_PRINT_TIMEOUT）：printing 上报把租约续到 10 分钟，
   agent 每 4 分钟重报 printing 续租——租约可无限续，等待上限只受打印超时约束。

## 实战记录（2026-10-22）：任务卡「已接受」但纸已打出

**症状**：网页任务永远停在「已接受」，打印机实际已出纸。
**根因**：agent 实现漏了 `report('printing')`——租约停在领取时的 120s；喷墨出纸超过 2 分钟后
done 上报被 409（租约过期），任务卡死 claimed，直到 sweeper 才会动作。
**教训**：docs/03、04 里的状态上报步骤要与实现逐一对照走查；测试用例要覆盖
「打印时长 > 领取租约」的场景（本轮集成测试没测到时间维度的组合）。
**修复**（agent v0.1.2）：lp 提交成功即上报 printing（租约 600s），轮询期间每 4 分钟续租；
顺带照片 fit-to-page、打印超时放宽 30 分钟。修复后事件序列
queued→claimed→printing→(printing 续租)→done 全部在网页可见。

## 排障速查

- 任务卡 `claimed`：agent 死了。等租约过期被 sweeper 重派，或手动
  `UPDATE print_jobs SET status='queued', lease_expires_at=NULL WHERE id=...`（等效 sweeper）
- 任务卡 `queued` 且 attempts≥3：sweeper 10 分钟内会置 failed
- 打印机显示离线：agent 心跳 30s 一次，60s 无心跳判离线 → 看 `launchctl list | grep cijian`
  与 `~/Library/Logs/cijian-agent.err.log`
