# Extruded Bubble — targets, lab and investigation

**Closed 2026-10-25 (operator):** Extruded Bubble is accepted; its recovery checklist (§4B, G00–G33, EB-*) is retired from `Current_Plan.md` (history: `git show 3c6cf7d8:Current_Plan.md`). This folder remains the reference for its targets, lab and investigation; reopen only on a concrete new defect.

**28 October scoped follow-up — implementation authorized:** drift consumers/ranges, ordinary stream inheritance,
framed viewport behavior, microbubble pause/resume and reliable ray controls are tracked in
[Motion, reactivity and viewport plan](Motion_Reactivity_Viewport_Plan.md), which also holds the remaining
idle-use observation (EB28-8). EB has no live `Current_Plan.md` tasks (closed 2026-10-31); performance is closed in
`Docs/Audits/EB_Performance_Investigation_2026-10-29.md`, its deferred rewrite in `Future_Work.md`.

The 22–23 October notices below are historical evidence, superseded by the 25 October closure. They do not restore the
retired recovery queue or establish that an old source-level defect remains present today.

**NEW 22 October independent code audit:** [Additional source-audit findings and falsifiers](Additional_Source_Audit_2026-10-22.md). Verified code behavior includes quiet/high Breathing handle coupling, Deep/SCENE water-plane EOL leakage, SCENE→BEAM cohort premature End retirement, GPU speck photometric masking, stacked quiet range compression and disabled-ray intermediate render work. These are **not visually accepted fixes**. See the single live `Current_Plan.md` §4B G00–G33 gates and [Acceptance Runbook](Acceptance_Runbook.md); retain every existing issue.

