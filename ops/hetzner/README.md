# Paper mode on Hetzner

Execution moved here on 2026-09-09 by the user's decision. **GitHub remains the
record**: the code is pulled from `main`, the shards are pushed to
`paper-state`, and nothing exists only on this box.

## Why

GitHub Actions cron did not deliver. Measured on its first day (A-70):

| slot | delivered |
|---|---|
| collector 12:07Z | never |
| collector 15:07Z | 16:33:54Z, **+86 min** |
| cycle 11:40Z | 15:15:30Z, **+215 min** |

Five of the seven captures that day were dispatched by hand. A lost *price* slot
is recoverable inside Open-Meteo's window; **a lost *book* slot is not** — and
the book is the substrate R21 had to assume away and R22 could not measure at
all, so every missed slot is a question that cannot be answered later.

## What runs

All times UTC; the host is `Etc/UTC` and `install.sh` refuses to install if it
is not.

| when | what |
|---|---|
| `7 */3 * * *` | `launcher.sh collect` — book snapshots |
| `40 2 * * *` | `launcher.sh decide 9` — lead 9 h, target today |
| `40 11 * * *` | `launcher.sh decide 24` — lead 24 h, target tomorrow |

Cron calls `launcher.sh`, which lives **outside** the checkout. `run_cycle.sh`
begins by updating the checkout it lives in, and a `git reset --hard` to a ref
that does not contain `ops/hetzner/` would delete the running script while bash
was still reading it — a half-executed file and a schedule that stops without an
error anyone would recognise. The launcher updates the tree, **checks the runner
still exists**, and stops loudly if it does not.

## Trading is OFF, and turning it on is a deliberate act

The decision cycles run `--collect-only` unless `/opt/pmw/PAPER_TAU` exists.
That file is what starts trading, and **R24 §6bis/P12 require the acceptance
criterion to be frozen and hashed BEFORE it exists**. It does not exist, and it
should not until:

1. the live eligibility series has several days in it (it accumulates on every
   cycle, at no cost in quota),
2. the coverage rule is reformulated over the EXECUTION gate — R21 measured that
   `tau_signal` is not the binding lever: 0.02 and 0.04 open the same 115 cycles,
3. and the amendment freezing `n_requerido(tau)` is hashed in `DECISIONS.md`.

Even then it is paper only. **Real money needs Gate D0, which only the user
lifts**, and R21 measured the strategy as NOT OPERABLE — median −0.0236 per
trade, negative in all 47 stations and all 37 dates, losing even with free
execution.

## What was verified, and why each one

Assuming any of these would have produced a schedule that looks installed and
does not run. Each was checked on the box, not reasoned about:

- **The full loop.** The runner pulled `main`, collected 1 078 tokens, and pushed
  to `paper-state` — commit visible on GitHub with its `venue_coverage` shard.
- **The cron environment.** `git push` under cron has no SSH agent and a minimal
  PATH, so it can fail where an interactive login succeeds — and it would fail
  SILENTLY, leaving shards on disk and nothing on GitHub. Tested with
  `env -i HOME=/root PATH=/usr/bin:/bin`: the launcher runs and pushes.
- **The host clock.** `Etc/UTC`, and `install.sh` refuses to install otherwise.
- **The test suite, on this machine.** It found a `pandas` import the paper tier
  does not install — green on the developer's laptop, broken here.
- **That cron actually FIRES the launcher.** "The entry is in the crontab" is a
  claim about a file; "cron executes it" is a claim about a daemon, and the gap
  between them fails invisibly — no error, no log, and a missing shard nobody
  notices for days, in the system whose headline measurement is *scheduled versus
  delivered*. Checked with a temporary entry two minutes out, marked `# PRUEBA`,
  pointing at the real launcher: it fired at 20:23:04Z on 2026-09-09, resolved the
  ref, updated the checkout and ran the cycle. The entry was then removed and its
  absence verified — the check must not survive itself.

