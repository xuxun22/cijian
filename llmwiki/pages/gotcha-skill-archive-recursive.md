# gotcha：归档技能照样被加载（opencode 递归扫描 skills 目录）

> 更新：2026-11-15 · 仓库：cijian-agent · 类别：gotcha · 状态：已修

## 症状

把不再使用的技能「删掉」（移到 `family/assistant/skills/.archive/<id>-<ts>/`）后，
模型仍然能用它：让模型列一下当前可用技能，输出里照样出现 `family-dead-20260101`。

## 根因

opencode 的 `skills: [dir]` 是**递归扫描**：只要某个子目录下有 `SKILL.md`，不管层级多深、
目录名是不是以 `.` 开头，都会注册成一个技能。实测用最小复现验证：

```bash
mkdir -p /tmp/probe/skills/family-live /tmp/probe/skills/.archive/family-dead-20260101
# 各写一个 SKILL.md，opencode.json 里 "skills": ["/tmp/probe/skills"]
opencode run --standalone --format json --auto "列出你能用的技能"
# → 同时出现 family-live 和 family-dead-20260101
```

而「本地文件删除」又违背了「只归档、可恢复」的设计。

## 解法

归档目录放到 **skills 同级**，不再嵌在 skills 里面：

```
family/assistant/skills/<id>/SKILL.md
family/assistant/skills-archive/<id>-<时间戳>/SKILL.md
```

- `cijian_agent/ai/skills.py: SkillStore.delete()` 用 `self.dir.parent / "skills-archive"`；
- `AiWorker._sync_skills()` 提交时把两个路径一起 `git add`（目录不存在就跳过）；
- `skill_restore()` 从 blobs 里取回正文写回 skills；若最近一条是 `create`，撤销新建 = 归档。

## 预防

- 任何「放在 skills 目录里但不希望被加载」的东西都不能放进去——递归扫描没有例外。
- 新增技能生命周期动作时，先问一句：这个目录会不会被 `skills:` 扫到？
- 回归：`python3 -m unittest discover -s tests`（`test_delete_is_archive`、`test_restore_undo_create_archives`）。
