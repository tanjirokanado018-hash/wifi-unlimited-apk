[app]

# App title
title = WiFi Unlimited

# Package name
package.name = wifiunlimited

# Package domain (needed for android)
package.domain = com.laminpaing

# Source code where the main.py lives
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf

# App version
version = 1.0.0

# Requirements – all libs the app needs
requirements = python3,kivy==2.3.0,requests,aiohttp,pycryptodome,certifi,urllib3,charset-normalizer,idna,multidict,yarl,aiosignal,frozenlist,async-timeout

# Entry point
entrypoint = main.py

# Android permissions
android.permissions = INTERNET,ACCESS_NETWORK_STATE,ACCESS_WIFI_STATE,CHANGE_WIFI_STATE

# Orientation
orientation = portrait

# Fullscreen
fullscreen = 0

# Minimum Android API level
android.minapi = 21

# Target Android API level
android.api = 33

# Android SDK
android.ndk = 25b
android.sdk = 33

# Android architecture (arm64-v8a covers most modern phones)
android.archs = arm64-v8a, armeabi-v7a

# Allow backup
android.allow_backup = True

# App icon (place icon.png in the same folder for a custom icon)
# icon.filename = %(source.dir)s/assets/icon.png

# Bootstrap
p4a.bootstrap = sdl2

# Buildozer log level
log_level = 2

# Warn on missing dependencies
warn_on_root = 1

[buildozer]
# Directory where buildozer stores its output
build_dir = .buildozer
bin_dir = ./bin
