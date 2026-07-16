---
name: modelhub-api-call
description: Use when writing, modifying, reviewing, or running code that calls the internal ModelHub API or AzureOpenAI-compatible gateway, especially batch model calls, retry handling, concurrency, endpoint selection, temperature, or ~/.modelhub_api configuration.
---

# ModelHub API Call

当任务需要调用模型 API、改模型调用脚本、排查 ModelHub/AzureOpenAI 网关错误、或做批量 query/job 生成时使用本 Skill。

## 默认调用方式

- 优先使用 AzureOpenAI 兼容网关：`from openai import AzureOpenAI` + `client.chat.completions.create(...)`。
- 配置优先来自 `~/.modelhub_api` 导出的环境变量：`AZURE_OPENAI_API_KEY`、`AZURE_OPENAI_ENDPOINT`、`AZURE_OPENAI_MODEL`、`AZURE_OPENAI_API_VERSION`。
- Python 代码里从 `os.environ` 读取配置，不把密钥、endpoint、model 硬编码进项目文件。
- `X-TT-LOGID` 在各项目 py 文件里按项目自定义。

## Endpoint

- 本机/办公网调试 SG 区域默认：`https://aidp-i18ntt-sg.tiktok-row.net/api/modelhub/online/v2/crawl`
- 服务器/生产环境默认：`https://aidp-i18ntt-sg.byteintl.net/api/modelhub/online/v2/crawl`
- 如果服务所在区域有明确生产域名，按服务区域要求覆盖。

## 标准代码模板

```python
import os
from openai import AzureOpenAI

project_logid = "your_project_logid"

client = AzureOpenAI(
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
    api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2026-06-23"),
    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    default_headers={"X-TT-LOGID": project_logid},
)

resp = client.chat.completions.create(
    model=os.environ.get("AZURE_OPENAI_MODEL", "gpt-5.5-2026-04-24"),
    messages=[...],
    max_tokens=500,
    stream=False,
    temperature=1,
)
```

## Temperature

- 调用该网关时 `temperature` 必须显式设为 `1`/`1.0`，或在确认 SDK/API 默认就是 `1` 时省略。
- 不要设置 `0`、`0.2`、`0.7` 等非默认值，避免 `unsupported_value`。

## 批量调用

- 批量模型调用默认使用 32 并发。
- 不要无故串行跑批量调用；只有调试单条 prompt、复现单个错误、或用户明确要求小步慢跑时才串行。

## Retry 与 429

- ModelHub/AzureOpenAI 网关出现 `429` 时，不要默认判断为本地并发资源不足；它经常是上游 API 供应不稳定或瞬时资源抖动。
- 单次调用函数内部应对 retryable 错误做多次带退避和 jitter 的重试：`429`、rate limit、resource insufficient、timeout、connection reset。
- 批处理结束后必须审计结果；若仍存在 `api_error` / `retryable_error` 的 query/job，把失败项以高并发方式单独重跑并回填。
- 持续重跑直到没有因 API 请求错误残留的样本，或达到明确重试上限。
- 只有多轮 retry 后仍大量失败，或同时出现明显连接池/本地资源压力时，才把并发从 32 降到 16。
