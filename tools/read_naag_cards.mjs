// read_naag_cards.mjs - a person's read of NAAG's "Find my AG" roster, in a
// windowed Chrome (rule 87; overrides.OFFICER_PHOTOS).
//
//   node tools/read_naag_cards.mjs [--out FILE] [--chrome PATH]
//
// naag.org answers a script, and a headless Chrome, with a Cloudflare
// challenge; a windowed Chrome a person could be sitting at passes. So this
// is not part of any refresh: a person runs it, looks at what it prints, and
// records what they checked as dated overrides.OFFICER_PHOTOS entries. It
// opens the roster, scrolls it so every lazy card loads, and for each card
// writes the words beside the image (the attorney general's name and the
// state), the profile it links, every size the card's own srcset offers,
// and - fetched from the page itself, so the same browser session - the
// bytes and pixel size of the smallest offered size at least 200px wide.
// Nothing is resized and no image service is asked (the owner's decision of
// 2026-10-19): a card whose every offered size is over 300 KB or 1,200px is
// marked "oversized" and is not a photograph to record.
//
// Node 22+ (a global WebSocket), no dependencies.
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const ROSTER = 'https://www.naag.org/find-my-ag/';
const args = process.argv.slice(2);
const opt = (name, fallback) => {
  const at = args.indexOf(name);
  return at >= 0 ? args[at + 1] : fallback;
};
const OUT = opt('--out', 'naag_cards.json');
const CHROME = opt('--chrome', process.env.CHROME ||
  'C:/Program Files/Google/Chrome/Application/chrome.exe');
const sleep = ms => new Promise(r => setTimeout(r, ms));

async function connect(url) {
  const ws = new WebSocket(url);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  let next = 0;
  const pending = new Map();
  ws.onmessage = ev => {
    const msg = JSON.parse(ev.data);
    if (msg.id && pending.has(msg.id)) {
      const p = pending.get(msg.id);
      pending.delete(msg.id);
      msg.error ? p.rej(new Error(msg.error.message)) : p.res(msg.result);
    }
  };
  return (method, params = {}, sessionId) => {
    const id = ++next;
    ws.send(JSON.stringify({ id, method, params, sessionId }));
    return new Promise((res, rej) => pending.set(id, { res, rej }));
  };
}

const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'kyc-naag-'));
// Windowed on purpose: see above.
const proc = spawn(CHROME, ['--no-first-run', '--no-default-browser-check', '--disable-extensions',
  '--remote-debugging-port=0', `--user-data-dir=${dir}`, '--window-size=1280,900', 'about:blank'],
{ stdio: 'ignore' });
let port, wsPath;
for (let i = 0; i < 150 && !port; i++) {
  const file = path.join(dir, 'DevToolsActivePort');
  if (fs.existsSync(file)) [port, wsPath] = fs.readFileSync(file, 'utf8').split('\n').map(s => s.trim());
  if (!port) await sleep(100);
}
if (!port) { proc.kill(); throw new Error('Chrome did not start'); }
const send = await connect(`ws://127.0.0.1:${port}${wsPath}`);
try {
  const { targetId } = await send('Target.createTarget', { url: 'about:blank' });
  const { sessionId } = await send('Target.attachToTarget', { targetId, flatten: true });
  const page = (m, p) => send(m, p, sessionId);
  const evaluate = async expression => {
    const r = await page('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
    if (r.exceptionDetails) {
      throw new Error((r.exceptionDetails.exception || {}).description || r.exceptionDetails.text);
    }
    return r.result.value;
  };
  await page('Page.enable');
  await page('Page.navigate', { url: ROSTER });
  // The challenge, when there is one, passes on its own in a window.
  for (let i = 0; i < 60; i++) {
    await sleep(1000);
    const title = await evaluate('document.readyState === "complete" ? document.title : ""')
      .catch(() => '');
    if (/Find my AG/i.test(title)) break;
  }
  const title = await evaluate('document.title').catch(() => '');
  if (!/Find my AG/i.test(title)) throw new Error(`the roster did not open: ${JSON.stringify(title)}`);
  // Every card is lazy: scroll to the end, slowly, twice.
  for (let pass = 0; pass < 2; pass++) {
    const height = await evaluate('document.documentElement.scrollHeight');
    for (let y = 0; y < height; y += 400) {
      await evaluate(`window.scrollTo(0, ${y})`);
      await sleep(250);
    }
  }
  await sleep(2000);
  const cards = await evaluate(`[...document.querySelectorAll('img')].map(img => {
    let card = img, text = '';
    for (let k = 0; k < 6 && card.parentElement; k++) {
      card = card.parentElement;
      text = (card.innerText || '').replace(/\\s+/g, ' ').trim();
      if (/VIEW PROFILE/i.test(text)) break;
    }
    if (!/VIEW PROFILE/i.test(text)) return null;
    const link = [...card.querySelectorAll('a')].map(a => a.href).find(h => /\\/attorney-general\\//.test(h)) || '';
    const offered = (img.getAttribute('srcset') || '').split(',').map(s => s.trim().split(/\\s+/))
      .filter(p => p.length === 2 && /^\\d+w$/.test(p[1])).map(p => [parseInt(p[1]), new URL(p[0], location.href).href]);
    return { words: text, alt: img.alt, src: img.currentSrc || img.src, offered, profile: link };
  }).filter(Boolean)`);
  const read = new Date().toISOString().slice(0, 10);
  for (const card of cards) {
    const sizes = card.offered.slice().sort((a, b) => a[0] - b[0]);
    const pick = (sizes.find(s => s[0] >= 200) || sizes[sizes.length - 1] || [0, card.src])[1];
    card.photo = pick;
    card.weight = await evaluate(`(async () => {
      const r = await fetch(${JSON.stringify(pick)}, { credentials: 'include' });
      if (!r.ok) return { status: r.status };
      const blob = await r.blob();
      const bmp = await createImageBitmap(blob);
      return { status: r.status, bytes: blob.size, width: bmp.width, height: bmp.height, type: blob.type };
    })()`).catch(e => ({ error: String(e) }));
    const w = card.weight || {};
    card.oversized = !!(w.bytes && (w.bytes > 300000 || Math.max(w.width, w.height) > 1200));
    card.read = read;
    console.log((card.oversized ? 'OVERSIZED ' : '') + card.words.replace(/ VIEW PROFILE$/i, '').padEnd(48),
      w.bytes, `${w.width}x${w.height}`, pick);
  }
  fs.writeFileSync(OUT, JSON.stringify({ roster: ROSTER, read, cards }, null, 1));
  console.log(`${cards.length} cards; wrote ${OUT}`);
} finally {
  try { await send('Browser.close'); } catch {}
  proc.kill();
  await sleep(300);
  try { fs.rmSync(dir, { recursive: true, force: true }); } catch {}
}
