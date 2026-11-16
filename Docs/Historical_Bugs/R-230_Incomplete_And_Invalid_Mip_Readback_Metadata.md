# R-230 | Mip readbacks were truncated and carried base-level content bounds

**Status:** fixed and proved 16 Nov 2026.

A fixed 92-result callback array silently truncated larger accepted declarations. Every nonzero mip also returned
base-level content dimensions against its smaller allocation. The old ABI22 module fails a legal 176-entry proof
and the subsequent bounded/odd-extent metadata checks on both backends.

`SceneReadback` now allocates one owned array for the entire enumeration before callback registration. Its existing
shared lifetime keeps addresses stable until completion. Each mip's nominal content rectangle projects the base
normalized rectangle outward, stays bottom anchored and fits its allocation. Filtering may cross this nominal
boundary; metadata does not promise clear filtered fringes. An initial vector implementation failed the existing
native DLL import gate; the accepted owned-array build passes that gate without introducing an STL DLL dependency.

ABI24 OpenGL/Vulkan return all 176 unique attachment/level entries, valid sizes/byte shapes, and successful
subsequent bounded and odd-extent reads, with pending resources retired. Evidence:
`native_core/n3_1/20261116_n34_readback_abi24/summary.json`; guard:
`tests/test_native_scene_readback_metadata.py`.
