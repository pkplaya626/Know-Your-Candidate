#!/usr/bin/env node
// Read court roster pages that draw themselves with JavaScript, or that
// answer a browser but not a plain request, in a headless Chrome of our own.
//
//   node tools/read_court_pages.mjs --out DIR CODE=URL [CODE=URL ...]
//
// Writes DIR/CODE.html (the page as drawn) and DIR/manifest.json:
//   {"chrome": "<version>", "pages": {"CODE": {"url", "finalUrl", "status",
//    "title", "read", "error"}}}
// `python build_profile_site.py courts` runs this and reads what it wrote
// with each court's recipe (kyc/courts.py); nothing is guessed from it.
//
// No dependencies: Node's own WebSocket (Node 22 or later) speaks the
// DevTools protocol to Chrome. Chrome is found from $CHROME, then the usual
// install paths. It runs with its own headless user agent and a fresh
// profile: a site that refuses this reader (a bot wall, a challenge page) is
// refused, not worked around - the recipe then reads no names and the
// courts command keeps the court's last good read (rule 8).
//
// Exit status: 0 when the reader ran (each page's outcome is in the
// manifest); 3 when there is no Chrome or no WebSocket to drive it.
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const NO_BROWSER = 3;
const LOAD_TIMEOUT_MS = 30000;   // a page's load event
const SETTLE_MS = 15000;         // at most this long for scripts to draw it
const PAUSE_MS = 2000;           // between pages: one request at a time

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function args(argv) {
  const out = { dir: null, pages: [] };
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === '--out') out.dir = argv[++i];
    else if (/^[A-Z][A-Z-]*=https:\/\//.test(argv[i])) {
      const at = argv[i].indexOf('=');
      out.pages.push([argv[i].slice(0, at), argv[i].slice(at + 1)]);
    } else {
      throw new Error(`not CODE=https://...: ${argv[i]}`);
    }
  }
  if (!out.dir) throw new Error('--out DIR is required');
  return out;
}

function findChrome() {
  const named = ['google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser', 'chrome'];
  const fixed = [
    process.env.CHROME,
    'C:/Program Files/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  ];
  for (const candidate of fixed) {
    if (candidate && fs.existsSync(candidate)) return candidate;
  }
  for (const dir of (process.env.PATH || '').split(path.delimiter)) {
    for (const name of named) {
      const full = path.join(dir, name);
      if (fs.existsSync(full)) return full;
    }
  }
  return null;
}

async function launch(chrome) {
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'kyc-court-chrome-'));
  // A GitHub runner's Ubuntu forbids the user namespaces Chrome's sandbox
  // needs; the runner is a throwaway machine, so there it runs without one.
  const sandbox = process.platform === 'linux' && process.env.GITHUB_ACTIONS ? ['--no-sandbox'] : [];
  const proc = spawn(chrome, ['--headless=new', '--disable-gpu', '--no-first-run',
    '--no-default-browser-check', '--disable-extensions', '--remote-debugging-port=0',
    ...sandbox, `--user-data-dir=${profile}`, 'about:blank'], { stdio: 'ignore' });
  const portFile = path.join(profile, 'DevToolsActivePort');
  for (let i = 0; i < 100 && !fs.existsSync(portFile); i++) await sleep(200);
  if (!fs.existsSync(portFile)) {
    proc.kill();
    throw new Error('Chrome did not start');
  }
  await sleep(100);
  const [port, wsPath] = fs.readFileSync(portFile, 'utf8').trim().split(/\r?\n/);
  const client = await connect(`ws://127.0.0.1:${port}${wsPath}`);
  return {
    client,
    async close() {
      try { await client.send('Browser.close'); } catch { /* already gone */ }
      client.close();
      proc.kill();
      await sleep(500);
      try { fs.rmSync(profile, { recursive: true, force: true }); } catch { /* Windows may hold it */ }
    },
  };
}

