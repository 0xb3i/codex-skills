# 认证

读取 Codebase 默认使用已配置的 `bytedcli`；先按当前错误或 `bytedcli auth status` 确认登录状态，不打印凭据检查登录。

本技能 `codebase.py` 支持子进程环境 `CODEBASE_JWT`。在 Python 中用 `subprocess.run(["bytedcli", "--no-auto-upgrade", "--json", "auth", "get-codebase-jwt-token"], capture_output=True, text=True, check=True)` 获取结果，从 `data.jwt` 取 token；仅放在内存或该次子进程环境，不打印、不落盘、不写 Git 配置、不放 argv，完成即释放引用。

BITS 链接额外需要 Cloud JWT 时按 `bytedcli auth --help` 的当前命令获取，放入脚本支持的 `CLOUD_JWT` 环境；Codebase JWT 与 Cloud JWT 不能混用。不要为了取得凭据自动安装另一套 CLI。失败先报告鉴权原因，确需 SSO 时按 CLI 指引登录。

脚本原有 AgentBuddy 自动取票只是上游兼容入口；本地默认使用上述显式内存/环境注入。不得通过单独运行会直接打印 token 的命令把凭据带入工具日志。
