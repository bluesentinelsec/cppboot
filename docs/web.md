# Web package (`--with-web-ci`)

Generate a project with a web/Emscripten pipeline aimed at **browser game
development**:

```bash
cppboot -n mygame --with-web-ci
```

The generated project builds its C++ library to WebAssembly, ships an HTML5
canvas demo structured like a game (an
[`emscripten_set_main_loop`](https://emscripten.org/docs/porting/emscripten-runtime-environment.html#browser-main-loop)
loop driven by requestAnimationFrame, simulation separated from rendering,
real delta time), and runs browser tests in headless Chrome on CI.

## What gets generated

```text
mygame/
  src/web/
    CMakeLists.txt   # canvas demo target (Emscripten only) + game-dev hooks
    main_web.cpp     # game loop: Update(dt) + EM_JS canvas renderer + HUD
    shell.html       # fullscreen-canvas shell page (--shell-file)
  tests/web/
    CMakeLists.txt   # GoogleTest compiled to wasm, SUFFIX .html, --emrun
    web_test.cpp     # version + JS-interop checks, run inside a real browser
  .github/workflows/web.yml
```

The root `CMakeLists.txt` gains Emscripten-aware guards: optional
dependencies default off, the CLI demo app and benchmarks are hard-disabled
for browser builds (the canvas demo replaces them), the core library is
always built **static**, and `tests/` switches to the browser test page under
Emscripten. A new `<MACRO>_BUILD_WEB_DEMO` option (default on for top-level
builds) controls the demo so library consumers don't build it.

## Game-development defaults

The demo target links with:

- `-sALLOW_MEMORY_GROWTH=1` — no fixed heap ceiling
- `-sUSE_WEBGL2=1` — WebGL2 context available when you graduate from
  canvas-2D
- `--shell-file src/web/shell.html` — a dark, fullscreen, DPI-aware canvas
  page you own completely (no Emscripten branding)

Commented, ready-to-enable hooks in `src/web/CMakeLists.txt`:

- **Assets:** `--preload-file assets@/assets` bundles a directory into the
  virtual filesystem — read with ordinary `std::ifstream("/assets/...")`.
- **SDL2:** `-sUSE_SDL=2` on both compile and link options for input, audio,
  and textures.

`main_web.cpp` shows the intended structure: keep per-frame simulation in
`Update(GameState&, double dt)`, render at the end of the frame, and never
block the main thread — the browser owns pacing.

## Requirements

| Context | Needs |
|---------|-------|
| Generating the project | nothing extra |
| Building locally | an activated [Emscripten SDK](https://emscripten.org/docs/getting_started/downloads.html) (`emcmake`, `emcc` on PATH) + Ninja |
| Running tests locally | Chrome (`emrun` drives it headless) |
| CI | nothing — `ubuntu-latest` + `mymindstorm/setup-emsdk` |

## Build and run

```bash
emcmake cmake -S . -B build/web-release -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build/web-release --parallel
emrun build/web-release/bin/mygame.html     # serves locally and opens the demo
```

Browser tests (GoogleTest compiled to wasm; exit code propagates through
`--emrun`):

```bash
emrun --browser=google-chrome \
  --browser_args="--headless=new --no-sandbox --disable-gpu" \
  --kill_exit --timeout 120 build/web-release/bin/mygame_web_test.html
```

## CI and releases

`.github/workflows/web.yml` runs on pull requests and pushes to the default branch:

1. Configure/build Debug and Release with `emcmake` (tests on).
2. Run the browser tests in headless Chrome for both configurations.
3. Verify the canvas demo (`mygame.html/.js/.wasm`) was produced.
4. Package `mygame-web-wasm32-release-<version>.zip`: the installed wasm32
   static library + headers (consumable via `find_package` from any
   Emscripten CMake build), the playable demo under `demo/`, the pinned
   `EMSCRIPTEN_VERSION`, and the LICENSE.

The Release workflow gains a `build-web` job with the same build/test/package
steps; on a `v*` tag or manual dispatch the zip is attached to the GitHub
Release next to the desktop zips (and the Android AAR / iOS XCFramework when
those flags are enabled).

Publishing the demo: the `demo/` directory in the package is a static site —
drop it on GitHub Pages, itch.io, or any static host. Serve over HTTP (wasm
does not load from `file://`).

## Limitations

- `--with-web-ci` cannot be combined with `--with-modules` (C++20 module
  scanning is untested with the Emscripten toolchain, and the package ships
  the classic header tree).
- `--shared` is honored on desktop platforms only; the web build always
  produces a static wasm library.
- The Emscripten SDK version floats (`setup-emsdk` with `latest`); the
  release package records the exact `EMSCRIPTEN_VERSION` used.

Android ([`--with-android-ci`](android.md)) and iOS
([`--with-ios-ci`](ios.md)) complete the platform set.