And one that was NOT verified, with the consequence it had: the first deployment
pointed the runner at a branch with a `sed` whose pattern did not match the real
line. The edit silently did nothing, the runner reset the checkout to `main`,
which had no `ops/`, and **deleted itself while bash was reading it**. No error,
no log, one collector slot lost. That is what `launcher.sh` now prevents — see
below — and why "I applied an edit" is not the same as "the edit applied".

## Operating it

```sh
ssh -p 443 root@95.217.131.145
/opt/pmw/repo/ops/hetzner/install.sh      # idempotent; re-run after a pull
                                          # (it re-execs itself from /opt/pmw/bin
                                          #  first — it resets the checkout it
                                          #  lives in, so it must not run there)
tail -f /opt/pmw/log/collect.log
crontab -l
```

To stop everything: `crontab -r` (or delete the delimited block).

## Reading the coverage series

`venue_coverage` rows carry `is_final`, and it means **the CUTOFF is final, not
the COUNT**. Session B's point on PR #15, and the difference decides how the
series is read:

- **`is_final = false`** — the cycle ran before `t_asof`, so the count is a
  partial one that will grow. Never enters the series.
- **`is_final = true`** — the cutoff reached the anchor. But several cycles run
  after `t_asof` for one target, and each writes its own row, so **two final rows
  for the same target can differ.**

**The rule: take the LAST final row per `(target_date, lead)` by `recorded_at`.
Never the mean of the final rows** — that counts one target several times.

`recorded_at` orders them, and what it gives you is **the most recent observation
of the venue's state — not "the maximum"**. The distinction is session B's and it
matters, because anyone reasoning from "it is the maximum" will deduce things
that do not hold:

- The **numerator** only grows: the cutoff is identical across those rows and
  `price_history` is append-only, so a later row saw a superset of the prices.
- The **denominators do not.** `bands` and `events` come from `markets` and
  `outcomes`, which are **re-discovered from gamma on every run**. A band
  discovered later raises them with no price having changed, and a revised
  `endDate` can move a market to another target date entirely. So
  `complete_rate_over_events` and `priced_rate_over_bands` can go **either way**
  between two final rows.

No extra tie-breaker field is added: maximality is not the property you want —
recency is, and `recorded_at` gives it. A field with no consumer is noise.

### Two admissibility rules, decided before the series is long enough to use

Both come from session B's review of PR #17, and both exclude rows for the same
underlying reason: **a band counts as priced iff OUR collector photographed it
before the cutoff.** That is not a venue property — it is measured, not assumed:
in `ds_paper_v1` the lag `ingestion_timestamp − observation_time` is 27 s at
worst, so `observation_time` IS the collection instant.

**1. WARM-UP. A row whose cutoff falls before the collector reached steady state
on that target does not measure the venue; it measures when we switched the
machine on.** One pass does not price everything — the 00:07Z pass priced 423 of
539 bands, the rest being one-sided books with no midpoint — so coverage
accumulates across passes and `events_complete`, which needs EVERY band of an
event, is far more sensitive to this than `bands_priced`.

> **Excluded: any row whose cutoff precedes the first `observation_time` of that
> target's tokens plus one collection interval (3 h).** The dataset-wide floor is
> declared too, measured from the data: `min(observation_time)` for `ds_paper_v1`
> is **2026-09-09T10:32:15Z**, so nothing cut before **2026-09-09T13:32:15Z** is
> admissible under any reading.

This is why the `events_complete = 4 of 49` (8.2 %) from the first partial row is
**not** evidence that coverage is low: it is a one-pass number. Reading it as a
low steady-state value, and concluding the threshold rule may have no solution,
would be the fourth wrong denominator in this project.

**2. ROWS OLDER THAN THE FIELD ARE ADJUDICATED, NOT RULED ON.** `is_final` and
`t_asof` arrived with PR #15. Eight rows predate them, all for
`target_date = 2026-09-10`:

