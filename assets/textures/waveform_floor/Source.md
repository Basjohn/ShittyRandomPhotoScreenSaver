# Generated concrete material

`concrete_albedo.png` is the unmodified output of the built-in image generation tool, generated 1 November 2026
for the Waveform Ribbon lab. RGB, 1254x1254; SHA-256
`8575a597f1ba2fdff9c89b19acaaaa9b8ba9eb2303d217045134b963f1b0ad90`.

The lab shades the material wet, uses a separate smooth surface-height map, and lights it using the native
3D reflection and ribbon-derived illumination. Reflections and cyan/violet light are not part of the bitmap.
This smooth finished-concrete revision replaces the rejected coarse aggregate colour in this lab only; the earlier
asset/prompt remains in git history. Source image remains in the generator's output directory.

Exact generation prompt:

> Use case: photorealistic-natural. Asset: a seamless PBR base-color/albedo texture of very smooth power-trowelled sealed concrete for a real-time 3D floor. This is a flat texture scan, NOT a scene. Full-bleed square 2048x2048 or largest available. Perfect orthographic straight-down view, entirely neutral flat diffuse illumination, charcoal gray average about sRGB 65/255. The material is finely polished smooth concrete: almost homogeneous continuous cement paste with extremely subtle broad trowel tonal variation, microscopic pinhead pores barely visible, a refined smooth satin appearance with no coarse aggregate visible. The floor must feel truly smooth, not a blurry photograph of rough concrete. No visible pebbles, gravel, sand speckling, large pores, pits, cracks, veins, chipped paint, wet/dry patches, circular marks, grid, slab seams, directional lines or strong motifs. No baked shadows, ambient occlusion, specular highlights, reflected lights, wet reflections, perspective, objects, vignette, colored illumination or text. Low contrast: large areas should stay within a narrow charcoal-gray value range, with detail present only as restrained subtle material variation. Seamless matching borders, equal treatment edge-to-edge. The engine will add true 3D lighting and gentle Gaussian planar reflections using separate smooth-height and restrained roughness maps. Deliver only the single base-color bitmap.

`concrete_roughness.png` is an unmodified built-in generation using the earlier aggregate albedo as its material reference.
RGB grayscale, 1254x1254; sampled as linear data, independently of the colour. SHA-256
`ea700b2e1215ae4102fad9de601c9a599509eaca2ef3b6d5b215080e6e577146`.
The renderer now maps its filtered values into a restrained optical-roughness range across a continuous wet film.
The former thresholded wet/dry coverage interpretation was rejected by the operator as mottled. It is not a
measured normal/height scan and must not control specular coverage.

Exact roughness generation prompt:

> Use case: precise-object-edit. Asset type: grayscale PBR roughness map paired with the supplied concrete base-colour map. The supplied image is a material reference and registration guide, not a scene. Create the wet-surface roughness map for this same continuous concrete floor, straight top-down, full bleed, same square shape and fine concrete scale. BLACK means very smooth wet film; LIGHT GRAY means exposed rough concrete. About 65 percent of the surface should be connected dark charcoal patches of thin water film, distributed as many irregular asymmetrical shallow islands and channels at medium scales; 35 percent irregular rough gray aggregate between them. No isolated circular puddles. Subtle fine-scale pore detail. Keep a natural dense but varied broken surface, not broad blurry clouds or uniform speckle: irregular smooth wet patches should vary from about 15 to 90 pixels across in a 1254-pixel map. Softly irregular physical boundaries, crisp enough to break up reflected light. No tile grid, no paving slabs, no repeating motifs, no directional lighting or shadow, no perspective, no reflected objects, no water ripples, no text or labels. Pure grayscale only; a flat data texture, not a photograph of reflections. Seamless matching borders. The renderer supplies real reflections and will use these values to vary optical roughness, not as colour.

`wet_surface_height.png` is the unmodified output of the built-in image generation tool, generated 1 November
2026 after the operator rejected the mottled floor. RGB grayscale, 1254x1254; sampled as linear data.
SHA-256 `27068607b6b85a1872295964e8c3b26ada6554caafc7a7cd814d82b65a7a32f8`.
It describes gentle relief of the continuous wet surface independently of the concrete colour pores.
The renderer filters its fine detail and derives normals at a restrained world-space amplitude. This is authored
material data, not a measured physical scan. Exact generation prompt:

> Use case: photorealistic-natural. Asset type: seamless grayscale HEIGHT DATA texture for a real-time 3D floor material, not a beauty render. Create one square full-bleed, seamless tileable 1254x1254 or larger height map describing the top surface of a continuous thin wet film over smoothly trowelled concrete. Mid-gray is the nominal perfectly flat plane. Most values should stay between about 100 and 155 out of 255. The surface must be almost flat, with gentle, irregular, smoothly rounded undulations at medium scale, varying roughly 15 to 90 pixels in width, and broader almost imperceptible trowel variation. The height transitions must be smoothly differentiable, rounded and soft, with no steep lips. It should resemble a very smooth flattened surface-relief data scan: quiet softly blended raised and lowered areas, irregular without a recognizable repeating motif. The film fills all small pores. NO granular speckle, NO aggregate dots, NO pinholes, NO pockmarks, NO sharp cracks, NO chipped-paint islands, NO isolated puddle masks, NO dramatic height contrast, NO black and white blobs, NO wave or ripple rings, NO tile/slab grid. Absolutely no baked lighting, cast shadows, ambient occlusion, highlights, perspective, reflections, colors, neon light, objects, horizon, labels or text. The entire image is data with equal visual treatment edge to edge. Matching seamless borders. This image will drive very shallow real 3D normal perturbations in a separate renderer; the renderer supplies all wet reflectivity, illumination and color. Deliver the height map alone.
