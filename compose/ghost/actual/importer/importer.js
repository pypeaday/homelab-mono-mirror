// actual-import: drop-folder importer for Actual Budget.
//
// Watches /import/<slug>/ for bank export files (.csv/.ofx/.qfx/.json),
// converts them to Actual's transaction JSON shape, and imports them with
// `actual transactions import --file -` (deduplicates via imported_id).
// Imported files move to /import/_processed/<slug>/, failures to _failed.

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { spawnSync } = require('child_process');

const IMPORT_DIR = process.env.IMPORT_DIR || '/import';
const ACCOUNTS_FILE = process.env.ACCOUNTS_FILE || '/etc/actual-import/accounts.json';
const SWEEP_MS = (parseInt(process.env.IMPORT_SWEEP_SEC || '60', 10)) * 1000;
const DRY_RUN = process.env.DRY_RUN === '1';
const MIN_AGE_MS = 3000; // don't touch files younger than this (still uploading)
const FILE_EXT = /\.(csv|ofx|qfx|json)$/i;

function log(...args) {
  console.log(new Date().toISOString(), ...args);
}

function loadAccounts() {
  try {
    return JSON.parse(fs.readFileSync(ACCOUNTS_FILE, 'utf8'));
  } catch (e) {
    log('ERROR reading accounts file', ACCOUNTS_FILE, e.message);
    return {};
  }
}

// ---------- CSV ----------

function parseCsvRows(text) {
  // RFC4180 tokenizer: returns array of rows (arrays of cell strings)
  const rows = [];
  let row = [], field = '', inQuotes = false, i = 0;
  while (i < text.length) {
    const c = text[i];
    if (inQuotes) {
      if (c === '"') {
        if (text[i + 1] === '"') { field += '"'; i += 2; continue; }
        inQuotes = false; i++; continue;
      }
      field += c; i++; continue;
    }
    if (c === '"') { inQuotes = true; i++; continue; }
    if (c === ',' || c === ';' || c === '\t') { row.push(field); field = ''; i++; continue; }
    if (c === '\n' || c === '\r') {
      if (c === '\r' && text[i + 1] === '\n') i++;
      row.push(field); field = '';
      if (row.length > 1 || row[0] !== '') rows.push(row);
      row = []; i++; continue;
    }
    field += c; i++;
  }
  if (field !== '' || row.length) { row.push(field); rows.push(row); }
  return rows.filter(r => r.some(c => c.trim() !== ''));
}

const MONTHS = {
  jan: 1, feb: 2, mar: 3, apr: 4, may: 5, jun: 6,
  jul: 7, aug: 8, sep: 9, oct: 10, nov: 11, dec: 12,
};

function parseDate(s) {
  s = s.trim();
  let m;
  if ((m = s.match(/^(\d{4})[-\/.](\d{1,2})[-\/.](\d{1,2})/))) {
    return `${m[1]}-${m[2].padStart(2, '0')}-${m[3].padStart(2, '0')}`;
  }
  if ((m = s.match(/^(\d{1,2})[-\/.](\d{1,2})[-\/.](\d{2,4})/))) {
    const yr = m[3].length === 2 ? '20' + m[3] : m[3];
    return `${yr}-${m[1].padStart(2, '0')}-${m[2].padStart(2, '0')}`;
  }
  if ((m = s.match(/^(\d{1,2})\s*[-\s]\s*([A-Za-z]{3})[a-z]*[-\s,]+\s*(\d{2,4})/))) {
    const mon = MONTHS[m[2].slice(0, 3).toLowerCase()];
    if (mon) {
      const yr = m[3].length === 2 ? '20' + m[3] : m[3];
      return `${yr}-${String(mon).padStart(2, '0')}-${m[1].padStart(2, '0')}`;
    }
  }
  if ((m = s.match(/^([A-Za-z]{3})[a-z]*\s+(\d{1,2}),?\s+(\d{4})/))) {
    const mon = MONTHS[m[1].slice(0, 3).toLowerCase()];
    if (mon) return `${m[3]}-${String(mon).padStart(2, '0')}-${m[2].padStart(2, '0')}`;
  }
  return null;
}

