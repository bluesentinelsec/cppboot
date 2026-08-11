"""Android Prefab AAR scaffold templates for generated projects.

Generates the ``android/`` Gradle project (library AAR with Prefab publishing
plus a consumer test application), the Android-only CMake component, the
device test sources, and the emulator test driver script. GitHub Actions
workflow content lives in :mod:`cppboot.generate.github_actions`.

Future platform scaffolds (iOS, web/Emscripten) should follow this module's
pattern: one ``generate/<platform>.py`` owning the platform files, with pinned
toolchain versions as module constants.
"""

from __future__ import annotations

from importlib import resources

from cppboot.generate.context import Context

_Context = Context

# Pinned Android toolchain (known-working combination; upgrade deliberately).
GRADLE_VERSION = "8.10.2"
GRADLE_DIST_SHA256 = "31c55713e40233a8303827ceb42ca48a47267a0ad4bab9177123121e71524c26"
GRADLE_WRAPPER_JAR_SHA256 = "2db75c40782f5e8ba1fc278a5574bab070adccb2d21ca5a6e5ed840888448046"
AGP_VERSION = "8.7.3"
NDK_VERSION = "27.2.12479018"
ANDROID_COMPILE_SDK = 35
ANDROID_MIN_SDK = 21
ANDROID_CMAKE_VERSION = "3.22.1"
ANDROID_ABIS = ("armeabi-v7a", "arm64-v8a", "x86_64")
EMULATOR_API_LEVEL = 30


def _android_package_segment(ctx: _Context) -> str:
    """Last segment of the Android package (project-derived, all-alphanumeric)."""
    return ctx.android_package.rsplit(".", 1)[-1]


def _jni_test_symbol(ctx: _Context) -> str:
    """JNI symbol for TestActivity.runNativeTests (package has no underscores)."""
    return (
        "Java_" + f"{ctx.android_package}.test".replace(".", "_") + "_TestActivity_runNativeTests"
    )


def _gradle_wrapper_jar() -> bytes:
    """Bundled Gradle wrapper bootstrap JAR (binary package data)."""
    return resources.files("cppboot").joinpath("data/android/gradle-wrapper.jar").read_bytes()


def _gradlew() -> str:
    """Stock Gradle wrapper shell script (bundled verbatim as package data)."""
    return resources.files("cppboot").joinpath("data/android/gradlew").read_text(encoding="utf-8")


def _gradlew_bat() -> str:
    """Stock Gradle wrapper batch script (bundled verbatim as package data)."""
    return (
        resources.files("cppboot").joinpath("data/android/gradlew.bat").read_text(encoding="utf-8")
    )


def _gradle_wrapper_properties() -> str:
    return f"""\
distributionBase=GRADLE_USER_HOME
distributionPath=wrapper/dists
distributionUrl=https\\://services.gradle.org/distributions/gradle-{GRADLE_VERSION}-bin.zip
distributionSha256Sum={GRADLE_DIST_SHA256}
networkTimeout=10000
validateDistributionUrl=true
zipStoreBase=GRADLE_USER_HOME
zipStorePath=wrapper/dists
"""


def _android_settings_gradle(ctx: _Context) -> str:
    return f"""\
pluginManagement {{
    repositories {{
        google()
        mavenCentral()
        gradlePluginPortal()
    }}
}}

dependencyResolutionManagement {{
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {{
        google()
        mavenCentral()
    }}
}}

rootProject.name = "{ctx.name}-android"
include(":{ctx.target}")
include(":test-app")
"""


def _android_root_build_gradle(ctx: _Context) -> str:
    _ = ctx
    return f"""\
plugins {{
    id "com.android.library" version "{AGP_VERSION}" apply false
    id "com.android.application" version "{AGP_VERSION}" apply false
}}
"""


def _android_gradle_properties() -> str:
    return """\
org.gradle.jvmargs=-Xmx4g -Dfile.encoding=UTF-8
org.gradle.parallel=true
android.useAndroidX=false
"""


