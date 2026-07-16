---
name: self-improve-skills
description: 复盘并改进已有 Codex Skill。Use when any Skill execution reveals a failed path, missed issue pointed out by the user, user correction, missing context, edge case, repeated workaround, simpler implementation path, stale instruction, poor trigger wording, a missed trigger for another Skill/AGENTS update, or when the user asks to update/evolve/harden/improve a Skill. Record evidence, dedupe learnings, apply necessary direct minimal patches to SKILL.md/references/scripts by default, and record candidates only for potential, long-term, uncertain, cross-skill, or high-risk improvements.
---

# Self Improve Skills

## 目标

把真实使用 Skill 时发现的问题，沉淀成目标 Skill 的最小、可验证改进。必要且直接影响目标 Skill 成功率、正确性或效率的问题默认直接改；潜在、长期、不确定或高风险优化才记录候选。

## 输入

先确认四件事：

- 目标 Skill 名称和路径。
- 触发原因：失败路径、用户指出 agent 没注意到的问题、用户纠正、边缘 case、重复绕路、更简单路径、缺失信息、触发不准。
- 证据：本轮任务中的具体现象、命令输出、错误、用户补充、成功替代路径。
- 期望结果：记录候选、直接补丁、只给建议，或用户明确要求的范围。

信息不足时，先从当前对话、目标 Skill 文件、相关脚本和引用文件里找；只有会误改时才问用户。

## 工作流

1. 读取目标 Skill 的 `SKILL.md`，只读取和问题相关的 `references/` 或 `scripts/`。
2. 判断根因在目标 Skill 的哪个层级：触发描述、主流程、边界处理、命令/API、验证步骤、脚本实现。
3. 用户指出 agent 漏掉的前置步骤、恢复顺序或判断条件时，先判断是否可泛化；可泛化就补进目标 Skill，不可泛化就只完成当前任务。
4. 用户指出“本应触发某个 Skill、AGENTS 写入或错题沉淀，但 agent 没触发”时，视为目标 Skill 的触发失败；即使现有文字看似覆盖，也必须修改触发描述或工作流，让下次更容易触发，不要以“规则已经足够，只是本次没执行”作为结论。
5. 先找现有规则或重复段落；能改一句就不要新增一节，能改引用文件就不要撑大 `SKILL.md`。
6. 按 `references/patch-policy.md` 判断：直接必要改进默认自动修改；潜在或高风险优化只记录候选。
7. 写入最小补丁；只有不应当下自动修改时，才记录候选改进到目标 Skill 目录下的 `improvement-candidates.md`，并告诉用户是否值得现在迭代。
8. 验证：运行 Skill 校验；改脚本时运行最小可执行检查；复杂流程可用子 agent 做一次 forward-test。
9. 最终用中文说明：改了什么、跳过了什么、下次什么时候再扩展。

## 候选记录格式

当问题只是潜在影响、长期优化、不确定泛化，或涉及安全/权限/生产/跨 Skill 边界时，把记录追加到目标 Skill 的 `improvement-candidates.md`：

```md
## YYYY-MM-DD - 简短标题

- 类型：failure | correction | edge_case | simpler_path | missing_context | trigger
- 状态：candidate | patched | rejected
- 证据：本轮可复查的具体现象。
- 根因：目标 Skill 当前缺少或误导的地方。
- 建议补丁：一句话描述最小修改。
- 验证方式：如何确认改动有效。
```

不要记录密钥、token、完整内部配置、个人隐私、无法脱敏的日志。需要保留证据时先脱敏。

## 输出规则

- 默认中文输出，除非用户明确要求英文。
- 优先直接完成必要补丁；不要只停在方案，也不要把明确问题推给用户决定。
- 每次只解决本轮证据支持的问题；不要顺手重构目标 Skill。
- 保持 Skill 简短。新增内容超过约 30 行时，优先放入 `references/` 并在 `SKILL.md` 中用一句话导航。
