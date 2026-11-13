// Shared loader for Actual ledger queries (better-sqlite3, read-only).
// Run inside actual-dash (or any container with better-sqlite3 + the db):
//   docker --context ghost exec actual-dash node /tmp/<script>.mjs
// Schema quirks: `description`=payee id, `transferred_id`=transfer pointer,
// dates are int yyyymmdd, flags `isParent`/`tombstone`.
import Database from '/usr/local/lib/node_modules/@actual-app/cli/node_modules/better-sqlite3/lib/index.js';

export const DB_PATH = process.env.ACTUAL_DB || '/cache/My-Finances-cb746f6/db.sqlite';
export const db = new Database(DB_PATH, { readonly: true });

export const pays = Object.fromEntries(db.prepare('select id,name,transfer_acct from payees').all().map(r => [r.id, r]));
export const cats = Object.fromEntries(db.prepare('select id,name from categories').all().map(r => [r.id, r.name]));
export const catsByName = Object.fromEntries(db.prepare('select id,name from categories').all().map(r => [r.id, r.name]).map(([id, n]) => [n, id]));
export const accs = Object.fromEntries(db.prepare('select id,name,offbudget,closed from accounts').all().map(r => [r.id, r]));

// Artifact/non-consumption filters — a row "is spend" iff this returns true.
export function isSpendRow(t) {
  const a = accs[t.acct];
  if (!a || a.offbudget) return false;
  if (t.transferred_id) return false;
  const p = pays[t.description];
  if (p && (p.transfer_acct || p.name === 'Rebaseline Transfer')) return false;
  if ((t.notes || '').includes('Rebaseline')) return false;
  if (cats[t.category] === 'Starting Balances') return false;
  return true;
}

export function spendRows(where = '') {
  return db.prepare(`select id,date,amount,description payee,category,acct,notes,imported_description ip,transferred_id
    from transactions where tombstone=0 and isParent=0 and amount<0 ${where}`).all().filter(isSpendRow);
}

export const payeeName = t => pays[t.payee]?.name || t.ip || '(none)';
export const cents = n => Math.round(n / 100);
