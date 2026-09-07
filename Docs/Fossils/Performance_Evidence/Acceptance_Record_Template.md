# Acceptance Evidence — YYYY-MM-DD HH:MM — <short name> — PASS/FAILED

## Provenance

Evidence classes:
- PRIMARY RAW
- PRIMARY OPERATOR
- CONTEMPORANEOUS REVIEW
- HISTORICAL SECONDARY
- INFERENCE

Raw pack:

```text
<filename>
SHA-256: <hash>
```

Log source identity:

```text
[SOURCE_HEAD] <sha>
```

If absent, write:

```text
Source SHA: not embedded.
```

Do not guess.

## Operator-visible result

<what the installed application actually looked/felt like>

## Logical runtime

<steps, skips, slow steps, failures, cadence>

## Physical presentation

### High-refresh display

<FPS, acceptance, tails>

### 60 Hz / visualizer display

<FPS, acceptance, tails>

## Delivery-stage attribution

<wake timing, dispatch pending, paint pending, request age>

## Relevant subsystem cost

<widget/media/compute/GPU>

## Hypotheses changed by this run

### Supported
- ...

### Weakened
- ...

### Rejected
- ...

## Conclusion

<what is allowed / forbidden next>

Do not rewrite this record after later runs. Add a later record that supersedes it.
