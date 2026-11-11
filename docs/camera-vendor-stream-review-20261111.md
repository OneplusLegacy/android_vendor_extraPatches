# OnePlus 7 Pro vendor stream configuration (2026-11-11)

Two distinct device failures were recorded:

* 11:16:24: camera provider SIGSEGV in stock libGLESv2_adreno.so at 0x24dbd0,
  followed by a camcorder teardown exception at 11:16:34.
* 11:41:31: reflective CameraDevice.setVendorStreamConfigMode(int) lookup fails,
  then video stream configuration mode 0x8116 is rejected by HAL with -38.

## Verified stock contract

Stock framework.jar declares the hidden method on CameraDevice. CameraDeviceImpl
stores its argument in customOpMode (default zero), then sends
`operatingMode | (customOpMode << 16)` to endConfigure. The app chooses this sensor
index from org.quic.camera2.sensormode.info.SensorModeTable. A read-only diagnostic
confirmed SM8150 detection, OnePlus identity and the stock feature configuration.
It granted no privacy permission and recorded no images or audio/video.

The patch restores the entry point, guards its per-device state with the interface
lock, and encodes it in both legacy endConfigure and Android 17's batched
configureStreams path. Local normal/high-speed checks retain the original type.
Zero preserves current behavior. A concrete CameraDevice default rejects other
unsupported implementations without introducing an abstract subclass requirement.

Validation: compiled both full modified Java sources against the current framework
and inspected the concrete `(I)V` ABI. The mail patch replays and matches the
reviewed files. HAL acceptance and the separate GPU crash require new-ROM testing.

## Additional reflection and reference audit

540 reflective caller methods were extracted from the actual Camera/Gallery APKs.
139 stock classes matched the candidate framework targets. Comparing full current
class files produces 13 stock-only name candidates, not 13 confirmed failures.
Turbine headers omit private fields: mProperties/mResults and Gallery editor/list
fields do exist, and must not be recreated based on those incomplete headers.

The live relevant missing method is setVendorStreamConfigMode. Other candidates
include optional BoostFramework hints, OEM identifier/network/touch-node APIs and
capability-gated HEIF rendering. Active callers and working backends must be
established before restoring them; no backend result should be fabricated.

Checked hardware/oplus HEAD, pre-revert 852ccb0 clients, repository history and
vendor/oplus/camera. They do not provide this exact sensor-mode bridge. Reference
camera docs warn about Java/JNI metadata ABI, but show newer unit-SDK portrait
crashes in libAlgoProcess::APSMetadata::copyMetadata, not this 7 Pro failure.
Their portrait-capture status is unresolved; status checkboxes do not certify 7 Pro.

The additional pagani/extraPatches reference contains ImageReader nativeGetConsumer,
OPlus HardwareBuffer holders, Qualcomm nativewindow plane handling, HDR recorder
metadata/reset fixes and ARR/VRR display policies. It has no setVendorStreamConfigMode
or customOpMode patch. The 7 Pro APK/native scan has none of getOplusHardwareBuffer,
nativeGetConsumer, setExcludeSnapshot or OplusUserData/oplus-user-data. The OPlus
holder/HDR-specific patches are not copied without a matching caller. Separately,
libCameraNext.so DOES import the standard AHardwareBuffer_lockPlanes API, so the
Qualcomm YUV-format recognition patch remains a candidate: the absence of newer
OPlus method names cannot rule it out. Actual buffer format/plane-layout evidence
is required before applying it. The VRR policy is not a validated fix for this
device's fixed 60/90Hz panel; its high-category default already matches 90Hz.
