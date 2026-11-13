// actual-dash: read-only dashboard for Actual Budget.
// Serves /index.html + /data.json (aggregates refreshed every REFRESH_MIN).
import * as http from 'node:http';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const API = 'file:///usr/local/lib/node_modules/@actual-app/cli/node_modules/@actual-app/api/dist/index.js';
const PORT = parseInt(process.env.DASH_PORT || '3000', 10);
const REFRESH_MS = (parseInt(process.env.REFRESH_MIN || '30', 10)) * 60 * 1000;
const INDEX = join(dirname(fileURLToPath(import.meta.url)), 'index.html');

let cached = { generated: null, months: [], periods: {}, catMonthly: {}, health: {} };
let refreshing = false, lastError = null;

const cents = n => Math.round(n / 100);
const ym = d => d.slice(0, 7);

function monthList(n) {
  const out = [], d = new Date();
  d.setDate(1);
  for (let i = n - 1; i >= 0; i--) {
    const t = new Date(d.getFullYear(), d.getMonth() - i, 1);
    out.push(`${t.getFullYear()}-${String(t.getMonth() + 1).padStart(2, '0')}`);
  }
  return out;
}

async function refresh() {
  if (refreshing) return;
  refreshing = true;
  const api = await import(API);
  try {
    await api.init({ dataDir: '/cache', serverURL: process.env.ACTUAL_SERVER_URL, password: process.env.ACTUAL_PASSWORD });
    await api.downloadBudget(process.env.ACTUAL_SYNC_ID);

    const [accounts, categories, payees] = await Promise.all([api.getAccounts(), api.getCategories(), api.getPayees()]);
    const acct = Object.fromEntries(accounts.map(a => [a.id, a]));
    const cat = Object.fromEntries(categories.map(c => [c.id, c.name]));
    const pay = Object.fromEntries(payees.map(p => [p.id, p]));
    const onBudget = new Set(accounts.filter(a => !a.offbudget && !a.closed).map(a => a.id));
    const isTransfer = t => !!t.transfer_id || !!(pay[t.payee] && pay[t.payee].transfer_acct) || pay[t.payee]?.name === 'Rebaseline Transfer';

    const txns = [];
    for (const a of onBudget) txns.push(...await api.getTransactions(a, '2025-01-01', '2030-01-01'));
    const rows = txns.filter(t => !isTransfer(t));

    const months = monthList(13);
    const mAgg = Object.fromEntries(months.map(m => [m, { m, in: 0, out: 0 }]));
    for (const t of rows) {
      const m = mAgg[ym(t.date)];
      if (!m) continue;
      if (t.amount < 0) m.out -= t.amount; else m.in += t.amount;
    }
    for (const m of months) { mAgg[m].in = cents(mAgg[m].in); mAgg[m].out = cents(mAgg[m].out); mAgg[m].net = mAgg[m].in - mAgg[m].out; }

    const periods = {};
    const now = new Date();
    const startOfYear = `${now.getFullYear()}-01-01`;
    const monthsAgo = n => { const d = new Date(now.getFullYear(), now.getMonth() - n + 1, 1); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-01`; };
    const ranges = { ytd: startOfYear, m3: monthsAgo(3), m6: monthsAgo(6), m12: monthsAgo(12), all: '2000-01-01' };
    for (const [k, since] of Object.entries(ranges)) {
      const sel = rows.filter(t => t.date >= since);
      const agg = { in: 0, out: 0, cats: {}, payees: {}, income: {} };
      for (const t of sel) {
        const name = pay[t.payee]?.name || '(no payee)';
        if (t.amount < 0) {
          agg.out -= t.amount;
          agg.payees[name] = (agg.payees[name] || 0) - t.amount;
          const c = t.category ? cat[t.category] || '(other)' : '(uncategorized)';
          agg.cats[c] = (agg.cats[c] || 0) - t.amount;
        } else {
          agg.in += t.amount;
          agg.income[name] = (agg.income[name] || 0) + t.amount;
        }
      }
      const top = o => Object.entries(o).sort((a, b) => b[1] - a[1]).slice(0, 25).map(([n, v]) => [n, cents(v)]);
      periods[k] = { in: cents(agg.in), out: cents(agg.out), net: cents(agg.in - agg.out), cats: top(agg.cats), payees: top(agg.payees), income: top(agg.income) };
    }

    // top-8 spend categories (ytd) monthly trend
    const top8 = periods.ytd.cats.filter(([n]) => n !== '(uncategorized)').slice(0, 8).map(([n]) => n);
    const catMonthly = Object.fromEntries(top8.map(c => [c, months.map(() => 0)]));
    for (const t of rows) {
      if (t.amount >= 0 || !t.category) continue;
      const c = cat[t.category], i = months.indexOf(ym(t.date));
      if (c && catMonthly[c] && i >= 0) catMonthly[c][i] -= t.amount;
    }
    for (const c of top8) catMonthly[c] = catMonthly[c].map(cents);

    // burn structure: fixed floor / giving / variable, per month
    const FIXED = new Set(['Housing', 'Bills', 'Bills (Flexible)', 'Car Payment', 'Student Loans', 'Childcare', 'Valor', 'Regular Deduction', 'Medical']);
    const GIVING = new Set(['Deductable', 'Not Deductable']);
    const SKIP = new Set(['Savings', 'Bonus Savings', '529s', "Girl's UTMAs", 'Abri - Individual', 'Starting Balances', 'Paycheck', 'Tax Refund', 'Bonus']);
    const structure = months.map(() => ({ m: '', fixed: 0, giving: 0, variable: 0 }));
    for (const t of rows) {
      if (t.amount >= 0) continue;
      const i = months.indexOf(ym(t.date));
      if (i < 0) continue;
      const c = cat[t.category] || '(uncategorized)';
      if (SKIP.has(c)) continue;
      if (FIXED.has(c)) structure[i].fixed -= t.amount;
      else if (GIVING.has(c)) structure[i].giving -= t.amount;
      else structure[i].variable -= t.amount;
    }
    for (const [i, s] of structure.entries()) { s.m = months[i]; s.fixed = cents(s.fixed); s.giving = cents(s.giving); s.variable = cents(s.variable); }

    const uncat = rows.filter(t => !t.category);
    const balances = [];
    for (const a of onBudget) balances.push([acct[a].name, cents(await api.getAccountBalance(a))]);
    balances.sort((x, y) => y[1] - x[1]);

    cached = {
      generated: new Date().toISOString(),
      months: months.map(m => mAgg[m]),
      periods, catMonthly, structure,
      health: {
        uncat: uncat.length,
        uncatNet: cents(uncat.reduce((s, t) => s + Math.abs(t.amount), 0)),
        latestTxn: rows.reduce((m, t) => t.date > m ? t.date : m, ''),
        balances,
      },
    };
    lastError = null;
  } catch (e) {
    lastError = e.message;
    console.error(new Date().toISOString(), 'refresh failed:', e.message);
  } finally {
    try { await api.shutdown(); } catch {}
    refreshing = false;
  }
}

http.createServer((req, res) => {
  if (req.url === '/data.json') {
    res.writeHead(200, { 'content-type': 'application/json', 'cache-control': 'no-store' });
    res.end(JSON.stringify({ ...cached, error: lastError }));
  } else if (req.url === '/healthz') {
    res.writeHead(cached.generated ? 200 : 503); res.end('ok');
  } else {
    res.writeHead(200, { 'content-type': 'text/html; charset=utf-8' });
    res.end(readFileSync(INDEX, 'utf8'));
  }
}).listen(PORT, () => console.log(`actual-dash listening :${PORT}`));

refresh();
setInterval(refresh, REFRESH_MS);
