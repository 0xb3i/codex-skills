#!/usr/bin/env node
'use strict';

const fs = require('fs');
const os = require('os');
const path = require('path');
const readline = require('readline');

const DEFAULT_URL = 'https://ask.feishu.cn/';
const DEFAULT_TIMEOUT_MS = 120000;
const DEFAULT_STABLE_MS = 5000;
const PLACEHOLDERS = [
  '正在搜索', '正在检索', '正在思考', '搜索文件', '搜索中', '生成中', '回答中',
  'thinking', 'searching', 'generating', 'loading'
];

function dataDir() {
  return process.env.ASK_FEISHU_DATA_DIR || path.join(os.homedir(), '.local', 'share', 'ask_feishu');
}

function defaultStatePath() {
  return path.join(dataDir(), 'storage_state.json');
}

function ensurePrivateDir(dir) {
  fs.mkdirSync(dir, { recursive: true, mode: 0o700 });
  try { fs.chmodSync(dir, 0o700); } catch (_) {}
}

function parseArgs(argv) {
  const out = { _: [] };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (!arg.startsWith('--')) {
      out._.push(arg);
      continue;
    }
    const [rawKey, inline] = arg.slice(2).split(/=(.*)/s, 2);
    const key = rawKey.replace(/-([a-z])/g, (_, c) => c.toUpperCase());
    if (['json', 'headed', 'selfTest', 'help'].includes(key)) {
      out[key] = true;
      continue;
    }
    out[key] = inline !== undefined ? inline : argv[++i];
  }
  return out;
}

function normalizeText(text) {
  return String(text || '').replace(/\u00a0/g, ' ').replace(/[ \t]+/g, ' ').replace(/\n{3,}/g, '\n\n').trim();
}

function hasOnlyPlaceholder(text) {
  const lower = normalizeText(text).toLowerCase();
  if (!lower) return true;
  return PLACEHOLDERS.some((p) => lower.includes(p.toLowerCase())) && lower.length < 80;
}

function deriveAnswer(bodyText, question) {
  const body = normalizeText(bodyText);
  const q = normalizeText(question);
  if (!body) return '';
  const clean = (s) => normalizeText(s
    .replace(/^[\s\u200b]*已完成深度思考\n?/, '')
    .replace(/\n?AI 基于你有权限的资料生成，数据保密仅你可见[\s\S]*$/m, '')
    .replace(/\n?分享\n?​?\n?联网搜索[\s\S]*$/m, ''));
  if (!q) return clean(body);
  const idx = body.lastIndexOf(q);
  if (idx === -1) return clean(body);
  return clean(body.slice(idx + q.length));
}

function loadPlaywright() {
  try {
    return require('playwright');
  } catch (err) {
    throw new Error('找不到 playwright。请设置 ASK_FEISHU_NODE_MODULES 指向包含 playwright 的 node_modules，或先 npm install playwright。');
  }
}

function waitForEnter(prompt) {
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  return new Promise((resolve) => rl.question(prompt, () => { rl.close(); resolve(); }));
}

async function setup(argv) {
  const args = parseArgs(argv);
  if (args.help) return usage();
  const statePath = path.resolve(args.state || defaultStatePath());
  const profileDir = path.resolve(args.profileDir || path.join(dataDir(), 'setup-profile'));
  ensurePrivateDir(path.dirname(statePath));
  ensurePrivateDir(profileDir);

  const { chromium } = loadPlaywright();
  const context = await chromium.launchPersistentContext(profileDir, {
    channel: process.env.ASK_FEISHU_CHANNEL || args.channel || 'chrome',
    headless: false,
    viewport: { width: 1280, height: 900 }
  });
  const page = context.pages()[0] || await context.newPage();
  await page.goto(args.url || DEFAULT_URL, { waitUntil: 'domcontentloaded', timeout: 60000 });

  console.log('\n已打开独立 Chrome 登录窗口。请在那个窗口里完成飞书知识问答登录。');
  await waitForEnter(`登录完成并能看到知识问答页面后，回到这里按 Enter 保存登录态到 ${statePath} ... `);

  await context.storageState({ path: statePath });
  try { fs.chmodSync(statePath, 0o600); } catch (_) {}
  await context.close();
  console.log(`已保存：${statePath}`);
}

