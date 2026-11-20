# Rejected Extruded cast shadow projections (R125–R128)

**STRONG RETENTION VALUE DOCUMENT**

**Resolution:** cast shadow is unavailable. One canonical availability flag excludes the GL pass and Edit/target reach even when historical user/curated values request it. Cast Shadow / Reach / Strength stay visible but disabled. General ordinary-widget shadows and Extruded floor reflections remain active. Never modify authored response or Spectrum Organs to compensate for rejected cast shapes.

**Failure mechanism and negative evidence:**

- **R119 to R121 (the attempts before R125):** R119 found a hidden 0.34 multiplier that cut the shadow-strength slider to about 12% cast alpha, and an alpha-only fix cannot repair geometry. R120 found the receiver was the horizontal plane `world.y = 0`, which projects edge-on in a front view (zero vertical extent), that the canonical screen direction was read as fixed world x/z so the cast reversed as the camera orbited (it must pass through the inverse of the orbit yaw), that the real-GL test rendered body alpha 0 and reflection 0 (a composite smoke test, not the operator's opaque reflective bars), and that Shadow Strength stayed active while Cast Shadow was off. R121 swept projected-space vertices by a reach times height along the direction. 972 and 1,060 grouped tests passed throughout while the operator still saw a tiny corner: a passing pixel-difference test is never the acceptance gate for a cast shadow. Any receiver or projection change must update the pure `extruded_reach` and `extruded_footprint` mirrors in lockstep.
- **R125:** projected distant top geometry was pulled toward the bar-row front while the base retained depth. Short mode collapsed to a triangular wedge and distant mode retained a diagonal taper. Passing source assertions did not mean acceptable pixels.
- **R126:** each bar's base footprint was swept by one equal fixed screen displacement, independently of actual height. A visually dominant diagonally sheared parallelogram with repeated bar seams resulted.
- **R127:** using true bar heights for the distant mode and a projected silhouette for Nearby still produced a dark attached extrusion rather than a plausible floor cast; frontal and rotated operator screenshots rejected it. Synthetic CPU mockups did not predict the final GL/composited appearance.
- **R128:** renderer/UI/target hard-disable, preserve persisted settings and authored preset semantics. Do not remove the canonical disabled inputs without a deliberate compatibility migration.

**Future admission:** reopen only with a clearly agreed on-screen target, projection plane/composition contract and physical proof under both display orientations, camera tilts, Widgets global directions and live music. Do not implement another sweep variation based solely on geometric assertions or mark it accepted from a numerical pixel gate.
