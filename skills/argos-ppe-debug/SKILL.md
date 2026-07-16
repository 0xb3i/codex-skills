---
name: argos-ppe-debug
description: Diagnose Argos logs for bytedance.agent.ecom_affiliate PPE tests, especially Planner vs Executor vs MCP tool issues for product selection, product board, candidate products, empty recalls, script generation followups, and query/result tracing. Use when the user mentions PPE, niubei, ppe_product_selection_niubei, Agos/Argos streamlog links, 家具/榜单/候选商品/Planner/Executor/tool 排查, or asks whether a PPE agent failure is planning, execution, or empty backend data.
---

# Argos PPE Debug

## Defaults

- Use `argos-query` / `gdpa-cli`; US-TTP logs usually need GDPA, not plain browser inspection.
- Default scope:
  - `psm`: `bytedance.agent.ecom_affiliate`
  - `vregion`: `US-TTP`
  - PPE env signal: `ppe_product_selection_niubei`
  - keyword must include `niubei`
  - time range: last 15 minutes unless the user gives a URL/time window or asks otherwise
- If the user gives an Argos URL, parse and preserve `data_source_uid`, `start_time`, `end_time`, `patterns`, `psm`, and `region` exactly.
- Prefer absolute `start`/`end` from the URL over `time_range`; otherwise use `time_range: "15m"`.

## Fast Path

1. Query the user keyword plus `niubei` first.

```bash
gdpa-cli run argos-query \
  --session-id "$SESSION_ID" \
  --timeout 180 \
  --input '{"psm":"bytedance.agent.ecom_affiliate","keywords":["niubei","<user-keyword>"],"keyword_operator":"AND","vregion":"US-TTP","time_range":"15m","limit":100,"timeout_in_ms":120000}' \
  --output work/gdpa-logs/<case>.json
```

2. Extract only decision logs. Do not dump whole logs.

```bash
jq -r '.logs[]?.content // ""' work/gdpa-logs/<case>.json |
  rg -i 'PLANNER NODE|EXECUTOR NODE|GENERATOR NODE|affiliate_product_search|affiliate_product_board|call_tool|result len|product list len|recalled product_ids|product candidate|last_product_context|queries_history|Found .*Home Furniture|ranking_list_type|error|exception|traceback' -C 1 |
  sed -n '1,260p'
```

3. If the first query is noisy or truncated, run narrow followups instead of increasing prose analysis:

```bash
# Board empty / non-empty evidence
gdpa-cli run argos-query --session-id "$SESSION_ID" --timeout 180 \
  --input '{"psm":"bytedance.agent.ecom_affiliate","keywords":["affiliate_product_board recalled product_ids"],"keyword_operator":"AND","vregion":"US-TTP","time_range":"15m","limit":200,"timeout_in_ms":120000}' \
  --output work/gdpa-logs/<case>_board_recalled.json

# Search fallback evidence
gdpa-cli run argos-query --session-id "$SESSION_ID" --timeout 180 \
  --input '{"psm":"bytedance.agent.ecom_affiliate","keywords":["affiliate_product_search query=","result len"],"keyword_operator":"AND","vregion":"US-TTP","time_range":"15m","limit":200,"timeout_in_ms":120000}' \
  --output work/gdpa-logs/<case>_search_len.json
```

## Judgment Rules

- Planner issue: Planner chooses the wrong domain/intent/tool, omits product-selection tools, or plans script/content creation before a product is selected.
- Executor issue: Planner is right, but Executor calls the wrong tool, drops required params, or fails before/while calling MCP.
- Backend/tool empty: Executor calls the expected tool with reasonable params and logs `product_ids=[]`, `product list len: 0`, or `result len: 0`.
- Fallback success: board is empty but later `affiliate_product_search ... result len: N` and `last_product_context.source=product_selection` contains product IDs.
- Display/state issue: logs show candidates saved or generator received `product candidate`, but UI/user sees no cards; suspect product-card formatting, inline tags, or context overwrite.

## Niubei Product Selection Checklist

For queries like “家具品类哪些产品好评高”:

1. Confirm the query in `History` or node logs.
2. Confirm Planner exposes product tools such as `affiliate_product_search` and, when relevant, board/review tools.
3. Confirm Executor sub_goal and `tool_name`.
4. Confirm category mapping, e.g. `Using category 'Home Furniture'` and `Found ... cate_id`.
5. Confirm actual MCP calls:
   - `affiliate_product_board` with `ranking_list_type: 4` for high-review/high-rated board requests
   - `affiliate_product_search` fallback with query strings
6. Confirm candidate result counts:
   - `affiliate_product_board recalled product_ids=[...]`
   - `Successfully parsed board product list len: N`
   - `affiliate_product_search query='...' result len: N`
7. Confirm downstream state:
   - `GENERATOR NODE ... product candidate`
   - `ConvStore save ... last_product_context.source=product_selection`
   - product IDs in `last_product_context.product_ids`

## Avoid These Traps

- Always include `niubei`; without it, the same PSM may return non-PPE or other swimlane logs.
- `total=300` with `truncated=true` means the query is too broad. Narrow by exact log phrases.
- History logs repeat old user/AI messages and can look like fresh requests. Use node timestamps plus Executor/Generator logs to identify the active turn.
- `product list len: 0` after a “生成脚本” turn is not evidence that the earlier product-selection turn failed.
- `last_product_context` can be overwritten by followup content creation. Use the save immediately after the selection answer, not a later save.
- `transaction call_tool is limited by debug trace limiter` is usually trace sampling/noise, not a business failure by itself.
- Some Argos output is masked as `.*`; trust counts and stable fields (`result len`, `product_ids=[]`, source names) more than redacted values.
- Hex-looking IDs in centralized logs are often not queryable logIDs. If logID trace fails with parse errors, continue with narrow keyword searches.

## Final Answer Shape

Report briefly:

- queried scope: PSM, region, env/swimlane, time window, keywords
- whether logs were finished/truncated
- Planner verdict
- Executor/tool verdict
- candidate/result-count evidence
- likely root cause and next owner: Planner, Executor, backend/tool data, display/card state, or followup context overwrite
