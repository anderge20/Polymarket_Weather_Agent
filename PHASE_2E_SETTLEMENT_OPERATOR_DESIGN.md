# Phase 2E — settlement observation operator

## Decision

`forecast_tmax` and its quantiles describe a continuous meteorological variable.
They do **not** by themselves define the discrete value that settles a Polymarket
contract.  A feature may calculate `weather_prob` only with an explicit,
versioned `SettlementOperator` applicable to that market's resolution source and
measurement rule.  In the absence of one, it must fail closed (the event is
excluded); it must not use a nearest-integer or rounding default.

## Why the current implementation is unsafe

`probability.quantiles_to_distribution()` assigns mass for integer `N` from the
continuous CDF over `[N-0.5, N+0.5]`.  That is an implicit round-to-nearest
operator.  It is not established by the market rules and therefore cannot be
the generic implementation used by `features.build_feature()`.

## Required interface

An operator must have all of:

* `operator_id` and immutable version;
* source and measurement-rule applicability predicates;
* unit declaration/conversion policy;
* a mapping from a continuous CDF to discrete settlement outcomes;
* tests for closed and open bands; and
* evidence reference, coverage and exceptions.

`features.build_feature()` receives the operator explicitly.  It records the
operator id/version and distribution in feature lineage.  `None` or an
inapplicable operator returns no feature; Strategy A records the normal
fail-closed exclusion.

## Existing evidence

The Hong Kong HKO audit is evidence for a **candidate source-specific** floor
operator only: it agrees in 164/166 resolved cases and differs from the tested
rounding rules in 77 discriminating cases.  Its two exceptions remain unresolved,
so it is not a global default and does not establish the Wunderground/NOAA
operator used by the other markets.

## Migration sequence

1. Introduce continuous forecast distribution and `SettlementOperator` protocol.
2. Remove the implicit nearest-integer mapping from production feature assembly.
3. Make the operator an obligatory, recorded argument of feature and Strategy A
   generation; update tests to pass an explicit test-only operator.
4. Add production operators only after their source-specific audit is closed.
5. Do not train M2/M3 or select a final strategy using rows without an operator.
