// The contract between this module and its one Python importer, rendering/native/ (D5.7).
//
// SRPSS_NATIVE_CORE_ABI is the version of everything the Python face calls or reads: the module's functions, their
// arguments, the keys of runtime_info(). It is raised whenever any of those changes, together with EXPECTED_ABI in
// rendering/native/loader.py (tests/test_native_core_loader.py fails while the two differ), so a module built from
// another commit is refused at load with one reason instead of failing somewhere later.
#pragma once

#define SRPSS_NATIVE_CORE_ABI 1
