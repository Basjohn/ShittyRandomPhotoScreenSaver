# Test Durability

SRPSS tests should be strict about **contracts** and tolerant of **authored data that is allowed to change**. A useful regression bar should fail when product behavior regresses, not because an operator changed a default, added a Visualizer mode, renamed a curated preset, or tuned a shipped preset value.

This guide owns test-authoring durability policy. `Docs/TestSuite.md` owns current suite/acceptance routing. Production source and canonical settings/registries remain the authorities that tests consume.

## Archived visualizer oracle trap (R-112)

Do not regenerate synthetic/golden expected data from the *current* curated Organs/Sphere/other editable preset and call the result a regression oracle. Own the fixture explicitly and test behavior against that independent source; shipped preset files receive schema, ownership, parse and preservation checks only. An intentional operator edit is not an error.

## 1. The rule

Before writing an exact assertion, ask what owns the expected value.

- If the value is a mutable product authority, **read or derive from that authority**.
- If the value belongs to the test fixture, **assert it exactly**.
- If the value is a deliberate protocol, compatibility, golden, safety or negative-control invariant, **assert it exactly and say why**.

Changing a test every time normal product authoring progresses is a smell unless the changed product contract is exactly what that test exists to guard.

## 2. Mutable authorities must not be copied

### Canonical defaults

Do not duplicate today's default value in an unrelated behavior test.

Bad:

```python
settings = SettingsManager()
assert settings.get("widgets.foo.position") == "Bottom Right"
```

when the operator is free to change that default.

Good:

```python
expected = require_canonical_default("widgets.foo.position")
assert settings.get("widgets.foo.position") == expected
```

Better still, when the behavior being tested does not care about the exact authored value, assert the relevant schema or relationship instead.

Tests whose purpose is **default authority itself** may compare all consumers to the canonical default. The canonical source is still the expected-value owner.

### Extensible registries and catalogs

Visualizer modes, transitions, providers, preset catalogs and similar extensible families must be discovered from their owning registry/descriptor/capability.

Bad:

```python
modes = ("spectrum", "oscilloscope", "sine_wave", "bubble")
```

when the test means "every registered mode."

Good:

```python
for mode in VISUALIZER_MODE_IDS:
    ...
```

For semantic subsets, derive from capabilities where possible. For example, test every descriptor whose presentation policy is carded rather than copying the current carded-mode names.

Do not assert a current catalog count unless the count itself is a fixed product/protocol requirement. Tests for "every implementation" should grow automatically when the registry grows.
Derivation must continue through the whole oracle: expected loop totals, release counts, final owners and ordering assertions must come from the same authority. Replacing only the input list while leaving `== 110`, `== 109` or `final == "today_last_mode"` behind is still a brittle catalog copy.

### Curated presets and other authored assets

A behavior/parser/render test must not depend on `preset_1_whatever.json` containing today's exact artistic choices unless the shipped preset itself is the subject under test.

Use one of these instead:

1. a self-owned temporary preset fixture containing the exact values required by the test;
2. a registry/catalog query plus schema/ownership assertions;
3. a dedicated shipped-asset audit when validating the curated tree itself.

Preset infrastructure tests may deliberately exercise filenames, sparse slot numbers, manifest mirroring and user-authored entries using test-owned files. Those names and payloads are fixture data, not product authority duplication.

A golden visualizer replay must keep its *input* separate from operator-authored presets. A
reference can contain a frozen, test-owned configuration, but a regeneration command must
not re-resolve today's shipped presets. Use behavioral/metamorphic GL assertions for
expected visual effects; pixel-for-pixel images are optional review artifacts unless
bitwise identity is itself a genuine protocol contract. Never bless updated artistic
choices merely to make a visual golden pass.

The same principle applies to themes, layout slots and other operator-authored content.

### Documentation prose is not a behavior oracle

Do not prove a runtime or architecture contract by opening a Markdown file and asserting that today's sentence is present.
That test protects wording, not behavior, and turns harmless documentation editing into a product RED.

Bad:

```python
text = (ROOT / "Docs" / "Guardrails" / "Visualizer_Presentation.md").read_text()
assert "inactive modes perform zero recurring work" in text
```

