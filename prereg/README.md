# The two citations in the vendored file, and where they resolve

`PREREG_M2_ERROR_v2.md` here is sha
`b2b168d4cddb65c469cbd00bd20cce30c54e5afd194526527714e23cf0d5b34c`. It was
vendored so that `m2.PREREG_SHA_V2` could be checked from a clone.

*(That is why the file is here, stated as purpose rather than as what the code
does today: a purpose becomes historical when the code moves on, a description of
current behaviour becomes false. Same reason nothing below asserts which version
production runs.)*

Its §6 qualifies its first reference `"(§2 de v1)"` and **drops the qualifier on
the next two**, which also mean v1:

| citation in v2 §6 | resolves inside v2 to | the section meant, in v1 |
|---|---|---|
| `(§7)` | §7 "Limitaciones que siguen en pie" — a different subject, **and it resolves confidently** | §7 "Cómo se obtienen los cuantiles" |
| `§10` | nothing: v2 has sections 0–7 | §10 "Prohibiciones" |

v2's own prohibitions clause is therefore **v1 §10**, not anything in this file.

The `§7` case is the worse shape even where it is the less harmful one — the
sentence states the method on the same line, so a reader gets the right answer
without following the citation. A dangling reference fails loudly; one that lands
on a plausible section does not.

The cause generalises: **the qualifier decays across an enumeration.** The first
citation carries its document and the rest drop it, and it happens exactly where
one document inherits from another — which is where citations point outward most.

**Nothing here is corrected in the file.** Its value is that a sha fixes a
content; editing it to repair a citation would break the chain in order to fix
what the chain exists to protect.

## v3 exists, and its header says v2 is retired

`PREREG_M2_ERROR_v3.md` opens with: *"Sustituye a v2 (`b2b168d4…`), que queda
RETIRADO por NO APTO (B-11)."*

**v3 then failed its own preregistered criterion.** The authority for that is
`M2_V3_REPORT.md`, sha
`397a1751cb4433f7b65965f234ee9284b0d7fea19104bf969694de79a44bd6ac` in
`M2_MANIFEST.sha256`: 6 of 46 stations against its 70 % threshold — 13 %, marked
FALLA — and correlation between period halves of **+0.080** for the per-station
bias it was built to correct. (`error_model.py` carries the same conclusion in
the block marked *WITHDRAWN — NOT IN PRODUCTION*; that is corroboration, not the
authority — a code comment is what let the chain mislead in the first place.)

So each document is correct on its own and only the chain misleads. **Which
version governs today is state, and state lives in the index below, not here.**

**And withdrawing a method does not withdraw what was measured while withdrawing
it.** The +0.080 is a frozen measurement: a per-station shift learned from the
past is applied to the future as noise, which is why a pooled probability for one
specific market is worse calibrated than any aggregate figure suggests.
Discarding v3 "because it was withdrawn" discards that measurement with it.

## The full state

`M2_PREREG_CHAIN.md`, on branch `research/modelsel-artifacts` — v1, v2 and v3
with their shas and the reason each is where it is.

Addressed by name and branch on purpose, so it resolves to the current state. Its
sha was `882206ad08f6212dca7922082187312769fa1ec48869254bc648f52479506582` when
this note was written — **a witness, not the address.** A pointer pinned to a sha
goes stale the moment the index is updated, which is the defect the index exists
to fix.
