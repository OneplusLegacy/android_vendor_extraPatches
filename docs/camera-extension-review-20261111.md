# Stock 7 Pro extension dispatch follow-up (2026-11-11)

The original factory treated the returned stock factory object as an artificial
function table, then invoked its member without the implicit `this` argument.
The current binary happens not to use that argument early, but the invocation
is invalid. Resolve its exported getCameraServiceExt method and supply the real
factory object. Keep the loaded singleton library alive. `std::call_once`
serializes loading and creation; the old boolean was a Binder-thread data race
and the extension singleton creation was also unsynchronized.

The stock getExtFactoryImpl at 0x40e98 returns an object with a vptr. Its table
starts at vtable+16 and relocates to getCameraServiceExt, then two destructors.
The original triple-dereference comments were inaccurate. This review does not
import a different device's vtable or reconstruct Android 12 private classes.

Stock onTransact at 0x36538 subtracts 10001 and unsigned-compares with 10;
unsupported codes return -38. Only 10001..10011 belong to this parser. The first
patch's claim that it handles 10015/CMD_UI_EVENT is not true for this pinned blob.
Do not treat that original commit message as evidence that zoom is validated.
Normal AOSP Binder traffic bypasses the loader/parser. Recognized extension
errors are returned to the caller, rather than falling through with a consumed
Parcel into the AOSP parser. Unhandled transactions retain normal AOSP behavior.
The unconditional CameraService transaction info log is removed.

Validation: six loader/enable/failure scenarios with 32 concurrent callers each,
explicit object identity, fail-closed dispatch, permission-error propagation,
ARM64 syntax checks of factory and CameraService using the generated CFI flags,
and all three camera mail patches replayed from the pre-extension file baseline.

Run the portable host test after applying patches:

```sh
python3 vendor/extraPatches/tests/camera/test_camera_extension.py \
  --source-dir frameworks/av/services/camera/libcameraservice/ext
```

This does not prove device CFI/linker selection, private object-layout safety,
zoom/capture callbacks or every OEM protocol. They require the next ROM runtime
check. The current flashed image does not contain this framework change.
