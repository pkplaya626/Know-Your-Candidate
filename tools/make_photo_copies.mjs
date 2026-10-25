#!/usr/bin/env node
// Make smaller copies of portraits in a headless Chrome of our own (rule 101).
//
//   node tools/make_photo_copies.mjs --jobs JOBS.json --out REPORT.json
//
// JOBS.json: {"quality": 0.86, "deadline": <Unix ms or null>,
//             "jobs": [{"id", "in", "out", "box": [w, h]}]}
// - no job is started after "deadline": each is reported "out of time";
// - "in" is a downloaded original, "out" where the copy is written;
// - "box" is the size, in device pixels, the copy must cover: the largest
//   CSS box any page draws that kind of portrait in, times three (phones
//   are DPR 3).
// REPORT.json: {"chrome": "<version>", "quality": q, "results": {id:
//   {"ok", "width", "height", "srcWidth", "srcHeight", "bytes", "error"}}}
//
// Each original is drawn once onto a canvas: the browser's own decoder and
// its EXIF orientation (createImageBitmap's "from-image"), white under any
// transparency, image smoothing at "high", scaled down - never up - so the
// copy just covers the box, and exported as JPEG. Nothing is cropped,
// retouched or sharpened: the copy is the photograph, smaller.
//
// `python build_profile_site.py photocopies` writes the jobs and reads the
// report (kyc/photocopies.py). No dependencies: Node's own WebSocket (Node
// 22 or later) speaks the DevTools protocol to Chrome, found from $CHROME,
// then the usual install paths, as tools/read_court_pages.mjs finds it.
// The originals are served to that Chrome from 127.0.0.1 by this script, so
// the canvas is never tainted and nothing leaves the machine.
//
// Exit status: 0 when the maker ran (each job's outcome is in the report);
// 3 when there is no Chrome or no WebSocket to drive it.
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';

const NO_BROWSER = 3;
const JOB_TIMEOUT_MS = 60000;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function args(argv) {
  const out = { jobs: null, out: null };
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === '--jobs') out.jobs = argv[++i];
    else if (argv[i] === '--out') out.out = argv[++i];
    else throw new Error(`unknown argument: ${argv[i]}`);
  }
  if (!out.jobs || !out.out) throw new Error('--jobs FILE and --out FILE are required');
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
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'kyc-photo-chrome-'));
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
    let next = 0;
    const client = {
      send(method, params = {}, sessionId) {
        const id = ++next;
        ws.send(JSON.stringify(sessionId ? { id, method, params, sessionId } : { id, method, params }));
        return new Promise((res, rej) => pending.set(id, { res, rej, method }));
      },
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
      }
    };
  });
}

/** Serve the page and each job's original, by its index, on 127.0.0.1. */
function serve(jobs) {
  const server = http.createServer((req, res) => {
    const m = /^\/f\/(\d+)$/.exec(req.url || '');
    if (req.url === '/') {
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
      res.end('<!doctype html><title>copies</title>');
      return;
    }
    if (!m || !jobs[Number(m[1])]) {
      res.writeHead(404);
      res.end();
      return;
    }
    fs.readFile(jobs[Number(m[1])].in, (err, data) => {
      if (err) {
        res.writeHead(404);
        res.end();
        return;
      }
      res.writeHead(200, { 'Content-Type': 'application/octet-stream' });
      res.end(data);
    });
  });
  return new Promise((resolve) => server.listen(0, '127.0.0.1', () => resolve(server)));
}

