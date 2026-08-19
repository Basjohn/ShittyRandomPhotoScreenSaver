# Hypothesis Record — Slice K / cba50b50 — Synchronous GSMTC Wait

## Hypothesis

The synchronous `done.wait(timeout=2.5)` in the GUI-owned transport path is the owner of:
- Pause/Play hitch;
- broad `dispatch_pending_skips`;
- visualizer visible-handoff collapse.

## Source correction

Commit:

```text
cba50b5067d654ee0865ba75c1c54a0161b43fef
```

Slice K changes transport command execution to fire-and-forget IO ownership.

## Mechanism status

**CONFIRMED REAL DEFECT / FIX VALID**

The GUI should not wait for a WinRT transport command result.

## Root-cause status

**REJECTED BY INSTALLED EVIDENCE**

Third installed run at:

```text
8ac2421e2bc0a7153942fc33eb9f348b505cde9d
```

still visibly hitches through:
- mouse Pause/Play;
- physical media key;
- all visualizer modes.

The old wait cannot be the primary shared owner if the hitch survives after its removal and also
appears on the OS-executed media-key path.

## Durable conclusion

Retain the asynchronous command ownership unless command correctness fails.

Do not resurrect this as the primary Pause/Play root-cause theory without new contradictory evidence.
