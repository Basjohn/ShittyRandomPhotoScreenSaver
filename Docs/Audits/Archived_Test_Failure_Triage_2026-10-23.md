# Archived 23 October test failures | source-oriented triage

**Status:** 102 failures recorded in four Windows pytest chunks, spanning **32 test files**. This audit is a classification of the *provided run logs*, not a new execution of the entire suite and **not** a claim that these tests currently pass or that all failures are stale. [Controlling plan](../../Current_Plan.md) | [Test durability](../Guides/Test_Durability.md) | [Settings startup flash audit](Settings_Transient_Window_Regression_2026-10-23.md).

The source handoff is the 23 October `e692801bb9` godzip. Archived log source: operator-provided `logs993de3141c.zip` (four `pytest_chunk_N.log` runs). A later source candidate changed Settings bucket policy, a Ray Fan Spread visibility gate and a couple of literal-default readers. **Do not treat archived failure counts as current rerun results.** Every original test remains present; no test was deleted or XFAIL-marked here.

## Immediate priorities and diagnosis

1. **Repair/validate the new Settings native transient-window regression first**, then native single-active bucket path behavior. The shared builder now hides the unparented bucket body and only shows it after attachment; [native HWND validation](Settings_Transient_Window_Regression_2026-10-23.md) is still open.
2. **Run real behavior falsifiers before weakening any oracle:** EB recorded breathing, pause release and fused camera/projection, Neon Lake Moon/Sun and terrain occlusion, 3D defocus image energy, engine/image speculative admission, Sphere projection, and full shader/GL admission. Failures with actual native pixels or recorded curves cannot be dismissed by observing a renamed class elsewhere.
3. **Upgrade unambiguous test harness/API drift** in small ownership clusters: OscilloscopeFrame smoke factory, 3D/Neon `shockwave_project` and `_initialize` assumptions, required EB `body_bands`, fake Settings hosts missing required methods, and executable defaults readers. Preserve each test's behavioral intent and assertions.
4. Re-run targeted related tests on **the final source revision**, not the stale archived suite, and apply the project's direct `py -3.14 -m pytest ...` commands with **no environment-variable setup**. Do not run a slow full suite/build on the agent's machine; operator/authorized native host runs it when requested. Prefer agent-performed HWND capture, PySide6 UI drive and comparison screenshots whenever technically possible; reserve operator acceptance for genuinely subjective looks.

## Failure-family inventory

