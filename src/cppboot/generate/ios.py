"""iOS XCFramework scaffold templates for generated projects.

Generates the build/verify/test scripts under ``scripts/`` and the Simulator
test application under ``tests/ios/``. The XCFramework packages the project's
static core library (built twice: device arm64 and simulator arm64/x86_64)
together with the public headers and the generated ``version.hpp``. GitHub
Actions workflow content lives in :mod:`cppboot.generate.github_actions`.

Follows the platform-scaffold pattern established by
:mod:`cppboot.generate.android`: one module owning the platform files, with
pinned toolchain versions as module constants.
"""

from __future__ import annotations

from cppboot.generate.context import Context

_Context = Context

# Pinned iOS toolchain knobs (upgrade deliberately).
IOS_DEPLOYMENT_TARGET = "13.0"
# tests/ios is a standalone CMake project driven by the Xcode generator on
# modern macOS runners; it does not inherit the root project's 3.20 floor.
IOS_TESTS_CMAKE_MINIMUM = "3.28"


def _ios_bundle_id(ctx: _Context) -> str:
    """Reverse-DNS id for the Simulator test app (shared with Android's)."""
    return f"{ctx.android_package}.test"


def _build_ios_xcframework_sh(ctx: _Context) -> str:
    return f"""\
#!/usr/bin/env bash
# Build {ctx.name}.xcframework: static device (arm64) and simulator
# (arm64/x86_64) libraries plus public headers and the generated version.hpp.
set -euo pipefail

repository_root="$(cd "$(dirname "$0")/.." && pwd)"
configuration="${{1:-Release}}"
configuration_lower="$(printf '%s' "${{configuration}}" | tr '[:upper:]' '[:lower:]')"
output_root="${{2:-${{repository_root}}/build/ios/${{configuration_lower}}}}"
deployment_target="${{{ctx.macro}_IOS_DEPLOYMENT_TARGET:-{IOS_DEPLOYMENT_TARGET}}}"

case "${{configuration}}" in
    Debug|Release) ;;
    *)
        echo "Configuration must be Debug or Release (got '${{configuration}}')" >&2
        exit 2
        ;;
esac

if [[ "${{output_root}}" != /* ]]; then
    output_root="${{repository_root}}/${{output_root}}"
fi

version="$(tr -d '[:space:]' <"${{repository_root}}/VERSION" | sed 's/^v//;s/^V//;s/#.*//')"
device_build="${{output_root}}/iphoneos"
simulator_build="${{output_root}}/iphonesimulator"
combined_root="${{output_root}}/combined"
headers_root="${{output_root}}/headers"
xcframework="${{output_root}}/{ctx.name}.xcframework"
archive="${{output_root}}/{ctx.name}-ios-xcframework-${{configuration_lower}}-${{version}}.zip"

for tool in cmake xcodebuild xcrun libtool lipo ditto; do
    command -v "${{tool}}" >/dev/null 2>&1 || {{
        echo "Required Apple build tool is missing: ${{tool}}" >&2
        exit 2
    }}
done

cmake -E remove_directory "${{output_root}}"
cmake -E make_directory "${{combined_root}}"

configure_and_build() {{
    local sdk="$1"
    local architectures="$2"
    local build_dir="$3"

    cmake -S "${{repository_root}}" -B "${{build_dir}}" -G Xcode \\
        -DCMAKE_SYSTEM_NAME=iOS \\
        -DCMAKE_OSX_SYSROOT="${{sdk}}" \\
        -DCMAKE_OSX_ARCHITECTURES="${{architectures}}" \\
        -DCMAKE_OSX_DEPLOYMENT_TARGET="${{deployment_target}}" \\
        -DCMAKE_XCODE_ATTRIBUTE_IPHONEOS_DEPLOYMENT_TARGET="${{deployment_target}}" \\
        -DCMAKE_XCODE_ATTRIBUTE_CODE_SIGNING_ALLOWED=NO \\
        -DCMAKE_XCODE_ATTRIBUTE_CODE_SIGNING_REQUIRED=NO \\
        -DCMAKE_XCODE_ATTRIBUTE_CODE_SIGN_IDENTITY= \\
        -D{ctx.macro}_BUILD_APP=OFF \\
        -D{ctx.macro}_BUILD_TESTS=OFF \\
        -D{ctx.macro}_BUILD_BENCHMARKS=OFF \\
        -D{ctx.macro}_WITH_CLI11=OFF \\
        -D{ctx.macro}_WITH_JSON=OFF \\
        -D{ctx.macro}_WITH_SPDLOG=OFF

    cmake --build "${{build_dir}}" --config "${{configuration}}" \\
        --target "{ctx.name}_lib" --parallel
}}

combine_archives() {{
    local build_dir="$1"
    local destination="$2"
    local candidate

    candidate="$(find "${{build_dir}}" -type f -name "lib{ctx.target}.a" -path "*/${{configuration}}*" -print -quit)"
    if [[ -z "${{candidate}}" ]]; then
        echo "Missing lib{ctx.target}.a in ${{build_dir}}" >&2
        exit 1
    fi

    libtool -static -o "${{destination}}" "${{candidate}}"
}}

configure_and_build iphoneos arm64 "${{device_build}}"
configure_and_build iphonesimulator 'arm64;x86_64' "${{simulator_build}}"

combine_archives "${{device_build}}" "${{combined_root}}/lib{ctx.target}-iphoneos.a"
combine_archives "${{simulator_build}}" "${{combined_root}}/lib{ctx.target}-iphonesimulator.a"

cmake -E make_directory "${{headers_root}}/{ctx.namespace}"
cmake -E copy_directory "${{repository_root}}/include/{ctx.namespace}" "${{headers_root}}/{ctx.namespace}"
cmake -E rm -f "${{headers_root}}/{ctx.namespace}/.gitkeep"
cmake -E copy "${{device_build}}/generated/include/{ctx.namespace}/version.hpp" \\
    "${{headers_root}}/{ctx.namespace}/version.hpp"

xcodebuild -create-xcframework \\
    -library "${{combined_root}}/lib{ctx.target}-iphoneos.a" \\
    -headers "${{headers_root}}" \\
    -library "${{combined_root}}/lib{ctx.target}-iphonesimulator.a" \\
    -headers "${{headers_root}}" \\
    -output "${{xcframework}}"

ditto -c -k --norsrc --noextattr --keepParent "${{xcframework}}" "${{archive}}"

"${{repository_root}}/scripts/verify_ios_xcframework.sh" "${{xcframework}}" "${{version}}"

echo "XCFramework: ${{xcframework}}"
echo "Package: ${{archive}}"
"""