**Latest review (23 October):** P1 is generally good and its latest shown idle capture is operator-accepted
([Investigation §57](Investigation.md#57-idle-particle-display-radius-and-authored-energy-2026-10-23)).
Long lifecycle, remaining specific P1 defects and substantial P7/other-preset fidelity changes stay open.

**This is the one home for EB images and investigation details.** Earlier live rejection: activation overshoot/
yank-down, large/small size judder, unreliable close DoF/pixelation, and about 50% excessive active speck glow.
Spherical form and readable overlap depth take priority over glow tuning. Details and solution plans:
[Investigation §19](Investigation.md#19-latest-live-rejection--overshoot-judder-and-near-field-pixels). Reproducible startup/ramp attribution and unresolved DoF/lighting boundaries:
[Investigation §20](Investigation.md#20-godzip-54cac99a6a-independent-follow-up-startup-reference-overshoot-2026-10-20).
New operator-rejected camera-orbit oblongness, the strict 1.5px near-layer switch and the
other-lane driver audit are in [Investigation §21](Investigation.md#21-camera-projection-judder-branches-and-other-lane-attribution-2026-10-20-source-level-only).
The latest **unaccepted Settings-size, source-ramp and centred-camera implementation candidates**
are documented in [Investigation §22](Investigation.md#22-2026-10-20-superseding-implementation-candidates-never-visual-acceptance).
A Qt-free [projection/near gate probe](../../../tools/visualizer_replay/extruded_bubble_projection_gate_probe.py)
is numerical attribution only. Earlier camera, material, judder and reaction failures are not closed by the scoped P1 idle review.
Live tasks remain in
[`Current_Plan.md`](../../../Current_Plan.md#4b-extruded-bubble--operator-rejected-behavior-every-acceptance-gate-remains-open).
Earlier rejected native results remain in the ledger; the scoped P1 idle review above supersedes only its shown appearance. A physical world and passing checks do not establish spherical
glass, depth, musical response or parity with these targets.

## Slim GODZIP resource boundary (current handoff)

Ordinary GODZIPs **intentionally exclude** bulky `Lab/2026-10-18/` and `Evidence/2026-10-20/` payloads, some original mock image bytes, and the separate workstation 11.6 GB evidence archive. The paths below describe the **full local repository/reference collection**, not files guaranteed to exist in the slim archive. Do not treat an absent Lab/Evidence file as permission to delete its requirement, reconstruct a screenshot or fetch an unrelated checkout. Current source, text Investigation/Target and the live `Current_Plan.md` are sufficient for code/docs handoffs; request a specifically needed image or recording only for a visual acceptance gate. EB Lab remains deliberately out of the archive.

## Start here

| Material | Canonical location | Meaning |
| --- | --- | --- |
| Original seven visual goals and two annotated mocks | [Targets/Originals](Targets/Originals) | Visual requirements; preserved original pixels |
| Lab preset comparison sheet | [presets_sheet.png](Lab/2026-10-18/presets_sheet.png) | Mock/product comparisons that expose the gap |
| Complete historical lab material | [Lab/2026-10-18](Lab/2026-10-18) | All 85 original files, including scene recipes and comparisons; reference, not current acceptance |
| Durable visual/behavior contract and earlier findings | [Target.md](Target.md) | Required appearance, ownership and preserved design provenance |
| Investigation, attempts, measurements and evidence limits | [Investigation.md](Investigation.md) | Full failure ledger; §§15–18 cover physical world, rejected response, clarification and passage-role candidate |
| Astra High visual audit | [Visual_Audit_2026-10-20.md](Visual_Audit_2026-10-20.md) | Concrete material/defocus leads and native falsifiers |
| Original forensic captures | [Evidence/2026-10-20/forensics](Evidence/2026-10-20/forensics) | 1,029 files moved from the former logs directory |
| Recovery captures and paired response custody | [Evidence/2026-10-20/recovery](Evidence/2026-10-20/recovery) | 8,009 files moved from the former logs directory |
| Asset provenance and move verification | [asset_manifest.json](asset_manifest.json) | Original paths, sizes, SHA-256 for all target/lab files and attachment deduplication |

The target/lab images, recipes, manifest and documents are versioned. The 11.6 GB native evidence archive stays
local and ignored, **inside this folder**. Capture receipts preserve the paths and producer hashes from their
original runs; those historical receipt strings were not rewritten. The original recorded sound inputs stay
with the recorder at `logs/visualizer_recordings`, not in a competing audio library.

**Active work and visual evidence:** [Execution & visual acceptance runbook](Acceptance_Runbook.md) documents every open gate in architectural order (G00–G33). The authoritative task statuses remain in `Current_Plan.md` §4B; past implementation notes and this README are not alternative task queues. A source test or attractive still never closes a visual failure.

## 22 October active architectural repair and continued SCENE rejection

The [newer operator screenshot](Evidence/2026-10-22_SCENE_operator_rejected_clustering.png) shows **SCENE still visibly clustered** after the R45 handoff: bright islands and wide empty gaps. This is rejected native appearance `[~]`, not a passed SCENE distribution fix. New audit also establishes Surface's dominant view-angular fan, source/end shafts without lateral beam width, inconsistent Deep positional light/glow and approximate four-bubble attenuation. Lighting-authority consolidation **precedes** adding a distinct Lighting Coverage BEAM/SCENE control. Full new findings, exact code owners, mode-switch bubble-cohort hypothesis and the test matrix: [Lighting Authority Repair](Lighting_Authority_Repair.md). Only `Current_Plan.md` G05/G06/G07/G08/G09/G27/G30/G32/G33 owns work/status; [Acceptance Runbook](Acceptance_Runbook.md) owns the necessary native evidence. R45's implementation candidate and the existing full failure inventories remain unaccepted and intact.

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
the useful musical breathing, not blindly reproduce the floor's adaptive behavior. See the active G13/G14/G25
items in `Current_Plan.md`, the detailed `Target.md` reactivity contract and the `Acceptance_Runbook.md` gate.
This is not operator acceptance of any current EB build.

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

- Historical passage-role candidate: [P1](Evidence/2026-10-20/recovery/passage_roles_native_p1/contact.png),
  [P7](Evidence/2026-10-20/recovery/passage_roles_native_p7_1440/contact.png),
  [same-sound logical comparison](Evidence/2026-10-20/recovery/passage_roles_final/summary.json).
  That checkpoint was unaccepted; it does not supersede the accepted baseline at the top of this document.
- Rejected P1 at that checkpoint: [contact sheet](Evidence/2026-10-20/recovery/clean_body_native_p1/contact.png),
  [full frame](Evidence/2026-10-20/recovery/clean_body_native_p1/frame_0060.png),
  [silent 30-fps sequence](Evidence/2026-10-20/recovery/clean_body_native_p1/motion.gif).
- Rejected P7 at that checkpoint: [contact sheet](Evidence/2026-10-20/recovery/clean_body_native_p7_1440/contact.png),
  [full frame](Evidence/2026-10-20/recovery/clean_body_native_p7_1440/frame_0090.png).
- Same-sound accepted 2D reference: [contact sheet](Evidence/2026-10-20/recovery/clean_body_2d_reference/contact.png).
- Paired source custody: [summary](Evidence/2026-10-20/recovery/matched_body_final/summary.json).
  Windowed logical ratios do not establish listening, display timing or visual acceptance.

The annotated targets are direct acceptance references:

[Blue sphere, light and trail requirements (full local reference set)](Targets/Originals/Informational%20mock.png)

[Copper sphere, light and trail requirements (full local reference set)](Targets/Originals/Informational%20mock%202.png)