| Archived file (tests failed) | Source-backed assessment | Required agent action |
|---|---|---|
| `test_default_settings_editor.py` (7) | **CONFIRMED harness/schema drift** | `ast.literal_eval()` cannot evaluate canonical `basin_profile()`; update read path without bypassing save/undo assertions |
| `test_defaults_schema_authority.py` (11) | **MIXED; default-reader drift dominates** | Many `ast.literal_eval()` failures, plus distinct schema/value assertions; repair reader then rerun individually |
| `test_theme_defaults_authority.py` (2) | **CONFIRMED reader drift** | Same executable-default literal parser; retain actual theme/default identity assertions |
| `test_defaults_projection.py` (1) | **NEEDS SOURCE TRACE** | SST/reset projection differs; distinguish newly added `ui.basic_bucket_path`/sparse state from product-authority violation |
| `test_3d_curated_preset_ownership.py` (11) | **LIKELY obsolete contracts; PRESERVE AUTHORING** | Test assumptions around curated 3D modes/presets changed; inspect each exact expected value against canonical mutable preset policy |
| `test_sphere_voxel_audio_contract.py` (1) | **NEEDS SOURCE TRACE** | Settings/default projection or Sphere response mismatch; do not change expected artifact blindly |
| `test_visualizer_technical_profile_contract.py` (1) | **LIKELY stale schema keys** | Expected Shockwave C6 bucket identities conflict with revised mode builder; verify descriptor authority first |
| `test_qtquick_visualizer_clip_smoke.py` (8) | **CONFIRMED smoke-tool ABI drift** | `tools/qtquick_visualizer_clip_smoke.py` constructs `OscilloscopeFrame(previous_waveform=...)`, a retired field; update builder to actual frame signature then RETAIN pixel assertions |
| `test_qtquick_visualizer_all_modes.py` (1) | **CONFIRMED harness-API mismatch** | EB fixture invokes `ExtrudedBubbleFrameRuntime.advance()` without required `body_bands`; supply proper recorded/input bands, do not make API optional |
| `test_qt611_shader_admission.py` (1) | **CONFIRMED harness-API mismatch** | Shader probe calls removed `QuickShockwaveGridRenderer._initialize`; adapt to real Neon Lake renderer creation/admission; still compile and retire on Windows |
| `test_qtquick_bootstrap.py` (1) | **CONFIRMED diagnostic GLSL mismatch** | `tools/visualizer_replay/eb_shaft_mesa_compile.py` still declares `#version 450 core` contrary to audited 460 core floor |
| `test_scene3d_foundation.py` (1) | **CONFIRMED removed API import** | Legacy `shockwave_project` import no longer exists in converted `shockwave_grid_program`; test current projection authority |
| `test_scene3d_quality_settings.py` (5) | **LIKELY stale rendering oracle** | Tests require historical Shockwave grid meshes (`grid 128x85`, etc.) and a removed `_shockwave_grid_terrain` fixture |
| `test_visualizer_edit_content_envelope.py` (13) | **MIXED: stale fake owner plus real geometry checks** | Fake `SimpleNamespace` lacks `_shockwave_grid_terrain`; migrate harness to current mode resources, then rerun all Edit-envelope visual/geometry assertions |
| `test_visualizer_3d_reach.py` (1) | **LIKELY removed mode oracle** | Old Shockwave reach/config expected after Neon Lake migration; prove new mode coverage and world boundaries |
| `test_visualizer_presentation_orientation.py` (1) | **LIKELY stale shell-policy oracle** | Expected Shockwave card/frameless policy disagrees with current registry; rederive from current presentation policy |
| `test_visualizer_runtime_controller.py` (1) | **LIKELY stale shell-policy oracle** | Same physical card/frameless policy conflict; preserve current user-visible framing rule |
| `test_visualizer_mode_settings_spec.py` (3) | **MIXED: 6-coordinate EB + dynamic control drift** | Test expects 2-value `extruded_bubble_light_direction` while current source uses 6 physical coordinates; widget field names for Rays/Light Type changed. Check consumer and runtime parity |
| `test_visualizer_settings_body_transaction_contract.py` (1) | **NEEDS SOURCE TRACE** | Settings builder reload/rollback contract may be stale or genuinely violated; must run live QWidget transaction tests |
| `test_visualizer_mode_isolation.py` (1) | **NEEDS SOURCE TRACE** | Source-contract isolation assertion needs review against new shared 3D resource owner; preserve non-cross-mode runtime authority |
| `test_visualizer_extreme_viewport_scaling_audit_contract.py` (1) | **LIKELY stale source-literal assertion** | Looks for exact Oscilloscope `line_width=2.0 * scale` spelling rather than current width function; maintain native pixel thickness invariants |
| `test_scene3d_defocus.py` (1) | **MEASURED MISMATCH; NOT SAFE TO DISMISS** | Actual image energy 50.61 versus 40±6; test cost/defocus parity with real native pixels |
| `test_extruded_bubble_recorded_reactivity.py` (2) | **MEASURED MISMATCH; NOT SAFE TO DISMISS** | Class median recorded excursion ~1.75 misses >1.8 and pause-rest phase check fails; retain thresholds unless acceptance oracle explicitly changes |
| `test_extruded_bubble_world_gpu.py` (1) | **MEASURED MISMATCH; NOT SAFE TO DISMISS** | Pinhole projection ordinary/fused 1.69 versus 1.269±.02. Diagnose camera/units/crop, not numerical tolerance |
| `test_neon_scene_materials.py` (11) | **NATIVE PIXEL FAILURES; NOT SAFE TO DISMISS** | Terrain body occlusion and alpha-compositing expectations fail, including Moon/Sun and Glass/Vertices combinations; separate outdated fixture coordinates from real depth bugs with visual captures |
| `test_image_prefetch_transport.py` (6) | **NEEDS RUNTIME ADMISSION REVIEW** | Startup speculative image-worker admission assumptions differ from runtime; check current first-frame budget and selected-quality safeguards |
| `test_engine_lifecycle.py` (1) | **NEEDS RUNTIME ADMISSION REVIEW** | First-frame scaled-prefetch deferral is lifecycle-sensitive and may regress; compare authoritative frame and job admission |
| `test_transition_distribution.py` (3) | **CONFIRMED incomplete fake owner, behavior still OPEN** | Test `SimpleNamespace` omits `_display_selection_suspended`; supply proper semantics and rerun image batch/distribution behaviors |
| `test_visualizer_custom_route_contract.py` (1) | **CONFIRMED incomplete fake owner, behavior still OPEN** | Fake lacks `set_visualizer_camera_reset_available`; restore current API in fixture and rerun real display-route assertions |
| `test_test_suite_durability.py` (1) | **CONFIRMED test literal-policy breach** | `tests/test_extruded_bubble_camera_reset_contract.py` pins an authored default literal; derive from canonical authority |
| `test_tooling_ownership.py` (1) | **LOCAL WORKTREE DEPENDENCY** | Fails on `.tmp\neon_...repair` scratch import paths in original Windows tree. Check ignored debris/build checkout rather than changing production imports without attribution |
| `test_sphere_shared_scene3d_projection.py` (1) | **NEEDS SOURCE TRACE** | Shared Sphere projection assertion differs, potentially actual orbit/projection regression; keep numeric/visual check |

