# What is vendored here, and what it cannot tell you

This directory holds **one** file: `PREREG_M2_ERROR_v2.md`, sha
`b2b168d4cddb65c469cbd00bd20cce30c54e5afd194526527714e23cf0d5b34c`.

It is vendored so that `m2.PREREG_SHA_V2` is checkable from a clone, and
`scripts/fit_quantile_artifact.py` writes that sha into every quantile artifact
as its provenance. So anyone auditing a production artifact arrives here.

**They arrive to a document with two broken citations and no way to resolve
them**, because v1 and v3 are not in this repository. This note supplies only
what cannot change; anything that can — which version governs, what is withdrawn
— lives in one place and is pointed at below.

## The two citations in v2 §6

The section reads:

```
Error `e = y − f` en °C … (§2 de v1);
percentiles empíricos por interpolación lineal, sin suavizado ni recorte (§7);
… mínimo 30 pares … prohibiciones de §10.
```

The first is qualified. The next two are not, and both mean **v1**:

| citation | resolves in v2 to | intended (v1) |
|---|---|---|
| `(§7)` | §7 "Limitaciones que siguen en pie" — **wrong section, and it resolves confidently** | §7 "Cómo se obtienen los cuantiles" |
| `§10` | **v2 has sections 0–7 only; nothing to resolve to** | §10 "Prohibiciones" |

**So the prohibitions in force for M2 v2 are the ones in v1 §10.** The `§7` case
is the worse shape even though it is the less harmful one here — the sentence
states the method on the same line, so a reader gets the right answer without
following the citation. A dangling reference fails loudly; one that lands on a
plausible section does not.

The cause is worth naming because it generalises: **the qualifier decays across
an enumeration.** The first citation carries "de v1" and the rest drop it, and
this happens exactly where one document inherits from another — which is where
citations point outward most.

**These are not corrected in the file.** Its value is that a sha fixes a content;
editing it to fix a citation would break the chain in order to repair what the
chain exists to protect.

## Which version governs

`PREREG_M2_ERROR_v3.md` exists and its header says v2 is **"RETIRADO por NO
APTO"**. That sentence is **not operative**: v3 was the proposed next step, v3
then failed its own preregistered criterion — 6 of 46 stations calibrated against
a 70 % threshold — and was withdrawn (`src/weather_agent/error_model.py`, the
block marked *WITHDRAWN — NOT IN PRODUCTION*). With v3 gone, **v2 is again the
best available, and production uses it deliberately.**

Each document is correct on its own. Only the chain misleads, which is why
reading either one alone gives the wrong answer.

**And withdrawing a method does not withdraw what was measured while withdrawing
it.** v3's finding stands: the per-station bias is **not persistent** —
correlation between period halves +0.080 — so a shift learned from the past is
applied to the future as noise. That is why v2's probability for **one specific
market** is worse calibrated than its aggregate figure suggests, and why that is
not fixable with this substrate. It is the most important limitation of M2, it is
live, and discarding v3 "because it was withdrawn" discards it too.

## The full state

`M2_PREREG_CHAIN.md`, on branch `research/modelsel-artifacts` — v1, v2 and v3
with their shas and the reason each is where it is.

Addressed by name and branch on purpose, so it resolves to the current state. Its
sha was `882206ad08f6212dca7922082187312769fa1ec48869254bc648f52479506582` when
this note was written — **that is a witness, not the address.** A pointer pinned
to a sha goes stale the moment the index is updated, which is the exact defect
the index exists to fix.
