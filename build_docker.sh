#!/bin/bash
# Local APK build using Docker – no Android SDK install needed on your machine
# Usage:  bash build_docker.sh
# Developed by LaMinPaing

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE="kivy/buildozer:latest"
OUT="$SCRIPT_DIR/bin"

echo "═══════════════════════════════════════════"
echo "  WiFi Unlimited APK Builder"
echo "  Developed by LaMinPaing"
echo "═══════════════════════════════════════════"

# Pull the official kivy/buildozer image (has all deps pre-installed)
echo "[*] Pulling buildozer Docker image…"
docker pull "$IMAGE"

mkdir -p "$OUT"

echo "[*] Building APK inside Docker…"
docker run --rm \
  -v "$SCRIPT_DIR":/home/user/hostcwd \
  -v "$HOME/.buildozer":/home/user/.buildozer \
  "$IMAGE" \
  bash -c "
    cd /home/user/hostcwd &&
    buildozer android debug &&
    cp bin/*.apk /home/user/hostcwd/bin/ 2>/dev/null || true
  "

echo ""
echo "════════════════════════════════════════════"
if ls "$OUT"/*.apk 1>/dev/null 2>&1; then
  echo "[✓] APK built successfully!"
  ls -lh "$OUT"/*.apk
  echo ""
  echo "  Install with:  adb install $OUT/*.apk"
  echo "  Or copy the APK to your phone and open it."
else
  echo "[!] Build failed. Check output above."
fi
echo "════════════════════════════════════════════"
