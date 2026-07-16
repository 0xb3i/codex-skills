# 完整项目与面试 QA 工作流

## 项目扩写

从简短描述扩写时，按以下顺序补齐：

1. 业务场景与用户问题。
2. 系统真实输入、输出、工具和运行循环。
3. 数据来源与真正的泛化单位。
4. 冷启动或训练数据如何构造与筛选。
5. 任务特有的 reward、loss 或验证机制。
6. 长上下文、工具错误、吞吐、成本等工程约束。
7. Benchmark、线上回流与局限。

扩写不是自由编造。对用户未提供的细节：

- 优先写成可自洽的实现方案或待确认项。
- 不新增内部专有数字。
- 若某项会改变架构事实，先确认或明确标注假设。

## QA 生成维度

每个项目至少覆盖：

- 背景：为什么现有方案不足？
- 数据：规模、来源、标注、偏差、去重、难例和审核。
- 方法：为什么选该模型/算法？核心机制是什么？
- 验证：指标如何定义？消融和反例是什么？
- 工程：延迟、显存、轨迹长度、工具失败如何处理？
- 质疑：是否数据泄漏、模板同质化、Reward Hacking、Groundtruth 不完整？
- 局限：哪些假设不成立时会失败？下一步怎么做？

## 吸收面试官新问题

1. 先判断问题是否暴露正文叙事错误，而非只补一个答案。
2. 用一两句给出核心判断，再展开实现机制。
3. 把问题拆成可复述的 QA；一个问题包含两个独立矛盾时拆成两条。
4. 插入对应章节，而非全部堆在文末。
5. 检查新增答案是否与摘要、指标或其他 QA 冲突。

## 沙箱与 RLVR 常见追问口径

### 推荐的数据生产主线

优先采用“线上发现 + 反向合成”，不要把人工预设长轨迹作为规模化方案：

1. 从线上 Query 与可回放快照分层采样真实 Case。
2. 让强 Teacher Agent 多次 rollout，高召回发现候选根因与证据；专家审核压缩后的候选，而非逐 token 轨迹。
3. 将确认结果抽象为 Root-Cause Card：前置条件、外生变量、传播图、protected variables、经验参数分布、可观测证据、混淆根因和兼容关系。
4. 从真实快照做 counterfactual intervention，通过指标 DAG、业务公式与 residual bootstrap 生成完整环境；intervention ledger 自动产生 Groundtruth。
5. 从真实基线、连续参数、多根因组合、干扰波动和证据可观测性扩展环境状态；不规定唯一 trajectory。
6. 用环境一致性、反事实恢复、可识别性、分布相似性、泄漏探针和难度成功率做质量门禁。
7. SFT 与 RL 共享 Case/沙箱/Verifier；SFT 使用筛选后的高质量轨迹，RL 使用当前策略 on-policy rollout。

公开工作可用于严谨论证：AgentGen（先环境后任务）、ToolSandbox（stateful 任意轨迹验证）、AgentGym（环境 + 轨迹 + 自演化）、WebRL（失败驱动课程）、RAGEN（多样初始状态与交互粒度）。只写与项目设计真实对应的启发，不宣称完全复现论文。

### 如何批量构造逻辑自洽的数据？

优先采用真实快照作为基线，对少量外生变量做参数化干预；用指标 DAG 重算派生指标；通过公式一致性、分项守恒、上下界、变化方向、时间连续性和反事实隔离做自动校验，不合格 Case 拒绝重采样。

### 固定因果模板是否导致同质化？

模板只约束因果合法性。多样性来自不同真实基线、连续扰动参数、多根因组合、干扰变量、异常时间窗和证据可观测性。Groundtruth 不规定唯一 trajectory，多条有效调查路径都可通过 Verifier。

### 人工如何审核大规模 Case 与轨迹？

