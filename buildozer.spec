[app]

title = WiFi Unlimited
package.name = wifiunlimited
package.domain = com.laminpaing

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf

version = 1.0.0

requirements = python3,kivy==2.3.0,requests,aiohttp,pycryptodome,certifi,urllib3,charset-normalizer,idna,multidict,yarl,aiosignal,frozenlist,async-timeout

orientation = portrait
fullscreen = 0

android.permissions = INTERNET,ACCESS_NETWORK_STATE,ACCESS_WIFI_STATE,CHANGE_WIFI_STATE

android.minapi = 21
android.api = 33
android.ndk = 25b
android.sdk = 33
android.ndk_api = 21

android.build_tools_version = 34.0.0
android.archs = arm64-v8a, armeabi-v7a

android.allow_backup = True
android.accept_sdk_license = True
android.skip_update = False

p4a.bootstrap = sdl2

log_level = 2
warn_on_root = 1

[buildozer]
build_dir = .buildozer
bin_dir = ./bin
