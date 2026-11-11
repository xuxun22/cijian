# gotcha：whereami.com 是第三方网站，不是本项目域名（易与 whereami.cn 混淆）

> 2026-11-11 · 仓库：cijian-site · 类别：gotcha · 状态：现行

## 症状

要求把企业微信域名验证文件 `WW_verify_*.txt` 挂到
`http://whereami.com/WW_verify_*.txt`——但该域名**根本不是我们的**，
文件永远挂不上去；若在微信/企业微信后台表单里填了 .com，验证必然失败。

## 事实

- `whereami.com`：**第三方网站**（Cloudflare 上的 "WhereAmI.com" IP/定位工具，
  带 GA、ipv4/ipv6.whereami.com 子域），与本项目无关
- 我们的域名家族：`whereami.cn` / `www.whereami.cn`（Vercel 主域，裸域 308 → www）、
  `api.whereami.cn`（腾讯云）
- 全部仓库 grep `whereami.com` 零命中——任何需求里出现 .com 都是笔误

## 解法：根路径静态文件的挂法

验证文件放 `cijian-site/public/`（Astro 原样拷贝到 dist 根），
`npm run build` 过后 push main → Vercel 自动发布（~1 分钟），
`https://whereami.cn/<file>` 与 `https://www.whereami.cn/<file>` 均 200。

```bash
cp WW_verify_*.txt ~/work/cijian-site/public/
cd ~/work/cijian-site && npm run build && git add -A && git commit && git push
curl -sL https://whereami.cn/WW_verify_*.txt   # 验证内容回显
```

## 预防

- 在微信 MP / 企业微信等后台填域名时，**逐字核对是 .cn**；
  「验证不通过且查不出原因」第一反应先 `dig` / `curl` 确认域名归属
- 根路径静态文件（验证文件、robots、安全文件）一律走 cijian-site/public/，
  不要想着去服务器 Caddy 或 Vercel 后台单独配