def _build_ios_test_apps_sh(ctx: _Context) -> str:
    return f"""\
#!/usr/bin/env bash
# Build the Simulator/device test apps against a packaged {ctx.name}.xcframework.
set -euo pipefail

repository_root="$(cd "$(dirname "$0")/.." && pwd)"
xcframework="${{1:-}}"
configuration="${{2:-Release}}"
output_root="${{3:-${{repository_root}}/build/ios/consumer}}"
deployment_target="${{{ctx.macro}_IOS_DEPLOYMENT_TARGET:-{IOS_DEPLOYMENT_TARGET}}}"
version="$(tr -d '[:space:]' <"${{repository_root}}/VERSION" | sed 's/^v//;s/^V//;s/#.*//')"

if [[ -z "${{xcframework}}" ]]; then
    echo "usage: $0 <{ctx.name}.xcframework> [Debug|Release] [output-directory]" >&2
    exit 2
fi
if [[ "${{xcframework}}" != /* ]]; then
    xcframework="${{repository_root}}/${{xcframework}}"
fi
if [[ "${{output_root}}" != /* ]]; then
    output_root="${{repository_root}}/${{output_root}}"
fi
if [[ ! -d "${{xcframework}}" ]]; then
    echo "XCFramework not found: ${{xcframework}}" >&2
    exit 2
fi

case "${{configuration}}" in
    Debug|Release) ;;
    *)
        echo "Configuration must be Debug or Release (got '${{configuration}}')" >&2
        exit 2
        ;;
esac

configure_and_build() {{
    local sdk="$1"
    local architecture="$2"
    local build_dir="$3"

    cmake -S "${{repository_root}}/tests/ios" -B "${{build_dir}}" -G Xcode \\
        -DCMAKE_SYSTEM_NAME=iOS \\
        -DCMAKE_OSX_SYSROOT="${{sdk}}" \\
        -DCMAKE_OSX_ARCHITECTURES="${{architecture}}" \\
        -DCMAKE_OSX_DEPLOYMENT_TARGET="${{deployment_target}}" \\
        -DCMAKE_XCODE_ATTRIBUTE_IPHONEOS_DEPLOYMENT_TARGET="${{deployment_target}}" \\
        -DCMAKE_XCODE_ATTRIBUTE_CODE_SIGNING_ALLOWED=NO \\
        -DCMAKE_XCODE_ATTRIBUTE_CODE_SIGNING_REQUIRED=NO \\
        -DCMAKE_XCODE_ATTRIBUTE_CODE_SIGN_IDENTITY= \\
        -D{ctx.macro}_XCFRAMEWORK="${{xcframework}}" \\
        -D{ctx.macro}_EXPECTED_VERSION="${{version}}"

    cmake --build "${{build_dir}}" --config "${{configuration}}" \\
        --target {ctx.target}_ios_test --parallel
}}

cmake -E remove_directory "${{output_root}}"
configure_and_build iphoneos arm64 "${{output_root}}/iphoneos"
configure_and_build iphonesimulator "$(uname -m)" "${{output_root}}/iphonesimulator"

echo "Device app build: ${{output_root}}/iphoneos"
echo "Simulator app build: ${{output_root}}/iphonesimulator"
"""