function connect(url) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(url);
    const pending = new Map();
    const listeners = new Set();
    let next = 0;
    const client = {
      send(method, params = {}, sessionId) {
        const id = ++next;
        ws.send(JSON.stringify(sessionId ? { id, method, params, sessionId } : { id, method, params }));
        return new Promise((res, rej) => pending.set(id, { res, rej, method }));
      },
      listen(fn) { listeners.add(fn); return () => listeners.delete(fn); },
      close() { ws.close(); },
    };
    ws.onopen = () => resolve(client);
    ws.onerror = (e) => reject(new Error('DevTools socket: ' + (e.message || e.type)));
    ws.onmessage = (ev) => {
      const msg = JSON.parse(typeof ev.data === 'string' ? ev.data : ev.data.toString());
      if (msg.id && pending.has(msg.id)) {
        const p = pending.get(msg.id);
        pending.delete(msg.id);
        if (msg.error) p.rej(new Error(`${p.method}: ${msg.error.message}`));
        else p.res(msg.result);
      } else if (msg.method) {
        for (const fn of listeners) fn(msg);
      }
    };
  });
}

/** One page, drawn: navigate, wait for the load event, then until the
 * visible text stops changing (or SETTLE_MS), and take the DOM. */
async function readPage(client, url) {
  const { targetId } = await client.send('Target.createTarget', { url: 'about:blank' });
  const { sessionId } = await client.send('Target.attachToTarget', { targetId, flatten: true });
  const result = { url, finalUrl: '', status: 0, title: '', read: new Date().toISOString(), error: '' };
  let loaded;
  const loadedOnce = new Promise((r) => { loaded = r; });
  const stop = client.listen((msg) => {
    if (msg.sessionId !== sessionId) return;
    if (msg.method === 'Page.loadEventFired') loaded();
    if (msg.method === 'Network.responseReceived' && msg.params.type === 'Document' && !result.status) {
      result.status = msg.params.response.status;
    }
  });
  const evaluate = async (expression) => (await client.send('Runtime.evaluate',
    { expression, returnByValue: true }, sessionId)).result.value;
  let html = '';
  try {
    await client.send('Page.enable', {}, sessionId);
    await client.send('Network.enable', {}, sessionId);
    const nav = await client.send('Page.navigate', { url }, sessionId);
    if (nav.errorText) throw new Error(nav.errorText);
    await Promise.race([loadedOnce, sleep(LOAD_TIMEOUT_MS)]);
    let last = -1;
    for (let waited = 0; waited < SETTLE_MS; waited += 1000) {
      await sleep(1000);
      const now = await evaluate('document.body ? document.body.innerText.length : 0');
      if (now > 0 && now === last) break;
      last = now;
    }
    html = await evaluate('document.documentElement.outerHTML');
    result.title = await evaluate('document.title');
    result.finalUrl = await evaluate('location.href');
  } catch (exc) {
    result.error = exc.message;
  } finally {
    stop();
    await client.send('Target.closeTarget', { targetId }).catch(() => {});
  }
  return { result, html };
}

async function main() {
  const { dir, pages } = args(process.argv.slice(2));
  if (typeof WebSocket !== 'function') {
    console.error('[error] this Node has no WebSocket; the reader needs Node 22 or later');
    return NO_BROWSER;
  }
  const chrome = findChrome();
  if (!chrome) {
    console.error('[error] no Chrome found (set CHROME to its path)');
    return NO_BROWSER;
  }
  let browser;
  try {
    browser = await launch(chrome);
  } catch (exc) {
    console.error(`[error] ${exc.message}`);
    return NO_BROWSER;
  }
  fs.mkdirSync(dir, { recursive: true });
  const manifest = { chrome: '', pages: {} };
  try {
    manifest.chrome = (await browser.client.send('Browser.getVersion')).product;
    for (const [i, [code, url]] of pages.entries()) {
      if (i) await sleep(PAUSE_MS);
      const { result, html } = await readPage(browser.client, url);
      manifest.pages[code] = result;
      fs.writeFileSync(path.join(dir, `${code}.html`), html, 'utf8');
      console.log(`  ${code}: ${result.error || `${result.status} ${html.length} characters`} ${url}`);
    }
  } finally {
    await browser.close();
  }
  fs.writeFileSync(path.join(dir, 'manifest.json'), JSON.stringify(manifest, null, 1) + '\n', 'utf8');
  return 0;
}

main().then((code) => { process.exitCode = code; }, (exc) => {
  console.error(`[error] ${exc.message}`);
  process.exitCode = 2;
});
