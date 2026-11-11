#!/usr/bin/env python3
"""Compile the actual CameraDevice API and implementation, then inspect the reflective ABI."""
from pathlib import Path
import argparse,subprocess,tempfile
p=argparse.ArgumentParser();p.add_argument('--rom-root',required=True,type=Path);p.add_argument('--framework-source',type=Path);a=p.parse_args();r=a.rom_root;src=a.framework_source or r/'frameworks/base'
java=r/'prebuilts/jdk/jdk21/linux-x86/bin'
cp=':'.join(str(r/x) for x in ['out/soong/.intermediates/frameworks/base/framework/android_common/turbine-combined/framework.jar','out/soong/.intermediates/libcore/core-all/android_common/turbine-combined/core-all.jar','out/soong/.intermediates/frameworks/base/location/framework-location.impl/android_common/javac/framework-location.jar'])
with tempfile.TemporaryDirectory(prefix='oneplus-camera-api-') as td:
 sources=[src/'core/java/android/hardware/camera2/CameraDevice.java',src/'core/java/android/hardware/camera2/impl/CameraDeviceImpl.java']
 subprocess.run([str(java/'javac'),'-J-Xmx192m','-proc:none','-source','17','-target','17','-cp',cp,'-sourcepath','','-d',td,*map(str,sources)],check=True)
 for cls in ['android.hardware.camera2.CameraDevice','android.hardware.camera2.impl.CameraDeviceImpl']:
  api=subprocess.check_output([str(java/'javap'),'-J-Xmx48m','-p','-classpath',td,cls],text=True)
  assert 'public void setVendorStreamConfigMode(int);' in api,cls+' lacks the concrete (I)V ABI'
 print('PASS full CameraDevice/CameraDeviceImpl compilation and reflective (I)V ABI on both types')
