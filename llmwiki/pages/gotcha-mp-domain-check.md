# gotcha：小程序真机「连不上服务器」= 域名未备案被微信拦截，本地工具永远复现不了

> 2026-11-04 · 仓库：cijian-mp · 类别：gotcha · 状态：现行（备案未完成前持续有效）

## 症状

真机预览/体验版小程序，输入打印口令点登录 → 提示「连不上服务器，请稍后再试」。
同一后端 `https://api.whereami.cn/api/health` curl 返回 200，网站（cijian-site）一切正常，
微信开发者工具里也一切正常——**只有真机坏**。

## 根因

三件事叠加：

1. 微信开发者工具 `project.config.json` / `project.private.config.json` 里 `"urlCheck": false`
   （「不校验合法域名」），本地开发**任何域名都能请求**，所以本地永远复现不了。
2. 真机（预览/体验版/正式版）**强制校验** request/uploadFile 合法域名：域名必须配在
   mp.weixin.qq.com 后台白名单，且**必须有 ICP 备案**（无备案域名加不进白名单）。
   `whereami.cn` 尚未 ICP 备案（docs/09 决策 #5 的已知上线阻塞项）。
3. 域名被拦时 `wx.request` 走 `fail` 回调（errMsg 形如 `request:fail url not in domain list`），
   cijian-mp 的 `utils/api.ts` 把它映射为 `status: 0`，`pages/print/print.ts` 对 status 0
   显示「连不上服务器」——**请求根本没到服务器**，与后端无关。

网站不受影响是因为浏览器只受 CORS 约束，没有微信域名白名单/备案这一层。

## 解法

- **立即验证（零改动）**：真机小程序右上角「…」→ 打开「开发调试」→ 重进小程序。
  调试模式跳过域名校验，可直接跑通口令登录/上传/打印全链路。
- **正式解法**（docs/09 §7 既定路线，无捷径）：
  ① 微信小程序备案（mp 平台内流程）；② whereami.cn 域名 ICP 备案（腾讯云流程，
  需内地机器挂接）；③ 通过后微信后台把 `https://api.whereami.cn` 配入
  request + uploadFile 合法域名。
- **备案期间兜底**：用已备案域名的子域反代到 43.159.141.66（docs/09 风险表已列）。

## 预防

- 「本地工具正常 + 真机异常」的小程序网络问题，第一反应查**域名校验层**
  （白名单 + 备案），不要先怀疑后端——`curl` 后端 200 时更是如此。
- 判别口径：`wx.request` fail 回调 / status 0 = 域名或网络被拦；HTTP 4xx/5xx = 后端问题。
  真机上开 vConsole 看 errMsg 可一锤定音。
- urlCheck:false 只许存在于开发期配置；上线检查清单里必须有「备案 + 白名单已配」一项。
- 相关：gotcha-cors-www-origin（浏览器侧 Origin 问题，与微信域名校验互不影响）
