---
name: trae-ai-maintenance
description: Diagnose and repair the user's modified Trae CN AI setup. Use when Trae CN, the local Codex extension, the local Claude Code extension, or the remote SSH Codex extension has sidebar/tab regressions, damaged-app prompts, stuck loading, missing plugins such as ponytail, wrong CLI paths, slow remote startup, Diff view/full-content failures, duplicate/stale agent extension installs, or when a Trae/Codex/Claude update may have overwritten local or remote injected patches.
---

# Trae AI Maintenance

## Core Paths

- Maintenance root: `/Users/bytedance/trae-codex-maintenance` (legacy path; also contains Claude Code maintenance)
- Main reapply script: `/Users/bytedance/trae-codex-maintenance/reapply-codex-tabs.js`
- Claude Code sidebar reapply script: `/Users/bytedance/trae-codex-maintenance/reapply-claude-sidebar.js`
- Auto reapply script: `/Users/bytedance/trae-codex-maintenance/auto-reapply-codex-tabs.sh`
- Remote patch script: `/Users/bytedance/trae-codex-maintenance/patch-remote-codex-navigator.sh`
- Local app: `/Users/bytedance/Applications/Trae CN.app`
- Local Codex extensions: `/Users/bytedance/.trae-cn/extensions/openai.chatgpt-*-darwin-arm64`
- Local Claude Code extensions: `/Users/bytedance/.trae-cn/extensions/anthropic.claude-code-*-darwin-arm64`
- Main remote host: `cloudide-wsed9ab0d425c9aa57`
- Logs: `/Users/bytedance/trae-codex-maintenance/logs/auto-reapply.log`
- Generated backups cleaned by auto reapply: `/Users/bytedance/trae-codex-maintenance/*.bak-*`, `app-bundles`, `build-work-reapply`
- Generated remote backups cleaned by remote patch checks: `~/.trae-cn-server/extensions/**/*.bak-*`, `~/.ttadk/bin/*.bak-*`

## Default Workflow

1. Inspect the latest local Codex and Claude Code extensions under `/Users/bytedance/.trae-cn/extensions` and the latest auto log before changing anything.
2. If only the local Codex extension is stale, run:

```bash
REAPPLY_CODEX_TABS_EXTENSION_ONLY=1 node /Users/bytedance/trae-codex-maintenance/reapply-codex-tabs.js '/Users/bytedance/Applications/Trae CN.app' '<extension-dir>'
```

3. If Claude Code opens as a tab or has multiple local extension installs, keep only the latest `anthropic.claude-code-*-darwin-arm64` directory, then run:

```bash
node /Users/bytedance/trae-codex-maintenance/reapply-claude-sidebar.js '/Users/bytedance/Applications/Trae CN.app' '<claude-extension-dir>'
```

4. If Trae app shell patches are missing, run the auto script only when Trae is closed, because app bundle replacement cannot safely happen while Trae is running.
5. For remote SSH issues, run:

```bash
/Users/bytedance/trae-codex-maintenance/patch-remote-codex-navigator.sh cloudide-wsed9ab0d425c9aa57
```

6. If the remote Codex CLI itself is stale, check `/usr/local/bin/codex`, `~/.local/bin/codex`, and `~/.local/bin/codex-real` first, then distinguish the intended provider. For internal ModelHub, do not replace the company build with `npm install -g @openai/codex`: fetch `codex.version` plus the matching `codex-darwin-arm64` / `codex-darwin-x64` / `codex-linux-x64` artifact from the internal toolchain, verify its platform MD5, and point `codex-real` at that internal binary while preserving the TTADK wrapper as a regular executable. Use the npm build only when the user intentionally wants the official CLI/provider path.
7. Validate with `node --check` on modified `out/extension.js`, `extension.js`, or Trae workbench JS, then grep for the injected markers or command IDs.
8. Ask the user to reload the Trae window after remote patching or after local extension-host changes.

## Known Version Shapes