function parseAmountCents(s) {
  s = s.trim();
  if (!s) return null;
  let neg = false;
  if (/^\(.*\)$/.test(s)) { neg = true; s = s.slice(1, -1); } // (123.45) = -123.45
  s = s.replace(/[$,\s]/g, '');
  if (s.endsWith('-')) { neg = true; s = s.slice(0, -1); }
  if (s.startsWith('-')) { neg = !neg; s = s.slice(1); } // explicit minus flips paren-neg handling
  const n = parseFloat(s);
  if (Number.isNaN(n)) return null;
  return Math.round(n * 100) * (neg ? -1 : 1);
}

function colIdx(headers, patterns, exclude = []) {
  for (const p of patterns) {
    const idx = headers.findIndex(h => p.test(h) && !exclude.some(e => e.test(h)));
    if (idx >= 0) return idx;
  }
  return -1;
}

function headerCols(headers) {
  return {
    iDate: colIdx(headers, [/posted.*date|posting.*date|post date/i, /date|datetime/i]),
    iAmount: colIdx(headers, [/^amount$/, /amount \(total\)|^amount|total/i], [/balance|available|beginning|ending|tip|tax|fee/i]),
    iDebit: colIdx(headers, [/debit|withdrawal/i], [/type/i]),
    iCredit: colIdx(headers, [/credit|deposit/i], [/type/i]),
  };
}

// Find the header row — banks like Venmo pad the top with preamble rows.
function findHeaderRow(rows) {
  for (let i = 0; i < Math.min(rows.length, 10); i++) {
    const headers = rows[i].map(h => h.trim().toLowerCase());
    const c = headerCols(headers);
    if (c.iDate >= 0 && (c.iAmount >= 0 || c.iDebit >= 0 || c.iCredit >= 0)) return i;
  }
  return -1;
}

function csvToTransactions(text, slug, opts) {
  const rows = parseCsvRows(text);
  if (rows.length < 2) return { txns: [], skipped: rows.length };
  const headerRow = findHeaderRow(rows);
  if (headerRow < 0) return { txns: [], skipped: rows.length, err: 'no header row found' };
  const headers = rows[headerRow].map(h => h.trim().toLowerCase());
  const { iDate, iAmount, iDebit, iCredit } = headerCols(headers);
  const iPayee = colIdx(headers, [/description|payee|merchant|name|payee.*name/i], [/type|category|check|account/i]);
  const iNotes = colIdx(headers, [/memo|note|extended.*detail/i]);
  const iStatus = colIdx(headers, [/status/i]);
  const iId = colIdx(headers, [/^(transaction )?id$|^fitid$|^reference( number)?$|^ref/i]);
  const iTo = colIdx(headers, [/^to$|^destination/i]);
  const iFrom = colIdx(headers, [/^from$|^funding source/i]);
  const self = (opts.self_names || []).map(s => s.toLowerCase());
  const skipped0 = headerRow;

  const txns = [];
  let skipped = 0;
  for (let r = headerRow + 1; r < rows.length; r++) {
    const cells = rows[r];
    // skip pending/scheduled rows — they'll re-export as posted later
    if (iStatus >= 0 && /pend|schedul|process/i.test(cells[iStatus] || '')) { skipped++; continue; }
    const date = parseDate(cells[iDate] || '');
    if (!date) { skipped++; continue; }
    // per-account floor: don't re-import history that predates the last txn
    if (opts.since && date < opts.since) { skipped++; continue; }

    let cents = null;
    if (iAmount >= 0) {
      cents = parseAmountCents(cells[iAmount]);
    } else {
      const d = iDebit >= 0 ? parseAmountCents(cells[iDebit]) : null;
      const c = iCredit >= 0 ? parseAmountCents(cells[iCredit]) : null;
      if (d != null) cents = -Math.abs(d);
      else if (c != null) cents = Math.abs(c);
    }
    if (cents == null) { skipped++; continue; }
    if (opts.invert) cents = -cents;

    let payee = iPayee >= 0 ? (cells[iPayee] || '').trim() : '';
    if (!payee && (iTo >= 0 || iFrom >= 0)) {
      // venmo-style: counterparty = the From/To that isn't the account holder
      payee = [cells[iTo], cells[iFrom]]
        .map(v => (v || '').trim())
        .find(v => v && !self.includes(v.toLowerCase())) || '';
    }
    const notes = iNotes >= 0 ? (cells[iNotes] || '').trim() : '';
    const importedId = (iId >= 0 && (cells[iId] || '').trim())
      ? 'id-' + cells[iId].trim()
      : 'csv-' + crypto.createHash('sha256').update(slug + '|' + cells.join('|')).digest('hex').slice(0, 32);

    const t = { date, amount: cents, imported_id: importedId };
    if (payee) { t.payee_name = payee; t.imported_payee = payee; }
    if (notes) t.notes = notes;
    txns.push(t);
  }
  return { txns, skipped: skipped + skipped0 };
}