def _verify_ios_xcframework_sh(ctx: _Context) -> str:
    # Itanium mangling of `<namespace>::Version` is `_ZN<len><namespace>7Version`.
    mangled_version = f"_?_ZN{len(ctx.namespace)}{ctx.namespace}7Version"
    return f"""\
#!/usr/bin/env bash
# Verify a packaged {ctx.name}.xcframework: slices, headers, version constants.
set -euo pipefail

xcframework="${{1:-}}"
expected_version="${{2:-}}"

if [[ -z "${{xcframework}}" || -z "${{expected_version}}" ]]; then
    echo "usage: $0 <{ctx.name}.xcframework> <expected-version>" >&2
    exit 2
fi

device_library="${{xcframework}}/ios-arm64/lib{ctx.target}-iphoneos.a"
simulator_library="${{xcframework}}/ios-arm64_x86_64-simulator/lib{ctx.target}-iphonesimulator.a"

test -f "${{xcframework}}/Info.plist"
test -f "${{device_library}}"
test -f "${{simulator_library}}"

device_arches="$(lipo -archs "${{device_library}}")"
simulator_arches="$(lipo -archs "${{simulator_library}}")"
[[ " ${{device_arches}} " == *" arm64 "* ]]
[[ " ${{simulator_arches}} " == *" arm64 "* ]]
[[ " ${{simulator_arches}} " == *" x86_64 "* ]]

for identifier in ios-arm64 ios-arm64_x86_64-simulator; do
    header_root="${{xcframework}}/${{identifier}}/Headers/{ctx.namespace}"
    test -f "${{header_root}}/version.hpp"
done

version_major="${{expected_version%%.*}}"
version_remainder="${{expected_version#*.}}"
version_minor="${{version_remainder%%.*}}"
version_patch="${{version_remainder#*.}}"
version_patch="${{version_patch%%[-.]*}}"
version_header="${{xcframework}}/ios-arm64/Headers/{ctx.namespace}/version.hpp"
grep -q "kVersionMajor = ${{version_major}}" "${{version_header}}"
grep -q "kVersionMinor = ${{version_minor}}" "${{version_header}}"
grep -q "kVersionPatch = ${{version_patch}}" "${{version_header}}"

symbols_file="$(mktemp)"
trap 'rm -f "${{symbols_file}}"' EXIT
nm -g "${{device_library}}" >"${{symbols_file}}"
grep -qE '[ST] {mangled_version}' "${{symbols_file}}"

echo "Verified iOS XCFramework ${{expected_version}}"
echo "  device: ${{device_arches}}"
echo "  simulator: ${{simulator_arches}}"
"""


