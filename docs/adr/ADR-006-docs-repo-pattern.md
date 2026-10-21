# ADR-006 · 文档仓与代码仓分离

日期：2026-10-21 · 状态：已接受（用户选定）

## 背景

用户明确要求：本仓（cijian）只负责存储**需求与设计文档**，不含具体代码；业务代码分散在独立 GitHub 仓，各自配置 CI/CD 部署。

## 决策

- **cijian = 文档仓**：需求（PRD）、架构、API 契约、数据模型、安全、部署手册、ADR；外加「仓库自动化」：`repos.yaml` + `scaffold/` 最小骨架 + `scripts/bootstrap-repos.sh`
- **代码仓**：cijian-site / cijian-api / cijian-agent，由 bootstrap 脚本按 repos.yaml 自动创建并推送初始内容
- 契约变更流程：先改本仓文档 → 三代码仓同步实现

## 关于 scaffold/ 的边界

经确认，本仓允许存放 scaffold 最小骨架：各仓 README、CI workflow、配置占位（package.json / pyproject.toml / .env.example）。**不含任何业务逻辑**；实现代码只存在于各代码仓。

## 后果

- ✅ 部署解耦：Vercel 只关联 site 仓，部署历史干净
- ✅ 文档有单一真相源，跨仓评审有依据
- ✅ 新地点/新组件 = repos.yaml 加一行 + 重跑 bootstrap
- ⚠️ 跨仓改动需要同时动两个仓（文档 + 代码）——以「里程碑回执」流程缓解（07 §里程碑回执）
