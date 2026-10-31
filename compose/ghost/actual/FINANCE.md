# FINANCE.md — household finance state for the Actual budget

Durable context for any agent doing budget work. The README covers
infrastructure (deploy, importer, sync recovery); this file covers *money*:
balances, categorization conventions, baseline numbers, open questions.

Update this file when balances, income sources, cadences, or decisions change.

## Accounts (on-budget)

| Account | Balance (2026-10-25) | Anchor | Notes |
|---------|---------------------|--------|-------|
| cefcu (checking) | $9,748.53 | bank-exact | rebaselined 2026-10-22 at export start 2024-09-23 |
| savings | $3,246.11 | bank-exact | rebaselined at export start 2024-09-30 |
| fox communities | $825.53 | bank-exact | full history kept (export since 2023-01) |
| Venmo | $187.00 | bank-exact | export since 2026-01 |
| chase-amazon | -$891.83 | implied OB | OB -$302.23 at 2025-12-31 is *unverified* — pin with statement if needed |
| capital-1 | $603.06 | implied OB | OB +$1,186.89 at 2026-01-02, unverified |
| bam (Allegiant Allways) | -$577.93 | implied OB | OB -$650.45 at 2025-12-22, unverified |

Off-budget (manual refs, contributions imported): Abri Individual (Zack, $300/mo),
Athalia-529 ($9,000), Micaiah-529 ($5,700), two UTMAs (~$3.5k each).
`ALTRUIST FINANCI` pulls → Individual + UTMAs ($100/UTMA ~23rd monthly).
`WI DIR ACH` pulls → 529s — through Jun-2026: Athalia $600 + Micaiah $100/mo;
from Jul-2026: **$600 each** monthly.

Sync group (current): `8f042e31-dfe2-40bb-b612-9a1842b67c4a` — keep
ACTUAL_SYNC_ID here and in docker-compose.yml in step.

## Income

- **Caterpillar only** (~$9k/mo take-home). Avant income ended ~Apr-2026
  (was ~$9k/mo). Cat paychecks ~$7.9k on the 26th + smaller amounts.
- Expected: ~$15.6k gross Cat bonus each Mar/Apr (2026-03-13 hit). Tax
  refunds land ~Mar (2026: ~$8.4k via TurboTax deposits).
- Historical monthly inflows (ledger): Oct-Dec 2025 ~$16.5k/mo, Jan-Mar 2026
  $26-33k/mo (Avant + Cat + bonus + refund), Apr-Sep 2026 ~$9k/mo.

## Burn structure (2026-10 dashboard view: fixed / giving / movable)

Recurring consumption ≈ **$11.3k/mo** vs ~$9k income → ~$2-4k/mo deficit
post-Avant. Structure (6-mo avg): fixed ~$4.1k, giving ~$1.7-1.8k, movable
$5.6-7k.

| Bucket | $/mo | Contents |
|--------|------|----------|
| Housing+Bills | 2,632 | mortgage $1,567 (stepped up ~Apr-2026) + bills $1,065 |
| Food | 2,153 | groceries $1,867 (heavy Instacart markup) + dining $286 |
| Giving | 1,666 | Olivet $500-1k + Andrew Belcher $700 (charitable support) |
| Shopping+Amazon | ~1,500 | Amazon ~$580 + retail ~$900 (needs order-match) |
| Kids | ~1,200 | Valor ~$520 + childcare $250 + kid's stuff $354 |
| Cars | 849 | car $634 + gas $215 |
| Student loans | 570 | Tim Payne $375 (through Apr-2027) + rest |
| Tail | ~750 | home maint $357, cash $252, smokes $186, pets $121 |

Predictable lumps: Valor annual ~$12.3k (June), vacations $3-5k (Jan/Mar),
giving spikes Apr+Dec (~$6.8k), Cat bonus Mar/Apr.

## Category conventions

- `Cash` = ATM withdrawals (untraceable by design).
- `Amazon` = staging for order-matching; do NOT recategorize casually —
  resolve via Amazon order-history match (csv at ~/Downloads/amazon-charges.csv,
  157 rows / $5.7k). Recurring identical amounts are Subscribe & Save
  ($20.53 biweekly, $16.18/$24.75/$25.28 monthly, etc.).
- `Shopping` = retail non-food (Kohl's, TJMaxx, Target, Dollar Tree, Etsy…).
- `Home Maintenance` = hardware/plumbing/improvement; mortgage stays `Housing`.
- `Deductable`/`Not Deductable` = giving (Andrew Belcher support here).
- `Bills` incl. Hall Block +$88/mo inflow = family phone-bill reimbursement.
- `Pets` = Pet Supplies Plus + vet. `Student Loans` incl. Tim Payne $375.
- `Valor` = school tuition (recurring ~$520 + annual lump).
- `Rebaseline Transfer` payee + `Starting Balances` cat = non-consumption
  artifacts — exclude from spend math.
- Uncategorized ≈ 180 rows, mostly small — diminishing returns.

## Open items / anomalies

- **$11.4k unidentified checks** in General: `Check` $4,057 + `Over Counter
  Check` $2,754 + payee `51` $2,550 (Dec-2023 $2,000+$500+$50 — check #51?)
  + `Ach Transaction Fox Communities Credit Union` $2,000. Mostly 2023-24
  fox history + a $1,000 Jan-2026 check + $275 Sep + $54 Oct.
- Feb-2025 $10,000 outflow categorized `Paycheck` — likely mislabeled
  transfer; review.
- Oct-2026 cash withdrawals $1,700 — visibility gap by design.
- Oct-2026 $700 childcare check + Victoria's dining rows: tips/giving are
  manually split (≥$20 tip expected).
- 3 implied card OBs (see table) — pin to statements if ever needed.

## Decisions log

- 2026-10: rebaseline chosen over older-statement archaeology; pre-window
  history truncated at export starts (bank-exact or implied OB).
- 2026-10: 529 recoup for the June $12.3k Valor payment — plan is to
  distribute by Dec-31-2026 (same-tax-year match); $10k/beneficiary federal
  K-12 cap — split across both kids if tuition was shared. Not tax advice.
- Giving floor ~$1.7k/mo is intentional but is ~18% of single-income burn.

## Query cookbook

Reusable query scripts live in `analysis/` (push to ghost, run with
`docker --context ghost exec actual-dash node /tmp/analysis/<x>.mjs`):
`balances.mjs`, `spend-by-cat.mjs` (START/END env), `cat-payees.mjs`
(CAT env) — all share `lib.mjs` which encodes the exclusion rules
(transferred_id, transfer payees, Rebaseline Transfer, Starting
Balances, off-budget).

Dashboard cache db: `docker --context ghost exec actual-dash` →
`/cache/My-Finances-cb746f6/db.sqlite`, better-sqlite3 at
`/usr/local/lib/node_modules/@actual-app/cli/node_modules/better-sqlite3`.
Schema quirks: `transferred_id` (not transfer_id), `description` = payee id,
dates are int yyyymmdd, `isParent`/`tombstone` flags.
Spend filters: `amount<0`, `isParent=0`, `tombstone=0`, onbudget acct,
exclude transfer payees + `Rebaseline Transfer` + `Starting Balances` cat.
Mutations: via `@actual-app/api` in a one-off container on `phantomlink`
(never raw sqlite writes — they don't emit sync messages). Category changes
+ rules are low-risk; deletes need the README strip-both-ends recipe.
