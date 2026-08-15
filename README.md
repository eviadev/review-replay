# ReviewReplay

**Replay yesterday's bugs to measure today's code-review agents.**

ReviewReplay turns a historical bug-fix commit into a blind, offline evaluation case. The agent receives the buggy file snapshot. The evaluator keeps the fix evidence separate and scores whether findings localize the regions that humans later changed.

This is not another AI reviewer. It is the missing test harness for deciding whether one can be trusted.

## Why this exists

Code-review demos usually showcase a few convincing comments. They rarely answer harder questions:

- Did the agent find a defect that actually mattered?
- Did it localize the problem, or produce plausible commentary elsewhere?
- Did a prompt or model change improve recall while flooding the review with noise?
- Can the result be reproduced without sending private code to a provider?

ReviewReplay makes those questions measurable with evidence already present in Git history.

## How it works

```text
historical fix commit
        │
        ├── parent snapshot ──> task.json ──> reviewer under test
        │                                      │
        └── changed old lines -> oracle.json    └──> predictions.json
                                   │                    │
                                   └──── scorer <───────┘
                                             │
                                  precision / recall / F1
```

The task and oracle are deliberately separate. `task.json` contains embedded buggy source files but no fix hash, message, or corrected code. `oracle.json` preserves commit provenance, old-side line regions, and whether the fix added test evidence.

## Quick start

ReviewReplay has no runtime dependencies beyond Python 3.11+ and Git.

```bash
python -m pip install -e .

review-replay mine \
  --repo /path/to/local/repository \
  --fix <bug-fix-commit> \
  --output cases/example
```

Give only `cases/example/task.json` to the reviewer. Save its output as:

```json
{
  "case_id": "rr-…",
  "findings": [
    {
      "path": "src/pricing.py",
      "start_line": 42,
      "end_line": 44,
      "message": "Quantity is subtracted instead of multiplied."
    }
  ]
}
```

Then score it:

```bash
review-replay score \
  --oracle cases/example/oracle.json \
  --predictions predictions.json \
  --json
```

For a benchmark directory, name each prediction `<case-id>.json` and aggregate it in one command:

```bash
review-replay score-suite \
  --cases cases/ \
  --predictions predictions/ \
  --json
```

## What the score means

- **Precision**: the share of findings that overlap a ground-truth region.
- **Recall**: the share of ground-truth regions found by the reviewer.
- **F1**: the harmonic mean of localization precision and recall.
- **One-to-one matching**: duplicate comments cannot inflate the score.
- **Tolerance**: an explicit optional line window for near-miss experiments.
- **Suite metrics**: micro precision/recall/F1 plus macro F1, with missing predictions reported instead of silently dropped.

The ground truth is intentionally modest: changed old-side lines are a localization proxy, not proof that every changed line is independently defective. Semantic judging and bug-inducing-commit discovery belong in later, separately evaluated layers.

## Trust model

ReviewReplay is local-first and provider-independent. It never invokes a model or network service.

For a valid blind run:

1. expose only `task.json` to the reviewer;
2. keep `oracle.json` and repository history outside its sandbox;
3. record the reviewer/model configuration with the prediction artifact;
4. compare versions on the same case set.

This is procedural isolation, not a cryptographic boundary. See [ADR 0001](docs/adr/0001-separated-task-and-oracle.md).

## Current scope

The v0.1 core supports single-parent fixes, text files, rename-aware Git diffs, test-change detection, deterministic JSON artifacts, line-localization scoring, and multi-case aggregation. It intentionally rejects cases with no scorable buggy-side source.

Planned next layers:

- dataset manifests and bootstrap confidence intervals;
- SZZ-style bug-introducing commit discovery;
- language-aware semantic regions;
- adapters for reviewer outputs from multiple providers;
- mutation-based controls to measure false-positive behavior.

## Development

```bash
make install
make check
```

The tests create real temporary Git repositories rather than mocking Git output. CI runs on Python 3.11, 3.12, and 3.13.

## License

MIT
