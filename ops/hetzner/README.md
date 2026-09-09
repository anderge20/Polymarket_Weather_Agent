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
tail -f /opt/pmw/log/collect.log
crontab -l
```

To stop everything: `crontab -r` (or delete the delimited block).

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
