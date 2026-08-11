"""Orchestrate writing a complete cppboot-generated project tree."""

from __future__ import annotations

import datetime as _dt
import logging
from pathlib import Path

from cppboot.generate.android import (
    AGP_VERSION,
    GRADLE_VERSION,
    NDK_VERSION,
    _android_gitignore_extra,
    _android_gradle_properties,
    _android_library_build_gradle,
    _android_library_manifest,
    _android_root_build_gradle,
    _android_settings_gradle,
    _android_shim_cpp,
    _android_src_cmake,
    _android_test_activity_java,
    _android_test_app_build_gradle,
    _android_test_app_manifest,
    _android_test_cpp,
    _android_tests_cmake,
    _gradle_wrapper_jar,
    _gradle_wrapper_properties,
    _gradlew,
    _gradlew_bat,
    _run_android_tests_sh,
)
from cppboot.generate.build_wrappers import _build_bat, _makefile
from cppboot.generate.cmake_files import (
    _benchmarks_cmake,
    _dependencies_cmake,
    _package_config_cmake_in,
    _root_cmake,
    _sanitizers_cmake,
    _src_cmake,
    _tests_cmake,
    _version_bench_cmake,
    _version_src_cmake,
    _version_tests_cmake,
    _warnings_cmake,
)
from cppboot.generate.context import Context
from cppboot.generate.docs import (
    _agents_md,
    _clang_format,
    _clangd,
    _code_of_conduct_md,
    _contributing_md,
    _doxyfile,
    _gitattributes,
    _gitignore,
    _readme,
    _security_md,
)
from cppboot.generate.github_actions import (
    _github_actions_android_workflow,
    _github_actions_ios_workflow,
    _github_actions_release_workflow,
    _github_actions_sanitizers_workflow,
    _github_actions_web_workflow,
    _github_actions_workflow,
)
from cppboot.generate.ide import (
    _cmake_presets,
    _ctags_config,
    _devcontainer_json,
    _devcontainer_setup_sh,
    _vimrc,
    _vscode_extensions,
    _vscode_launch,
    _vscode_settings,
    _vscode_tasks,
)
from cppboot.generate.ios import (
    _build_ios_test_apps_sh,
    _build_ios_xcframework_sh,
    _ios_info_plist_in,
    _ios_test_mm,
    _ios_tests_cmake,
    _run_ios_tests_sh,
    _verify_ios_xcframework_sh,
)
from cppboot.generate.sources import (
    _main_cpp,
    _version_bench,
    _version_file,
    _version_header_in,
    _version_module_in,
    _version_source_in,
    _version_test,
)
from cppboot.generate.tooling import _create_github_repo, _git_init, _run_make_fmt
from cppboot.generate.web import (
    _web_demo_cmake,
    _web_demo_main_cpp,
    _web_shell_html,
    _web_test_cpp,
    _web_tests_cmake,
)
from cppboot.licenses import fetch_license_text, normalize_license_id
from cppboot.names import (
    to_android_package,
    to_macro_prefix,
    to_namespace,
    to_target_name,
    validate_project_name,
)
from cppboot.options import GenerateResult, ProjectOptions

logger = logging.getLogger(__name__)


