# 参与贡献

欢迎修正规则、补充使用场景或改进脚本。提交问题时，提供具体任务、实际表现和期望结果；提交改动时，说明解决了什么问题及验证方式。

## 修改技能

- 技能放在 `skills/<skill-name>/`，入口为 `SKILL.md`；脚本、引用和评测案例放在对应技能目录中。
- 根据真实使用证据修改规则，保留任务范围和已有行为。新增技能先通过 Issue 说明用途与现有技能的区别。
- 公开内容使用构造案例，不包含凭据、个人资料、内部文档链接或真实业务数据。
- 全局约定同步到仓库根目录的 `AGENTS.md`，保留跨任务原则，内部业务定位信息不公开。
- 用户本地的激活技能与公开副本分别维护；同步后检查脱敏内容，缓存和临时产物不提交。

## 验证与提交

```bash
python3 -m pip install PyYAML markdown-it-py
python3 skills/self-improve-skills/scripts/audit_skills.py --root skills --no-config
python3 skills/self-improve-skills/scripts/skill_evals.py validate \
  skills/mistake-notebook/evals/cases.json \
  skills/self-improve-skills/evals/cases.json
git diff --check
```

上述检查使用 Python 3.11 或更新版本，不调用模型。脚本改动还需验证受影响的输入、输出和异常路径。

Pull Request 保持单一主题，在描述中列出改动与验证结果。自动检查会核验技能元数据、本地资源引用和评测集结构。
