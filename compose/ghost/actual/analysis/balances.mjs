// Per-account balances + transfer-pointer health. Usage:
//   docker --context ghost exec actual-dash node /tmp/analysis/balances.mjs
import { db, accs, cents } from './lib.mjs';

let anyDangling = 0;
for (const r of db.prepare(`select a.id, a.name, a.offbudget, coalesce(sum(t.amount),0) s
    from accounts a left join transactions t on t.acct=a.id and t.tombstone=0
    group by a.id order by a.offbudget, a.name`).all())
  console.log(`  ${(r.offbudget ? '(off) ' : '')}${r.name.padEnd(24)} ${(r.s / 100).toFixed(2).padStart(12)}`);

for (const t of db.prepare(`select count(*) n from transactions where tombstone=0 and transferred_id is not null
    and transferred_id not in (select id from transactions where tombstone=0)`).all())
  anyDangling = t.n;
console.log(`\ndangling transfer pointers: ${anyDangling}`);
