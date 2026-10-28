# Bubble gradient authoring

Original Bubble's Appearance group combines the existing named Gradient Direction recipes with a two-node
Custom Gradient editor. Specular Direction remains a separate compass control. The gradient's redundant compass
is removed. Dark and Light move independently; their line sets direction, separation sets blend span, and moving
both shifts placement. Tab visits both nodes; arrows move a node, Shift makes fine steps. Very short spans reject.

`core/settings/default_settings.py` alone owns the default `bubble_gradient_endpoints` list (Dark XY, Light XY,
normalized top-left coordinates). The typed `Gradient` control in `visualizer_mode_settings.py` supplies model
admission, serialization, UI construction, and immutable presentation capture. The shared `GradientMapper` supplies
the gesture, accessibility and Settings undo path. There is no new logical/audio input or motion owner.

`bubble_gradient_direction` remains the geometry discriminator: the original eight directional recipes and two
radial recipes keep their exact stored values and appearance; `custom` consumes the endpoints. Existing versioned
brightest-point migration remains in `bubble_gradient_semantics.py`. Adding nodes does not reinterpret or rewrite
old preset files. Missing or malformed nodes admit the canonical default through the typed control.

Custom nodes are latent when another recipe is selected. Selecting a recipe never overwrites them. A node gesture
selects Custom and saves both values through the existing page save flow; one undo restores recipe and nodes
together. Radial recipes hide the inapplicable linear editor. Silent recipe restoration refreshes the same shared
conditions without generating an extra save or undo entry.

`QuickBubbleRenderer._gradient_parameters` projects custom nodes through `project_linear_gradient` using the
actual inner content aspect. The existing shader consumes the same packed vector/bias/mode input; no shader or
drawing algorithm is forked. Custom physical-metric lines are distinct from the original aspect-independent named
recipes: entering Custom is an explicit geometry edit, not a claim that normalized nodes reproduce every old
diagonal at every aspect. The editor is labelled Custom Gradient even while a named linear recipe is active.

Focused proof: `tests/test_bubble_gradient_nodes.py` crosses model/snapshot/import normalization, Settings gesture,
save, latent-value and compound undo boundaries, plus actual GL pixel oracles for wide/narrow/shifted custom nodes
at wide and tall aspects. `test_bubble_gradient_projection.py` compares every original recipe against the original
shader formula on the native driver at three aspects, requiring byte-identical RGBA. Existing Bubble spec/runtime
and shared geometry tests retain the legacy version migration and endpoint admission contracts.

The production Settings dialog was rendered at minimum logical1280×760 and actual DPR1.5 with file-backed Neon Mall
and Pearl Blush themes; both node and coordinate rows fit. Captures under `tmp/bubble_gradient_native` are local
diagnostic evidence, not operator acceptance. The lab `tools/labs/bubble_gradient_mapper_lab.py` now uses the actual
Custom settings/capture/render path and remains useful for an isolated visual look; it has no renderer-input override.
