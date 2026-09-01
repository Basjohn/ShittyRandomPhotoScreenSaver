# R-72 — Production Shutdown Imported A Dead Performance Parser

**Status:** RESOLVED / PERMANENT TOOLING-OWNERSHIP GUARDRAIL  
**Date:** 2026-09-01

## Failure

`main.py --perf` flushed logging during shutdown and then attempted to import and execute:

```python
from scripts import spotify_vis_metrics_parser
```

The `scripts` parser no longer existed. A similarly named `tools/spotify_vis_metrics_parser.py` survived, but it parsed retired GL/overlay Visualizer telemetry.

This was more dangerous than a dead helper import. A tempting repair would have been to repoint production teardown at the surviving `tools` parser, giving an operator analysis program in-process authority over application shutdown and reconnecting current runtime behavior to obsolete telemetry assumptions.

## Root cause

Migration tooling and production diagnostics had never been given a hard ownership boundary. A historical convenience hook survived after the parser and the architecture it understood had ceased to be current.

## Correction

Production shutdown now only flushes/closes telemetry. Analysis consumes logs **after process exit** and out of process.

`tools/run_tests.py` likewise delegates to the canonical `tests/run_chunked.py` authority instead of retaining an independent suite manifest.

`tests/test_tooling_ownership.py` permanently rejects production imports from `tools`/`scripts` analysis modules.

## Failed / forbidden repair

Do **not**:

- change the dead import from `scripts.spotify_vis_metrics_parser` to `tools.spotify_vis_metrics_parser`;
- copy parser logic into `main.py`;
- run argparse/reporting tools from shutdown hooks;
- preserve obsolete parser schemas by restoring old GL/overlay owners;
- let a tool create a second test/performance authority because the canonical path is inconvenient.

## Durable rule

```text
production emits evidence
operator tools consume evidence out of process
```

Runtime construction harnesses are allowed only when their purpose specifically requires constructing the current owner (for example focused Quick smoke or ImageWorker shared-memory lifecycle proof). They do not become production lifecycle participants.

See `Docs/Tooling_Audit_2026-09-01.md`.