- Local Codex sidebar injection should not key off minified names like `qi` or `Bi`. The reapply script should match the stable open/focus flow around `workbench.view.extension.${containerId}` and `${viewId}.focus`.
- If the auto log says `Codex extension sidebar patch: expected 1 generic entrypoint match, got 0`, inspect the new `out/extension.js` around `workbench.view.extension` and update the one generic matcher in `/Users/bytedance/trae-codex-maintenance/reapply-codex-tabs.js`.
- Claude Code may open as an editor tab in Trae when the extension gates `secondarySidebar` on VS Code `>=1.106`. Patch the latest `anthropic.claude-code-*-darwin-arm64/extension.js` with `/Users/bytedance/trae-codex-maintenance/reapply-claude-sidebar.js` so `claude-vscode.sidebar.open` targets `claudeVSCodeSidebarSecondary`, and add the `Claude` auxiliary-bar title tab in Trae's workbench shell.
- For Claude's auxiliary-bar tab, do not only call `openPaneComposite("workbench.view.extension.claude-sidebar-secondary", ...)`: that can select the container without reliably letting Claude Code create/focus its chat webview. The tab action should first execute `claude-vscode.sidebar.open`, then open/focus `workbench.view.extension.claude-sidebar-secondary` / `claudeVSCodeSidebarSecondary.focus` as a fallback/lock-in.
- When registering Claude's `secondarySidebar` contribution in Trae, keep the patch narrow: only register `claude-sidebar-secondary` into location `2` and only mark `workbench.view.extension.claude-sidebar-secondary` as `type: "ai"`. Broadly registering every `secondarySidebar` container can destabilize Trae's auxiliary bar.
- If the auxiliary-bar header shows both `Claude` and `Claude Code`, keep the injected `Claude` title tab and hide the extension's automatic composite-bar item by filtering `workbench.view.extension.claude-sidebar-secondary` out of `refreshCompositeBarItems` while leaving its AI type and registration intact.
- Local Diff file reads should be patched by stable semantics, not minified version names. If an `MC`-style helper strips `a/` or `b/`, patch that normalizer once so absolute diff paths stay absolute; otherwise patch the single async read helper identified by `isAbsolute`, `Uri.file`, `workspaceFolders`, `findFiles`, and `Unable to read file`.
- For bottom-right yellow icons, distinguish the input footer warning from avatar overlays first. A yellow Codex/OpenAI knot icon outside the composer with tooltip `Using a custom CLI executable` is the custom CLI composer footer warning; patch `webview/assets/composer-external-footer-*` near the `codex-*` icon import / `text-token-editor-warning-foreground` and return `null` from its footer component so it does not reserve a horizontal strip. Only treat it as an avatar activity overlay when the asset path/DOM points to `avatar-mascot-button-*`, `avatar-overlay-page-*`, or `avatar-overlay-native-page-*`.
- Newer builds may move that warning into `composer-utility-bar-*`. Locate it by the combined semantics `has-custom-cli-executable`, `hasCustomCliExecutable`, and `composer.customCliTooltip`; if the reapply log says the footer asset was not found, do not report success until the semantic component is patched and its marker is verified. Keep the local and remote reapply matchers aligned.
- Treat CLI version, extension version/model UI, and provider authorization as separate layers. A devbox has its own `~/.codex/config.toml` and `auth.json`; a local Trae `chatgpt.cliExecutable` pointing at `codex-vscode-wrapper.cjs` injects `-c model_provider="ttadk"` / a fixed model and therefore overrides the Codex.app ModelHub configuration. To reuse the app configuration, point the plugin at `/usr/local/bin/codex`, sync only the ModelHub provider/auth to the devbox, and verify with a real `codex exec` showing the intended model/provider. A TTADK `model not allowed` 403 is not a config syntax issue: the model must first be enabled in ModelHub and then approved through TTADK model management; direct ModelHub avoids that TTADK tenant gate.
- The remote model picker comes from the remote Linux `openai.chatgpt` extension, not from the CLI version alone. Compare local and remote extension versions, install the matching `linux-x64` VSIX when stale, reapply remote patches, bump the visible patch version, and reload the remote Trae window.
- If the composer still floats too high or leaves a large bottom gap after hiding the custom CLI footer, check both `webview/assets/composer-*` and `webview/assets/thread-scroll-layout-*`. The home/thread composer footer may have a default `mb-2`, while thread scroll layout may add `--thread-scroll-padding-bottom` as measured footer height plus `16px` and a sticky footer `pb-4`; compact these together and add marker checks to the auto reapply and remote patch scripts. Do not compact the non-home `pg.Input` `minHeight` branch by default: it removes blank space but also visibly compresses the conversation input box.
- Cloud/remote task pages may use `webview/assets/remote-conversation-page-*` instead of the local thread scroll wrapper. If local conversations are compact but cloud still has a gap above the composer, check that asset for the composer wrapper `flex flex-col gap-2` and compact it separately. If the cloud gap only disappears after dragging the secondary sidebar width, the CSS patch is present but cached measurements need a real dimension change; install a short-lived mutation observer and temporarily shrink the parent of `[data-thread-find-composer='true']` by 1px before restoring it. The composer wrapper itself is `className:"contents"`, so changing its own width has no box-model effect.
- If the Gallery extension list briefly shows an OpenAI/default icon for installed Codex before switching to the Codex blossom icon, do not replace downloaded icon caches. Patch `byted-ide.gallery-*-universal/dist/extension.js` at the `parseExtensionsForWebview` normalization path so installed extensions prefer the local `vscode.extensions.getExtension(id).packageJSON.icon` file when it exists, falling back to the newest matching directory under the local extensions root, then let `asWebviewUri` convert it for the webview. Keep this patch in `/Users/bytedance/trae-codex-maintenance/reapply-codex-tabs.js` so Codex or Gallery updates reapply it.

## Safety Notes

- Do not delete or reset user Trae bundles unless explicitly requested. The modified app is intentionally signed ad hoc and registered as the default Trae CN app.
- Do not re-add remote wrapper flags that disable plugins; that previously hid installed plugins such as ponytail. The fast-start wrapper should keep analytics disabled only.
- Distinguish network slowness from patch failure. Slow Diff view/sidebar loading after window reload is often remote app-server/network startup; missing injected markers or path errors are patch issues.
- Automatic reapply is a LaunchAgent scheduled daily at 12:30, not every five minutes.
- Automatic reapply also clears generated local and remote backup files plus temporary app bundle copies; keep logs unless the user explicitly asks to remove logs too.
- If the user asks for screenshot/UI proof, first check macOS TCC screen recording and Accessibility viability. `screencapture`, Computer Use, AX, CDP, and Node inspector can all fail independently; when screen capture is denied, do not claim visual verification. Report the exact verification paths that worked and the blocked screenshot path.
