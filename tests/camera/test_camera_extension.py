#!/usr/bin/env python3
"""Exercise the real factory with a fake loader: concurrency, ABI and fail-closed dispatch."""
from pathlib import Path
import argparse, subprocess, tempfile
p=argparse.ArgumentParser();p.add_argument('--source-dir',required=True,type=Path);a=p.parse_args()
fakes={
'binder/Parcel.h': '#pragma once\n#include <cstdint>\nnamespace android {class Parcel {};}',
'utils/Errors.h': '#pragma once\nnamespace android {constexpr int UNKNOWN_TRANSACTION=-74;constexpr int NO_ERROR=0;}',
'utils/String8.h': '#pragma once\nnamespace android {class String8 {};}',
'utils/String16.h': '#pragma once\nnamespace android {class String16 {};}',
'log/log.h': '#pragma once\n#define ALOGI(...) ((void)0)\n#define ALOGE(...) ((void)0)',
'cutils/properties.h': '#pragma once\nbool property_get_bool(const char*, bool);',
'dlfcn.h': '#pragma once\n#define RTLD_NOW 2\n#define RTLD_LOCAL 0\nvoid* dlopen(const char*, int);void* dlsym(void*, const char*);int dlclose(void*);char* dlerror();',
'binderthreadstate/CallerUtils.h': '''#pragma once
#include <sys/types.h>
namespace android {
enum class BinderCallType { BINDER, HWBINDER };inline BinderCallType getCurrentServingCall(){return BinderCallType::BINDER;}
class IPCThreadState {public:static IPCThreadState* self(){static IPCThreadState s;return &s;}pid_t getCallingPid(){return 17;}uid_t getCallingUid(){return 23;}};
namespace hardware {using IPCThreadState=android::IPCThreadState;}}
''',
'check.cpp': '''#include "CameraServiceExtFactory.h"
#include <atomic>
#include <cassert>
#include <cstring>
#include <string>
#include <thread>
#include <vector>
using namespace android;
static std::string mode;
static std::atomic<int> opens{},closes{},factories{},extensions{},calls{};
static int factory,extension;
static String8 cameraId;static String16 packageName;
static std::atomic<int> connections{};
bool property_get_bool(const char*,bool){return mode!="disabled";}
char* dlerror(){return nullptr;}
void* dlopen(const char*,int){++opens;return mode=="load-fail"?nullptr:&factory;}
int dlclose(void*){++closes;return 0;}
void* getFactory(){++factories;return mode=="null-factory"?nullptr:&factory;}
void* getExtension(void* self){assert(self==&factory);++extensions;return mode=="null-extension"?nullptr:&extension;}
int transact(void* self,uint32_t,const Parcel&,Parcel*,uint32_t){assert(self==&extension);++calls;return -1;}
int connect(void* self,const String8& id,const String16& name,bool shim){assert(self==&extension);assert(&id==&cameraId);assert(&name==&packageName);++connections;return shim?4:7;}
void* dlsym(void*,const char* name){
 if(!strcmp(name,"getExtFactoryImpl"))return reinterpret_cast<void*>(&getFactory);
 if(!strcmp(name,"_ZN7android10ExtFactory19getCameraServiceExtEv"))return mode=="missing-export"?nullptr:reinterpret_cast<void*>(&getExtension);
 if(!strcmp(name,"_ZN7android20CameraServiceExtImpl10onTransactEjRKNS_6ParcelEPS1_j"))return reinterpret_cast<void*>(&transact);
 if(!strcmp(name,"_ZN7android20CameraServiceExtImpl13beforeConnectERKNS_7String8ERKNS_8String16Eb"))return mode=="missing-connect-export"?nullptr:reinterpret_cast<void*>(&connect);
 assert(false);return nullptr;}
int main(int argc,char**argv){assert(argc==2);mode=argv[1];Parcel data,reply;
 for(unsigned code:{1u,10000u,10012u,10015u,0x5f504e47u})assert(CameraServiceExtFactory::onTransact(code,data,&reply,0)==UNKNOWN_TRANSACTION);
 assert(opens==0); // Normal Camera2 traffic cannot initialize or enter the OEM parser.
 std::vector<std::thread> threads;
 bool ok=mode=="ok";
 for(int i=0;i<32;i++)threads.emplace_back([&]{
  auto result=CameraServiceExtFactory::onTransact(10001,data,&reply,0);
  assert(result==(ok?-1:UNKNOWN_TRANSACTION)); // Permission errors survive instead of falling through.
  assert(CameraServiceExtFactory::getInstance()==(ok?&factory:nullptr));
  assert(CameraServiceExtFactory::beforeConnect(cameraId,packageName,true)==(ok?4:NO_ERROR));
  assert(CameraServiceExtFactory::beforeConnect(cameraId,packageName,false)==(ok?7:NO_ERROR));
 });
 for(auto&t:threads)t.join();
 assert(opens==(mode=="disabled"?0:1));assert(factories<=1&&extensions<=1);
 if(ok){assert(connections==64);assert(factories==1&&extensions==1&&closes==0&&calls==32);assert(CameraServiceExtFactory::onTransact(10011,data,&reply,0)==-1);}
 else{assert(connections==0);assert(calls==0);assert(closes==((mode=="disabled"||mode=="load-fail")?0:1));}
}
'''}
with tempfile.TemporaryDirectory(prefix='camera-factory-') as td:
 td=Path(td)
 for name,text in fakes.items():
  dest=td/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(text)
 subprocess.run(['g++','-std=c++17','-pthread','-Wall','-Wextra','-Werror','-I'+str(td),'-I'+str(a.source_dir),'-I'+str(a.source_dir/'include'),str(a.source_dir/'CameraServiceExtFactory.cpp'),str(td/'check.cpp'),'-o',str(td/'check')],check=True)
 for mode in ['ok','disabled','load-fail','missing-export','null-factory','null-extension','missing-connect-export']:
  subprocess.run([str(td/'check'),mode],check=True)
 print('PASS: 7 factory scenarios, 32 concurrent callers each, exact this pointer, error propagation, connection identity/flags and AOSP dispatch isolation')