async function markQuestionInput(page, selectorOverride) {
  const deadline = Date.now() + 30000;
  let ok = false;
  while (Date.now() < deadline && !ok) {
    try {
      ok = await page.evaluate((selector) => {
    const selectors = selector ? [selector] : ['[contenteditable="true"]', 'textarea', 'input:not([type="hidden"])'];
    const visible = (el) => {
      const r = el.getBoundingClientRect();
      const s = getComputedStyle(el);
      return r.width > 80 && r.height > 12 && s.visibility !== 'hidden' && s.display !== 'none';
    };
    const candidates = selectors.flatMap((s) => Array.from(document.querySelectorAll(s))).filter(visible);
    candidates.sort((a, b) => {
      const ar = a.getBoundingClientRect();
      const br = b.getBoundingClientRect();
      return (br.y + br.height / 2) - (ar.y + ar.height / 2) || (br.width * br.height) - (ar.width * ar.height);
    });
    const el = candidates[0];
    if (!el) return false;
    document.querySelectorAll('[data-ask-feishu-input]').forEach((n) => n.removeAttribute('data-ask-feishu-input'));
    el.setAttribute('data-ask-feishu-input', '1');
    return true;
      }, selectorOverride || process.env.ASK_FEISHU_INPUT_SELECTOR || '');
    } catch (err) {
      if (!/Execution context was destroyed|navigation/i.test(err.message || '')) throw err;
      ok = false;
    }
    if (!ok) await page.waitForTimeout(500);
  }
  if (!ok) throw new Error('没有找到可见输入框。若已登录仍失败，可能是登录态过期或页面结构变化；可用 ASK_FEISHU_INPUT_SELECTOR 指定选择器。');
  return page.locator('[data-ask-feishu-input="1"]');
}

async function submitQuestion(page, selectorOverride) {
  const selector = selectorOverride || process.env.ASK_FEISHU_SUBMIT_SELECTOR || '';
  let marked = false;
  try {
    marked = await page.evaluate((explicitSelector) => {
    const visible = (el) => {
      const r = el.getBoundingClientRect();
      const s = getComputedStyle(el);
      return r.width > 8 && r.height > 8 && s.visibility !== 'hidden' && s.display !== 'none';
    };
    const input = document.querySelector('[data-ask-feishu-input="1"]');
    const inputRect = input?.getBoundingClientRect();
    const explicit = explicitSelector ? Array.from(document.querySelectorAll(explicitSelector)).filter(visible) : [];
    const buttons = explicit.length ? explicit : Array.from(document.querySelectorAll('button,[role="button"]')).filter(visible).filter((el) => {
      const text = [el.innerText, el.getAttribute('aria-label'), el.getAttribute('title'), el.className].join(' ').toLowerCase();
      if (/发送|提交|提问|send|ask|submit|arrow|enter|roundbutton/.test(text)) return true;
      if (!inputRect) return false;
      const r = el.getBoundingClientRect();
      return r.y >= inputRect.y - 30 && r.y <= inputRect.y + inputRect.height + 120 && r.x >= inputRect.x + inputRect.width - 120;
    });
    buttons.sort((a, b) => b.getBoundingClientRect().y - a.getBoundingClientRect().y);
    const btn = buttons[0];
    if (!btn) return false;
    document.querySelectorAll('[data-ask-feishu-submit]').forEach((n) => n.removeAttribute('data-ask-feishu-submit'));
    btn.setAttribute('data-ask-feishu-submit', '1');
    return true;
    }, selector);
  } catch (err) {
    if (!/Execution context was destroyed|navigation/i.test(err.message || '')) throw err;
  }
  if (marked) {
    await page.locator('[data-ask-feishu-submit="1"]').click({ timeout: 10000 });
    return;
  }
  await page.keyboard.press(process.env.ASK_FEISHU_SUBMIT_KEY || 'Enter');
}

async function extractState(page, answerSelector) {
  return page.evaluate((selector) => {
    const visible = (el) => {
      const r = el.getBoundingClientRect();
      const s = getComputedStyle(el);
      return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
    };
    const picked = selector ? Array.from(document.querySelectorAll(selector)).filter(visible) : [];
    const answerText = picked.length ? picked.map((el) => el.innerText || el.textContent || '').join('\n\n') : (document.body?.innerText || '');
    const sources = Array.from(document.querySelectorAll('a[href]')).filter(visible).map((a) => ({
      title: (a.innerText || a.textContent || '').trim(),
      url: a.href
    })).filter((x) => {
      if (!x.url || x.url.startsWith('javascript:')) return false;
      try {
        const host = new URL(x.url).host;
        return !/^(ask\.)?(feishu\.cn|larksuite\.com)$/.test(host) && !host.startsWith('ask.');
      } catch (_) {
        return true;
      }
    }).slice(0, 30);
    return { answerText, sources, url: location.href, title: document.title };
  }, answerSelector || process.env.ASK_FEISHU_ANSWER_SELECTOR || '');
}

