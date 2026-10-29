# gotcha：Vercel 主域是 www，CORS 白名单只写了裸域 → 前端全被拦

> 2026-10-24 · 仓库：cijian-api / cijian-site · 类别：gotcha · 状态：现行

## 症状

打印工作台登录报「连不上此间后端：请检查 api 地址配置」，console 显示 CORS error。
但 `curl` 直接预检 `Origin: https://whereami.cn` 一切正常——**API 明明没问题**。

## 根因

Vercel 项目添加 `whereami.cn` 时把 **`www.whereami.cn` 设为主域**，裸域 308 跳转到 www。
于是浏览器里页面的真实 Origin 是 **`https://www.whereami.cn`**，
而 API 的 CORS 白名单只放了 `https://whereami.cn`（裸域）——来源不匹配，响应缺 ACAO 头。

## 解法

API 的 CORS 来源判定改为**正则放行整个域家族**（cijian-api/src/app.ts）：

```ts
/^https:\/\/([\w-]+\.)*whereami\.cn$/.test(origin)   // 裸域 + 任意子域（www 等）
|| /^https:\/\/[\w-]+\.vercel\.app$/.test(origin)    // Vercel 预览/部署域
|| /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/    // 本地开发
```

## 预防

- 配置自定义域名时，**先看 Vercel 实际把哪个域名设为主域**（Settings → Domains 里标注
  production 的那个），浏览器地址栏是什么 Origin 就放行什么——以实测为准，不靠猜
- 诊断顺序：console 的 CORS 报错会写明 Origin；先 `curl -X OPTIONS` 该 Origin 复现，
  再对比白名单，最后改代码
- 相关：api.whereami.cn 的合法域名校验（小程序）用的是域名备案，与 CORS 互不影响
