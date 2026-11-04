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

## 实战记录（2026-10-24）：打印机断电后「假在线」

**症状**：用户给打印机断电（`lpstat -p` 显示 `Looking for printer.`，队列任务挂 28 小时），
工作台却仍显示「在线」——agent 心跳正常，没人采集 CUPS 的设备状态。
**教训**：「agent 存活」≠「打印机可用」，两者要分开观测。心跳 detail 现携带
`printer_state`（lpstat -p 解析：printing/idle/unreachable/paused）。
**修复**（agent v0.2.0 + api v1.2）：心跳携带硬件状态 → `printers.device_state` →
前端三态展示；打印等待中不可达超 3 分钟 → 取消 CUPS 任务并报失败（防来电补打）。

## 实战记录（2026-11-04）：打印机掉线三连——取消不触发、删队列误报、mDNS 失效

**症状**：小程序任务停在「打印中」，迟迟不出纸也不报失败（最终会挂满 30 分钟超时）。

**根因 1（防补打取消不触发）**：打印机掉线时 CUPS 以 ~100s 为周期、每次 ~10s 短暂丢失
"Looking for printer." 消息，`printer_state()` 把这 ~10s 判成健康态 printing；旧逻辑要求
**连续**不可达 180s，计时器每周期被闪断清零，取消条件永远凑不满。
**修复（agent v0.2.1）**：`UnreachableClock`——不可达改**累计**计时；健康须**持续 30s** 才重置
（真恢复）；unknown（探测超时）中性不清零。`handlers/print.py` 等待循环与 `agent.py`
`_wait_gone` 恢复循环共用同一判定，`poll(state, now)` 支持注入时间做模拟测试。

**根因 2（删队列 → 误报完成）**：排障时手动删除 Mac 的打印机队列，挂起的 CUPS 任务随队列
一起消失，agent 按「离开 not-completed 队列 = 完成」上报 done——实际一张没打。
教训：**队列里有任务时别删队列**；「离开队列即完成」的简化在队列被外部改动时会误报。

**根因 3（mDNS 失效但 IP 可达）**：Mac 上「扫描打印机」扫不到（`dns-sd -B _ipps/_ipp` 零结果），
但 `nc -z 192.168.1.22 631` 通——打印机 IP 层完全可达（ARP MAC 尾巴 `cb:22:aa` 与设备名
[CB22AA] 对上）。手机米家能打是因为米家用自家发现协议，不吃 mDNS，**不能**据此推断局域网 mDNS
正常。`tailscale down` 的 A/B 测试排除了 MagicDNS 嫌疑。
**修复**：按 IP 重建队列绕过 Bonjour，且比 dnssd URI 抗漂移：

```bash
lpadmin -p Mi_All_in_One_Inkjet_Printer -E -v ipp://192.168.1.22:631/ipp/print -m everywhere
lpadmin -d Mi_All_in_One_Inkjet_Printer   # 队列名必须与 agent.env 的 CIJIAN_PRINTER_NAME 一致
```

另：cijian 架构**数据面不依赖 Tailscale**（mp/site/agent → api 全走公网
https://api.whereami.cn）；依赖它的只有运维面（服务器 SSH/CI，22 端口对外关闭，另有 5 分钟
自拉取 timer 兜底）。

## 排障速查

- 任务卡 `claimed`：agent 死了。等租约过期被 sweeper 重派，或手动
  `UPDATE print_jobs SET status='queued', lease_expires_at=NULL WHERE id=...`（等效 sweeper）
- 任务卡 `queued` 且 attempts≥3：sweeper 10 分钟内会置 failed
- 打印机显示离线：agent 心跳 30s 一次，60s 无心跳判离线 → 看 `launchctl list | grep cijian`
  与 `~/Library/Logs/cijian-agent.err.log`
- 任务卡 `printing` 超 ~4 分钟：查 err.log 是否循环刷「打印机不可达」；v0.2.1 起累计 3 分钟
  （闪断不清零）应自动取消报失败，若仍挂满 30 分钟说明跑的还是旧代码 → 重启 launchd 服务
- 手机米家能打、Mac 扫不到打印机：mDNS 坏了 → `nc -z <打印机IP> 631` 确认 IP 可达后按 IP
  重建队列（见 2026-11-04 实战记录），别纠结 mDNS 为什么坏
- **队列里有挂起任务时别删打印机队列**：任务会一起消失且 agent 误报完成