## Numerical and native falsifiers to retain verbatim

- EB recorded breathing: class-median values included **1.75060387** against a test minimum **greater than 1.8**; separately, pause release/slow-rest invariants failed. This is borderline in one measurement but **not** permission to loosen the acceptance criterion. Re-evaluate against 2D Dynamic Floor ON and EB Dynamic Floor OFF using same passages.
- EB ordinary versus fused perspective projection: obtained approximately **1.6976/1.6908**, expected **1.2691 ± 0.02**, a substantive 25% scale discrepancy. Validate actual camera projection, viewport crop and ray-domain sampling.
- Scene3D defocus: measured small/large highlight energy **50.61264**, expected **40 ± 6**. Test spatial energy and quality lever cost with native pixels.
- Neon Lake pixels: several supposedly transparent surfaces retained median alpha **128** or **255** versus expected at most **2**, and a separate body/terrain occlusion count was **0** versus expected >20. These are measurable failures; first establish whether the sampled pixel regions still represent the intended geometry, then fix the renderer or the *sampling location*, not the visual contract.
- Native GL shader admission encountered `QuickShockwaveGridRenderer._initialize` removed API, so it never established the actual shader results for the current renderer. Replace the obsolete harness call and **run the GL compile/retire test**, rather than marking shaders valid.

## Original failing-test identity list (unchanged)

Grouped by archived run, to give the next agent exact targeted selectors without rediscovering test names. Entries below record archived failures, not live status.

### pytest_chunk_1.log