// ---------- OFX / QFX ----------

function ofxField(block, tag) {
  const m = block.match(new RegExp('<' + tag + '>([^<\\r\\n]*)', 'i'));
  return m ? m[1].trim() : null;
}

function ofxToTransactions(text, slug, opts) {
  const blocks = text.split(/<STMTTRN>/i).slice(1);
  const txns = [];
  let skipped = 0;
  for (let raw of blocks) {
    const end = raw.search(/<\/STMTTRN>/i);
    if (end >= 0) raw = raw.slice(0, end);
    const dtposted = ofxField(raw, 'DTPOSTED');
    const trnamt = ofxField(raw, 'TRNAMT');
    if (!dtposted || trnamt == null) { skipped++; continue; }
    const y = dtposted.slice(0, 4), mo = dtposted.slice(4, 6), d = dtposted.slice(6, 8);
    const date = `${y}-${mo}-${d}`;
    if (opts.since && date < opts.since) { skipped++; continue; }
    const cents = Math.round(parseFloat(trnamt) * 100);
    if (Number.isNaN(cents)) { skipped++; continue; }
    const name = ofxField(raw, 'NAME') || '';
    const memo = ofxField(raw, 'MEMO') || '';
    const fitid = ofxField(raw, 'FITID');
    const t = {
      date,
      amount: cents,
      imported_id: 'ofx-' + (fitid || crypto.createHash('sha256').update(raw).digest('hex').slice(0, 32)),
    };
    const payee = name || memo;
    if (payee) { t.payee_name = payee; t.imported_payee = payee; }
    if (memo && memo !== payee) t.notes = memo;
    txns.push(t);
  }
  return { txns, skipped };
}

// ---------- driver ----------

function fileToTransactions(file, slug, opts) {
  const text = fs.readFileSync(file, 'utf8');
  const ext = path.extname(file).toLowerCase();
  if (ext === '.json') {
    const data = JSON.parse(text);
    return { txns: Array.isArray(data) ? data : [data], skipped: 0 };
  }
  if (ext === '.ofx' || ext === '.qfx') return ofxToTransactions(text, slug, opts);
  return csvToTransactions(text, slug, opts);
}

function importBatch(accountId, txns, slug) {
  const args = ['transactions', 'import', '--account', accountId, '--file', '-'];
  if (DRY_RUN) args.push('--dry-run');
  const res = spawnSync('actual', args, {
    input: JSON.stringify(txns),
    encoding: 'utf8',
    env: process.env,
    maxBuffer: 32 * 1024 * 1024,
  });
  return res;
}

function ensureDir(p) { fs.mkdirSync(p, { recursive: true }); }

