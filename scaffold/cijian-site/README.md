# cijian-site · 此间站点

**此间**（whereami.cn）的 Astro 站点：公开内容（所学 / 生活 / 关于）+ 登录后的打印工作台。

需求、架构与接口契约见文档仓 [`cijian`](https://github.com/xuxun22/cijian)（`docs/`）。

## 开发

```bash
npm install
npm run dev       # http://localhost:4321
npm run build     # 构建到 dist/
```

## 部署

Vercel 关联本仓库即可：push `main` 自动部署，PR 自动预览。接线步骤见文档仓 `docs/07-deploy-cicd.md`。

## 里程碑

- [x] 公开内容（所学 / 生活 / 关于 / RSS）
- [ ] M1 登录态（单口令 + JWT）
- [ ] M2 打印工作台（上传 / 选地点 / 提交）
- [ ] M4 任务状态页