- `tests/test_3d_curated_preset_ownership.py::test_every_curated_3d_file_explicitly_owns_its_complete_consumed_namespace[shockwave_grid-0]`
- `tests/test_3d_curated_preset_ownership.py::test_every_curated_3d_file_explicitly_owns_its_complete_consumed_namespace[shockwave_grid-10]`
- `tests/test_3d_curated_preset_ownership.py::test_every_curated_3d_file_explicitly_owns_its_complete_consumed_namespace[shockwave_grid-11]`
- `tests/test_3d_curated_preset_ownership.py::test_every_curated_3d_file_explicitly_owns_its_complete_consumed_namespace[shockwave_grid-12]`
- `tests/test_3d_curated_preset_ownership.py::test_every_curated_3d_file_explicitly_owns_its_complete_consumed_namespace[shockwave_grid-2]`
- `tests/test_3d_curated_preset_ownership.py::test_every_curated_3d_file_explicitly_owns_its_complete_consumed_namespace[shockwave_grid-4]`
- `tests/test_3d_curated_preset_ownership.py::test_every_curated_3d_file_explicitly_owns_its_complete_consumed_namespace[shockwave_grid-5]`
- `tests/test_3d_curated_preset_ownership.py::test_every_curated_3d_file_explicitly_owns_its_complete_consumed_namespace[shockwave_grid-6]`
- `tests/test_3d_curated_preset_ownership.py::test_every_curated_3d_file_explicitly_owns_its_complete_consumed_namespace[shockwave_grid-7]`
- `tests/test_3d_curated_preset_ownership.py::test_every_curated_3d_file_explicitly_owns_its_complete_consumed_namespace[shockwave_grid-8]`
- `tests/test_3d_curated_preset_ownership.py::test_every_curated_3d_file_explicitly_owns_its_complete_consumed_namespace[shockwave_grid-9]`
- `tests/test_default_settings_editor.py::test_by_transition_view_gathers_each_transitions_settings_and_edits_in_place`
- `tests/test_default_settings_editor.py::test_editor_color_swatch_survives_modal_picker_and_persists`
- `tests/test_default_settings_editor.py::test_editor_transactional_save_and_single_level_undo`
- `tests/test_default_settings_editor.py::test_editor_uses_alpha_swatch_and_font_delegate_editors`
- `tests/test_default_settings_editor.py::test_every_text_setting_tooltip_describes_valid_text_domain`
- `tests/test_default_settings_editor.py::test_failed_save_restores_previous_undo_source_and_artifacts`
- `tests/test_default_settings_editor.py::test_failed_undo_restores_current_source_and_artifacts`
- `tests/test_defaults_projection.py::test_sst_projection_import_matches_fresh_profile_reset[Screensaver]`
- `tests/test_defaults_schema_authority.py::test_canonical_defaults_have_one_shape_for_previously_duplicated_roots`
- `tests/test_defaults_schema_authority.py::test_custom_visualizer_state_is_not_a_product_default_and_reset_preserves_it`
- `tests/test_defaults_schema_authority.py::test_dead_transition_precompute_worker_is_removed`
- `tests/test_defaults_schema_authority.py::test_derived_snapshot_tracks_clean_normal_defaults`
- `tests/test_defaults_schema_authority.py::test_fresh_profile_collapsible_bucket_states_are_boolean_maps`
- `tests/test_defaults_schema_authority.py::test_fresh_profile_widget_sections_are_well_formed_and_architecture_safe`
- `tests/test_defaults_schema_authority.py::test_real_persisted_fallbacks_are_canonical_product_defaults`
- `tests/test_defaults_schema_authority.py::test_retired_visualizer_growth_is_invalidated_once_not_preserved_as_schema`
- `tests/test_defaults_schema_authority.py::test_runtime_history_and_settings_session_state_are_not_product_defaults`
- `tests/test_defaults_schema_authority.py::test_runtime_recovery_metadata_starts_empty_instead_of_copying_widget_defaults`
- `tests/test_defaults_schema_authority.py::test_visualizer_literal_and_derived_snapshot_have_identical_schema`
- `tests/test_engine_lifecycle.py::TestEngineState::test_initialize_defers_scaled_prefetch_until_authoritative_first_frames`
- `tests/test_extruded_bubble_recorded_reactivity.py::test_active_recorded_phrase_has_large_absolute_excursion_in_each_class`
- `tests/test_extruded_bubble_recorded_reactivity.py::test_pause_releases_radius_and_every_motion_phase_into_slow_rest`
- `tests/test_extruded_bubble_world_gpu.py::test_ordinary_and_fused_coverage_share_true_pinhole_projection`
- `tests/test_image_prefetch_transport.py::test_worker_startup_admits_speculation_only_for_selected_quality_and_budget[0-smooth-False-2-True-expected1]`
- `tests/test_image_prefetch_transport.py::test_worker_startup_admits_speculation_only_for_selected_quality_and_budget[4-hamming-True-2-True-expected3]`
- `tests/test_image_prefetch_transport.py::test_worker_startup_admits_speculation_only_for_selected_quality_and_budget[4-lanczos-False-2-True-expected2]`
- `tests/test_image_prefetch_transport.py::test_worker_startup_admits_speculation_only_for_selected_quality_and_budget[4-smooth-False-1-True-expected4]`
- `tests/test_image_prefetch_transport.py::test_worker_startup_admits_speculation_only_for_selected_quality_and_budget[4-smooth-False-2-False-expected5]`
- `tests/test_image_prefetch_transport.py::test_worker_startup_admits_speculation_only_for_selected_quality_and_budget[4-smooth-False-2-True-expected0]`

### pytest_chunk_2.log

- `tests/test_neon_scene_materials.py::test_actual_body_depth_is_occluded_by_solid_terrain[Vertices]`
- `tests/test_neon_scene_materials.py::test_rear_body_survives_zero_alpha_surface_and_attenuates_through_water_or_glass[128-Glass-Moon]`
- `tests/test_neon_scene_materials.py::test_rear_body_survives_zero_alpha_surface_and_attenuates_through_water_or_glass[128-Glass-Sun]`
- `tests/test_neon_scene_materials.py::test_rear_body_survives_zero_alpha_surface_and_attenuates_through_water_or_glass[128-Vertices-Moon]`
- `tests/test_neon_scene_materials.py::test_rear_body_survives_zero_alpha_surface_and_attenuates_through_water_or_glass[128-Vertices-Sun]`
- `tests/test_neon_scene_materials.py::test_rear_body_survives_zero_alpha_surface_and_attenuates_through_water_or_glass[255-Glass-Moon]`
- `tests/test_neon_scene_materials.py::test_rear_body_survives_zero_alpha_surface_and_attenuates_through_water_or_glass[255-Glass-Sun]`
- `tests/test_neon_scene_materials.py::test_rear_body_survives_zero_alpha_surface_and_attenuates_through_water_or_glass[255-Vertices-Moon]`
- `tests/test_neon_scene_materials.py::test_rear_body_survives_zero_alpha_surface_and_attenuates_through_water_or_glass[255-Vertices-Sun]`
- `tests/test_neon_scene_materials.py::test_translucent_body_blends_over_opaque_terrain_instead_of_revealing_sky[Moon]`
- `tests/test_neon_scene_materials.py::test_translucent_body_blends_over_opaque_terrain_instead_of_revealing_sky[Sun]`
- `tests/test_qt611_shader_admission.py::test_registered_transition_and_visualizer_shaders_compile_and_retire`
- `tests/test_qtquick_bootstrap.py::test_runtime_and_diagnostic_glsl_sources_have_one_460_core_contract`