def _run_ios_tests_sh(ctx: _Context) -> str:
    bundle_id = _ios_bundle_id(ctx)
    sentinel = f"{ctx.macro}_IOS_TEST_RESULT"
    return f"""\
#!/usr/bin/env bash
# Run the packaged iOS tests in a temporary Simulator, polling os_log output.
set -euo pipefail

app="${{APP:-}}"
app_name="${{APP_NAME:-{ctx.target}_ios_test.app}}"
build_dir="${{BUILD_DIR:-build/ios/consumer/iphonesimulator}}"
bundle_id="${{BUNDLE_ID:-{bundle_id}}}"
log_subsystem="${{LOG_SUBSYSTEM:-{bundle_id}}}"
sentinel="${{SENTINEL:-{sentinel}}}"
timeout_seconds="${{{ctx.macro}_IOS_TEST_TIMEOUT:-180}}"
simulator_name="${{SIM_NAME:-{ctx.name} iOS Tests}}"

simulator_udid=""
launch_pid=""
stream_pid=""
log_file="$(mktemp)"

cleanup() {{
    if [[ -n "${{launch_pid}}" ]]; then
        kill "${{launch_pid}}" >/dev/null 2>&1 || true
        wait "${{launch_pid}}" >/dev/null 2>&1 || true
    fi
    if [[ -n "${{stream_pid}}" ]]; then
        kill "${{stream_pid}}" >/dev/null 2>&1 || true
        wait "${{stream_pid}}" >/dev/null 2>&1 || true
    fi
    if [[ -n "${{simulator_udid}}" ]]; then
        xcrun simctl shutdown "${{simulator_udid}}" >/dev/null 2>&1 || true
        xcrun simctl delete "${{simulator_udid}}" >/dev/null 2>&1 || true
    fi
    rm -f "${{log_file}}"
}}
trap cleanup EXIT

if [[ -z "${{app}}" ]]; then
    app="$(find "${{build_dir}}" -type d -name "${{app_name}}" -print -quit)"
fi
if [[ -z "${{app}}" || ! -d "${{app}}" ]]; then
    echo "iOS test app not found under ${{build_dir}}: ${{app_name}}" >&2
    exit 2
fi

selection="$(python3 - <<'PY'
import json
import subprocess

def simctl(*args):
    return json.loads(subprocess.check_output(["xcrun", "simctl", "list", *args, "-j"], text=True))

runtimes = [
    runtime for runtime in simctl("runtimes").get("runtimes", [])
    if runtime.get("isAvailable") and runtime.get("identifier", "").startswith(
        "com.apple.CoreSimulator.SimRuntime.iOS-"
    )
]
if not runtimes:
    raise SystemExit("No available iOS Simulator runtime")
runtime = runtimes[-1]["identifier"]

device_types = [
    device for device in simctl("devicetypes").get("devicetypes", [])
    if device.get("name", "").startswith("iPhone")
]
if not device_types:
    raise SystemExit("No available iPhone Simulator device type")

preferred = ("iPhone 17", "iPhone 16", "iPhone 15", "iPhone 14")
device = next(
    (item for name in preferred for item in device_types if item.get("name") == name),
    device_types[-1],
)
print(runtime)
print(device["identifier"])
PY
)"
runtime_id="$(printf '%s\\n' "${{selection}}" | sed -n '1p')"
device_type_id="$(printf '%s\\n' "${{selection}}" | sed -n '2p')"

echo "Using ${{runtime_id}} with ${{device_type_id}}"
simulator_udid="$(xcrun simctl create "${{simulator_name}}" "${{device_type_id}}" "${{runtime_id}}")"
xcrun simctl boot "${{simulator_udid}}"
xcrun simctl bootstatus "${{simulator_udid}}" -b
xcrun simctl install "${{simulator_udid}}" "${{app}}"

xcrun simctl spawn "${{simulator_udid}}" log stream \\
    --style compact \\
    --level debug \\
    --predicate "subsystem == \\"${{log_subsystem}}\\"" >"${{log_file}}" 2>&1 &
stream_pid=$!

# CI simulators occasionally wedge on the first launch after boot; retry once.
result=""
for attempt in 1 2; do
    xcrun simctl launch --console-pty "${{simulator_udid}}" "${{bundle_id}}" >>"${{log_file}}" 2>&1 &
    launch_pid=$!

    deadline=$((SECONDS + timeout_seconds))
    while [[ -z "${{result}}" && ${{SECONDS}} -lt ${{deadline}} ]]; do
        if grep -q "${{sentinel}}:" "${{log_file}}"; then
            result="$(grep "${{sentinel}}:" "${{log_file}}" | tail -n 1 | sed -E "s/.*${{sentinel}}: ([0-9]+).*/\\\\1/")"
            break
        fi
        sleep 1
    done
    if [[ -n "${{result}}" || ${{attempt}} -eq 2 ]]; then
        break
    fi

    echo "No ${{sentinel}} within ${{timeout_seconds}}s (attempt ${{attempt}}); relaunching" >&2
    kill "${{launch_pid}}" >/dev/null 2>&1 || true
    wait "${{launch_pid}}" >/dev/null 2>&1 || true
    launch_pid=""
    xcrun simctl terminate "${{simulator_udid}}" "${{bundle_id}}" >/dev/null 2>&1 || true
done

echo "----- iOS test log -----"
sed -n "/PASS:/p;/FAIL:/p;/${{sentinel}}:/p" "${{log_file}}"
echo "----- end iOS test log -----"

if [[ -z "${{result}}" ]]; then
    echo "Timed out waiting for ${{sentinel}}; raw simulator log tail:" >&2
    tail -n 100 "${{log_file}}" >&2
    exit 1
fi

echo "iOS test failures: ${{result}}"
exit "${{result}}"
"""


