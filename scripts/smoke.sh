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

echo "SMOKE OK"