### pytest_chunk_3.log

- `tests/test_qtquick_visualizer_all_modes.py::test_all_registered_modes_keep_one_runtime_across_pause_play_and_retire_terminally[extruded_bubble]`
- `tests/test_qtquick_visualizer_clip_smoke.py::test_oscilloscope_idle_carrier_and_delayed_ghost_are_real_quick_pixels`
- `tests/test_qtquick_visualizer_clip_smoke.py::test_oscilloscope_quick_geometry_reflows_without_bitmap_stretch`
- `tests/test_qtquick_visualizer_clip_smoke.py::test_production_oscilloscope_draws_and_releases_inside_quick[canonical]`
- `tests/test_qtquick_visualizer_clip_smoke.py::test_production_oscilloscope_draws_and_releases_inside_quick[ghost]`
- `tests/test_qtquick_visualizer_clip_smoke.py::test_production_oscilloscope_draws_and_releases_inside_quick[idle]`
- `tests/test_qtquick_visualizer_clip_smoke.py::test_production_oscilloscope_draws_and_releases_inside_quick[scaled]`
- `tests/test_qtquick_visualizer_clip_smoke.py::test_production_oscilloscope_draws_and_releases_inside_quick[tall]`
- `tests/test_qtquick_visualizer_clip_smoke.py::test_production_oscilloscope_draws_and_releases_inside_quick[wide]`
- `tests/test_scene3d_defocus.py::test_mixed_budget_preserves_small_and_large_highlight_energy[6.0]`
- `tests/test_scene3d_foundation.py::test_the_shared_orbit_reproduces_each_3d_visualizers_former_projection`
- `tests/test_scene3d_quality_settings.py::test_a_3d_visualizer_draws_with_its_tiers_levers[Balanced]`
- `tests/test_scene3d_quality_settings.py::test_a_3d_visualizer_draws_with_its_tiers_levers[High]`
- `tests/test_scene3d_quality_settings.py::test_a_3d_visualizer_draws_with_its_tiers_levers[KAK]`
- `tests/test_scene3d_quality_settings.py::test_a_3d_visualizer_draws_with_its_tiers_levers[Performance]`
- `tests/test_scene3d_quality_settings.py::test_an_activation_carries_each_modes_tier_from_the_3d_settings`
- `tests/test_sphere_shared_scene3d_projection.py::test_sphere_edit_cage_uses_live_presentation_orbit_even_with_accepted_logical_frame`
- `tests/test_sphere_voxel_audio_contract.py::test_sphere_energy_floor_persistence`

### pytest_chunk_4.log