def _android_library_build_gradle(ctx: _Context) -> str:
    abi_filters = ", ".join(f'"{abi}"' for abi in ANDROID_ABIS)
    return f"""\
plugins {{
    id "com.android.library"
}}

def repositoryRoot = rootProject.projectDir.parentFile
def prefabHeaders = file("${{buildDir}}/generated/prefab-headers")
def packageVersion = new File(repositoryRoot, "VERSION").readLines()[0]
        .replaceFirst(/^[vV]/, "")
        .replaceFirst(/[ \\t]*#.*$/, "")
        .trim()

version = packageVersion

android {{
    namespace "{ctx.android_package}"
    compileSdk {ANDROID_COMPILE_SDK}
    ndkVersion "{NDK_VERSION}"

    defaultConfig {{
        minSdk {ANDROID_MIN_SDK}

        ndk {{
            abiFilters {abi_filters}
        }}

        externalNativeBuild {{
            cmake {{
                arguments "-DANDROID_STL=c++_shared",
                          "-D{ctx.macro}_BUILD_APP=OFF",
                          "-D{ctx.macro}_BUILD_TESTS=OFF",
                          "-D{ctx.macro}_BUILD_BENCHMARKS=OFF",
                          "-D{ctx.macro}_WITH_CLI11=OFF",
                          "-D{ctx.macro}_WITH_JSON=OFF",
                          "-D{ctx.macro}_WITH_SPDLOG=OFF"
                targets "{ctx.target}"
            }}
        }}
    }}

    buildTypes {{
        release {{
            minifyEnabled false
        }}
    }}

    buildFeatures {{
        prefabPublishing true
    }}

    prefab {{
        {ctx.target} {{
            headers prefabHeaders.absolutePath
        }}
    }}

    externalNativeBuild {{
        cmake {{
            path repositoryRoot.toPath().resolve("CMakeLists.txt").toFile()
            version "{ANDROID_CMAKE_VERSION}"
        }}
    }}
}}

// Prefab ships a header snapshot with the AAR: the public include/ tree plus a
// rendered version.hpp (Gradle-side equivalent of the CMake configure_file).
tasks.register("preparePrefabHeaders") {{
    inputs.dir(new File(repositoryRoot, "include"))
    inputs.file(new File(repositoryRoot, "VERSION"))
    inputs.file(new File(repositoryRoot, "cmake/version.hpp.in"))
    outputs.dir(prefabHeaders)

    doLast {{
        delete(prefabHeaders)
        copy {{
            from new File(repositoryRoot, "include")
            into prefabHeaders
            include "**/*.h", "**/*.hpp"
        }}

        def components = packageVersion.tokenize(".-")
        if (components.size() < 3 || !components.take(3).every {{ it ==~ /[0-9]+/ }}) {{
            throw new GradleException("VERSION must begin with numeric major.minor.patch")
        }}

        def versionHeader = new File(repositoryRoot, "cmake/version.hpp.in").text
                .replace("@PROJECT_NAMESPACE@", "{ctx.namespace}")
                .replace("@PROJECT_VERSION_MAJOR@", components[0])
                .replace("@PROJECT_VERSION_MINOR@", components[1])
                .replace("@PROJECT_VERSION_PATCH@", components[2])
        def output = new File(prefabHeaders, "{ctx.namespace}/version.hpp")
        output.parentFile.mkdirs()
        output.text = versionHeader
    }}
}}

tasks.named("preBuild").configure {{
    dependsOn("preparePrefabHeaders")
}}
"""


def _android_library_manifest() -> str:
    return '<manifest xmlns:android="http://schemas.android.com/apk/res/android" />\n'


