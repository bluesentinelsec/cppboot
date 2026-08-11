#!/usr/bin/env bash
# Smoke-test cppboot: fresh projects must build and test cleanly.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${TMPDIR:-/tmp}/cppboot-smoke-$$"
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"

cleanup() { rm -rf "${OUT}"; }
trap cleanup EXIT

mkdir -p "${OUT}"
python3 -m pip install -e "${ROOT}" -q

echo "== classic headers =="
python3 -m cppboot -n smoke_classic --output-dir "${OUT}"
cd "${OUT}/smoke_classic"
# Bootstrap should leave a clean git tree (fmt + initial commit).
if command -v git >/dev/null; then
  test -d .git
  test -z "$(git status --porcelain)"
  git log -1 --pretty=%s | grep -q 'Initial commit from cppboot'
fi
make
make test
./smoke_classic --version | tee /dev/stderr | grep -q '0\.1\.0'
./smoke_classic -V | grep -q '0\.1\.0'
make bench
test -e compile_commands.json
test -f .ctags
test -f .github/workflows/ci.yml
test -d .vscode
test -f CMakePresets.json

echo "== all extras off =="
python3 -m cppboot -n smoke_min \
  --no-vim --no-ctags --no-vscode --no-github-actions \
  --output-dir "${OUT}"
cd "${OUT}/smoke_min"
make
make test
./smoke_min --version | grep -q '0\.1\.0'
test ! -d android

echo "== android + ios + web scaffold =="
python3 -m cppboot -n smoke_droid --with-android-ci --with-ios-ci --with-web-ci \
  --no-git --no-fmt --output-dir "${OUT}"
cd "${OUT}/smoke_droid"
test -x android/gradlew
test -f android/gradle/wrapper/gradle-wrapper.jar
test -f android/smoke_droid/build.gradle
test -x scripts/run_android_tests.sh
test -x scripts/build_ios_xcframework.sh
test -x scripts/verify_ios_xcframework.sh
test -x scripts/run_ios_tests.sh
test -f tests/ios/test_main.mm
test -f src/web/main_web.cpp
test -f src/web/shell.html
test -f tests/web/web_test.cpp
test -f .github/workflows/android.yml
test -f .github/workflows/ios.yml
test -f .github/workflows/web.yml
grep -q 'build-android' .github/workflows/release.yml
grep -q 'build-ios' .github/workflows/release.yml
grep -q 'build-web' .github/workflows/release.yml
grep -q 'if(ANDROID OR IOS OR EMSCRIPTEN)' CMakeLists.txt
# Host build and tests must still pass with the platform CMake blocks present.
make
make test

echo "SMOKE OK"