```
session_id                       recorded_at (Z)       origin             bands  priced
col_20260909T185316Z_77df77      2026-09-09T18:58:50   hetzner              561       0
col_20260909T192211Z_4a1aa2      2026-09-09T19:28:06   hetzner              561       0
col_34395159658_2026-09-10       2026-09-09T19:32:25   workflow_dispatch    561       0
col_20260909T195134Z_138c4d      2026-09-09T19:58:04   hetzner              561       0
col_20260909T202305Z_63236f      2026-09-09T20:30:14   hetzner              561       0
col_34403706557_2026-09-10       2026-09-09T21:00:39   schedule             561       0
col_20260909T210326Z_e36a8f      2026-09-09T21:12:54   hetzner              561       0
col_20260909T210705Z_a101fc      2026-09-09T21:16:48   hetzner              561       0
```

Two of the eight came from Actions — one scheduled, one hand-dispatched — which
is the last trace of the migration and the reason `github_event` exists. All
eight share `prediction_time = 2026-09-09T12:00:00Z` and `bands = 561`.

They are **the cold-start fact, not the low end of a coverage distribution**:
each says `bands_priced = 0` because for a lead-24 target no price of that
universe existed before its anchor — the collector was born that morning. They
are reported as that fact and **never enter the coverage series**, which also
means there is no series with two reading rules: there is a series, and a fact.

**A consumer must treat a missing `is_final` as UNKNOWN and refuse, not infer
it.** The tempting inference — final iff `recorded_at` beats `prediction_time` by
more than a few seconds — is correct for these eight and **wrong as a rule**, and
this is session B's catch: with early firing `prediction_time = now`, so the gap
is just stage time. Measured on the live rows, the eight sit at 25 130–33 409 s
while the partial one sits at **0.018 s** — an enormous margin today, and an
accident of it: those 18 ms are the distance between the `timing` stage and this
one. Insert a stage between them and a PARTIAL row starts being classified as
final. **That is the #15 defect reappearing inside the rule meant to replace it.**
The eight work only because their `prediction_time` is 12:00:00Z, which IS
`t_asof` at lead 24 — a property of those rows, not of the condition.

A closed set adjudicated once by id is auditable. A fragile rule running forward
over rows nobody will look at is not.

*(No consumer exists yet — `venue_coverage` has a writer and no reader in
`src/` or `scripts/`. So "refuse" is stated here as required behaviour for
whoever writes that reader, and nothing in the code enforces it today. Saying
otherwise would be claiming a guard that is not there.)*

*(A third route to differing finals opens when the price-history backfill lands:
a row with `observation_time <= t_asof` ingested afterwards. Measured on the live
store it is not open today — every price row is ingested within 27 s of its
observation instant, p95 = 22 s — because `observation_time` IS the collection
instant, so a late slot writes a late observation and loses the measurement
rather than back-filling it. The rule above covers all three.)*

## Host events

A slot the launcher gives up on — the run lock still held after `PMW_LOCK_WAIT` —
is appended to `/opt/pmw/pending_host_events.ndjson` and drained into a
`host_events` shard by the next cycle that gets the lock. It is queued rather
than pushed on the spot because committing in the state checkout while the
lock-holder is writing there is the race the lock exists to prevent.

Without this, a skipped slot leaves **exactly the trace of a host that never
fired**: no shard, a hole in "delivered", nothing to tell the two apart — which
is the distinction R24 §4quater rests on when it attributes `NO EVALUABLE` to the
host rather than to the strategy.

## Layout

```
/opt/pmw/bin/launcher.sh   what cron calls — OUTSIDE the checkout on purpose
/opt/pmw/REF               which ref to run (default `main`); switching branch
                           is editing this file and nothing else
/opt/pmw/repo    clone of main          — code, pulled every run
/opt/pmw/state   clone of paper-state   — shards, pushed every run
/opt/pmw/venv    requirements-paper.txt
/opt/pmw/log     collect.log, cycle.log
/opt/pmw/PAPER_TAU   absent = no trading (fail-closed)
```

## Access

The box authenticates to GitHub with a **deploy key with write access**, added
to the repository on 2026-09-09 as `hetzner-hel1-paper-runner (rw)`. It can push
to this repository and nothing else. To revoke it: Settings → Deploy keys, or
`gh api -X DELETE repos/anderge20/Polymarket_Weather_Agent/keys/162799493`.
