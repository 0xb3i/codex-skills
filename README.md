# Codex Skills

这个仓库用于在不同电脑之间同步个人 Codex skills。仓库里的 skills 放在 `skills/<skill-name>` 目录下，每个目录通常包含一个 `SKILL.md` 和该 skill 需要的引用文件、脚本或资源。

## 同步到另一台电脑

首次安装：

```bash
git clone https://github.com/0xb3i/codex-skills.git ~/codex-skills
mkdir -p ~/.codex/skills
rsync -a --delete --exclude .git ~/codex-skills/skills/ ~/.codex/skills/
```

之后更新：

```bash
git -C ~/codex-skills pull --ff-only
rsync -a --delete --exclude .git ~/codex-skills/skills/ ~/.codex/skills/
```

如果在某台电脑上修改了 skill：

```bash
rsync -a --delete ~/.codex/skills/<skill-name>/ ~/codex-skills/skills/<skill-name>/
git -C ~/codex-skills add skills/<skill-name>
git -C ~/codex-skills commit -m "update <skill-name>"
git -C ~/codex-skills push
```

## Skills 清单

| Skill | 用途 |
| --- | --- |
| `agent-browser` | 浏览器自动化。用于打开网页、填写表单、点击按钮、截图、抓取数据、测试 Web 应用，也可用于部分 Electron 桌面应用自动化。 |
| `argos` | 通过 Argos CLI 诊断服务问题、分析报警、追踪请求、查看可用性、延迟、错误率、日志和配置。 |
| `argos-ppe-debug` | 诊断 `bytedance.agent.ecom_affiliate` PPE 测试日志，重点排查 Planner、Executor、MCP tool、候选商品和空召回等问题。 |
| `argos-query` | 按 PSM、关键字、时间范围或 logID 查询 Argos 服务日志，并汇总分析错误日志。 |
| `argos-tools` | 运行 Argos 日志工具并自动保存输出，适合需要调用 `log.*` 类工具的排查任务。 |
| `ask-feishu` | 查询公司内部 Feishu/Lark 信息源，包括同事对话、群消息、内部文档、知识库、会议纪要和项目上下文。 |
| `bytefaas-release` | 自动化 ByteFaaS 国际电商联盟 Agent 函数编译与发版流程，包括 Bits 编译、审批、镜像解析、Canary、切镜像和工单轮询。 |
| `canary-profile-browser` | 控制本机 Chrome Canary 用户 Profile，用于复用登录态访问网页、检查 DOM、点击输入、抓取数据和调试浏览器扩展。 |
| `data-organizer` | 整理混乱的数据目录或工作区，进行归档、重命名、分组、扁平化、合并索引和清理临时文件。 |
| `design-md` | 创建和维护 `DESIGN.md`，集中记录设计方向、设计 token 和视觉规则。 |
| `docx-template-fill` | 填写现有 Word `.docx` 模板、表单、访谈模板或问卷，同时尽量保留原始版式、字体、边框和页面布局。 |
| `focused-output` | 优化面向用户的回答、解释、摘要、建议、分析、状态更新、代码审查和最终回复。 |
| `hatch-pet` | 创建、修复、验证并打包 Codex v2 动态宠物，包括角色图、品牌视觉、九行动画、方向帧和 QA 产物。 |
| `meego-fill-project` | 在 Meego/Meegle 中填写项目记录，定位父工作项，创建或完成周度子任务，并写入实际 PD、排期、负责人等字段。 |
| `mistake-notebook` | 在发现反复出错、用户纠正、隐藏坑点或可能复发的问题时，判断并更新全局或项目级 `AGENTS.md`。 |
| `modelhub-api-call` | 编写、修改、审查或运行内部 ModelHub API / AzureOpenAI 兼容网关调用代码，覆盖批量调用、重试、并发和配置。 |
| `playwright` | 通过 Playwright 从终端自动化真实浏览器，适合页面导航、表单填写、截图、数据提取和 UI 流程调试。 |
| `polishing-feishu-docs` | 将粗糙的 Feishu/Lark 文档材料润色为更适合汇报的文档，包含结构调整、结论提炼、表格、标注和流程图建议。 |
| `self-improve-skills` | 复盘并改进已有 Codex skill，在发现遗漏触发、失败路径、边界情况或过时说明时做最小必要更新。 |
| `sync-codex-skills` | 在本机与开发机/服务器之间同步单个 Codex skill 的旧工作流；保留在仓库中作为现有 skill 备份。 |
| `taste-skill` | 面向落地页、作品集和 redesign 的前端审美 skill，用于避免模板感，做设计审计并交付更精致的界面。 |
| `trae-codex-maintenance` | 诊断和修复 Trae CN AI、本地 Codex/Claude 扩展、远程 SSH Codex 扩展的侧边栏、插件、CLI 路径和加载问题。 |
| `weekly-report` | 将中文周报素材、进展记录、指标、实验结果、风险和计划整理成面向上级的精炼周报。 |

