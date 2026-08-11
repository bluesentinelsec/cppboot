# Android package (`--with-android-ci`)

Generate a project with an Android package pipeline:

```bash
cppboot -n mylib --with-android-ci
```

The generated project packages its C++ library as a multi-ABI
[Prefab](https://developer.android.com/build/native-dependencies) AAR — the
native dependency format consumed by Gradle/CMake Android applications — and
ships with on-device tests and GitHub Actions jobs that build, verify, and test
the package on an emulator. No Java/Kotlin wrapper API is added; the AAR
exposes the project's normal C++ API to an application's CMake build.

Android API 21 or newer is supported. The AAR contains `armeabi-v7a`,
`arm64-v8a`, and `x86_64` libraries.

## What gets generated

```text
mylib/
  android/                    # Gradle project (JDK 17)
    mylib/                    # library module → Prefab AAR
    test-app/                 # consumer app hosting the device tests
    gradlew, gradle/          # pinned Gradle wrapper (offline-bundled)
  src/android/                # Android shared library target (whole-archives the core)
  tests/android/              # native on-device tests (JNI → logcat PASS/FAIL)
  scripts/run_android_tests.sh  # adb driver: install APK, launch, poll logcat
  .github/workflows/android.yml # CI: build AARs, verify, emulator tests
```

The root `CMakeLists.txt` gains `if(ANDROID)` guards: optional dependencies and
app/tests/benchmarks are forced off, position-independent code is enabled, and
the core library is always built **static** on Android (even with `--shared`)
so it folds into a single `libmylib.so`.

The Android Gradle Plugin drives the same root `CMakeLists.txt` through
`externalNativeBuild` — there is no separate Android build system to maintain.

## Requirements

| Context | Needs |
|---------|-------|
| Generating the project | nothing extra (the Gradle wrapper is bundled offline) |
| Building the AAR locally | JDK 17 and an Android SDK (`ANDROID_HOME`); Gradle auto-installs the pinned NDK and CMake |
| Running device tests locally | `adb` plus an emulator or attached device |
| CI | nothing — `ubuntu-latest` runners have the SDK; the workflow installs JDK 17 |

## Build the AAR

```bash
bash android/gradlew -p android :mylib:assembleRelease
```

Output: `android/mylib/build/outputs/aar/mylib-release.aar`. The AAR bundles
the native libraries for all three ABIs, the public `include/` tree, and the
generated `version.hpp` (rendered from the root `VERSION` file, which remains
the single source of truth).

## Use the AAR from an application

Copy the AAR into the application's `app/libs` directory, enable Prefab, and
select the shared C++ runtime:

```groovy
android {
    defaultConfig {
        minSdk 21
        externalNativeBuild {
            cmake {
                arguments "-DANDROID_STL=c++_shared"
            }
        }
    }

    buildFeatures {
        prefab true
    }
}

dependencies {
    implementation files("libs/mylib-android-release-<version>.aar")
}
```

Import the Prefab package from the application's `CMakeLists.txt`:

```cmake
find_package(mylib REQUIRED CONFIG)
target_link_libraries(app_native PRIVATE mylib::mylib)
```

The AAR is built with the shared LLVM libc++ (`c++_shared`); an Android process
must use one compatible C++ runtime across all of its native libraries, so
build the application with `-DANDROID_STL=c++_shared` as shown.

## Device tests

`tests/android/android_test.cpp` consumes the built AAR exactly the way an
application would (`find_package` via Prefab) and reports results through
logcat. The generated `test-app` hosts it; `scripts/run_android_tests.sh`
installs the APK, launches the test activity, and polls logcat for
`<MACRO>_ANDROID_TESTS: PASS` / `FAIL`:

```bash
bash android/gradlew -p android :test-app:assembleRelease
bash scripts/run_android_tests.sh   # needs adb + a running emulator/device
```

Add project-specific device checks to `tests/android/android_test.cpp`; the
host-side GoogleTest suite under `tests/<component>/` does not run on Android.

## CI and releases

`.github/workflows/android.yml` runs on every push and pull request:

1. Build Debug and Release AARs plus the consumer test APK.
2. Verify the release AAR contents: every ABI's `libmylib.so`, the packaged
   headers, and that `prefab.json` matches the `VERSION` file.
3. Run the device tests on an Android emulator (API 30, x86_64, KVM).
4. Upload `mylib-android-release-<version>.aar` as a workflow artifact.

The Release workflow gains a `build-android` job with the same build/verify/
emulator steps; on a `v*` tag or manual dispatch it attaches
`mylib-android-release-<version>.aar` to the GitHub Release next to the
desktop zips.

## Application ID / package name

The generated Android namespace defaults to `com.example.<name>` (all
non-alphanumeric characters stripped). Before publishing anything, rename it
in:

- `android/mylib/build.gradle` (`namespace`)
- `android/test-app/build.gradle` (`namespace`, `applicationId`)
- `android/test-app/src/main/java/.../TestActivity.java` (package + directory)
- `tests/android/android_test.cpp` (the JNI export symbol)

## Pinned toolchain

| Component | Version |
|-----------|---------|
| Gradle | 8.10.2 (wrapper bundled, distribution SHA-256 pinned) |
| Android Gradle Plugin | 8.7.3 |
| NDK | 27.2.12479018 |
| CMake (driven by AGP) | 3.22.1 |
| compileSdk / minSdk | 35 / 21 |
| Emulator (CI) | API 30, x86_64 |

Upgrade these deliberately in `android/` and `.github/workflows/android.yml`
(source of the pins: `src/cppboot/generate/android.py`).

## Limitations

- `--with-android-ci` cannot be combined with `--with-modules`: the Android
  Gradle Plugin builds with CMake 3.22.1, and C++20 modules require CMake
  3.28+.
- `--shared` is honored on desktop platforms only; Android always builds the
  core static and ships one shared object (see above).

iOS (`--with-ios-ci`) and web/Emscripten (`--with-web-ci`) are planned
follow-ups using the same layout.
