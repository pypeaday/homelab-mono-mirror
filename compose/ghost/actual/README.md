# Actual

[docs](https://actualbudget.org/)

I use this as a migration from YNAB which served us well for several years.

## Services

- `actual_server` — the Actual Budget sync server/web app (actual.paynepride.com).
- `actual_import` — drop-folder importer. Converts bank exports and pushes them
  in with the official `@actual-app/cli` (`transactions import`, dedup on
  `imported_id`).

## Importing bank transactions

Drop exports into the per-account folder on ghost:

```
scp chase-jan.csv ghost:/tank/encrypted/docker/actual/import-drop/chase-amazon/
```

Folders (mapped to account IDs in `importer/accounts.json`):

| Folder                  | Account             |
|-------------------------|---------------------|
| `cefcu`                 | cefcu               |
| `cefcu-savings`         | cefcu - savings     |
| `chase-amazon`          | chase-amazon        |
| `fox-communities`       | fox-communities     |
| `capital-1`             | capital-1           |
| `bam-allegiant-allways` | bam-allegiant-allways |
| `venmo`                 | Venmo               |

Supported files: `.csv`, `.ofx`/`.qfx`, `.json` (already in Actual transaction
shape). The importer sweeps every 60s, batches per account, then moves files to
`_processed/<slug>/` (success) or `_failed/<slug>/` + a `.err` note.

CSV needs a header row with a date column, an `Amount` column (signed) or
`Debit`/`Credit` pair, and a description/payee column. Handles `MM/DD/YYYY`,
`YYYY-MM-DD`, `05-Jan-2026`, `Jan 5, 2026`, `$`, and `(paren)` negatives.
If a bank exports expenses as positive (Amex-style), add `"invert": true` to
that account in `importer/accounts.json`. Each entry also supports:
`"since"` (YYYY-MM-DD floor — older rows are skipped; set to the day after
the account's latest txn to avoid dupes on historical exports),
`"self_names"` (for Venmo-style From/To files — the name that means "me").

Logs: `docker --context ghost logs actual-import`

## Auto-categorization

Two-stage rule setup (Oct 2026 cleanup): ~40 `pre`-stage rules map
`imported_payee contains X` → canonical payee + category; the user's ~270
`payee is Y` → category rules then apply. Covers the top ~35 merchants —
new store-number variants (`ALDI 99999`, `KWIK-TRIP #n`) categorize at
import instead of spawning new payees.

Gotchas found while doing it:

- Actual **auto-creates `set category = null` rules** when a txn is saved
  uncategorized — they silently strip categories on later imports. If a
  payee won't stay categorized, check for a contradicting null rule
  (`rules list` | grep for `"value": null` on category actions) and delete it.
- Instacart strings poison substring terms (`IC* INSTACART*ALDI` contains
  `ALDI`) — contested terms need a `doesNotContain INSTACART` guard.
- Payee merging is one-shot `payees merge --target <id> --ids <a,b,c>` —
  cluster by normalized stem (strip `ACH TRANSACTION`/`PWP`/`POS PURCHASE`
  prefixes, store numbers, city/address tails, truncation variants).
- For bulk mutations skip the per-call CLI (each run loads the whole ~55MB
  budget): run a node script inside the `actual-import` container against
  `@actual-app/cli/node_modules/@actual-app/api/dist/index.js` — env vars
  are already set in that container, one `downloadBudget` then loop.
- Per-order payees (`AMAZON MKTPL*XYZ123`, `SPOTIFY P4XX`) spawn endless
  one-off payees — the `AMAZON`/`SPOTIFY` contains-rules catch them now, but
  already-created payees need a merge pass when they accumulate.

## Transfers (Oct 2026)

Card payments and Venmo funding pulls are linked as real transfers so
payment legs don't double-count as spend+income:

- `updateTransaction(id, {payee: <dest transfer-payee id>, transfer_id:
  <counterpart id>})` links an **existing pair** — `updateTransfer` fills the
  counterpart's payee/amount itself, then a second update sets
  `counterpart.transfer_id` back (the link is two one-way pointers).
- Same call **without** `transfer_id` runs `addTransfer` and *creates* the
  counterpart — used for the cefcu→venmo ACH pulls (Venmo statements omit
  bank-funding inflows, so the +X rows were auto-created on venmo).
- Actual's importer can **self-link** a same-account pair (chase/cap1 CSVs
  each produced a real +X inflow plus a phantom -X/+X mirror pair linked to
  each other). The real payment pair is usually already correctly linked;
  the self-pair is pure noise.
- **Deleting a transfer-payee txn can REGENERATE its counterpart** — the
  transfer engine "completes" broken links by spawning a mirror row (same
  account, flipped sign, `transfer_id` → the dead row). The reliable kill:
  first `updateTransaction(id, {payee: <normal payee>, transfer_id: null})`
  to strip its transfer nature, *then* `deleteTransaction`. Re-check for
  spawns after every delete.
- **Only link never-before-linked txns.** Calling `updateTransaction` with
  `transfer_id` on a txn that already has transfer history (or a *self*
  transfer payee) migrates it to the other account and/or spawns mirrors.
  **Imported legs duplicate too**: pointing an imported (CSV/`imported_id`)
  row at an existing counterpart keeps the original AND spawns a mirror
  copy with the same pointer — the row receiving the pointer must be
  freshly created via `addTransactions`. If a link is contaminated,
  strip+delete the row, re-create it fresh, then set
  `{payee: <dest transfer-payee>, transfer_id: <counterpart>}` + the
  reciprocal pointer in one pass. Verify no same-pointer dupes remain.
- Deleting a *linked* txn cascades to its counterpart — when fixing venmo,
  deleting the venmo-side inflow legs also killed the cefcu-side pull legs
  that had just been re-pointed. Always clear `transfer_id` on BOTH ends
  and verify survival before deleting.
- Both accounts on-budget → categories are cleared automatically (transfers
  aren't income/expense).

## Venmo model (Oct 2026)

Bank-funded Venmo payments **never touch the Venmo balance** — the money
goes bank→recipient directly. Statements (`Funding Source` column) prove
which payments were bank-funded vs balance-funded. Correct modeling:

- Bank-funded payments live on **cefcu** with the real recipient as payee
  (Andrew Belcher → Deductable, Tim Payne → Student Loans) — the
  `ACH TRANSACTION VENMO` pull legs get re-pointed.
- The Venmo account holds only: received payments (Hall Block, etc.),
  balance-funded spend, and transfers in/out. Anchor the balance with the
  statement `Beginning/Ending Balance` (Jan-1-2026 = $119.29 verified).
- Statement `To`/`From` columns: received payments show `To: Nicholas
  Payne` — the `From` field is the sender.
- 2025 pulls have no statements → recipients unknown, left as `Venmo`.

## Account validation (Oct 2026)

Every on-budget account was diffed row-by-row against bank exports
(amount ± date within 5d, payee-blind). `AccountHistory*.csv` carry a
`Balance` column = bank truth.

| Account | State |
|---------|-------|
| fox-communities | **bank-exact** ($825.53) |
| Venmo | **bank-exact** ($187.00, Oct statement) |
| chase-amazon | 100% in-window (Dec-31-2025→); pre-window residual ≈ -$1.9k |
| capital-1 | 100% in-window (Jan-2-2026→); entered window at +$1,186.89 (pre-window residual) |
| bam | 2026 import-verified + Dec-2025 PDF to the cent; pre-2026 residual |
| cefcu | in-window clean; residual ≈ **+$1,063** (all pre-window) |
| cefcu-savings | 100% in-window; **-$2,893.71** pre-window (plug/early history) |

Findings fixed along the way: a Sep-2024 "replay cluster" of ~19 phantom
rows (extra copies of recurring payments + fake inflows, all dated Sep
3-20 2024 — likely from the old manual cleanup process), several phantom
transfer pairs (±$1,614.37 self-pair etc.), a wrong-account -$7,000
(savings→fox linked to a checking phantom), and a missing Jan 12-31 +
Feb 2-4 2026 window.

Held Abri legs **resolved** (Oct-21): all three cefcu outflows
(`-$5,000→Zack`, `-$600→Athalia 529`, `-$100→Micaiah UTMA`, Sep 3-4
2024) deleted — they date before the checking export's Sep-23 start,
so they're *unverifiable*, not bank-disproved; the deciding evidence
is the boundary balance (below). The destination inflows were kept on
the investment accounts, re-payeed to `Abri` and noted "funding
source unverified, pending Abri statements." If Abri statements show
no Sep contributions, delete those marked inflows.

**Export-start caveat + boundary-balance arbiter:** `AccountHistory.csv`
starts **2024-09-23** — "no matching bank row" only means phantom for
rows *inside* the window. For pre-window rows the arbiter is the
export's `Balance` column: bank truth at end of Sep-22 = **$2,645.38**.
Restoring the whole deleted Sep-3→20 cluster would put the ledger at
≈ -$2,400 there (impossible) → the cluster deletions stand. Two rows
were restored on re-review: `+$1,000` Sep-9 inflow (real — fox sent
-$1,000 "CEFCU - CEFCUonlin" Sep-10; linked as a transfer pair)
and the `-$3,398.92` chase payment leg (chase-side inflow existed and
fits the monthly card-payment cadence).

`AccountHistory(2).csv` (`200003596361`, 2023-01→2026-10, ~$825.53
ending balance) is the **fox-communities export** — Fox Communities
CU uses the same CSV format and its own account numbering. Its
`CEFCU - CEFCUonlin` -$1,000 (Sep-10-2024) is the confirmed source
of the restored cefcu +$1,000 inflow; now a linked transfer pair.

Bank-name → account mapping (user-confirmed): `ALTRUIST FINANCI` pulls =
Zack Individual + both UTMAs (-100 each, ~23rd monthly); `WI DIR ACH`
pulls = the two 529s — through Jun-2026: Athalia -600 + Micaiah -100;
from Jul-2026: **-600 each** (two identical -600 pulls per month —
split one to each 529; both were wrongly pointed at Athalia until
Oct-21). The `-300 Abri` ACH pull is the
monthly advisory fee (real expense). Oct-2025→Sep-2026 Altruist legs
were imported unlinked (counted as spend); re-linked to the UTMA
accounts Oct-21 — importer-created legs had to be rebuilt fresh to
link without mirror dupes.

## Rebaseline (done Oct 22 2026)

All windowed accounts were truncated at their verified export-start
dates; pre-window history (2022 noise, phantom replays, old plugs) is
gone. Each account got a `Starting Balances` opening row:

| Account | Window start | Opening balance | Final = bank |
|---------|-------------|-----------------|--------------|
| cefcu | 2024-09-23 | +$6,845.47 (bank-anchored) | **$9,748.53** exact |
| cefcu - savings | 2024-09-30 | $1,091.28 (bank-anchored) | **$3,246.11** exact |
| chase-amazon | 2025-12-31 | -$302.23 (**implied/unverified**) | -$891.83 |
| capital-1 | 2026-01-02 | +$1,186.89 (**implied/unverified**) | +$603.06 |
| bam | 2025-12-22 | -$650.45 (**implied/unverified**) | -$577.93 |

fox-communities (native full history, bank-exact) and Venmo (already
anchored at $187) were not touched. Card OBs are marked
`(implied/unverified)` in their notes — refine if older statements
surface. Off-budget accounts unchanged (their balances are manual
references, not derived from imports).

**Safe-bulk-delete recipe** (what the first attempt got wrong — it cost
a full recovery cycle): deleting a linked/transfer-payee row while the
counterpart still carries transfer semantics makes the engine cascade
and respawn mirrors. The working order: (1) for every doomed linked row
AND its counterpart AND any kept row pointing at a doomed row —
`updateTransaction(id, {payee: <non-transfer payee>, transfer_id: null})`
first; (2) only then `deleteTransaction`; (3) compute opening balances
from a *fresh* balance read after deletes settle, never mid-mutation.
Severed counterparts survive as plain rows labeled `Rebaseline
Transfer` (a payee created for the purpose).

## Sync recovery playbook (Oct 22 2026 incident)

The first rebaseline committed ~4k mangled mutations, then the host
wedged (ZFS iowait storm → corrupted-snapshot churn) before rollback
was possible. Recovery that worked:

- **Deletes are permanent in the sync log** — an old client db cannot
  push "undeletes". The fix is a *file-level* reset: load a clean
  client db locally, `internal.send('sync-reset')`, then `api.sync()`
  re-uploads it as a fresh sync group. The file keeps its `cloudFileId`
  (`73b86e85…`) and name; only `ACTUAL_SYNC_ID` (the group id) changes.
- `api.init()` returns the internal dispatcher —
  `internal.send('sync-reset')` reaches the unexported method.
- **A snapshot hides in every client's cache** — `actual-dash`'s
  `/cache/<file>/db.sqlite` was the last clean pre-incident copy; keep
  one off-box before bulk work (`docker cp` writes to the *client* side
  even with `--context ghost`).
- `metadata.json` must carry `cloudFileId` + `groupId` before
  `loadBudget`+sync, else the server answers `invalid fileId`. A
  crashed run leaves metadata.json unflushed — rewrite it by hand.
- **640m mem_limit OOMs bulk mutations** — the budget engine balloons
  on ~4k ops. Run one-off mutator scripts in a plain `docker run` of
  the `actual-actual_dash` image (no limit) on `phantomlink` with
  `-e ACTUAL_PASSWORD` and a `-v /tmp/x:/work` mount.
- Local db autopsy: `better-sqlite3` inside the image reads
  `/cache/.../db.sqlite` directly — columns are `transferred_id` (not
  `transfer_id`), `description` = payee id, `date` = int yyyymmdd.
- Orphaned `group-*.sqlite` files under `/data/user-files/` on the
  server are stale post-reset (old groups `444e32ae`, `1b99417f`) —
  safe to delete server-side, they no longer serve any client.

Current `ACTUAL_SYNC_ID` = `8f042e31-…` (compose env). The Komodo
deployed copy under `/tank/…/stacks/actual/` is root-owned — container
recreates used `docker run` with the same env/volumes; a normal Komodo
redeploy converges the file.

## Dashboard

`actual_dash` serves a read-only chart page at
`https://budget.paynepride.com` (same `default-whitelist` middleware as the
app). It's a tiny node server in `dashboard/` running on the same image as
the importer — every `REFRESH_MIN` (default 30) it does one
`downloadBudget`, computes aggregates (monthly in/out/net, category + payee
breakdown, top-8 category trend, account balances, uncategorized count),
and serves them as `/data.json` to a dependency-free HTML page. Its budget
cache is a separate `actual-dash-data` volume — never share `/cache`
between containers (concurrent sqlite access on the same volume).

## Getting exports out of each bank

Gap-fill window: last txn in the budget is **Feb 4, 2026** — export
**Feb 2026 → now** (a few days of overlap is fine, dedup handles it).
Budget already holds everything older.

| Account | Where | Notes |
|---------|-------|-------|
| chase-amazon | chase.com → card → "Download account activity" | pick CSV + custom date range; signed Amount col |
| capital-1 | capitalone.com → account → "Download Transactions" | CSV, custom range, ~3y back; Debit/Credit cols |
| cefcu, cefcu-savings | CEFCU online banking → account → download/export | CSV or Quicken(QFX) both work |
| fox-communities | online banking export | CSV or QFX |
| venmo | venmo.com → Statements | monthly CSV only — grab each month Feb→now (~9 files) |
| bam-allegiant-allways | allwayscard.com portal | if it only offers PDF statements, flag it — needs a different parser |

## CLI helper

`just actual-accounts` lists the folder names;
`just actual-drop <folder> <file...>` scps exports into place, e.g.
`just actual-drop venmo ~/Downloads/venmo-feb.csv ~/Downloads/venmo-mar.csv`

## Secrets/config

`ACTUAL_PASSWORD` is set in the Komodo stack's Environment (periphery can't
see `/tank/...` host paths, so a file wouldn't work — Komodo writes stack
env vars into the deployed `.env`). Sync ID + server URL are in the compose
file.

When changing `importer/` code, remember deploys only *build* when the image
is missing — force a rebuild with
`docker --context ghost compose -p actual build actual_import` or Komodo's
stack redeploy.