def _ios_tests_cmake(ctx: _Context) -> str:
    bundle_id = _ios_bundle_id(ctx)
    return f"""\
cmake_minimum_required(VERSION {IOS_TESTS_CMAKE_MINIMUM})

project({ctx.target}_ios_package_test LANGUAGES CXX OBJCXX)

if(NOT IOS)
  message(FATAL_ERROR "The {ctx.name} iOS package test must be configured with CMAKE_SYSTEM_NAME=iOS")
endif()

set({ctx.macro}_XCFRAMEWORK "" CACHE PATH "Path to the packaged {ctx.name}.xcframework")
set({ctx.macro}_EXPECTED_VERSION "" CACHE STRING "Version expected from the packaged library")

if(NOT IS_DIRECTORY "${{{ctx.macro}_XCFRAMEWORK}}")
  message(FATAL_ERROR "Set {ctx.macro}_XCFRAMEWORK to the packaged {ctx.name}.xcframework directory")
endif()
if({ctx.macro}_EXPECTED_VERSION STREQUAL "")
  message(FATAL_ERROR "Set {ctx.macro}_EXPECTED_VERSION to the root VERSION value")
endif()

add_executable({ctx.target}_ios_test MACOSX_BUNDLE test_main.mm)
target_compile_features({ctx.target}_ios_test PRIVATE cxx_std_20)
target_compile_options({ctx.target}_ios_test PRIVATE -fobjc-arc)
target_compile_definitions({ctx.target}_ios_test PRIVATE
  {ctx.macro}_EXPECTED_VERSION="${{{ctx.macro}_EXPECTED_VERSION}}"
)
target_link_libraries({ctx.target}_ios_test PRIVATE
  "${{{ctx.macro}_XCFRAMEWORK}}"
  "-framework Foundation"
  "-framework UIKit"
)

set_target_properties({ctx.target}_ios_test PROPERTIES
  MACOSX_BUNDLE_INFO_PLIST "${{CMAKE_CURRENT_SOURCE_DIR}}/Info.plist.in"
  MACOSX_BUNDLE_GUI_IDENTIFIER "{bundle_id}"
  MACOSX_BUNDLE_BUNDLE_NAME "{ctx.name} iOS Tests"
  MACOSX_BUNDLE_BUNDLE_VERSION "1"
  MACOSX_BUNDLE_SHORT_VERSION_STRING "${{{ctx.macro}_EXPECTED_VERSION}}"
  XCODE_ATTRIBUTE_PRODUCT_BUNDLE_IDENTIFIER "{bundle_id}"
  XCODE_ATTRIBUTE_CODE_SIGNING_ALLOWED "NO"
  XCODE_ATTRIBUTE_CODE_SIGNING_REQUIRED "NO"
  XCODE_ATTRIBUTE_CODE_SIGN_IDENTITY ""
)
"""


