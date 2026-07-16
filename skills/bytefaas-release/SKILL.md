---
name: "bytefaas-release"
description: "ByteFaaS 国际电商联盟 Agent 函数自动编译与发版（US-TTP / faas-us-ttp / 99sxastl PPE，svqk5ou9 online/prod）。完整工作流：运行/复用内置 Bits 编译脚本（pipeline 1168542993666 / space 201141148930；master 分支复用自动触发的 active run，不新建 run）→自动审批 TTP 同步节点并持续轮询→只从 ICM镜像构建TTP 产物解析 TTP 镜像版本号→启动 Canary→切镜像版本→保存并校验→提工单（审批人 NOC）→脚本轮询→全机房灰度自动点节点内『全量』→完成后通知用户。当用户说『发版』『发布镜像 X.X.X.X』『编译并发版』『编译完发版』『提发版工单』『编译 debug_ppe』『编译 short 分支』『发到 brandon 那个 ppe』『master 发 online/prod』时调用；如果用户只要求编译，也必须等 TTP 同步/ICM镜像构建TTP 完成并解析出 TTP 镜像版本后才汇报完成，不能把仅 SCM 构建成功当作编译完成。"
---

# ByteFaaS Release Skill

为「国际电商联盟 Agent」（PSM: `bytedance.agent.ecom_affiliate`，ServiceID: `99sxastl`）做 ByteFaaS 自动发版。

## 输入参数

| 参数 | 必填 | 默认值 | 示例 | 说明 |
|---|---|---|---|---|
| `version_desc` | 发版时必填 | — | `测试` / `修复 xxx 问题` | 版本描述。只编译不发版时不需要 |
| `branch` | 否 | `debug_ppe` | `debug_ppe` / `feature_xxx` / `short` | 内置 Bits 编译脚本要编译的分支。用户没说就用默认 |
| `image_version` | 否 | 由 bits 产物自动解析 | `2.0.0.50` | 要发布的镜像版本号。**正常不需要用户提供**，由内置 Bits 编译脚本跑完后从 ICM 产物字段解析；只有用户明确说『跳过编译』『直接用现成镜像 X.X.X.X 发版』时才让用户给 |
| `ppe` | 否 | `ppe_product_selection_niubei` | `ppe_product_selection_niubei` / `brandon` | PPE 环境名（页面顶部 `US-TTP / ppe / <ppe_name>`） |
| `target_env` | 否 | `ppe` | `ppe` / `online` / `prod` | 用户说 online/prod 时发线上函数 `svqk5ou9`；否则发 PPE 函数 `99sxastl` |

如果用户要求发版但没提供 `version_desc`，先问清楚再开始执行。只编译请求不需要 `version_desc`。`branch` / `ppe` 用户没说就直接用默认值，不要追问。

### 分支别名

- `short` / `short 分支` / `short branch` 统一映射为 `short-circuit-generator`
- 传给 Bits 编译脚本前，先把上述别名规范化为真实分支名 `short-circuit-generator`

### PPE 别名

- `brandon` / `brandon 那个 ppe` / `brandon ppe` 统一映射为 `ppe_ppe_creator_agent_brandon`
- 打开发布页面后，若用户给的是上述别名，先规范化成真实 PPE 名，再在页面顶部 PPE 下拉里切到 `ppe_ppe_creator_agent_brandon`

`image_version` 默认通过内置 Bits 编译脚本拿到：非 `master` 分支用 `branch` 触发 bits 流水线 `1168542993666`；`master` 分支**不要触发新 run**，因为系统会在 master 更新后自动发起 ICM 编译，脚本会先复用当前 active run 并审批 TTP 同步节点。等编译完成后，**只读取 `ICM镜像构建TTP` job 的 `output.image_version` / `build_status_list[].image_version`**（不要从全局 artifacts 取，避免拿到 `ICM镜像构建ROW` 的版本号），形如 `2.0.0.59`。如果用户显式说『跳过编译，直接发 X.X.X.X』，跳过步骤 0.5，直接拿用户给的 `image_version`。

## 固定参数（不要每次问用户）

