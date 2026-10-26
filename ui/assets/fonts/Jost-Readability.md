# Private variable Jost faces

`Jost-Readability-Variable.ttf` and `Jost-Readability-Italic-Variable.ttf` are
Jost 3.710 from the Google Fonts `ofl/jost` directory, licensed under the
adjacent `Jost-OFL.txt`. Google Fonts metadata identifies upstream
`https://github.com/indestructible-type/Jost` revision
`35f141c970538f1ed0f235789c19156b3ce2a762`.

Sources:

- https://raw.githubusercontent.com/google/fonts/main/ofl/jost/Jost%5Bwght%5D.ttf
  SHA-256 `6343b70971000b04c5d401c96ae08ce371086135e999d5e1e1413039c0213076`
- https://raw.githubusercontent.com/google/fonts/main/ofl/jost/Jost-Italic%5Bwght%5D.ttf
  SHA-256 `15a6f7e3e11f9e8e338a583a6fe03e8f6b1d9ce877efa3fe579282b6c1cb15fe`

Only font naming records were changed with FontTools 4.67.0. The private family
`SRPSS Jost Variable` prevents variable-face registration from changing matching
of the existing static `Jost` family used by dark themes. Outlines, metrics,
variation axes and named instances are unchanged. The separate registration is
used only by the shared light-palette typography projection; it adds 50 to the
resolved weight with an explicit `wght` axis, retaining the font's other inputs.

To reproduce, load each source with `fontTools.ttLib.TTFont`, replace existing
name IDs 1, 16 and 21 with `SRPSS Jost Variable`, ID 4 with
`SRPSSJostVariable Regular` (or `SRPSSJostVariable Italic`), and ID 6 with
`SRPSSJostVariable-Regular` (or `SRPSSJostVariable-Italic`), using each record's
existing encoding. Save under the corresponding readability filename. Do not
register these faces under the original `Jost` family.