def _android_test_app_build_gradle(ctx: _Context) -> str:
    return f"""\
plugins {{
    id "com.android.application"
}}

def testAbi = providers.gradleProperty("{ctx.target}TestAbi").getOrElse("x86_64")

android {{
    namespace "{ctx.android_package}.test"
    compileSdk {ANDROID_COMPILE_SDK}
    ndkVersion "{NDK_VERSION}"

    defaultConfig {{
        applicationId "{ctx.android_package}.test"
        minSdk {ANDROID_MIN_SDK}
        targetSdk {ANDROID_COMPILE_SDK}
        versionCode 1
        versionName "1.0"

        ndk {{
            abiFilters testAbi
        }}

        externalNativeBuild {{
            cmake {{
                arguments "-DANDROID_STL=c++_shared"
                targets "{ctx.target}_android_test"
            }}
        }}
    }}

    buildTypes {{
        release {{
            minifyEnabled false
            signingConfig signingConfigs.debug
        }}
    }}

    compileOptions {{
        sourceCompatibility JavaVersion.VERSION_17
        targetCompatibility JavaVersion.VERSION_17
    }}

    buildFeatures {{
        prefab true
    }}

    packaging {{
        jniLibs {{
            // Prefab stages the imported AAR libraries beside the consumer's
            // JNI target; both copies originate from this exact AAR/NDK build.
            pickFirsts += ["**/lib{ctx.target}.so", "**/libc++_shared.so"]
        }}
    }}

    externalNativeBuild {{
        cmake {{
            path rootProject.projectDir.toPath().resolve("../tests/android/CMakeLists.txt").toFile()
            version "{ANDROID_CMAKE_VERSION}"
        }}
    }}
}}

dependencies {{
    debugImplementation files("../{ctx.target}/build/outputs/aar/{ctx.target}-debug.aar")
    releaseImplementation files("../{ctx.target}/build/outputs/aar/{ctx.target}-release.aar")
}}
"""


def _android_test_app_manifest(ctx: _Context) -> str:
    return f"""\
<manifest xmlns:android="http://schemas.android.com/apk/res/android">

    <application
        android:allowBackup="false"
        android:label="{ctx.name} Android tests"
        android:supportsRtl="true"
        android:theme="@android:style/Theme.Material.Light.NoActionBar">
        <activity
            android:name=".TestActivity"
            android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>
"""


def _android_test_activity_java(ctx: _Context) -> str:
    return f"""\
package {ctx.android_package}.test;

import android.app.Activity;
import android.os.Bundle;
import android.util.Log;

public final class TestActivity extends Activity {{
    private static final String TAG = "{ctx.name}-android-test";

    static {{
        System.loadLibrary("{ctx.target}_android_test");
    }}

    private static native int runNativeTests();

    @Override
    protected void onCreate(Bundle state) {{
        super.onCreate(state);
        Thread runner = new Thread(() -> {{
            int failures = runNativeTests();
            if (failures == 0) {{
                Log.i(TAG, "{ctx.macro}_ANDROID_TESTS: PASS");
            }} else {{
                Log.e(TAG, "{ctx.macro}_ANDROID_TESTS: FAIL (" + failures + " failures)");
            }}
            finishAndRemoveTask();
        }}, "{ctx.name}-native-tests");
        runner.start();
    }}
}}
"""


def _android_src_cmake(ctx: _Context) -> str:
    return f"""\
# Android Prefab library. Gradle publishes this target as the `{ctx.target}`
# module in the AAR. Whole-archive linking keeps every public C++ API symbol
# while folding the static core library into one shared object.
add_library({ctx.target} SHARED android_library.cpp)

target_compile_features({ctx.target} PUBLIC cxx_std_20)
target_include_directories({ctx.target}
  PUBLIC
    $<BUILD_INTERFACE:${{CMAKE_SOURCE_DIR}}/include>
    $<BUILD_INTERFACE:${{{ctx.macro}_GENERATED_INCLUDE_DIR}}>
)

add_dependencies({ctx.target} ${{PROJECT_NAME}}_lib)
target_link_options({ctx.target}
  PRIVATE
    "LINKER:--whole-archive,$<TARGET_FILE:${{PROJECT_NAME}}_lib>,--no-whole-archive"
)

set_target_properties({ctx.target} PROPERTIES
  OUTPUT_NAME {ctx.target}
)

cppboot_set_project_warnings({ctx.target})
"""


def _android_shim_cpp(ctx: _Context) -> str:
    return f"""\
/**
 * @file android_library.cpp
 * @brief Translation-unit anchor for the Android Prefab shared library.
 */

namespace {ctx.namespace}::android_detail
{{

[[maybe_unused]] constexpr bool kPrefabLibrary = true;

}} // namespace {ctx.namespace}::android_detail
"""