审核根因模板、约束规则和高风险 Case，而非逐条轨迹。实例先自动验证，trajectory 由执行回放、根因匹配和 evidence 校验；人工对新模板、多根因、临界样本和自动/人工评分冲突样本分层抽检。

## 长轨迹 Agent SFT 推荐口径

1. 用 SFT 将策略带入 RL 可学习区间：工具调用可执行、中等难度 Case 有部分成功率、组内 rollout reward 有方差。
2. 以 Full-Trajectory 为主，保留跨步骤状态依赖；将同一轨迹在关键决策点展开为 Prefix-to-Next-Action 或 Prefix-to-Suffix 样本，提高监督利用率。
3. 不把 A/B/C/D 片段脱离前缀独立训练。超长轨迹在 turn 边界切片，并携带 Query、Schema、已确认/排除假设、evidence 和剩余目标的状态摘要。
4. 使用 assistant-only loss：system、Query 和 tool observation 作为输入但 mask；对有效 assistant token 做长度 normalization，必要时提高 tool call 与 final answer 权重。
5. 两阶段训练应表述为“显式 CoT 轨迹 → Action + Answer SFT”，而不是只训练 final answer；后者会遗忘工具动作。
6. 鲁棒性增强必须可执行：Tool Dropout、真实 Schema 版本、错误注入、observation 扰动、Tool Distractor 和 Availability Mask。禁止只在文本里随机改必填参数名。
7. 错误轨迹不直接作为正标签；用于 failure mining、对抗 Case，或将错误 action mask 后监督恢复动作。

可用于严谨论证的公开工作：AgentTuning（轨迹 + 通用指令混训）、Agent-FLAN（能力拆分与负样本）、ToolLLM（真实 API 与路径搜索）、ToolACE（数据合成与双层验证）。

## GSPO 与 Reward 推荐口径

### 算法选型

- PPO：能用 Critic/GAE 做细粒度优势，但长工具状态下 Value Model 难训且工程成本高。
- DPO/RFT：适合离线轨迹，不能充分利用当前策略的 on-policy 探索和负优势。
- GRPO：critic-free 且适合 RLVR，但 token-level importance ratio 与 trajectory-level reward 粒度不一致。
- GSPO：使用长度归一化 sequence-level ratio 和 sequence clipping，与整条 Agent 轨迹的 outcome reward 对齐。不要宣称它自动解决 step-level credit assignment。

### Reward 设计

采用层级门禁，不做无条件加权：

1. 工具可执行、答案 Schema、evidence 真实性作为硬门禁。
2. 根因集合 F1 作为主奖励，抑制万金油式罗列。
3. 定位深度和 evidence coverage 只在根因匹配后生效。
4. 步数、重复调用和 token 成本只在正确性达到门槛后生效，避免过早停止。
5. 各分量先归一化与 clipping；权重通过 Proxy Reward 与独立 Gold Benchmark 的排序一致性确定。

### 稳定性

- 过滤全同 Reward 组，并按成功率做难度课程；全错回流 SFT，全对降低采样权重。
- 使用较小 LR、有限更新 epoch、sequence clip、reward/advantage/gradient clipping。
- 监控 Gold success、Reward 分量、KL、sequence ratio、entropy、clip fraction、grad norm、轨迹长度和 invalid call rate。
- Reward 上升但 Gold 指标下降视为 Reward Hacking 信号，审计高分轨迹并回滚。
- 保证 rollout 与训练的 policy version、tokenizer、chat template、tool schema、assistant mask 和 logprob 计算一致。

可引用：GSPO 原论文（sequence-level optimization）、GRPO/DAPO 工程经验、Multi-Step Agentic RL 的 credit assignment 局限和 Reward Hacking 的条件奖励实践。

## 回答风格

- 先给结论，再给 2–4 个机制点。
- 明确哪些是项目事实、哪些是合理设计口径。
- 遇到强质疑时承认边界，不用绝对化语言掩盖风险。
- 答案应能在 60–120 秒内口述；数学细节另做深入追问。