// Runs in the page: one original, drawn smaller. Returns the JPEG as base64.
const DRAW = `async (index, boxW, boxH, quality) => {
  const response = await fetch('/f/' + index);
  if (!response.ok) throw new Error('original not served: ' + response.status);
  const bitmap = await createImageBitmap(await response.blob(), { imageOrientation: 'from-image' });
  const sw = bitmap.width, sh = bitmap.height;
  // Just cover the box, as the page's object-fit: cover draws it; never up.
  const scale = Math.min(1, Math.max(boxW / sw, boxH / sh));
  const w = Math.max(1, Math.round(sw * scale)), h = Math.max(1, Math.round(sh * scale));
  const canvas = new OffscreenCanvas(w, h);
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, w, h);
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = 'high';
  ctx.drawImage(bitmap, 0, 0, w, h);
  bitmap.close();
  const blob = await canvas.convertToBlob({ type: 'image/jpeg', quality });
  const bytes = new Uint8Array(await blob.arrayBuffer());
  let text = '';
  for (let i = 0; i < bytes.length; i += 0x8000) {
    text += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
  }
  return { w, h, sw, sh, type: blob.type, data: btoa(text) };
}`;

async function main() {
  const { jobs: jobsPath, out } = args(process.argv.slice(2));
  const spec = JSON.parse(fs.readFileSync(jobsPath, 'utf8'));
  const jobs = spec.jobs || [];
  const quality = Number(spec.quality);
  // Unix milliseconds after which no job is started (the run's time budget).
  const deadline = Number(spec.deadline) || 0;
  if (!(quality > 0 && quality <= 1)) throw new Error('quality must be in (0, 1]');
  if (typeof WebSocket !== 'function') {
    console.error('[error] this Node has no WebSocket; the maker needs Node 22 or later');
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
  const server = await serve(jobs);
  const report = { chrome: '', quality, results: {} };
  try {
    const { client } = browser;
    report.chrome = (await client.send('Browser.getVersion')).product;
    const { targetId } = await client.send('Target.createTarget', { url: 'about:blank' });
    const { sessionId } = await client.send('Target.attachToTarget', { targetId, flatten: true });
    await client.send('Page.enable', {}, sessionId);
    await client.send('Page.navigate', { url: `http://127.0.0.1:${server.address().port}/` }, sessionId);
    await sleep(500);
    for (const [index, job] of jobs.entries()) {
      const result = { ok: false, width: 0, height: 0, srcWidth: 0, srcHeight: 0, bytes: 0, error: '' };
      if (deadline && Date.now() > deadline) {
        // The run's budget is spent: the rest wait for the next run.
        result.error = 'out of time';
        report.results[job.id] = result;
        continue;
      }
      try {
        const [boxW, boxH] = job.box;
        const expression = `(${DRAW})(${index}, ${Number(boxW)}, ${Number(boxH)}, ${quality})`;
        const call = client.send('Runtime.evaluate',
          { expression, awaitPromise: true, returnByValue: true }, sessionId);
        let timer;
        const answer = await Promise.race([call, new Promise((_, reject) => {
          timer = setTimeout(() => reject(new Error('timed out')), JOB_TIMEOUT_MS);
        })]).finally(() => clearTimeout(timer));
        if (answer.exceptionDetails) {
          throw new Error((answer.exceptionDetails.exception || {}).description
            || answer.exceptionDetails.text || 'draw failed');
        }
        const v = answer.result.value;
        if (v.type !== 'image/jpeg') throw new Error(`Chrome wrote ${v.type}, not a JPEG`);
        const data = Buffer.from(v.data, 'base64');
        fs.writeFileSync(job.out, data);
        Object.assign(result, { ok: true, width: v.w, height: v.h, srcWidth: v.sw, srcHeight: v.sh,
                                bytes: data.length });
      } catch (exc) {
        result.error = String(exc.message || exc).split('\n')[0];
      }
      report.results[job.id] = result;
    }
    await client.send('Target.closeTarget', { targetId }).catch(() => {});
  } finally {
    server.close();
    await browser.close();
  }
  fs.writeFileSync(out, JSON.stringify(report, null, 1) + '\n', 'utf8');
  const made = Object.values(report.results).filter((r) => r.ok).length;
  console.log(`  ${made} of ${jobs.length} copies made in ${report.chrome}`);
  return 0;
}

main().then((code) => { process.exitCode = code; }, (exc) => {
  console.error(`[error] ${exc.message}`);
  process.exitCode = 2;
});