function sweep() {
  const accounts = loadAccounts();
  let entries;
  try {
    entries = fs.readdirSync(IMPORT_DIR, { withFileTypes: true });
  } catch (e) {
    log('ERROR reading import dir', e.message);
    return;
  }

  // gather files per account
  const pending = new Map(); // slug -> [{file, txns}]
  for (const ent of entries) {
    if (!ent.isDirectory() || ent.name.startsWith('_') || ent.name.startsWith('.')) continue;
    const slug = ent.name;
    const acct = accounts[slug];
    const dir = path.join(IMPORT_DIR, slug);
    let files;
    try {
      files = fs.readdirSync(dir).filter(f => FILE_EXT.test(f));
    } catch { continue; }
    const now = Date.now();
    for (const f of files) {
      const fp = path.join(dir, f);
      let st;
      try { st = fs.statSync(fp); } catch { continue; }
      if (!st.isFile() || now - st.mtimeMs < MIN_AGE_MS) continue;
      if (!acct) {
        moveTo(fp, path.join(IMPORT_DIR, '_failed', slug), 'no account mapping for dir "' + slug + '" in accounts.json');
        continue;
      }
      let parsed;
      try {
        parsed = fileToTransactions(fp, slug, acct);
      } catch (e) {
        moveTo(fp, path.join(IMPORT_DIR, '_failed', slug), 'parse error: ' + e.message);
        continue;
      }
      if (!parsed.txns.length) {
        moveTo(fp, path.join(IMPORT_DIR, '_failed', slug),
          'no transactions parsed' + (parsed.err ? ' (' + parsed.err + ')' : '') +
          (parsed.skipped ? `, skipped ${parsed.skipped} rows` : ''));
        continue;
      }
      if (!pending.has(slug)) pending.set(slug, { acct, items: [] });
      pending.get(slug).items.push({ file: fp, name: f, txns: parsed.txns, skipped: parsed.skipped });
    }
  }

  // one CLI call per account with all parsed txns merged
  for (const [slug, batch] of pending) {
    const all = batch.items.flatMap(i => i.txns);
    log(`importing ${all.length} txn(s) into "${slug}" (${batch.items.length} file(s))${DRY_RUN ? ' [dry-run]' : ''}`);
    const res = importBatch(batch.acct.id, all, slug);
    const ok = res.status === 0;
    if (res.stderr && res.stderr.trim()) log(`[${slug}] stderr:`, res.stderr.trim().slice(0, 800));
    if (res.stdout && res.stdout.trim()) {
      try {
        const j = JSON.parse(res.stdout);
        log(`[${slug}] added=${(j.added || []).length} updated=${(j.updated || []).length} errors=${(j.errors || []).length}`);
        if ((j.errors || []).length) log(`[${slug}] errors:`, JSON.stringify(j.errors).slice(0, 800));
      } catch {
        log(`[${slug}]`, res.stdout.trim().slice(0, 800));
      }
    }
    for (const item of batch.items) {
      if (ok) {
        const destDir = path.join(IMPORT_DIR, '_processed', slug);
        try {
          ensureDir(destDir);
          fs.renameSync(item.file, path.join(destDir, new Date().toISOString().replace(/[:.]/g, '-') + '-' + item.name));
          log(`[${slug}] imported ${item.name} (${item.txns.length} txns${item.skipped ? `, ${item.skipped} skipped` : ''})`);
        } catch (e) {
          log(`[${slug}] ERROR archiving ${item.name}: ${e.message}`);
        }
      } else {
        moveTo(item.file, path.join(IMPORT_DIR, '_failed', slug), 'actual import failed: ' + (res.stderr || res.error || 'exit ' + res.status));
      }
    }
  }
}

function moveTo(file, destDir, errMsg) {
  const base = path.basename(file);
  const dest = path.join(destDir, new Date().toISOString().replace(/[:.]/g, '-') + '-' + base);
  try {
    ensureDir(destDir);
    fs.renameSync(file, dest);
    if (errMsg) fs.writeFileSync(dest + '.err', errMsg + '\n');
    log(`moved ${base} -> ${dest}${errMsg ? ' (' + errMsg + ')' : ''}`);
  } catch (e) {
    log('ERROR moving', file, e.message);
  }
}

log(`actual-import starting: dir=${IMPORT_DIR} sweep=${SWEEP_MS / 1000}s dryRun=${DRY_RUN}`);
sweep();
setInterval(sweep, SWEEP_MS);
