// Monthly spend by category (transfers + artifacts excluded).
// Optional args: START=yyyymmdd END=yyyymmdd env or argv[2], argv[3]
//   docker --context ghost exec -e START=20260401 -e END=20261001 actual-dash node /tmp/analysis/spend-by-cat.mjs
import { spendRows, cats, cents } from './lib.mjs';

const start = process.env.START || process.argv[2] || '0';
const end = process.env.END || process.argv[3] || '99999999';
const rows = spendRows(`and date>=${+start} and date<${+end}`);
const byCat = {}, byMonth = {};
for (const t of rows) {
  const c = cats[t.category] || '(uncategorized)';
  const m = String(t.date).slice(0, 6);
  byCat[c] = (byCat[c] || 0) - t.amount;
  (byMonth[m] = byMonth[m] || {})[c] = (byMonth[m][c] || 0) - t.amount;
}
const tot = Object.values(byCat).reduce((s, x) => s + x, 0);
const months = Object.keys(byMonth);
console.log(`spend ${start}..${end}: $${cents(tot)} across ${months.length} month(s)`);
console.log(`\nmonthly totals:`);
for (const m of months) {
  const mt = Object.values(byMonth[m]).reduce((s, x) => s + x, 0);
  console.log(`  ${m}  $${cents(mt).toLocaleString().padStart(8)}`);
}
console.log(`\nby category:`);
for (const [c, v] of Object.entries(byCat).sort((a, b) => b[1] - a[1]).slice(0, 25))
  console.log(`  ${c.padEnd(22)} $${cents(v).toLocaleString().padStart(8)}${months.length > 1 ? `  ($${Math.round(cents(v) / months.length)}/mo)` : ''}`);