def _android_tests_cmake(ctx: _Context) -> str:
    return f"""\
cmake_minimum_required(VERSION {ANDROID_CMAKE_VERSION})
project({ctx.target}_android_test LANGUAGES CXX)

find_package({ctx.target} REQUIRED CONFIG)

add_library({ctx.target}_android_test SHARED android_test.cpp)
target_compile_features({ctx.target}_android_test PRIVATE cxx_std_20)
target_compile_options({ctx.target}_android_test PRIVATE
  -Wall
  -Wextra
  -Wpedantic
  -Werror
)
target_link_libraries({ctx.target}_android_test PRIVATE {ctx.target}::{ctx.target} log)
"""


def _android_test_cpp(ctx: _Context) -> str:
    return f"""\
/**
 * @file android_test.cpp
 * @brief End-to-end Android tests consuming the {ctx.name} Prefab package.
 */

#include <android/log.h>
#include <jni.h>
#include <{ctx.namespace}/version.hpp>
#include <string>
#include <string_view>

namespace
{{

constexpr const char *kLogTag = "{ctx.name}-android-test";

class TestRun
{{
  public:
    void Check(bool condition, std::string_view message)
    {{
        if (condition)
        {{
            __android_log_print(ANDROID_LOG_INFO, kLogTag, "PASS: %.*s",
                                static_cast<int>(message.size()), message.data());
            return;
        }}
        ++failures_;
        __android_log_print(ANDROID_LOG_ERROR, kLogTag, "FAIL: %.*s",
                            static_cast<int>(message.size()), message.data());
    }}

    [[nodiscard]] int failures() const noexcept
    {{
        return failures_;
    }}

  private:
    int failures_ = 0;
}};

int RunTests()
{{
    TestRun run;
    const std::string_view version = {ctx.namespace}::Version();
    run.Check(!version.empty(), "Prefab package exports the generated version API");
    const std::string major_prefix = std::to_string({ctx.namespace}::kVersionMajor) + ".";
    run.Check(version.substr(0, major_prefix.size()) == major_prefix,
              "Version() matches the compiled major version");
    run.Check({ctx.namespace}::kVersionMajor >= 0, "major version is non-negative");
    return run.failures();
}}

}} // namespace

extern "C" JNIEXPORT jint JNICALL
{_jni_test_symbol(ctx)}(JNIEnv *, jclass)
{{
    return RunTests();
}}
"""


def _run_android_tests_sh(ctx: _Context) -> str:
    return f"""\
#!/usr/bin/env bash
set -euo pipefail

apk="${{1:-android/test-app/build/outputs/apk/release/test-app-release.apk}}"
package="{ctx.android_package}.test"
activity="${{package}}/.TestActivity"
timeout_seconds="${{{ctx.macro}_ANDROID_TEST_TIMEOUT:-120}}"

if [[ ! -f "${{apk}}" ]]; then
  echo "Android test APK not found: ${{apk}}" >&2
  exit 1
fi

adb install -r "${{apk}}" >/dev/null
adb logcat -c
adb shell am force-stop "${{package}}"
adb shell am start -W -n "${{activity}}" >/dev/null

deadline=$((SECONDS + timeout_seconds))
while (( SECONDS < deadline )); do
  logs="$(adb logcat -d -s {ctx.name}-android-test:I '*:S')"
  if grep -q "{ctx.macro}_ANDROID_TESTS: PASS" <<<"${{logs}}"; then
    printf '%s\\n' "${{logs}}"
    exit 0
  fi
  if grep -q "{ctx.macro}_ANDROID_TESTS: FAIL" <<<"${{logs}}"; then
    printf '%s\\n' "${{logs}}" >&2
    exit 1
  fi
  sleep 1
done

adb logcat -d -s {ctx.name}-android-test:I '*:S' >&2
echo "Timed out after ${{timeout_seconds}}s waiting for Android tests" >&2
exit 1
"""


def _android_gitignore_extra() -> str:
    return """\

# Android / Gradle
android/.gradle/
android/local.properties
local.properties
.cxx/
"""
