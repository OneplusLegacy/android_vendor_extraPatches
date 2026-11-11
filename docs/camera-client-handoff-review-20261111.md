# Stock camera client identity handoff (2026-11-11)

Video still fails before recording: HAL configureStreams returns -38 for vendor
session 0x8116. A diagnostic sensor-table header correction changes the selected
sensor index from -1 to 1 and transmits 0x18116, but the HAL still rejects it.
This test does not establish a successful recording fix.

Another concrete omission is the stock connection lifecycle hook. The port only
calls the extension onTransact; stock libcameraservice calls beforeConnect from
connectHelper, passing camera ID, client package and shimUpdateOnly, before HAL
initialization. It forwards nonzero hook results as service-specific errors.
Stock disassembly evidence: connectHelper at 0xe380c; call at 0xe38a8 through
vtable offset 0x48. The pinned extension relocates that slot to beforeConnect at
0x387a4. The package is converted to a HIDL string and delivered to cameraMDM
setPackageName (vtable slot 0x70). No private CameraService/BasicClient object is
passed across the Android 12/17 boundary by this hook.

The stock odm/etc/camera/fwk_config.json has feature_cameramdm=true, mdm_v2=true.
CamX chi override queries getPackageName (slot 0x78) during OP_InitOperationMode,
compares it with com.oneplus.camera and selects OEM usecases accordingly. Current
runtime logs report [OP_EXT] 000, 0, consistent with missing client identity.
This is supporting evidence, not proof that it is the sole HAL error cause.

Restore beforeConnect after validateConnectLocked and client eviction handling,
while the service lock serializes connection setup, before preparing/opening the
HAL device. Pass the validated attribution package, preserve OEM errors and leave
the opt-out/unavailable-extension behavior functional. Resolve the exact exported
member with its implicit this pointer; do not import the old private class layout.

A matching vendor policy change in camera-guacamole is required:
hal_client_domain(cameraserver, vendor_hal_cameraMDM). The current compiled policy
has no cameraserver -> cameraMDM service discovery or Binder call. Stock vendor
policy explicitly grants cameraserver_30_0 -> hal_cameraMDM_hwservice find and
cameraserver_30_0 -> hal_cameraMDM_default Binder call/transfer. The existing
cameraMDM attribute rules supply these permissions once the client is assigned.
No app gets authority to choose another app's HAL identity.

Validation: portable factory test covers seven loader scenarios, 32 concurrent
callers, real this pointer, package/camera reference and shim flag propagation,
and nonzero error preservation. ARM64 CFI compiler syntax checks cover both the
factory and CameraService. The expanded full policy passes checkpolicy with
neverallows enabled and resolves the necessary find/call/transfer/fd-use rules.
The complete ROM has not been rebuilt or flashed. Runtime identity, video and
multi-client behavior need a new-ROM check; an app update cannot replace this
cameraserver/policy change.
