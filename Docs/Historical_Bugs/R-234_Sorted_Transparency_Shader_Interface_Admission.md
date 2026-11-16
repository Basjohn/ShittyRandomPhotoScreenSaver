# R-234: Sorted transparency shader bypassed deep interface admission

**16 November 2026. Repaired and proved on official build `14be99283`; independent High review.**

`checkSortedPack` admitted an alternate fragment shader using only outer uniform block name/binding/size,
storage name/binding, and partial sampler/input metadata. The program packs and binds resources from the OIT
shader, then can run the sorted shader into the owner target. Equal outer block sizes therefore did not protect
member offsets. Resource categories omitted by the comparison could also enter an alternate that had never
passed the primary shader's admission rules. Device capability selection did not make that pair valid.

On the official ABI25 module from `6e187d2a6`, GPU-free `module.mode_blocks` admits a sorted pack that swaps
two vec4 members of PostLayer1 while retaining the same reflected block size. Reflected members differ before
the rejection test reaches `DID NOT RAISE`. It also admits a sorted-only, live readonly storage image despite no
binding for that image. The real OIT/sorted pair and an existing mismatched-input refusal pass. A source-order-only
control initially passed because qsb reflected the same order; the strengthened fixture verifies different actual
reflection orders and exposes a second defect: the old check refuses an equivalent reordered interface.
An independently baked geometry pair also proves that equal-size reordered SSBO members and a changed storage
access qualifier pass the shallow check.
Valid pairs with different explicit storage instance aliases are admitted by the old module; the reflection
control verifies that only the instance name differs. These aliases are not resource binding identities.
These are independent valid shader packs; no undefined draw or GPU pipeline is needed to reproduce
the admission failures. Final fixture receipts and additional controls are retained in
`.artifacts/evidence/native_core/n3_4/20261116_sorted_pack_old/`.

The repair shares L1's reflected resource/user-input comparator between alternate vertex and sorted fragment
packs. It compares full uniform member layouts (including nested members and strides), storage layouts/access,
descriptor sets, samplers and every other resource category using Qt6.12's deep reflection equality. Top-level
declarations are permutations; nested member layout remains ordered. Uniform `structName` and storage
`instanceName` are excluded on local copies before Qt equality: these translated/explicit instance aliases belong
to their compiled pack. The core matches storage by block name and binding; Qt's OpenGL/Vulkan paths bind it
numerically. The valid SSBO alias control prevents the shared L1 comparison from introducing a false rejection.
No per-record comparison, ABI change, new fallback or render-state mutation is introduced.

Output checking remains distinct. L1's vertex wrapper compares user outputs and output built-ins. A sorted
fragment intentionally writes different owner attachments from the OIT shader, so its existing owner-output
validation and gl_FragDepth refusal remain in force. Input built-ins and arbitrary shader semantics are outside
this resource admission contract; backend pixel proof remains necessary.

`tests/test_native_sorted_pack_interface.py` crosses the actual admission seam. Its direct module call includes
targets through the canonical `program_json`; the convenience Python `mode_blocks` helper declares no targets
and cannot represent this test. The old nine-case receipt has four passes and five intended failures: four unsafe
interfaces accepted and one valid reflected-order permutation rejected. The rebuilt module passes all 75 focused
sorted, mesh-buffer, generic-mode and post-stage tests, with no skips.

Hidden OpenGL/Vulkan post-stage gate and parity rounds pass with the Python reference, rule(a), rule(b) and
analytic checks; the lead inspected both native sheets. A separate forced-sorted draw proves the live SSBO
binding with anonymous versus different explicit instance aliases: all three nonzero/zero/restored RGBA frames
match exactly between those programs, zeroing the payload changes 21,992 pixels, and restoring it restores exact
pixels. Each program records its actual sorted fallback once and retires owned resources to zero; all 19 guards
pass per backend. Vulkan required synchronisation validation has zero unexplained errors/warnings, with ten
recorded Qt defectA errors excluded for post stages and seven for the alias proof. The instance-creation loader
warning remains attributed in the receipts. This is not a D3D/Metal or overall performance claim; D17's existing
non-gating odd-size product-bloom diagnostic remains separate.
The shared L1 vertex comparison also retains both-backend form3, loop and direct-draw proof on this module;
`n3_2/20261116_alternate_interface_14be99283/summary.json` records that focused regression.

Evidence under `.artifacts/evidence/native_core/`: `n3_4/20261116_sorted_pack_fixed/` holds passing XML and
official manifest (run43921798161, token20261116_194557_828140); `n3_4/20261116_sorted_pack_interface_14be99283/`
holds gate/parity results and native/reference sheets; `n3_4/20261116_sorted_pack_runtime/` holds the bounded
`alias_check.py`, actual backend receipts and raw frames. D17 owns the durable contract.

The adjacent vertex/fragment shared-block union is a separately recorded follow-up: it selects one packed layout
for both stages but compares only outer metadata. Do not claim this alternate-pack repair fixes that boundary.

Primary source: [Qt6.12 reflection equality](https://github.com/qt/qtbase/blob/v6.12.0/src/gui/rhi/qshaderdescription.cpp).
D17 owns the durable sorted-pack contract; Current_Plan.md owns remaining work.
