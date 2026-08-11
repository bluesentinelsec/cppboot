# iOS package (`--with-ios-ci`)

Generate a project with an iOS package pipeline:

```bash
cppboot -n mylib --with-ios-ci
```

The generated project packages its C++ library as a static
[XCFramework](https://developer.apple.com/documentation/xcode/creating-a-multi-platform-binary-framework-bundle)
— the binary distribution format Xcode consumes directly — with a device slice
(arm64) and a simulator slice (arm64/x86_64), the public headers, and the
generated `version.hpp`. It ships with Simulator-driven package tests and
GitHub Actions jobs that build, verify, and test the package. No Swift or
Objective-C wrapper API is added; the XCFramework exposes the project's normal
C++ API to an application's Xcode or CMake build.

iOS 13.0 or newer is targeted by default (override with the
`<MACRO>_IOS_DEPLOYMENT_TARGET` environment variable at build time).

## What gets generated

```text
mylib/
  scripts/
    build_ios_xcframework.sh   # device + simulator builds → mylib.xcframework + zip
    build_ios_test_apps.sh     # consumer test apps against a packaged XCFramework
    verify_ios_xcframework.sh  # slices, arches, headers, version constants, symbols
    run_ios_tests.sh           # boots a temp Simulator, installs, polls os_log
  tests/ios/                   # package test app (Objective-C++ host, C++ checks)
    CMakeLists.txt
    test_main.mm
    Info.plist.in
  .github/workflows/ios.yml    # CI: Debug+Release builds, verify, Simulator tests
```

The root `CMakeLists.txt` gains `if(IOS)` guards: optional dependencies and
app/tests/benchmarks are forced off, and the core library is always built
**static** on iOS (even with `--shared`) because the XCFramework packages a
static archive.

Unlike Android (which needs a Gradle project), the iOS pipeline is pure
CMake + Xcode tooling driven by four shell scripts — the same root
`CMakeLists.txt` is configured twice with `-G Xcode -DCMAKE_SYSTEM_NAME=iOS`,
once per SDK.

## Requirements

| Context | Needs |
|---------|-------|
| Generating the project | nothing extra |
| Building the XCFramework | macOS with Xcode command line tools (`cmake`, `xcodebuild`, `libtool`, `lipo`, `ditto`) |
| Running package tests | an iOS Simulator runtime (`xcrun simctl`) |
| CI | nothing — `macos-latest` runners have Xcode and Simulator runtimes |

## Build the XCFramework

```bash
bash scripts/build_ios_xcframework.sh Release
```

The script builds the static core for `iphoneos` (arm64) and
`iphonesimulator` (arm64/x86_64), assembles `mylib.xcframework` with headers,
produces the versioned archive
`build/ios/release/mylib-ios-xcframework-release-<version>.zip`, and runs the
verifier. Code signing is disabled throughout — sign in the consuming
application.

## Use the XCFramework from an application

**Xcode:** drag `mylib.xcframework` into the project (or add it under
*Frameworks, Libraries, and Embedded Content*). Headers are found
automatically; include them as `#include <mylib/version.hpp>`.

**CMake** (Xcode generator, `CMAKE_SYSTEM_NAME=iOS`): link the `.xcframework`
directory directly — CMake resolves the right slice per SDK:

```cmake
target_link_libraries(app_native PRIVATE "/path/to/mylib.xcframework")
```

The library is static: no embedding step, no code-signing implications from
the framework itself, and the app's binary contains the C++ code.

## Package tests

`tests/ios/test_main.mm` is a minimal UIKit app that consumes the packaged
XCFramework exactly as an application would, runs the native checks off the
main thread, and reports through `os_log` (subsystem
`com.example.mylib.test`). `run_ios_tests.sh` creates a throwaway Simulator,
installs the app, and polls the log for the `<MACRO>_IOS_TEST_RESULT`
sentinel:

```bash
bash scripts/build_ios_test_apps.sh build/ios/release/mylib.xcframework Release
bash scripts/run_ios_tests.sh
```

Add project-specific package checks to `tests/ios/test_main.mm`; the
host-side GoogleTest suite under `tests/<component>/` does not run on iOS.

## CI and releases

`.github/workflows/ios.yml` runs on every push and pull request
(`macos-latest`):

1. Build Debug and Release XCFrameworks plus the consumer test apps
   (the build script verifies each package as part of the build).
2. Run the Release package tests in an iOS Simulator.
3. Upload `mylib-ios-xcframework-release-<version>.zip` as a workflow
   artifact.

The Release workflow gains a `build-ios` job with the same steps plus an
explicit verify against the release version; on a `v*` tag or manual dispatch
it attaches the XCFramework zip to the GitHub Release next to the desktop
zips (and the Android AAR when `--with-android-ci` is also enabled).

## Bundle identifier

The Simulator test app's bundle identifier defaults to
`com.example.<name>.test` (shared derivation with the Android test app).
Rename it in `tests/ios/CMakeLists.txt` (`MACOSX_BUNDLE_GUI_IDENTIFIER` and
`XCODE_ATTRIBUTE_PRODUCT_BUNDLE_IDENTIFIER`) and in `test_main.mm` /
`run_ios_tests.sh` (os_log subsystem) before shipping anything derived from
it.

## Limitations

- `--with-ios-ci` cannot be combined with `--with-modules`: the XCFramework
  build uses the Xcode generator, which does not support C++20 module
  dependency scanning, and the package ships the classic `include/` header
  tree.
- `--shared` is honored on desktop platforms only; iOS always builds the core
  static.
- `tests/ios` configures with CMake 3.28+ (available on GitHub `macos-latest`
  runners and any recent Homebrew/official CMake).

Android is available today via [`--with-android-ci`](android.md);
web/Emscripten (`--with-web-ci`) is the planned follow-up.
