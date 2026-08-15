# ADR 0001: Separate task evidence from the scoring oracle

- Status: accepted
- Date: 2026-08-15

## Context

A historical fix contains the answer to the review task. Giving a model the commit hash, message, or fixed diff makes the evaluation easy to leak and hard to trust.

## Decision

Mining emits two artifacts:

- `task.json` contains only the buggy file snapshot and the prediction contract;
- `oracle.json` contains provenance, fix-side localization, and test evidence.

The runner must expose only `task.json` to the system under evaluation. The separation is procedural, not a security boundary, and the limitation is documented explicitly.

## Consequences

Evaluations are provider-independent and repeatable offline. Operators remain responsible for isolating the oracle and repository history from the model.