def generate_project(options: ProjectOptions) -> GenerateResult:
    """Create the project directory and write all scaffold files."""
    name = validate_project_name(options.name)
    if options.build_system != "cmake":
        raise ValueError(
            f"unsupported build system {options.build_system!r}; only 'cmake' is available"
        )
    if options.with_android_ci and options.with_modules:
        raise ValueError(
            "--with-android-ci does not support --with-modules: the Android Gradle "
            "Plugin builds with CMake 3.22.1, which cannot compile C++20 modules "
            "(requires 3.28+)"
        )
    if options.with_ios_ci and options.with_modules:
        raise ValueError(
            "--with-ios-ci does not support --with-modules: the XCFramework build "
            "uses the Xcode generator, which does not support C++20 module "
            "dependency scanning, and packages the classic include/ header tree"
        )
    if options.with_web_ci and options.with_modules:
        raise ValueError(
            "--with-web-ci does not support --with-modules: C++20 module scanning "
            "is untested with the Emscripten toolchain, and the web package ships "
            "the classic include/ header tree"
        )

    license_id = normalize_license_id(options.license_id)
    project_dir = (options.root / name).resolve()
    if project_dir.exists():
        if any(project_dir.iterdir()):
            raise FileExistsError(
                f"project directory already exists and is not empty: {project_dir}"
            )
    else:
        project_dir.mkdir(parents=True)

    ctx = Context(
        name=name,
        namespace=to_namespace(name),
        target=to_target_name(name),
        macro=to_macro_prefix(name),
        android_package=to_android_package(name),
        project_dir=project_dir,
        license_id=license_id,
        with_modules=options.with_modules,
        shared_library=options.shared_library,
        with_android_ci=options.with_android_ci,
        with_ios_ci=options.with_ios_ci,
        with_web_ci=options.with_web_ci,
        with_vim=options.with_vim,
        with_ctags=options.with_ctags,
        with_vscode=options.with_vscode,
        with_codespaces=options.with_codespaces,
        with_github_actions=options.with_github_actions,
        year=str(_dt.date.today().year),
    )

    if options.with_modules:
        logger.info(
            "C++20 modules scaffold enabled: requires CMake 3.28+, Ninja, and a "
            "compiler with module dependency scanning (Clang 16+, GCC 14+, or "
            "MSVC 17.4+). AppleClang often lacks CMake module scanning support."
        )
    written: list[Path] = []

    def write(relpath: str, content: str) -> None:
        path = project_dir / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        written.append(path)
        logger.debug("wrote %s", path)

    def write_bytes(relpath: str, data: bytes) -> None:
        path = project_dir / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        written.append(path)
        logger.debug("wrote %s", path)

    def make_executable(relpath: str) -> None:
        path = project_dir / relpath
        path.chmod(path.stat().st_mode | 0o111)

    # Root files
    write("VERSION", _version_file())
    write("CMakeLists.txt", _root_cmake(ctx))
    write("Makefile", _makefile(ctx))
    write("build.bat", _build_bat(ctx))
    write("README.md", _readme(ctx))
    write("AGENTS.md", _agents_md(ctx))
    # Repo-local community health files override GitHub user/org defaults
    # (e.g. a personal .github repo with company-specific templates).
    if options.with_community_docs:
        write("CODE_OF_CONDUCT.md", _code_of_conduct_md())
        write("CONTRIBUTING.md", _contributing_md(ctx))
        write("SECURITY.md", _security_md(ctx))
    write(
        ".gitignore",
        _gitignore() + (_android_gitignore_extra() if ctx.with_android_ci else ""),
    )
    write(".gitattributes", _gitattributes())
    write(".clang-format", _clang_format())
    write(".clangd", _clangd())
    write("Doxyfile", _doxyfile(ctx))
    write("cmake/Dependencies.cmake", _dependencies_cmake(ctx))
    write("cmake/CompilerWarnings.cmake", _warnings_cmake())
    write("cmake/Sanitizers.cmake", _sanitizers_cmake())
    write(f"cmake/{ctx.name}Config.cmake.in", _package_config_cmake_in(ctx))
    # Version API is generated from VERSION via configure_file (single source).
    if ctx.with_modules:
        write("cmake/version.cppm.in", _version_module_in(ctx))
    else:
        write("cmake/version.hpp.in", _version_header_in(ctx))
        write("cmake/version.cpp.in", _version_source_in(ctx))
        # Keep the public include tree present for new components (version.hpp
        # is generated into the build tree, not checked into include/).
        write(f"include/{ctx.namespace}/.gitkeep", "")

    # Default library surface: version API + thin CLI with --version.
    write("src/CMakeLists.txt", _src_cmake(ctx))
    write("src/main.cpp", _main_cpp(ctx))
    write("src/version/CMakeLists.txt", _version_src_cmake(ctx))

    # Tests
    write("tests/CMakeLists.txt", _tests_cmake(ctx))
    write("tests/version/CMakeLists.txt", _version_tests_cmake(ctx))
    write("tests/version/version_test.cpp", _version_test(ctx))

    # Benchmarks
    write("benchmarks/CMakeLists.txt", _benchmarks_cmake(ctx))
    write("benchmarks/version/CMakeLists.txt", _version_bench_cmake(ctx))
    write("benchmarks/version/version_bench.cpp", _version_bench(ctx))

    if ctx.with_android_ci:
        # Gradle project: Prefab AAR library module + consumer test application.
        write("android/settings.gradle", _android_settings_gradle(ctx))
        write("android/build.gradle", _android_root_build_gradle(ctx))
        write("android/gradle.properties", _android_gradle_properties())
        write("android/gradlew", _gradlew())
        write("android/gradlew.bat", _gradlew_bat())
        write("android/gradle/wrapper/gradle-wrapper.properties", _gradle_wrapper_properties())
        write_bytes("android/gradle/wrapper/gradle-wrapper.jar", _gradle_wrapper_jar())
        write(f"android/{ctx.target}/build.gradle", _android_library_build_gradle(ctx))
        write(f"android/{ctx.target}/src/main/AndroidManifest.xml", _android_library_manifest())
        write("android/test-app/build.gradle", _android_test_app_build_gradle(ctx))
        write("android/test-app/src/main/AndroidManifest.xml", _android_test_app_manifest(ctx))
        java_dir = f"{ctx.android_package}.test".replace(".", "/")
        write(
            f"android/test-app/src/main/java/{java_dir}/TestActivity.java",
            _android_test_activity_java(ctx),
        )
        # Android-only CMake component and on-device test suite.
        write("src/android/CMakeLists.txt", _android_src_cmake(ctx))
        write("src/android/android_library.cpp", _android_shim_cpp(ctx))
        write("tests/android/CMakeLists.txt", _android_tests_cmake(ctx))
        write("tests/android/android_test.cpp", _android_test_cpp(ctx))
        write("scripts/run_android_tests.sh", _run_android_tests_sh(ctx))
        make_executable("android/gradlew")
        make_executable("scripts/run_android_tests.sh")
        logger.info(
            "wrote Android Prefab AAR scaffold under android/ (Gradle %s, AGP %s, NDK %s)",
            GRADLE_VERSION,
            AGP_VERSION,
            NDK_VERSION,
        )

    if ctx.with_ios_ci:
        # XCFramework build/verify scripts and the Simulator test application.
        write("scripts/build_ios_xcframework.sh", _build_ios_xcframework_sh(ctx))
        write("scripts/build_ios_test_apps.sh", _build_ios_test_apps_sh(ctx))
        write("scripts/verify_ios_xcframework.sh", _verify_ios_xcframework_sh(ctx))
        write("scripts/run_ios_tests.sh", _run_ios_tests_sh(ctx))
        write("tests/ios/CMakeLists.txt", _ios_tests_cmake(ctx))
        write("tests/ios/test_main.mm", _ios_test_mm(ctx))
        write("tests/ios/Info.plist.in", _ios_info_plist_in(ctx))
        for script in (
            "scripts/build_ios_xcframework.sh",
            "scripts/build_ios_test_apps.sh",
            "scripts/verify_ios_xcframework.sh",
            "scripts/run_ios_tests.sh",
        ):
            make_executable(script)
        logger.info("wrote iOS XCFramework scaffold under scripts/ and tests/ios/")

    if ctx.with_web_ci:
        # HTML5 canvas demo (game loop) plus browser-run wasm tests.
        write("src/web/CMakeLists.txt", _web_demo_cmake(ctx))
        write("src/web/main_web.cpp", _web_demo_main_cpp(ctx))
        write("src/web/shell.html", _web_shell_html(ctx))
        write("tests/web/CMakeLists.txt", _web_tests_cmake(ctx))
        write("tests/web/web_test.cpp", _web_test_cpp(ctx))
        logger.info("wrote web/Emscripten scaffold under src/web/ and tests/web/")

    if ctx.with_vim:
        write(".vimrc", _vimrc(ctx))

    if ctx.with_ctags:
        write(".ctags", _ctags_config())
        logger.info("wrote Universal Ctags config (.ctags); run: make tags")

    # CMakePresets are shared by local VS Code and GitHub Codespaces.
    if ctx.with_vscode or ctx.with_codespaces:
        write("CMakePresets.json", _cmake_presets(ctx))

    if ctx.with_vscode:
        write(".vscode/extensions.json", _vscode_extensions())
        write(".vscode/settings.json", _vscode_settings(ctx))
        write(".vscode/tasks.json", _vscode_tasks(ctx))
        write(".vscode/launch.json", _vscode_launch(ctx))
        logger.info("wrote VS Code config under .vscode/ and CMakePresets.json")

    if ctx.with_codespaces:
        write(".devcontainer/devcontainer.json", _devcontainer_json(ctx))
        write(".devcontainer/setup.sh", _devcontainer_setup_sh(ctx))
        setup_sh = project_dir / ".devcontainer" / "setup.sh"
        setup_sh.chmod(setup_sh.stat().st_mode | 0o111)
        logger.info("wrote GitHub Codespaces / Dev Container config under .devcontainer/")

    if ctx.with_github_actions:
        write(".github/workflows/ci.yml", _github_actions_workflow(ctx))
        write(".github/workflows/sanitizers.yml", _github_actions_sanitizers_workflow(ctx))
        write(".github/workflows/release.yml", _github_actions_release_workflow(ctx))
        if ctx.with_android_ci:
            write(".github/workflows/android.yml", _github_actions_android_workflow(ctx))
        if ctx.with_ios_ci:
            write(".github/workflows/ios.yml", _github_actions_ios_workflow(ctx))
        if ctx.with_web_ci:
            write(".github/workflows/web.yml", _github_actions_web_workflow(ctx))
        logger.info("wrote GitHub Actions workflows under .github/workflows/")

    year = ctx.year
    holder = name
    license_result = fetch_license_text(
        license_id,
        year=year,
        holder=holder,
        offline=options.offline_license,
    )
    write("LICENSE", license_result.text)
    logger.info(
        "license %s written from %s",
        license_result.license_id,
        license_result.source,
    )

    # Format before the initial commit so the tree is in a predictable state.
    formatted = False
    if options.with_fmt:
        formatted = _run_make_fmt(project_dir)
    git_ok = False
    if options.with_git:
        git_ok = _git_init(project_dir)
    github_ok = False
    if options.create_github:
        github_ok = _create_github_repo(project_dir, name)

    return GenerateResult(
        project_dir=project_dir,
        files_written=written,
        git_initialized=git_ok,
        github_created=github_ok,
        license_source=license_result.source,
        formatted=formatted,
    )