- PPE 函数页 URL: `https://cloud-ttp-us.bytedance.net/faas/function/99sxastl/code?region=us-ttp&cluster=faas-us-ttp`
- online/prod 函数页 URL: `https://cloud-ttp-us.bytedance.net/faas/function/svqk5ou9/code?region=us-ttp&cluster=faas-us-ttp`
- 代码版本: `$Latest`
- 审批人: 选下拉里第三个 `TikTok USDS JV-US Tech and Product-Eng Support-NOC`
- 发布方式: 系统模板 / 灰度 10%
- 目标机房: 全勾（默认）
- Canary 连接: 先使用 `canary-profile-browser` skill 的 `connect-canary-profile.sh`
- CDP 端口: `9223`（按 `canary-profile-browser` 默认；如需沿用旧会话，可显式传 `PORT` / `CDP_PORT`）
- 轮询脚本: `/Users/bytedance/.codex/skills/bytefaas-release/scripts/watch-ticket.sh`
- Bits 编译脚本: `/Users/bytedance/.codex/skills/bytefaas-release/scripts/bits-auto-compile.sh`（pipeline `1168542993666` / space `201141148930`）
- 镜像版本解析脚本: `/Users/bytedance/.codex/skills/bytefaas-release/scripts/parse-bits-image-version.sh`
- agent-browser HOME workaround: 必须设 `HOME` 到一个独立可写目录（推荐 `/tmp/ab-home-bytefaas`，首次用前 `mkdir -p /tmp/ab-home-bytefaas`）。如果当前工作区可写，也可以用 `<workspace>/.ab-home`。

## 浏览器使用强约束（必须遵守）

**只允许使用 `canary-profile-browser` 连接的 Canary（默认 `agent-browser --cdp 9223`）操作页面。严禁使用 Codex in-app Browser、普通 Chrome、`browser`/`integrated_browser` MCP 或其他未连接到目标 CDP 端口的浏览器实例。**

- 所有页面交互（打开 URL、snapshot、click、type、wait 等）都必须通过 Canary 的 CDP 端口（默认 `9223`）操作。
- 严禁调用 in-app Browser / `browser` / `integrated_browser` 系列工具（`browser_navigate` / `browser_snapshot` / `browser_click` 等）。
- 严禁让 Codex 自己启动新的内嵌浏览器或普通 Chrome 去打开 ByteFaaS 控制台、SSO 页面或任何工单页。
- 如果目标 CDP 端口不可用，必须先按 `canary-profile-browser` 运行 `PORT=<port> /Users/bytedance/.codex/skills/canary-profile-browser/scripts/connect-canary-profile.sh`，**不要 fallback 到内嵌浏览器**。
- 如果打开 ByteFaaS 后落到 SSO 登录页，不要尝试复制 profile、绕过登录或索要密码；向用户报告 `SSO pending`，然后每隔 10-15 秒用当前 Canary 轮询 URL/title/snapshot。用户完成登录并跳回 ByteFaaS 后，直接从当前页面继续发版。
- 标准命令形式（每条都必须前置独立可写 `HOME`，推荐 `/tmp/ab-home-bytefaas`）：
  ```bash
  HOME=/tmp/ab-home-bytefaas agent-browser --cdp 9223 open "<url>"
  HOME=/tmp/ab-home-bytefaas agent-browser --cdp 9223 snapshot -i
  HOME=/tmp/ab-home-bytefaas agent-browser --cdp 9223 click @e<N>
  HOME=/tmp/ab-home-bytefaas agent-browser --cdp 9223 fill  @e<N> "<text>"
  HOME=/tmp/ab-home-bytefaas agent-browser --cdp 9223 wait  <ms>
  HOME=/tmp/ab-home-bytefaas agent-browser --cdp 9223 get url
  ```
- Canary profile 在 `/Users/bytedance/chrome-agent-profile`；登录态过期时按上面的 `SSO pending` 处理。

## 执行步骤

### 步骤 0 — 确认参数 + 连接 Canary
1. 如果用户只要求编译，跳过 Canary，直接执行步骤 0.5；只有确认 TTP 同步/`ICM镜像构建TTP` 完成并解析出 TTP 镜像版本后才能停止。否则校验拿到 `version_desc`，缺就问用户。`branch` / `ppe` 没说用默认值，不要追问。`image_version` 默认走步骤 0.5 自动获取
2. 使用 `canary-profile-browser` 连接 Canary（幂等）：
   ```bash
   PORT=9223 /Users/bytedance/.codex/skills/canary-profile-browser/scripts/connect-canary-profile.sh
   ```
3. 验证 CDP 可达：
   ```bash
   curl -sf http://localhost:9223/json/version
   ```