async function waitForStableAnswer(page, question, opts) {
  const deadline = Date.now() + opts.timeoutMs;
  let last = '';
  let stableSince = 0;
  let lastState = null;
  while (Date.now() < deadline) {
    try {
      lastState = await extractState(page, opts.answerSelector);
    } catch (err) {
      if (/Execution context was destroyed|navigation/i.test(err.message || '')) {
        await page.waitForTimeout(1000);
        continue;
      }
      throw err;
    }
    const answer = deriveAnswer(lastState.answerText, question);
    if (answer && !hasOnlyPlaceholder(answer)) {
      if (answer === last) {
        stableSince ||= Date.now();
        if (Date.now() - stableSince >= opts.stableMs) return { answer, state: lastState };
      } else {
        last = answer;
        stableSince = 0;
      }
    }
    await page.waitForTimeout(1000);
  }
  const partial = deriveAnswer(lastState?.answerText || '', question);
  throw new Error(`等待回答超时。${partial ? `已捕获部分内容：${partial.slice(0, 200)}` : '没有捕获到可用回答。'}`);
}

async function ask(argv) {
  const args = parseArgs(argv);
  const question = args._.join(' ').trim() || args.question;
  if (!question || args.help) return usage();

  const statePath = path.resolve(args.state || defaultStatePath());
  if (!fs.existsSync(statePath)) throw new Error(`缺少登录态：${statePath}\n先运行 ask_feishu_setup。`);

  const { chromium } = loadPlaywright();
  const browser = await chromium.launch({
    channel: process.env.ASK_FEISHU_CHANNEL || args.channel || 'chrome',
    headless: !args.headed
  });
  const context = await browser.newContext({ storageState: statePath, viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();
  try {
    await page.goto(args.url || DEFAULT_URL, { waitUntil: 'domcontentloaded', timeout: 60000 });
    const input = await markQuestionInput(page, args.inputSelector);
    await input.click({ timeout: 10000 });
    await page.keyboard.type(question, { delay: Number(args.typeDelay || 5) });
    await submitQuestion(page, args.submitSelector);
    const result = await waitForStableAnswer(page, question, {
      timeoutMs: Number(args.timeout || DEFAULT_TIMEOUT_MS),
      stableMs: Number(args.stableMs || DEFAULT_STABLE_MS),
      answerSelector: args.answerSelector
    });
    const payload = {
      ok: true,
      question,
      answer: result.answer,
      sources: result.state.sources,
      backend: 'playwright-web',
      url: result.state.url
    };
    if (args.json) console.log(JSON.stringify(payload, null, 2));
    else {
      console.log(payload.answer);
      if (payload.sources.length) {
        console.log('\n来源：');
        for (const s of payload.sources) console.log(`- ${s.title || s.url}: ${s.url}`);
      }
    }
  } finally {
    await browser.close();
  }
}

function usage() {
  console.log(`用法：\n  ask_feishu_setup [--state PATH] [--url ${DEFAULT_URL}]\n  ask_feishu "问题" [--json] [--timeout 120000] [--headed]\n\n可选环境变量：ASK_FEISHU_INPUT_SELECTOR / ASK_FEISHU_SUBMIT_SELECTOR / ASK_FEISHU_ANSWER_SELECTOR / ASK_FEISHU_DATA_DIR`);
}

function selfTest() {
  console.assert(deriveAnswer('导航\n问题 A\n答案 B', '问题 A') === '答案 B');
  console.assert(deriveAnswer('问题 A\n已完成深度思考\n答案 B', '问题 A') === '答案 B');
  console.assert(hasOnlyPlaceholder('正在搜索文件...'));
  console.assert(!hasOnlyPlaceholder('这是一个真实回答，包含足够多的信息，不应被当作占位文本。'));
  console.assert(parseArgs(['--json', '--timeout', '10', 'hello']).json === true);
  console.log('self-test ok');
}

async function main() {
  const [cmd, ...argv] = process.argv.slice(2);
  if (cmd === '--self-test') return selfTest();
  if (cmd === 'setup') return setup(argv);
  if (cmd === 'ask') return ask(argv);
  return usage();
}

if (require.main === module) {
  main().catch((err) => {
    const payload = { ok: false, error: err.message };
    if (process.argv.includes('--json')) console.error(JSON.stringify(payload, null, 2));
    else console.error(`ask_feishu: ${err.message}`);
    process.exit(1);
  });
}

module.exports = { deriveAnswer, hasOnlyPlaceholder, parseArgs };
