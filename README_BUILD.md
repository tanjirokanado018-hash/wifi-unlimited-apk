# WiFi Unlimited — APK Build Guide
**Developed by LaMinPaing**

---

## Files in this folder

| File | Description |
|---|---|
| `main.py` | Kivy UI app entry point |
| `wifi_core.py` | WiFi logic (setup, login, auth) |
| `buildozer.spec` | Buildozer configuration for APK |
| `assets/` | App icon and resources |

---

## Requirements (on your build machine)

You need a **Linux** machine (or WSL2 on Windows, or Ubuntu in Termux on Android).

```bash
# Install system dependencies
sudo apt update
sudo apt install -y git zip unzip python3-pip python3-venv \
    build-essential libssl-dev libffi-dev libsqlite3-dev \
    libltdl-dev autoconf libtool pkg-config \
    cmake zlib1g-dev

# Install Java (required by Gradle/Android SDK)
sudo apt install -y openjdk-17-jdk

# Install buildozer
pip install buildozer cython
```

---

## Build the APK

```bash
# Navigate to the wifi_apk folder
cd wifi_apk

# First build (downloads Android SDK/NDK – ~2 GB, takes 20–40 min)
buildozer android debug

# The APK will be at:
# wifi_apk/bin/wifiunlimited-1.0.0-arm64-v8a_armeabi-v7a-debug.apk
```

### On Android (Termux)

```bash
pkg update
pkg install -y python git openssl libffi
pip install buildozer cython
# Then run the same buildozer command above
```

---

## Install on phone

```bash
# With ADB (phone in developer mode)
adb install bin/*.apk

# Or copy the APK to your phone and open it
# (enable "Install from unknown sources" in Settings)
```

---

## How to use the app

1. **Connect your phone to the Ruijie WiFi** (you'll see the captive portal).
2. Open the app.
3. Tap **Setup** — the app will unbind any old session and grab the gateway IP.
4. Enter your **voucher code** in the input field.
5. Tap **Connect** — the app authenticates and upgrades to unlimited.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Build fails on first run | Let it finish downloading SDK/NDK (can take 30–40 min) |
| `pycryptodome` not found | Already in `buildozer.spec` requirements |
| App crashes on launch | Run `buildozer android logcat` to see logs |
| Setup fails | Make sure you're connected to the Ruijie WiFi first |

---

*WiFi Unlimited v1.0.0 — © LaMinPaing*
