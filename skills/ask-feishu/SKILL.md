---
name: ask-feishu
description: "Use when you need to query internal company sources: conversations with colleagues, group chat messages, internal docs, wiki/knowledge-base pages, meeting/minutes content, project context, or other private Feishu/Lark-accessible information. Also use after reading a single internal doc/wiki when the user asks what can be done, whether a company tool/API exists, how an internal workflow works, or what parts an agent can help automate; ask Feishu to discover related docs, APIs, permissions, and caveats before answering. Ask the official Feishu Knowledge Q&A bot through ask.feishu.cn. Also use when the user mentions Ask Feishu, 飞书知识问答, or ask_feishu. Do not use Lark IM/iDA bots as a substitute."
allowed-tools: Bash(scripts/ask_feishu:*), Bash(scripts/ask_feishu_setup:*), Bash(test:*), Bash(node:*)
---

# ask-feishu

通过网页版 `https://ask.feishu.cn/` 调用飞书官方知识问答。这个 skill 是桥接，不重造 RAG，也不把飞书聊天/文档同步到本地。

## 安全边界

- **不要用飞书 IM bot / iDA bot 代替**。它们不是飞书官方知识问答。
- **不要读取或拷贝用户当前浏览器 cookie/profile**。
- 登录态只允许保存在私密目录，默认：`~/.local/share/ask_feishu/storage_state.json`。
- 登录态文件绝不能放进本 skill、仓库、`outputs/`、日志或对话正文。
- 日常问答使用独立 headless Chrome，不操作用户当前浏览器窗口。

## 命令

Skill 目录固定为：

```bash
ASK_FEISHU_SKILL="$HOME/.codex/skills/ask-feishu"
```

首次或登录态失效时：

```bash
"$ASK_FEISHU_SKILL/scripts/ask_feishu_setup"
```

它会打开一个独立 Chrome 窗口。用户完成登录并看到飞书知识问答页面后，回到终端按 Enter，脚本会保存登录态。

提问：

```bash
"$ASK_FEISHU_SKILL/scripts/ask_feishu" "问题"
```

结构化输出：

```bash
"$ASK_FEISHU_SKILL/scripts/ask_feishu" "问题" --json
```

调试页面结构时显示浏览器：

```bash
"$ASK_FEISHU_SKILL/scripts/ask_feishu" "问题" --headed --json
```

## 工作流

1. 用户给出内部文档/知识库链接并追问“能不能做 / 能帮哪些 / 有没有 API / 怎么自动化 / 权限限制”时，先读用户给的源文档，再用 `scripts/ask_feishu "问题" --json` 查询相关内部资料补全能力边界。
2. 用户要问飞书知识问答时，直接运行 `scripts/ask_feishu "问题" --json`。
3. 对需要可靠结论、细节核验或可追溯出处的回答，先使用 `answer` 和 `sources` 得到候选结论，再递归打开可访问引用源夯实结果：Doc/Wiki 链接用 `lark-doc` 或 `lark-wiki`，表格/多维表格用 `lark-sheets`/`lark-base`，妙记/纪要用 `lark-minutes`/`lark-note`，聊天线索用 `lark-im`。不要只复述知识问答摘要；把二次读取到的源内容合并、校验后再回答用户。
4. 如果 `sources` 没有 URL，但正文或页面引用区出现文档标题、群聊、会议、人员或时间线索，用对应 lark CLI 搜索/读取这些线索；无法打开时明确说明该来源未能二次验证。
5. 如果报缺少登录态，运行 `scripts/ask_feishu_setup`，让用户在独立窗口完成登录并按 Enter 保存。
6. 如果报找不到输入框，优先判断登录态过期；重新 setup。
7. 如果多链接或多子问题查询超时但返回了部分内容，先保留部分答案，再把问题拆成单篇文档、单个能力点或单个命令参数继续问；不要反复用同一个大问题重试。
8. 如果登录态有效但 DOM 变化，使用环境变量临时指定选择器：

```bash
ASK_FEISHU_INPUT_SELECTOR='[contenteditable="true"]' \
ASK_FEISHU_SUBMIT_SELECTOR='button[aria-label="发送"]' \
ASK_FEISHU_ANSWER_SELECTOR='.answer-container' \
"$ASK_FEISHU_SKILL/scripts/ask_feishu" "问题" --json
```

## 实现细节

- 使用 bundled Node + Playwright，默认通过系统 Chrome channel 运行，避免下载 Playwright 自带浏览器。
- 输入富文本编辑器时用键盘逐字输入，不用直接 fill。
- 提交后按回答内容稳定判断完成，避免固定 sleep 截断流式回答。
- 默认会抽取页面里的可见链接作为 `sources`，但飞书的私聊/纪要等非链接来源可能只能在正文里体现。

## 验证

最小自检：

```bash
"$ASK_FEISHU_SKILL/scripts/ask_feishu" --self-test
```

真实 smoke test：

```bash
"$ASK_FEISHU_SKILL/scripts/ask_feishu" "测试一下，请只回答：ask_feishu smoke ok" --json --timeout 60000
```
