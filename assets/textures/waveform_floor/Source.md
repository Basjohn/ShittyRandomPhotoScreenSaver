# Generated concrete material

`concrete_albedo.png` is the unmodified output of the built-in image generation tool, generated 1 November 2026
for the Waveform Ribbon lab. RGB, 1254x1254; SHA-256
`7335a8fc10e432566c348ea8e139f780d44b7992d1b255deea80e12645d9dfc0`.

The lab shades the material wet, derives a restrained micro-surface from its grain, and lights it using the native
3D reflection. Reflections and cyan/violet light are not part of the bitmap. The generated asset replaces the
rejected repeated concrete pack in this lab only. Source image remains in the generator's output directory.

Exact generation prompt:

> Use case: photorealistic-natural. Asset type: a production PBR base-color texture for a real-time 3D wet concrete floor, NOT a scene render or a concept picture. Create one square, high-resolution 2048 x 2048 or largest available seamless tileable texture. Orthographic straight-down surface scan, completely flat and uniform diffuse illumination. Material: dark charcoal-grey poured concrete with very fine mineral aggregate, pinhead-sized pores, subtle worn smooth patches, a few extremely fine irregular hairline fissures. Fine-scale photographic detail throughout, understated organic variation at multiple scales, broadly homogeneous in value. This is the dry base colour that will be shaded wet by the renderer. It must have NO baked wet reflections, NO highlights, NO directional shadows, NO ambient-occlusion halos, NO vignette, NO blue/purple/neon light, NO perspective, NO horizon, NO slabs or paving-grid pattern, NO conspicuous repeating motifs, NO big pits or crater-like blobs. Neutral dark gray only, restrained contrast, average sRGB grey approximately 70/255. Edge-to-edge identical material scale, seamless matching borders. One single full-bleed texture map, no labels, no margins, no collage, no text. It will cover a broad floor patch and receive real cyan/violet light and real planar reflections in a separate renderer.

`concrete_roughness.png` is a second unmodified built-in generation using the albedo as its material reference.
RGB grayscale, 1254x1254; sampled as linear data, independently of the colour. SHA-256
`ea700b2e1215ae4102fad9de601c9a599509eaca2ef3b6d5b215080e6e577146`.
It describes the distribution of wet film and exposed concrete. The renderer remaps it to optical roughness and
attenuates the micro-normal in the wet areas. It is not a measured normal/height scan.

Exact roughness generation prompt:

> Use case: precise-object-edit. Asset type: grayscale PBR roughness map paired with the supplied concrete base-colour map. The supplied image is a material reference and registration guide, not a scene. Create the wet-surface roughness map for this same continuous concrete floor, straight top-down, full bleed, same square shape and fine concrete scale. BLACK means very smooth wet film; LIGHT GRAY means exposed rough concrete. About 65 percent of the surface should be connected dark charcoal patches of thin water film, distributed as many irregular asymmetrical shallow islands and channels at medium scales; 35 percent irregular rough gray aggregate between them. No isolated circular puddles. Subtle fine-scale pore detail. Keep a natural dense but varied broken surface, not broad blurry clouds or uniform speckle: irregular smooth wet patches should vary from about 15 to 90 pixels across in a 1254-pixel map. Softly irregular physical boundaries, crisp enough to break up reflected light. No tile grid, no paving slabs, no repeating motifs, no directional lighting or shadow, no perspective, no reflected objects, no water ripples, no text or labels. Pure grayscale only; a flat data texture, not a photograph of reflections. Seamless matching borders. The renderer supplies real reflections and will use these values to vary optical roughness, not as colour.