4. 准备 agent-browser 工作目录：
   ```bash
   mkdir -p /tmp/ab-home-bytefaas
   ```
5. 如果 ByteFaaS 页面跳到 SSO，报告 `SSO pending` 并轮询当前 Canary；用户登录完成后继续，不要改用其他浏览器或复制 profile。

### 步骤 0.5 — 运行内置 Bits 编译并解析镜像版本号

如果用户没说『跳过编译 / 直接用现成镜像』，必须先跑这一步拿到 `image_version`。

如果用户只要求『编译』而没有要求发版，只执行本步骤，不进入 ByteFaaS 页面；但“编译完成”的标准仍是 TTP 同步节点已授权/完成、`ICM镜像构建TTP` job 成功，并且 `parse-bits-image-version.sh <runSeq>` 能解析出 TTP `image_version`。只看到 `SCM构建:14`、SCM tarball artifacts、或 summary 中 `running=1` 时，都不是完整编译完成，必须继续刷新/轮询或排查脚本提前退出。

1. 调用内置编译脚本：
   ```bash
   /Users/bytedance/.codex/skills/bytefaas-release/scripts/bits-auto-compile.sh "<branch>"
   ```
   - 默认 `branch=debug_ppe`
   - 非 `master` 分支：触发流水线 `1168542993666` / 轮询 / 自动审批 TTP 同步节点 `同步代码Commit到TTP` (`ttp_code_sync_de0a`) / 失败自动重试一次
   - `master` 分支：**不触发新 run**；先查询当前 active master 自动编译 run，复用该 run 并自动审批 TTP 同步节点。若没找到 active run，脚本退出，不要手动 trigger，避免被 Bits 单并发锁阻塞
   - 脚本最后会输出 JSON summary（含 `runSeq` / `runId` / `url` / `artifacts` / `jobs`）
   - 可选环境变量：`POLL_SECONDS`（默认 20）/ `MAX_POLLS`（默认 120）/ `WORK_DIR`（默认 `work`）/ `NPM_CONFIG_REGISTRY`（默认 `http://bnpm.byted.org`）
   - 鉴权要求：本地 `bytedcli auth status` 和 `bytedcli bits auth status` 可用；如果 ByteCloud auth 缺失，先执行 `bytedcli --json auth login --begin`，把返回的授权 URL 或二维码交给用户，授权后用返回的 complete token 执行 `bytedcli --json auth login --complete <complete_token>`，再执行 `bytedcli --json bits auth login`
   - 安全要求：不要打印或持久化原始 JWT。脚本会在状态文件里把 JWT-like 字符串替换成 `[JWT_REDACTED]`

2. 从 bits 输出的 JSON summary 里解析镜像版本号：
   ```bash
   bash /Users/bytedance/.codex/skills/bytefaas-release/scripts/parse-bits-image-version.sh <runSeq>
   ```
   - 该脚本读取 `<WORK_DIR>/bits-auto-compile-1168542993666-<runSeq>.json`（默认 `WORK_DIR=work`，与内置编译脚本保持一致）
   - 解析规则：**只取 `ICM镜像构建TTP` (`icm_build_atomic_ttp_from_cn`) 这个 job 的 output**，优先字段：`output.image_version` / `output.build_status_list[].image_version` / `output.triggered_image_versions[].image_version`；只在 `regions` 含 `US-TTP` 时才认；**严禁回退到 `ICM镜像构建ROW` 或全局 `pipelineRunArtifacts`，否则会把 ROW 的版本误发到 TTP 环境**
   - 如果 TTP job 还没跑完（`jobStatus !== 14`），必须等待，不要拿别的 job 的版本糊弄
   - 把解析出的版本号当作 `image_version`，传到步骤 1

   只编译请求也必须跑这一步做终态校验；解析成功后把 `image_version` 和 run 信息一起汇报给用户。

3. 解析失败的兜底：
   - 如果 bits 编译失败 → 直接把失败原因报给用户，**不要进发版**
   - 如果 bits 编译成功但脚本没解析出版本号 → 把 bits 给的 `url` 链接打给用户，让用户告诉你具体的 `image_version`，再进步骤 1
4. 把 `image_version` 报给用户做一次确认（用户已说『直接发』则跳过确认）

### 步骤 1 — 打开函数页并切换镜像版本
所有 agent-browser 命令必须前置 `HOME=/tmp/ab-home-bytefaas`（或其他可写目录），并使用步骤 0 中的 CDP 端口。

