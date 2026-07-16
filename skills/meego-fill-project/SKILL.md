---
name: meego-fill-project
description: 在 Meego/Meegle 中填写项目记录：从 Meego 链接或常用项目别名定位父工作项，创建/完成周度子任务，并写入项目字段（如实际 PD、排期、负责人）。Use when the user asks to "填 Meego 项目", "开一条项目", "写项目记录", "填实际 PD", "写实际工时", or wants one-click project entry in Feishu Project/Meego.
---

# Meego Fill Project

## Goal

Fill one project/task entry under the relevant Meego work item node: create the row, set the standard weekly schedule, mark it done when appropriate, and write requested row-level project fields. Actual PD is only one supported project field, not the whole purpose of the skill.

Always use the `meegle` CLI. If authentication fails, run `meegle auth status` and ask the user to log in only when needed.

## Inputs

Expect these from the user:

- Meego work-item URL, or enough task context to match one of the saved common projects below.
- Task name to create.
- Project fields to fill. Actual PD is the common default field and should be interpreted in days/person-days.

Use the current Meegle user as assignee unless the user names another owner. Get it with:

```bash
meegle user me --format json
```

## Common Projects

When the user omits the Meego URL, match the user's work description to these saved projects. Use the matched `project_key`, `work_item_id`, and `work_item_type` directly, then continue with the normal workflow.

If exactly one project matches confidently, proceed without asking. If multiple projects match or no project matches, ask a concise clarification before writing to Meego.

For all saved common projects, use the TTP development node by default: `state_27` / 开发（TTP）. Do not choose ROW or EU for these common projects unless the user explicitly changes this rule later.

| Alias | Match keywords | Project | Work item | Type | Title | Node hint |
| --- | --- | --- | --- | --- | --- | --- |
| planner-verifier-training | planner, verifier, 训练, 选品 agent planner, 选品 agent verifier | data_ecom | 7336845771 | story | 【算法需求】选品agent planner&verifier训练 | Prefer `state_27` / 开发（TTP） when still current. |
| selection-agent-iteration | 选品 agent, 选品Agent, 选品Agent-1.5, 迭代, 一些迭代工作 | data_ecom | 7306503596 | story | 【产品需求】选品Agent-1.5 | Prefer `state_27` / 开发（TTP） when still current. |
| selection-agent-eval-framework | 评估框架, eval, evaluation, 选品 agent 评估, 选品agent-评估 | data_ecom | 7034901529 | story | 【算法需求】-选品agent-评估框架 | Prefer `state_27` / 开发（TTP） when still current. |

Saved source URLs:

- `planner-verifier-training`: `https://meego.larkoffice.com/data_ecom/story/detail/7336845771?parentUrl=%2Fdata_ecom%2FstoryView%2Fqf76XvSNR%3Fnode%3D59747994%26scope%3Dworkspaces%26viewMode%3Dchart&scope=workspaces&node=59747994&openScene=4&quickFilterId=PZPgHEAt-PeBG-i8V0-aBgS-Sb1BFPGw58sB`
- `selection-agent-iteration`: `https://meego.larkoffice.com/data_ecom/story/detail/7306503596?parentUrl=%2Fdata_ecom%2FstoryView%2Fqf76XvSNR%3Fnode%3D59747994%26scope%3Dworkspaces%26viewMode%3Dchart&openScene=6`
- `selection-agent-eval-framework`: `https://meego.larkoffice.com/data_ecom/story/detail/7034901529?parentUrl=%2Fdata_ecom%2FstoryView%2F1zB4_yMNg%3Fscope%3Dworkspaces%26node%3D59411903&scope=workspaces&node=59411903&openScene=4`

## Weekly Window

Use Asia/Shanghai dates.

The schedule window is the Wednesday-to-Tuesday cycle containing the current date:

- Start: most recent Wednesday at `00:00:00`.
- End: the following Tuesday at `23:59:59`.
- If today is Wednesday, start today and end next Tuesday.

Convert both to millisecond timestamps before passing to Meegle.

Example on Wednesday `2026-06-24`:

- Start: `2026-06-24 00:00:00+08:00`.
- End: `2026-06-30 23:59:59+08:00`.

## Workflow

1. Resolve the parent work item.

If the user provided a URL, decode it:

```bash
meegle url decode --url '<url>' --format json
```

Use `simple_name` as `project-key`, `work_item_id` as the parent work item ID, and `work_item_type` for context.

If the user did not provide a URL, use the Common Projects table. Match against the task description and project name; do not rely on fuzzy guessing when the description could refer to more than one saved project.

2. Read nodes and find the target node:

```bash
meegle workflow get-node --project-key <project_key> --work-item-id <work_item_id> --node-id-list _all --field-key-list _all --need-sub-task true --format json
```

Choose the current `doing` node. For saved Common Projects, use `state_27` / 开发（TTP） when it is still current/doing. Do not choose ROW or EU for saved Common Projects. For unsaved URL-based projects, if multiple nodes are `doing`, prefer a node whose name contains `开发`; when multiple development nodes remain possible, ask the user which node to use.

3. Create the subtask under that node:

```bash
meegle subtask update \
  --project-key <project_key> \
  --work-item-id <parent_work_item_id> \
  --node-id <node_key> \
  --action create \
  --assignee <user_key> \
  --fields '[{"field_key":"name","field_value":"<task_name>"}]' \
  --schedule '{"estimate_start_date":<start_ms>,"estimate_end_date":<end_ms>,"owners":["<user_key>"]}' \
  --format json
```

Capture returned `ID`; this is the subtask work item ID.

4. Mark the subtask complete:

```bash
meegle subtask update \
  --project-key <project_key> \
  --work-item-id <parent_work_item_id> \
  --node-id <node_key> \
  --task-id <subtask_id> \
  --action confirm \
  --format json
```

5. Write requested row-level project fields on the subtask work item.

Treat the subtask as an independent work item and use `workitem update` with a JSON array of field updates:

```bash
meegle workitem update \
  --project-key <project_key> \
  --work-item-id <subtask_id> \
  --fields '<fields_json>' \
  --format json
```

For actual PD, use `actual_work_time`:

```json
[{"field_key":"actual_work_time","field_value":"<actual_pd>"}]
```

Important: do not use `subtask update --fields actual_work_time` for row-level actual PD. It may return success but not update the row.

6. Verify by querying the subtask itself:

```bash
meegle workitem get \
  --project-key <project_key> \
  --work-item-id <subtask_id> \
  --fields <updated_field_key> \
  --fields points \
  --fields sub_task_schedule \
  --fields name \
  --format json
```

Report the final state to the user: task name, subtask ID, schedule, filled project fields, estimated PD if visible, and status.

## Guardrails

- Do not trust `workflow get-node`'s `sub_tasks` list for row-level fields such as `actual_work_time`; it may omit them. Verify with `workitem get` on the subtask ID.
- Do not overwrite node-level aggregate fields unless explicitly asked. Row-level project fields belong on the subtask work item.
- If a command returns success but verification does not show the new value, say so and continue with the verified route.
- If creating the subtask succeeds but later steps fail, report the created subtask ID and current verified state.
- If the user asks for a dry run, compute the date window and show commands without executing writes.
