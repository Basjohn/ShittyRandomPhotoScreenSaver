# Extruded Bubble — targets, lab and investigation

**Accepted baseline.** Extruded Bubble and its later scoped drift/viewport/ray follow-up are closed. This folder is the
durable target/investigation/regression reference; reopen only a concrete reproduced defect. The accepted follow-up contract
lives in [Motion, reactivity and viewport plan](Motion_Reactivity_Viewport_Plan.md), performance findings in
`Docs/Audits/EB_Performance_Investigation_2026-10-29.md`, and the explicitly deferred vectorised rewrite in `Future_Work.md`.

The dated notices below are historical evidence. They do not restore the retired recovery queue or imply that an old
source-level defect remains present today. [Additional source-audit findings and falsifiers](Additional_Source_Audit_2026-10-22.md)
and the [Acceptance Runbook](Acceptance_Runbook.md) remain useful when reproducing a related regression.

**Historical review (23 October):** P1 is generally good and its latest shown idle capture is operator-accepted
([Investigation §57](Investigation.md#57-idle-particle-display-radius-and-authored-energy-2026-10-23)).
Those items were open at that checkpoint; they are preserved as historical evidence rather than current task status.

**This is the one home for EB images and investigation details.** Earlier live rejection: activation overshoot/
yank-down, large/small size judder, unreliable close DoF/pixelation, and about 50% excessive active speck glow.
Spherical form and readable overlap depth take priority over glow tuning. Details and solution plans:
[Investigation §19](Investigation.md#19-latest-live-rejection-overshoot-judder-and-near-field-pixels). Reproducible startup/ramp attribution and unresolved DoF/lighting boundaries:
[Investigation §20](Investigation.md#20-godzip-96d5408a09-independent-follow-up-startup-reference-overshoot-2026-10-20).
New operator-rejected camera-orbit oblongness, the strict 1.5px near-layer switch and the
other-lane driver audit are in [Investigation §21](Investigation.md#21-camera-projection-judder-branches-and-other-lane-attribution-2026-10-20-source-level-only).
The latest **unaccepted Settings-size, source-ramp and centred-camera implementation candidates**
are documented in [Investigation §22](Investigation.md#22-2026-10-20-superseding-implementation-candidates-never-visual-acceptance).
A Qt-free [projection/near gate probe](../../../tools/visualizer_replay/extruded_bubble_projection_gate_probe.py)
is numerical attribution only. Earlier camera, material, judder and reaction failures are not closed by the scoped P1 idle review.
New work enters `Current_Plan.md` only when a concrete EB regression is reproduced. Earlier rejected native results remain in the ledger; the scoped P1 idle review above supersedes only its shown appearance. A physical world and passing checks do not establish spherical
glass, depth, musical response or parity with these targets.

## Slim GODZIP resource boundary (current handoff)

Normal GODZIPs intentionally exclude root `assets/`, root `references/`, `ui/assets/` and operator themes; this EB reference also omits bulky local `Lab/2026-10-18/` and `.artifacts/evidence/visualizers/extruded_bubble/20261020/` payloads, some original mock image bytes, and the separate workstation 11.6 GB evidence archive. The paths below describe the **full local repository/reference collection**, not files guaranteed to exist in the slim archive. Do not treat an absent Lab/Evidence file as permission to delete its requirement, reconstruct a screenshot or fetch an unrelated checkout. Current source, text Investigation/Target and the live `Current_Plan.md` are sufficient for code/docs handoffs; request a specifically needed image or recording only for a visual acceptance gate. EB Lab remains deliberately out of the archive.

## Start here

| Material | Canonical location | Meaning |
| --- | --- | --- |
| Original seven visual goals and two annotated mocks | [Targets/Originals](Targets/Originals) | Visual requirements; preserved original pixels |
| Lab preset comparison sheet | `Lab/2026-10-18/presets_sheet.png` (local historical evidence; omitted here) | Mock/product comparisons that exposed the gap |
| Complete historical lab material | `Lab/2026-10-18/` (local historical evidence; omitted here) | All 85 original files, including scene recipes and comparisons; reference, not current acceptance |
| Durable visual/behavior contract and earlier findings | [Target.md](Target.md) | Required appearance, ownership and preserved design provenance |
| Investigation, attempts, measurements and evidence limits | [Investigation.md](Investigation.md) | Full failure ledger; §§15–18 cover physical world, rejected response, clarification and passage-role candidate |
| Astra High visual audit | [Visual_Audit_2026-10-20.md](Visual_Audit_2026-10-20.md) | Concrete material/defocus leads and native falsifiers |
| Original forensic captures | `.artifacts/evidence/visualizers/extruded_bubble/20261020/forensics/` (local historical evidence; omitted here) | 1,029 files moved from the former logs directory |
| Recovery captures and paired response custody | `.artifacts/evidence/visualizers/extruded_bubble/20261020/recovery/` (local historical evidence; omitted here) | 8,009 files moved from the former logs directory |
| Asset provenance and move verification | [asset_manifest.json](asset_manifest.json) | Original paths, sizes, SHA-256 for all target/lab files and attachment deduplication |

The target/lab images, recipes, manifest and documents are versioned. The 11.6 GB native evidence archive of
20 October stays local and ignored in the evidence layout, `.artifacts/evidence/visualizers/extruded_bubble/20261020/`
(formerly `Evidence/2026-10-20/` inside this folder; mapping in `tools/artifact_migration.py` `RELOCATED`). Capture receipts preserve the paths and producer hashes from their
original runs; those historical receipt strings were not rewritten. The original recorded sound inputs stay
with the recorder at `logs/visualizer_recordings`, not in a competing audio library.

**Regression protocol:** [Execution & visual acceptance runbook](Acceptance_Runbook.md) preserves the old gate structure for
reproducing related failures. It is not a live task queue; accepted EB status changes only when a concrete regression is
reopened and physically evaluated.

## 22 October active architectural repair and continued SCENE rejection

The local historical screenshot `Evidence/2026-10-22_SCENE_operator_rejected_clustering.png` shows **SCENE visibly clustered** after the R45 handoff: bright islands and wide empty gaps. This is rejected native appearance `[~]`, not a passed SCENE distribution fix. New audit also establishes Surface's dominant view-angular fan, source/end shafts without lateral beam width, inconsistent Deep positional light/glow and approximate four-bubble attenuation. Lighting-authority consolidation **precedes** adding a distinct Lighting Coverage BEAM/SCENE control. Full new findings, exact code owners, mode-switch bubble-cohort hypothesis and the test matrix: [Lighting Authority Repair](Lighting_Authority_Repair.md). The [Acceptance Runbook](Acceptance_Runbook.md) preserves the native evidence protocol for this historical failure. R45's candidate and the full failure inventories remain historical evidence, not current work status.

## Response roles — operator clarification, 2026-10-20

| Passage | Large bubbles | Small bubbles and other lanes |
| --- | --- | --- |
| Softer/changing music | Significant breathing, especially downward contraction; do not maintain a generic inflated hold | Express vocal/high/body changes at a useful visible scale |
| Sustained/loud music | Carry sustained body while retaining meaningful musical changes | Keep expressing changes within that passage; avoid a bass/transient-held small field or pinned emission/drift/speed/rays |
| Silence/idle | Gently settle into tiny collapsed rest | Every lane remains extremely slow, with gentle release and visibly sparse living motion where authored |

Accepted 2D Bubble is the response-scale comparator on **the same sections of recorded sound**. Its current
small lane is not literally bass-free: it has bounded hot/body support, a separate mid/high running reference,
clean positive changes and its own release. Its transient/event lane does not directly own ordinary size.
Reproduce the useful role separation; do not copy a generic shared loudness hold. Controls and preset settings
may be corrected where needed, with actual endpoint/Range effects proved. The passage-role source candidate
and its captures are not an accepted physical response baseline.

**Operator clarification, 22 October:** the ideal *visual* comparison is **2D Bubble with Dynamic Floor
ON** (accepted reference) versus **Extruded Bubble with Dynamic Floor OFF** (required EB goal), at matching
recorded musical timestamps. Dynamic Floor can even hurt response when song dynamics change, so EB must match
the useful musical breathing, not blindly reproduce the floor's adaptive behavior. See the detailed `Target.md`
reactivity contract and `Acceptance_Runbook.md` when reproducing a related regression. This paragraph records the
historical comparison requirement, not current task status.

## Target and lab registry

`asset_manifest.json` owns each current target path and its `lab_recipe` identity. Renamed originals were
reconciled by exact SHA-256 equality to the historical inventory, not by guessed preset order. In particular,
`Preset1Goal.png` is the original ExBubble3, while `AchievedPreset2Goal.png` is the original ExBubble1.
Goal filenames are operator assignments; historical recipe identities do not renumber mutable production presets.

| Current target | Historical lab recipe |
| --- | --- |
| [AchievedPreset2Goal](Targets/Originals/AchievedPreset2Goal.png) | ExBubble1 |
| [ExBubble2](Targets/Originals/ExBubble2.png) | ExBubble2 |
| [Preset1Goal](Targets/Originals/Preset1Goal.png) | ExBubble3 |
| [Preset4Goal](Targets/Originals/Preset4Goal.png) | ExBubble4 |
| [Preset5Goal](Targets/Originals/Preset5Goal.png) | ExBubble5CameraAbyss |
| [Preset6Goal](Targets/Originals/Preset6Goal.png) | ExBubble5Cameradown |
| [Preset7Goal](Targets/Originals/Preset7Goal.png) | ExBubble6Diagonal |

The executable composition lab `tools/labs/extruded_bubble_lab.py` resolves paths through that registry before
creating GL resources. Missing/duplicate associations fail loudly; archived lab output is never substituted.
Archived recipe payloads may be absent from slim handoffs and are not required by the current executable lab.

## Historical recovery evidence (20 October; not current acceptance)

- Historical passage-role candidate: `.artifacts/evidence/visualizers/extruded_bubble/20261020/recovery/passage_roles_native_p1/contact.png`,
  `.artifacts/evidence/visualizers/extruded_bubble/20261020/recovery/passage_roles_native_p7_1440/contact.png`,
  `.artifacts/evidence/visualizers/extruded_bubble/20261020/recovery/passage_roles_final/summary.json`.
  That checkpoint was unaccepted; it does not supersede the accepted baseline at the top of this document.
- Rejected P1 at that checkpoint: `.artifacts/evidence/visualizers/extruded_bubble/20261020/recovery/clean_body_native_p1/contact.png`,
  `.artifacts/evidence/visualizers/extruded_bubble/20261020/recovery/clean_body_native_p1/frame_0060.png`,
  `.artifacts/evidence/visualizers/extruded_bubble/20261020/recovery/clean_body_native_p1/motion.gif`.
- Rejected P7 at that checkpoint: `.artifacts/evidence/visualizers/extruded_bubble/20261020/recovery/clean_body_native_p7_1440/contact.png`,
  `.artifacts/evidence/visualizers/extruded_bubble/20261020/recovery/clean_body_native_p7_1440/frame_0090.png`.
- Same-sound accepted 2D reference: `.artifacts/evidence/visualizers/extruded_bubble/20261020/recovery/clean_body_2d_reference/contact.png`.
- Paired source custody: `.artifacts/evidence/visualizers/extruded_bubble/20261020/recovery/matched_body_final/summary.json`.
  Windowed logical ratios do not establish listening, display timing or visual acceptance.

The annotated targets are direct acceptance references:

Blue sphere/light/trail local reference: `Targets/Originals/Informational mock.png` (omitted from this handoff).

Copper sphere/light/trail local reference: `Targets/Originals/Informational mock 2.png` (omitted from this handoff).
