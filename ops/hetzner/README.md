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

### Rows written before the field existed

**`is_final` and `t_asof` arrived with PR #15 on 2026-09-09. Eight rows predate
them**, all for `target_date = 2026-09-10`, and a consumer that applies the rule
above naively gets one of two wrong answers:

- **missing ⇒ `false`** drops all eight SILENTLY, and target 2026-09-10 vanishes
  from the series entirely — silent data loss in the series that fixes the
  threshold;
- **missing ⇒ `true`** is right here and right by accident. It would be wrong for
  any pre-#15 partial row, and the only reason none exists is when the collector
  happened to start.

**The rule for that segment: a row without `is_final` is treated as final iff
`recorded_at` is later than `prediction_time` by more than a few seconds.** All
eight are — `prediction_time` is 12:00:00Z and they were recorded between 18:58Z
and 21:16Z — and all eight report `bands_priced = 0`, which is the cold-start
fact: for a lead-24 target, no price of that universe existed before its anchor
because the collector was born that morning.

That derivation is exactly the fragile inference `is_final` was added to replace,
and for the legacy rows there is nothing else: they carry no `t_asof` either,
since it landed in the same commit. So:

**The series proper begins 2026-09-10T00:07Z. The earlier segment is reported
separately and never averaged into it.**

*(The lesson, recorded because it cost a defect: adding a field is a schema
change to a LIVE series, and the moment to write the rule for the old segment is
when the field is added — not when someone comes to consume it. The consumer rule
above was written the same day and still assumed the series began with the
change.)*

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