def _ios_test_mm(ctx: _Context) -> str:
    bundle_id = _ios_bundle_id(ctx)
    sentinel = f"{ctx.macro}_IOS_TEST_RESULT"
    return f"""\
/**
 * @file test_main.mm
 * @brief End-to-end iOS tests consuming the packaged {ctx.name} XCFramework.
 */

#import <UIKit/UIKit.h>
#import <os/log.h>

#include <{ctx.namespace}/version.hpp>

#include <string>
#include <string_view>

namespace
{{

os_log_t TestLog()
{{
    static os_log_t log = os_log_create("{bundle_id}", "tests");
    return log;
}}

class TestRun
{{
  public:
    void Check(bool condition, std::string_view message)
    {{
        const std::string text{{message}};
        if (condition)
        {{
            os_log_info(TestLog(), "PASS: %{{public}}s", text.c_str());
            return;
        }}
        ++failures_;
        os_log_error(TestLog(), "FAIL: %{{public}}s", text.c_str());
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
    run.Check(version == {ctx.macro}_EXPECTED_VERSION,
              "XCFramework exports the VERSION-derived API");
    const std::string major_prefix = std::to_string({ctx.namespace}::kVersionMajor) + ".";
    run.Check(version.substr(0, major_prefix.size()) == major_prefix,
              "Version() matches the compiled major version");
    run.Check({ctx.namespace}::kVersionMajor >= 0, "major version is non-negative");
    return run.failures();
}}

}} // namespace

@interface TestAppDelegate : UIResponder <UIApplicationDelegate>
@property(nonatomic, strong) UIWindow *window;
@end

@implementation TestAppDelegate

- (BOOL)application:(UIApplication *)application
    didFinishLaunchingWithOptions:(NSDictionary<UIApplicationLaunchOptionsKey, id> *)launchOptions
{{
    (void)application;
    (void)launchOptions;
    self.window = [[UIWindow alloc] initWithFrame:UIScreen.mainScreen.bounds];
    self.window.rootViewController = [[UIViewController alloc] init];
    self.window.rootViewController.view.backgroundColor = UIColor.systemBackgroundColor;
    [self.window makeKeyAndVisible];

    dispatch_async(dispatch_get_global_queue(QOS_CLASS_USER_INITIATED, 0), ^{{
      const int failures = RunTests();
      os_log_info(TestLog(), "{sentinel}: %{{public}}d", failures);
    }});
    return YES;
}}

@end

int main(int argc, char *argv[])
{{
    @autoreleasepool
    {{
        return UIApplicationMain(argc, argv, nil, NSStringFromClass(TestAppDelegate.class));
    }}
}}
"""


def _ios_info_plist_in(ctx: _Context) -> str:
    return f"""\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDevelopmentRegion</key>
  <string>en</string>
  <key>CFBundleExecutable</key>
  <string>$(EXECUTABLE_NAME)</string>
  <key>CFBundleIdentifier</key>
  <string>$(PRODUCT_BUNDLE_IDENTIFIER)</string>
  <key>CFBundleInfoDictionaryVersion</key>
  <string>6.0</string>
  <key>CFBundleName</key>
  <string>$(PRODUCT_NAME)</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>@{ctx.macro}_EXPECTED_VERSION@</string>
  <key>CFBundleVersion</key>
  <string>1</string>
  <key>LSRequiresIPhoneOS</key>
  <true/>
  <key>UILaunchScreen</key>
  <dict/>
  <key>UISupportedInterfaceOrientations</key>
  <array>
    <string>UIInterfaceOrientationPortrait</string>
    <string>UIInterfaceOrientationLandscapeLeft</string>
    <string>UIInterfaceOrientationLandscapeRight</string>
  </array>
</dict>
</plist>
"""
