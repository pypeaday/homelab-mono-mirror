// Top payees inside one category (default: General), for categorization passes.
//   docker --context ghost exec -e CAT="General" actual-dash node /tmp/analysis/cat-payees.mjs
import { spendRows, catsByName, payeeName, cents } from './lib.mjs';

const name = process.env.CAT || 'General';
const cid = catsByName[name];
if (!cid) { console.error(`no category "${name}"`); process.exit(1); }
const rows = spendRows(`and category='${cid}'`);
const agg = {};
for (const t of rows) {
  const p = payeeName(t);
  agg[p] = (agg[p] || 0) + Math.abs(t.amount);
}
console.log(`${name}: ${rows.length} rows, $${cents(Object.values(agg).reduce((s, x) => s + x, 0))}`);
for (const [p, v] of Object.entries(agg).sort((a, b) => b[1] - a[1]).slice(0, 30))
  console.log(`  ${p.slice(0, 45).padEnd(45)} $${cents(v).toLocaleString().padStart(8)}`);