Good: exercise the dormant mode and assert that it performs zero recurring work. The document explains the contract; the
test proves it.

A generated documentation artifact may be tested when **the generated document is itself the product output**: generated
API tables, machine-produced SST snapshots, packaging manifests, or similar deterministic artifacts. Keep those tests
separate from runtime behavior and annotate the content assertion immediately above it with:

```python
# DOCUMENT-CONTENT INVARIANT: generated API table is itself a shipped artifact.
```

Merely passing a Markdown-looking path into path-selection/packaging code is not a prose assertion and remains valid.

## 3. Exact brittleness is sometimes the contract

Do **not** weaken tests merely to avoid maintenance. Exact assertions are appropriate for:

- compatibility/migration semantics where old persisted input must resolve identically;
- protocol or binary-format constants;
- hard resource/capacity bounds whose number is itself the requirement;
- accepted goldens and negative controls;
- Bubble temporal/reactivity guardrails and other explicit feel/visual contracts;
- exact geometry/pixel/state restoration where approximation would hide a regression;
- fixture-owned round trips where the fixture deliberately sets a value and must receive that same value back;
- one-shot/cardinality/lifecycle assertions such as "exactly one callback" when singular ownership is the architecture.

When a high-signal static durability rule would otherwise resemble an intentional exact pin, annotate the test immediately above the assertion with a reason:

```python
# EXACT-VALUE INVARIANT: binary record version is part of the on-disk protocol.
assert version == 1
```

or:

```python
# DURABILITY: exact - compatibility mapping for already-shipped persisted input.
assert migrated == expected_legacy_result
```

The marker is not a waiver for convenience. It documents why future maintainers should preserve the exact bar.

## 4. Ordering

Do not pin ordering merely because a registry happens to have an order today.

Assert order exactly only when order has behavior, such as:

- cycle/navigation order;
- z-order or draw order;
- priority/fallback order;
- deterministic serialization/protocol order;
- an authored user-facing ordered catalog whose order is itself intentional.

Otherwise compare sets, keyed mappings, or derive the expected order from the authority.

The same rule applies to UI choice controls. If a test means “select the semantic value `custom`,” find/select that value by
stable item data or token rather than assuming it will forever be combo index `5`. Numeric indices are exact only when index
semantics themselves are the contract (for example a dedicated index-binding adapter test).

## 5. Two audit layers

### Blocking high-confidence audit

Run:

```powershell
python tools/test_durability_audit.py
python -m pytest tests/test_test_suite_durability.py tests/test_default_pin_scan.py tests/test_test_oracle_review.py -q
```

The audit intentionally flags only high-confidence authority-copy patterns. It is a maintained regression bar, not a general style linter.

Current protected smells include:

- canonical defaults compared directly or through a local alias to copied literals;
- canonical default snapshots compared to copied authored literals;
- behavior tests opening a specifically named shipped Visualizer preset;
- fixed cardinality assertions over extensible registries;
- large hand-copied Visualizer mode or transition catalogs (including mapping keys);
- authored Markdown prose used as a proxy oracle for runtime behavior.

A new high-confidence recurring smell may be added to the audit when it can distinguish authority duplication from legitimate fixture exactness without creating a repair treadmill.

### Review-only heuristic

Run:

```powershell
python tools/default_pin_scan.py --summary
python tools/default_pin_scan.py
```

This deliberately remains review-only, but it suppresses one high-confidence false-positive class: when the same test explicitly authors a literal ``{key: value}`` mapping before asserting that same key/value, the value is treated as fixture-owned rather than an unexplained copy of the production default. Computed mappings, control setters and helper-driven setup stay in the queue for human classification. Do not mechanically rewrite the remaining hits; a candidate may still be a correct migration contract, geometry oracle or negative control.


## 5.1 Source-string and UI-copy oracles are review-only by default

Static source tests are not inherently bad. They are valuable when the **absence or presence of a source construct is itself the architecture contract**, such as forbidding a polling call, retired import, fallback presenter or per-frame Settings read. They are brittle when they merely freeze today's method name, button caption, source layout, branch spelling or helper call.

Prefer behavioral tests whenever there is a cheap deterministic seam. Keep a source oracle when behavior would require constructing the wrong subsystem merely to prove a negative architecture rule. When the exact spelling is intentionally the contract, annotate it near the assertion:

