# Installation & Setup

Before using the log tools, ensure the Argos CLI is installed and configured.

## 1. Install CLI

**Standard Installation (Linux / macOS):**
```bash
sh -c "$(curl -L https://argos.byted.org/cli/install.sh)" && export PATH=~/.local/bin:$PATH
```

**Devbox Environment (BOE, Linux / macOS):**
```bash
sh -c "$(curl -L https://sre-agent-cli.gf-boe.bytedance.net/cli/install-boe.sh)" && export PATH=~/.local/bin:$PATH
```

**Windows (PowerShell):**
```powershell
# CN / 默认
iwr -useb https://argos.byted.org/cli/install.ps1 | iex

# Devbox / BOE
iwr -useb https://sre-agent-cli.gf-boe.bytedance.net/cli/install-boe.ps1 | iex
```

> Windows 安装路径为 `%USERPROFILE%\.local\bin\argos.exe`，已自动写入用户 PATH，新开终端即可使用。

## 2. Authentication

**Interactive Login:**
Run `argos` in a standard terminal (not inside an IDE sandbox) to scan the QR code or open the login link.

**Token-based Login (CI/CD):**
Set the environment variable:
```bash
export ARGOS_JWT_TOKEN="your-jwt-token"
```

**Skills CLI SSO Login (Internal API Auth):**
Use Skills CLI to obtain a JWT via SSO, no QR code needed. Set NPM registry to BNPM first:
```bash
export npm_config_registry=https://bnpm.byted.org/

# ByteCloud JWT
npx -y skills get-jwt

# Codebase JWT
npx -y skills get-codebase-jwt

# Help
npx -y skills -h
```

Optional `--region` parameter: `cn`, `i18n`, `boe`, `sandbox`. Example:
```bash
npx -y skills get-jwt --region i18n
```

> **Security:** JWT is sensitive. Do not echo the token unless explicitly required.

## 3. Environment Configuration

For I18n or BOE regions, set the default environment:
```bash
argos config set env i18n
# or
argos config set env boe
```