1. 打开页面（PPE 用 `99sxastl`；online/prod 用 `svqk5ou9`）：
   ```bash
   HOME=/tmp/ab-home-bytefaas agent-browser --cdp 9223 open "https://cloud-ttp-us.bytedance.net/faas/function/99sxastl/code?region=us-ttp&cluster=faas-us-ttp"
   ```
2. `wait 2000` 后再 `snapshot -i`，避免页面还没 hydrate 完就拿 ref
3. **切换 PPE**（仅 PPE 发版需要；online/prod 跳过。仅当 `<ppe>` 与页面顶部当前显示的不一致时）：
   - 页面顶部有 `US-TTP / ppe / <当前 ppe>` 下拉
   - `snapshot -i` 找到该下拉，点击展开 → 在 listitem 列表里点击目标 `<ppe>`
   - 等页面切换完成（`wait 2000`）
   - 如果当前已经是目标 `<ppe>`，直接跳过这一步
4. 重新 `snapshot -i` 拿当前页面结构，找「镜像版本」下拉
   - 有时 snapshot 不会把它暴露成标准 combobox，**当前版本号文本本身**（如 `2.0.0.58`）也可能是可点击入口
5. 点开下拉 → 在 listitem 列表里点击目标版本（`<image_version>`）
6. 点击右上「保存」按钮
7. **保存后做二次校验**：
   - 当前镜像版本文本应变成 `<image_version>`
   - 若页面仍提示“代码内容有更新，请及时保存”，等待 2s 后重试一次保存
   - 不要在未确认保存成功前进入发布流程

### 步骤 2 — 进入「构建并发布」对话框，填写信息
1. 点击页面右上「**发布**」按钮（蓝色主按钮）
2. 弹出“构建并发布”对话框，第 1 步「发布设置」：
   - **代码版本**：点“请选择代码版本” → 选 `$Latest`
   - **版本描述**：fill `<version_desc>` 进描述输入框
   - **审批人**：点“请选择审批人” → 在下拉中选**第三个**含 `NOC` 的选项（完整名: `TikTok USDS JV-US Tech and Product-Eng Support-NOC`）
     - 「审批类型」会自动带出“部门账号”
   - 其他字段保持默认（系统模板 / 灰度 10% / 全机房）
3. 点击「下一步」

### 步骤 3 — 信息确认并提交
1. 第 2 步「信息确认」校验：
   - 代码版本: `$Latest <version_desc>`
   - 发布方式: 全机房发布-灰度发布 灰度-10%
   - 发布机房: 全机房发布
2. **可选**：截屏给用户看一下要不要确认。如果用户已说“直接发”则跳过
3. 点击「确定」按钮
4. URL 自动跳转到 `/ticket?...&ticketId=<id>`，用 `agent-browser get url` 提取 ticketId
5. 工单链接：
   `https://cloud-ttp-us.bytedance.net/faas/function/99sxastl/ticket?region=us-ttp&cluster=faas-us-ttp&ticketId=<id>`

   把这个链接告诉用户

### 步骤 4 — 用脚本轮询发布进度
优先使用官方轮询脚本，而不是每轮手写 evaluate：

```bash
AB_HOME=/tmp/ab-home-bytefaas CDP_PORT=9223 bash /Users/bytedance/.codex/skills/bytefaas-release/scripts/watch-ticket.sh "<工单链接>"
```

脚本行为：
- 先打开工单页一次；每轮读取当前页面状态，只有连续读到空节点时才重开，避免反复打断 hydration
- 页面刚打开若节点数组为空，会按 `HYDRATION_RETRIES`（默认 15）× `HYDRATION_WAIT_MS`（默认 2000ms）的节奏循环补读，规避 hydration 延迟（实测有的工单需要 ~30s 才完成 hydrate）
- 通过 `.pipelines-node` 的 className 判断状态，不依赖“审批 X分Ys”这类耗时文本
- 在 `全机房灰度` 进入 `loading` 且该节点内出现「全量」操作时自动点击；**不要点 banner 右上角的「全量发布」按钮**
- 在 `全机房全量` 节点进入 `success` 时退出并返回成功；若节点状态已完成但页面先渲染出 banner“成功”，也接受 banner 作为成功兜底
- 任意阶段出现 `error` / `fail` 时立即退出并返回失败