- `tests/test_test_suite_durability.py::test_test_suite_has_no_blocking_authority_copy_smells`
- `tests/test_theme_defaults_authority.py::test_settings_theme_selection_is_canonical_and_snapshotted`
- `tests/test_theme_defaults_authority.py::test_widget_theme_missing_values_read_canonical_defaults`
- `tests/test_tooling_ownership.py::test_production_python_never_imports_operator_analysis_tools`
- `tests/test_transition_distribution.py::test_empty_queue_result_releases_opened_batch_and_shows_nothing`
- `tests/test_transition_distribution.py::test_show_next_image_does_not_prepare_random_choice_without_runtime_targets`
- `tests/test_transition_distribution.py::test_show_next_image_prepares_random_choice_once_for_accepted_image_batch`
- `tests/test_visualizer_3d_reach.py::test_a_3d_frameless_mode_leaves_its_frame_and_its_target_never_cuts_it[shockwave_grid-views1]`
- `tests/test_visualizer_custom_route_contract.py::test_custom_owner_binds_media_model_from_the_other_live_display`
- `tests/test_visualizer_edit_content_envelope.py::test_accepted_shallow_bars_are_not_ceiling_allocation_bounds`
- `tests/test_visualizer_edit_content_envelope.py::test_envelope_is_read_only_content_not_stage_geometry[extruded_spectrum]`
- `tests/test_visualizer_edit_content_envelope.py::test_envelope_is_read_only_content_not_stage_geometry[shockwave_grid]`
- `tests/test_visualizer_edit_content_envelope.py::test_extruded_empty_audio_yields_projected_cage_without_fabricated_content`
- `tests/test_visualizer_edit_content_envelope.py::test_framed_scene_guide_and_selection_never_escape_card_at_extreme_pose`
- `tests/test_visualizer_edit_content_envelope.py::test_missing_or_silent_extruded_source_has_no_fake_maximum_height_item`
- `tests/test_visualizer_edit_content_envelope.py::test_north_is_centered_on_world_face_and_rotates_with_projected_cage_edge[extruded_spectrum]`
- `tests/test_visualizer_edit_content_envelope.py::test_north_is_centered_on_world_face_and_rotates_with_projected_cage_edge[shockwave_grid]`
- `tests/test_visualizer_edit_content_envelope.py::test_north_is_centered_on_world_face_and_rotates_with_projected_cage_edge[sphere]`
- `tests/test_visualizer_edit_content_envelope.py::test_orbit_changes_only_the_derived_envelope[extruded_spectrum-extruded_spectrum_turn-extruded_spectrum_tilt]`
- `tests/test_visualizer_edit_content_envelope.py::test_orbit_changes_only_the_derived_envelope[shockwave_grid-shockwave_grid_turn-shockwave_grid_tilt]`
- `tests/test_visualizer_edit_content_envelope.py::test_planar_mode_has_no_edit_content_envelope`
- `tests/test_visualizer_edit_content_envelope.py::test_sphere_uses_its_own_reach_and_pivot_not_a_generic_3d_circle`
- `tests/test_visualizer_extreme_viewport_scaling_audit_contract.py::test_line_mode_pixel_thickness_is_uniform_scale_owned`
- `tests/test_visualizer_mode_isolation.py::test_dedicated_visualizer_modules_do_not_read_foreign_mode_runtime_fields`
- `tests/test_visualizer_mode_settings_spec.py::test_a_spec_is_a_registered_mode_and_owns_canonical_keys[extruded_bubble]`
- `tests/test_visualizer_mode_settings_spec.py::test_conditional_controls_follow_their_condition_live_and_on_load[extruded_bubble]`
- `tests/test_visualizer_mode_settings_spec.py::test_the_settings_body_builds_saves_and_reloads_every_control[extruded_bubble]`
- `tests/test_visualizer_presentation_orientation.py::test_content_rotation_capability_tracks_carded_presentation_policy`
- `tests/test_visualizer_runtime_controller.py::test_current_modes_resolve_their_proven_carded_presentation_policy`
- `tests/test_visualizer_settings_body_transaction_contract.py::test_c6_3d_bucket_defaults_match_current_builder_contract`
- `tests/test_visualizer_technical_profile_contract.py::test_rejected_smooth_sphere_settings_are_not_canonical_defaults`

## New scoped checks after the Settings source mitigation

`python -m pytest -q --noconftest tests/test_settings_bucket_single_open_contract.py tests/test_settings_active_bucket_path.py -k 'not full_map_bucket_profile_projects_to_current_sparse_state_idempotently'` → **22 passed, 1 deselected** in the available Qt-free environment. The excluded legacy fixture is absent from the slim archive; the test was **not** removed or weakened. New `tests/test_settings_bucket_tree.py::test_initially_open_bucket_is_parented_before_any_show` is PySide6-dependent and **unrun here**. Neither run validates Windows HWND behavior.

This inventory supplements the canonical tests under `Docs/TestSuite.md` and does **not** supersede any prior rejection, accepted baseline or user-authored preset.

## Subsequent test-oracle repair note (2026-10-23)

See [Test Oracle Repair](Test_Oracle_Repair_2026-10-23.md). The previous Windows failures describe the archived run, not an acceptable reason to restore authored presets to BEAM or to assume an obsolete bucket-state policy. The seven-presets lighting-coverage assertion was invalid and removed. Multiple specific failures remain open until native agent validation.