```python
# SOURCE-ORACLE INVARIANT: process polling would reintroduce a forbidden scheduler.
assert "process.poll()" not in source
```

Run the advisory review queue with:

```powershell
python tools/test_oracle_review.py
```

It does not fail CI. The queue distinguishes source-string implementation oracles, exact ``widget.text() == ...`` UI-copy oracles, and potentially intrusive window operations. Exact UI text remains appropriate when wording/formatting itself is the product contract; otherwise assert the stable semantic state or action instead. Intentional exact copy may be annotated with ``UI-COPY INVARIANT`` near the assertion. **A review finding never justifies skipping, xfail-ing, deselecting or stopping the test that produced it, and it is not an operator-action request.** Agents should keep the suite running and either make a high-confidence durability improvement in the same slice or leave the candidate in the review queue.

## 5.2 Tests should not punish the operator

The development machine is also the operator's only physical acceptance machine. Automated tests should therefore be silent and non-intrusive whenever the evidence level allows it.

Use the least intrusive surface that still proves the contract:

1. no top-level window for pure model/signal/geometry tests;
2. `QT_QPA_PLATFORM=offscreen` for tests that do not need the native GL/window-system path;
3. `tests._invisible_windows.keep_off_screen()` or `WA_DontShowOnScreen` for real native/GL windows that must be shown/exposed to initialize correctly;
4. a deliberately visible/focused window only when real focus, OS input routing, taskbar/DWM behavior or physical pixels are the contract. Such tests belong in an explicit physical/operator gate, not a routine suite.

Do not replace a real-GL test with software/offscreen rendering merely to hide it. Visibility containment must preserve the evidence being claimed. Avoid `raise_()`, `activateWindow()`, fullscreen display and focus theft in automated profiles unless the test explicitly owns that behavior. **Do not solve operator intrusion by skipping the test:** if native visibility/focus is truly part of the contract, the test still runs; if it is not, contain the same test surface invisibly/minimized without weakening its assertions.

`tools/test_oracle_review.py` also reports potentially visible window operations that lack a recognized containment pattern. This is advisory because only the test owner can decide whether a native visible surface is essential.

## 5.3 Async/runtime-shaped fixtures must preserve callback topology

A synchronous fake may execute expensive work immediately for speed, but it must not invent callback re-entrancy that production never has. If production submits work and receives completion later, a deterministic test fake should queue the completion and let the test drain that queue explicitly. This keeps ordering/lifecycle assertions meaningful without sleeps, polling or real worker threads.

Do not "simplify" a shared-owner/runtime test by invoking its completion callback from inside ``submit_*`` when the real owner receives that callback asynchronously. That can create impossible nested state transitions, invert cache/fresh metadata, or turn serialized admission into recursion. Prefer a tiny fixture-owned completion queue plus ``drain_one()``/``drain()`` helpers.

Likewise, do not pin an incidental callback count when the contract is a state boundary such as "remain loading until all providers settle." Step the deterministic queue through that boundary and assert the semantic state before and after it.

## 6. Review questions

For any suspicious assertion, answer these in order:

1. **What behavior is this test supposed to protect?**
2. **Who owns the expected value?** Canonical defaults, registry, descriptor, fixture, compatibility table, protocol, golden?
3. **Would an intentional product-authoring change require this test to change even though the protected behavior stayed correct?** If yes, the test is probably brittle.
4. **Can the expectation be expressed as a relationship?** Consumer equals authority, every registered item participates, disabled item stays dormant, round-trip preserves authored fixture, etc.
5. **If exactness is intentional, is the reason obvious enough to survive the next cleanup?** Add an exact-value marker when useful.

## 7. New feature checklist

When adding a mode, transition, provider, preset family or Settings surface:

- extend the canonical source/descriptor first;
- prefer registry-derived parametrization so existing family-wide tests pick it up automatically;
- add feature-specific tests only for its unique behavior/capabilities;
- do not update unrelated test mode lists/counts merely to make them green;
- use self-owned fixtures for parser/round-trip tests;
- keep shipped-asset validation separate from behavior validation;
- run the blocking durability audit before handoff.