可选环境变量：`POLL_INTERVAL_SECONDS` / `MAX_POLLS` / `HYDRATION_RETRIES` / `HYDRATION_WAIT_MS` / `AB_HOME` / `CDP_PORT`。

如果不用脚本，手工轮询时也必须遵守上面的判断规则。

### 步骤 5 — 通知用户
发版完成后给用户一段简短总结：

```
✅ 发版成功
- 分支: <branch>
- bits runSeq: <runSeq>（步骤 0.5 跳过则省略）
- 镜像: <image_version>
- 描述: <version_desc>
- 工单 ID: <id>
- 工单链接: <full url>
```

## 关键避坑点

1. **审批阶段判断**：banner 上的“审批 X分Ys”是耗时不是状态。看节点 class 是不是 `success`。
2. **页面 hydration 有延迟**：刚打开工单页时，节点可能短暂为空或全部是 `gray`。先 `wait 2000` 再读；如果仍拿不到有效状态，按 `HYDRATION_RETRIES × HYDRATION_WAIT_MS` 多轮补读（实测有的工单要 ~30s 才完成 hydrate）。官方轮询脚本已把这套循环内置好。
3. **agent-browser ref 易失效**：每次页面变化（点击 / 导航 / 弹窗）后必须重新 `snapshot -i` 拿新 `@eN` ref。
4. **HOME 必须设**：每条 agent-browser 命令前面都要设独立可写 `HOME`（推荐 `/tmp/ab-home-bytefaas`），否则可能复用旧 daemon / 旧 CDP 端口。
5. **审批人是第三个**：下拉里有多个含 “NOC” 的选项，要选 `TikTok USDS JV-US Tech and Product-Eng Support-NOC`（部门账号）。
6. **不要漏点保存**：步骤 1 切完镜像版本必须点保存，否则发布时还是旧版本。
7. **全量入口**：灰度完成后要点 `全机房灰度` 节点里的「全量」，不是 banner 右上角的「全量发布」按钮；如果 `snapshot -i` 里出现 `generic "全量"`，优先点这个 ref，ref 点不动再用鼠标坐标点该节点内的小「全量」。
8. **优先用脚本轮询**：轮询、判断节点状态、点节点内“全量”这几步都容易写出一次性代码，统一收敛到官方脚本里更稳；脚本不再每轮重开页面，只在连续读空状态时重开，避免 hydration 被反复打断。
9. **bits 编译失败要止血**：步骤 0.5 内置编译脚本失败必须停在那里，把失败原因 / 链接给用户，**不要拿旧镜像**糊弄上去发版。
10. **只审批固定 TTP 节点**：自动审批只允许作用于 pipeline `1168542993666` 的 `ttp_code_sync_de0a` 节点，不要强跳或重试其他失败节点，除非用户明确要求。
11. **绝对不要用 Codex in-app Browser、普通 Chrome、`browser`/`integrated_browser` MCP**：必须只用 `canary-profile-browser` 连接的 Canary 打开页面；遇到 SSO 就 pending 轮询等用户登录。
12. **镜像版本只认 TTP**：解析镜像版本必须只取 `ICM镜像构建TTP` job 的 output，禁止从全局 artifacts 或 `ICM镜像构建ROW` 取版本号。
13. **master 分支不要新建 Bits run**：master 更新会自动开始 ICM 编译；先复用 active run 并点 TTP 同步审批。新建 run 会被 Bits 单并发锁阻塞，也会把真正等待审批的自动 run 藏起来。

## 工具/资源清单

- Bits 编译脚本: `/Users/bytedance/.codex/skills/bytefaas-release/scripts/bits-auto-compile.sh`
- 镜像版本解析脚本: `/Users/bytedance/.codex/skills/bytefaas-release/scripts/parse-bits-image-version.sh`
- Canary 连接脚本: `/Users/bytedance/.codex/skills/canary-profile-browser/scripts/connect-canary-profile.sh`
- 轮询脚本: `/Users/bytedance/.codex/skills/bytefaas-release/scripts/watch-ticket.sh`
- Canary profile: `/Users/bytedance/chrome-agent-profile`（登录态过期时 pending 等用户登录）
- agent-browser 工作目录: `/tmp/ab-home-bytefaas`（首次使用前 `mkdir -p /tmp/ab-home-bytefaas`）
- CDP: 默认 `localhost:9223`
- 完整 SOP 落在该 skill 的 `SKILL.md`（本文件）
