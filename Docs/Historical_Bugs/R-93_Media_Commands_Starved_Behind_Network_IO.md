# R-93 — Media Commands And Refreshes Starved Behind Network IO

Date: 2026-09-23  
Status: SOLVED — runtime audit PW-02, accepted from operator logs 2026-09-23

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

## Observed Failure

Media transport commands and the Media refresh (the Visualizer's play/pause truth) could wait behind slow
network work. Fault injection on a real ThreadManager IO pool: four stalled network tasks kept a transport
command and an activation refresh queued past 0.42 s.

## Root Cause

Media work shared the FIFO IO pool with feeds/providers. FIFO head-of-line blocking meant any burst of slow
network tasks delayed user-facing media actions.

## Rejected Fix

Running Media work on the WinRT observation affinity worker: observation teardown waits only 2 s on that single
worker, and a WinRT query can hold it that long.

## Fix

`ThreadManager` offers named dedicated affinity workers; the shared Media runtime creates a lazy `"media"` lane
on first use, submits refreshes there and injects it into its controller for commands, and stops it at
retirement (`a8e38012`, `468ec0cc`). Refresh one-in-flight/one-pending, command de-dup and event authority are
unchanged. Operator logs: IO max 1736.9 ms under load while the media lane stayed ≤7.17 ms.

## Regression Coverage

`tests/test_media_io_starvation.py` (formerly strict xfails, now pass).

## Guardrail

Durable rule in `Spec.md` (Media lane): user-facing media actions never share a FIFO queue with network IO.
