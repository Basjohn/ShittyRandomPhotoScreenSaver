# Documentation Maintenance

Last updated: 2026-08-09

Rules for keeping SRPSS documentation accurate, navigable, and cheap for Codex to read.

## 1. File Stability

- Existing files and documents are edited in place.
- **Do not rename or move any file, directory, or document unless the user explicitly requests that exact rename or move.**
- Do not create “v2”, “new”, “replacement”, or “proposed” canonical duplicates.
- Preserve incoming links and paths.

## 2. Document Roles

| File | Owns |
|---|---|
| `Docs/00_PROJECT_OVERVIEW.md` | short orientation and read order |
| `Index.md` | navigation and ownership map |
| `Docs/Guardrails.md` | durable cross-cutting safety rules |
| `Docs/Contracts.md` | task-to-owner routing |
| `Spec.md` | stable architecture and behaviour |
| `Current_Plan.md` | active unfinished work |
| focused docs | subsystem-specific contracts |
| `Docs/Historical_Bugs/` | full standalone significant-regression narratives |
| `Docs/Historical_Bugs.md` | compact historical status/navigation map |
| `Docs/Regression_Notes.md` | small resolved notes |
| `Docs/TestSuite.md` | validation levels and gates |
| `Docs/Harness_Index.md` | recurring commands |

State a rule once in the strongest owner document. Other documents link to it.

## 3. Codex Read Budget

Target sizes:

- Project Overview: under 100 lines;
- Guardrails: under 450 lines;
- Contracts: under 220 lines;
- Current Plan: under 250 lines;
- Documentation Maintenance: under 150 lines;
- Index: concise tables, no module essays;
- Spec: stable contracts only;
- focused architecture docs may be longer but are read only for relevant work.

When a document exceeds its role:

- move module-specific detail to the existing focused document;
- move completed evidence to historical/benchmark records;
- remove duplicated prose;
- do not solve size by renaming the file.

## 4. Drift Check

Run after:

- architecture changes;
- settings/default/import changes;
- visualizer/transition changes;
- widget descriptor changes;
- logging/storage path changes;
- completion of a large task.

### Navigation

- every canonical document is reachable from `Index.md`;
- removed references disappear from all core docs;
- new architectural owners appear in `Index.md` and `Contracts.md`;
- implementation helpers do not clutter `Index.md`.

Useful:

```powershell
rg -n "OldName|RemovedName" Index.md Spec.md Current_Plan.md Docs tests
rg --files Docs core engine rendering widgets ui tools tests
```

### Ownership

Check for duplicate authority in:

- settings;
- visualizer identity/activation;
- transition identity;
- widget descriptors;
- display lifecycle;
- compositor scheduling;
- GL resource cleanup.

Useful:

```powershell
rg -n "SettingsManager|visualizer_mode_registry|transition_registry|widget_descriptors" core engine rendering widgets ui Docs
rg -n "__getattr__|__setattr__|fallback|retry|generation|makeCurrent|doneCurrent" engine rendering widgets Docs
```

### Active plan

- completed work is removed;
- benchmark narratives are archived elsewhere;
- stable rules move to `Spec.md` or focused docs;
- dated failures move to history;
- future low-priority ideas move to `Future_Cleanup.md`.

### Tests and harnesses

- `Docs/TestSuite.md` lists validation classes, not every test description;
- `Docs/Harness_Index.md` lists recurring procedures only;
- rejected architecture tests are removed or rewritten;
- user-visible failures have meaningful runtime-shaped coverage.

## 5. Architecture Drift Rule

Documentation must not canonize an implementation merely because it exists.

Before adding a mechanism to `Spec.md` or `Guardrails.md`, ask:

1. Is it a durable product/safety invariant?
2. Has runtime evidence validated it?
3. Is it simpler than the alternatives?
4. Does it preserve visualizer fidelity and lifecycle safety?
5. Is the mechanism better placed in a focused design document?

Paint acknowledgements, terminal transactions, partial reinit, or other provisional machinery do not become permanent rules by surviving one test suite.

## 6. Link and Name Verification

Before completion:

```powershell
rg -n "\.md|Docs/" Index.md Spec.md Current_Plan.md Docs
```

Verify referenced tracked paths exist.

Do not rename files to repair broken links. Correct the link or update the existing file in place.

## 7. Good Outcome

- Codex can identify the owner without reading the entire repository.
- Core docs do not duplicate implementation detail.
- Current work is obvious.
- Stable rules are not mixed with benchmark history.
- Existing names and paths remain stable.
- Runtime evidence can overturn a bad implementation-specific assumption.
