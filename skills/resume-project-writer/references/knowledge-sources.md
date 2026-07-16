# 前沿知识库与检索规则

## 飞书知识库入口

1. **从0到∞: 大语言模型知识面试一本通**
   - URL：`https://my.feishu.cn/wiki/M1Cew0iYaiH9jfkeD5XcXEuZn3d`
   - `space_id`：`7447505756926246913`
   - 根 `node_token`：`M1Cew0iYaiH9jfkeD5XcXEuZn3d`
   - 一级栏目包括大模型基础、架构、预训练、SFT、强化学习、应用、推理优化、评测、项目实践、经典面试题与论文笔记。
2. **从1到∞: 多模态大模型知识面试一本通**
   - URL：`https://scnajei2ds6y.feishu.cn/wiki/XdeBwWZi7iSxMJkXh6qcCmPWnqZ`
   - `space_id`：`7475697798785024003`
   - 根 `node_token`：`XdeBwWZi7iSxMJkXh6qcCmPWnqZ`
   - 一级栏目包括基础技术、模型、速通面试与代码实践。

这两个入口用于检索 LLM、Agent、RAG、SFT、RL/RLVR、Embedding、推理与工程优化相关论文、概念和常见面试追问。

## 何时检索

- 用户要求增加前沿性、论文依据、技术选型比较或引用。
- 某个项目机制需要更严谨的原理解释。
- 生成高级面试追问，尤其是算法对比、失败模式、假设与局限。
- 用户提出的新问题超出现有项目文档的知识覆盖。

不要为了显得前沿而强行检索或引用。简历短文本通常不放论文名，论文更适合用于 QA 和选型论证。

## lark-cli 流程

1. 先检查用户身份：`lark-cli auth status --json --verify`。
2. 优先复用上方已验证的 `space_id` 和根 `node_token`；若入口变化，再执行 `lark-cli wiki +node-get --node-token "<URL>" --as user --format json`。
3. 列子节点：`lark-cli wiki +node-list --space-id <space_id> --parent-node-token <node_token> --page-all --as user --format json`。
4. 根据标题定位相关页面，再用 `lark-cli docs +fetch --doc "<URL或token>" --scope outline` 或 `--scope keyword` 局部读取。
5. 若缺少 `wiki:wiki:readonly` / `wiki:node:read` 等 scope，按 `lark-shared` 的 split-flow 发起最小权限授权；不要假装已完成全库检索。

## 检索策略

- 用用户问题中的核心方法、别名和对比方法作为关键词，例如 `GSPO|GRPO|sequence policy optimization`。
- 先看标题和目录，再读目标章节，避免整库全文拉取。
- 同一结论优先寻找原论文或多个独立页面交叉验证。
- 记录来源页面标题和 URL，回答中需要引用时明确来源。

## 引用纪律

- 区分论文结论、知识库作者观点和当前项目推演。
- 不把尚未核实的年份、会议、指标或公式写进简历。
- 论文方法与项目实现不完全一致时，使用“参考其思路”而不是宣称直接采用。
- 新方法随时间变化较快；涉及“最新”“当前 SOTA”时重新检索，不依赖 skill 内静态记忆。
