"""Web/Emscripten scaffold templates for generated projects.

Generates the browser test page under ``tests/web/`` (GoogleTest compiled to
WebAssembly, run in headless Chrome via ``emrun``) and a game-development
oriented HTML5 canvas demo under ``src/web/``: an ``emscripten_set_main_loop``
game loop rendering to a fullscreen canvas through a custom shell page, with
commented hooks for asset preloading and SDL2. GitHub Actions workflow content
lives in :mod:`cppboot.generate.github_actions`.

Follows the platform-scaffold pattern established by
:mod:`cppboot.generate.android` and :mod:`cppboot.generate.ios`.
"""

from __future__ import annotations

from cppboot.generate.context import Context

_Context = Context

# Browser test runner knobs (upgrade deliberately).
EMRUN_TIMEOUT_SECONDS = 120
EMRUN_BROWSER = "google-chrome"


def _web_tests_cmake(ctx: _Context) -> str:
    return f"""\
# Browser-runtime tests: GoogleTest compiled to WebAssembly, run via emrun.
add_executable({ctx.target}_web_test web_test.cpp)
target_link_libraries({ctx.target}_web_test
  PRIVATE
    ${{PROJECT_NAME}}_lib
    GTest::gtest_main
)
set_target_properties({ctx.target}_web_test PROPERTIES SUFFIX ".html")
target_link_options({ctx.target}_web_test
  PRIVATE
    "--emrun"
    "SHELL:-sEXIT_RUNTIME=1"
    "SHELL:-sALLOW_MEMORY_GROWTH=1"
)
cppboot_set_project_warnings({ctx.target}_web_test)
"""


def _web_test_cpp(ctx: _Context) -> str:
    return f"""\
/**
 * @file web_test.cpp
 * @brief Browser-runtime tests for the WebAssembly build of {ctx.name}.
 *
 * Runs inside a real browser (see .github/workflows/web.yml and `emrun`);
 * the process exit code is reported back through --emrun / -sEXIT_RUNTIME=1.
 */

#include <emscripten.h>
#include <gtest/gtest.h>

#include <{ctx.namespace}/version.hpp>

#include <string>

TEST(WebVersion, IsNonEmpty)
{{
    EXPECT_FALSE({ctx.namespace}::Version().empty());
}}

TEST(WebVersion, MatchesComponentConstants)
{{
    const std::string expected = std::to_string({ctx.namespace}::kVersionMajor) + "." +
                                 std::to_string({ctx.namespace}::kVersionMinor) + "." +
                                 std::to_string({ctx.namespace}::kVersionPatch);
    EXPECT_EQ({ctx.namespace}::Version().substr(0, expected.size()), expected);
}}

TEST(WebRuntime, RunsInsideBrowserJavaScriptEnvironment)
{{
    // Proves the JS interop bridge works — the same bridge a game uses for
    // canvas/audio/input glue.
    const char *agent = emscripten_run_script_string(
        "typeof navigator !== 'undefined' ? navigator.userAgent : 'node'");
    ASSERT_NE(agent, nullptr);
    EXPECT_FALSE(std::string(agent).empty());
}}
"""


def _web_demo_cmake(ctx: _Context) -> str:
    return f"""\
# HTML5 canvas demo: a minimal Emscripten game loop around the project library.
# Built only for top-level web builds (option {ctx.macro}_BUILD_WEB_DEMO).
if(NOT {ctx.macro}_BUILD_WEB_DEMO)
  return()
endif()

add_executable({ctx.target}_web_demo main_web.cpp)
set_target_properties({ctx.target}_web_demo PROPERTIES
  OUTPUT_NAME {ctx.name}
  SUFFIX ".html"
)
target_link_libraries({ctx.target}_web_demo PRIVATE ${{PROJECT_NAME}}_lib)
target_link_options({ctx.target}_web_demo
  PRIVATE
    "SHELL:-sALLOW_MEMORY_GROWTH=1"
    "SHELL:-sUSE_WEBGL2=1"
    "SHELL:-sEXIT_RUNTIME=0"
    "--shell-file" "${{CMAKE_CURRENT_SOURCE_DIR}}/shell.html"
)
set_property(TARGET {ctx.target}_web_demo APPEND PROPERTY
  LINK_DEPENDS "${{CMAKE_CURRENT_SOURCE_DIR}}/shell.html"
)
# Game assets: uncomment to bundle a directory into the virtual filesystem
# (readable in C++ as /assets/...):
#   target_link_options({ctx.target}_web_demo PRIVATE
#     "SHELL:--preload-file ${{CMAKE_SOURCE_DIR}}/assets@/assets")
# SDL2 (input/audio/textures): add to BOTH compile and link options:
#   target_compile_options({ctx.target}_web_demo PRIVATE "SHELL:-sUSE_SDL=2")
#   target_link_options({ctx.target}_web_demo PRIVATE "SHELL:-sUSE_SDL=2")
cppboot_set_project_warnings({ctx.target}_web_demo)
"""


def _web_demo_main_cpp(ctx: _Context) -> str:
    return f"""\
/**
 * @file main_web.cpp
 * @brief HTML5 canvas demo: a minimal Emscripten game loop.
 *
 * Structure to keep as the game grows: per-frame state updates driven by a
 * real delta time, rendering separated from simulation, and the browser in
 * control of frame pacing via emscripten_set_main_loop (requestAnimationFrame).
 * Replace the EM_JS canvas-2D renderer with WebGL2/SDL2 calls as needed.
 */

#include <emscripten.h>
#include <emscripten/html5.h>

#include <{ctx.namespace}/version.hpp>

#include <string>

// Renders one frame through the canvas 2D context. EM_JS defines the function
// once in JavaScript; calls from C++ are ordinary function calls.
EM_JS(void, {ctx.target}_draw_frame, (double x, double y, double size, const char *hud), {{
    const canvas = document.getElementById('canvas');
    const dpr = window.devicePixelRatio || 1;
    const width = canvas.clientWidth * dpr;
    const height = canvas.clientHeight * dpr;
    if (canvas.width !== width || canvas.height !== height) {{
        canvas.width = width;
        canvas.height = height;
    }}
    const g = canvas.getContext('2d');
    g.fillStyle = '#101418';
    g.fillRect(0, 0, canvas.width, canvas.height);
    g.fillStyle = '#4fc3f7';
    g.fillRect(x * canvas.width, y * canvas.height, size * dpr, size * dpr);
    g.fillStyle = '#e0e0e0';
    g.font = `${{14 * dpr}}px monospace`;
    g.fillText(UTF8ToString(hud), 12 * dpr, 24 * dpr);
}});

namespace
{{

struct GameState
{{
    double x = 0.1;
    double y = 0.1;
    double vx = 0.25;  // canvas-widths per second
    double vy = 0.2;   // canvas-heights per second
    double last_ms = 0.0;
    double frames = 0.0;
    std::string hud;
}};

GameState g_state;

void Update(GameState &state, double dt)
{{
    state.x += state.vx * dt;
    state.y += state.vy * dt;
    if (state.x < 0.0 || state.x > 0.95)
    {{
        state.vx = -state.vx;
    }}
    if (state.y < 0.0 || state.y > 0.95)
    {{
        state.vy = -state.vy;
    }}
    state.frames += 1.0;
}}

void Frame()
{{
    const double now_ms = emscripten_get_now();
    double dt = (now_ms - g_state.last_ms) / 1000.0;
    if (g_state.last_ms == 0.0 || dt > 0.1)
    {{
        dt = 1.0 / 60.0;  // first frame / tab was backgrounded
    }}
    g_state.last_ms = now_ms;

    Update(g_state, dt);

    g_state.hud = std::string("{ctx.name} ") + std::string({ctx.namespace}::Version()) +
                  " — wasm game loop, frame " + std::to_string(static_cast<long>(g_state.frames));
    {ctx.target}_draw_frame(g_state.x, g_state.y, 48.0, g_state.hud.c_str());
}}

}} // namespace

int main()
{{
    // 0 fps == drive the loop with requestAnimationFrame (the right default
    // for games); the final `true` hands control to the browser.
    emscripten_set_main_loop(Frame, 0, true);
    return 0;
}}
"""


_SHELL_HTML = """\
<!doctype html>
<!-- Minimal game shell for Emscripten builds (--shell-file). The canvas fills
     the viewport; Module.status text shows load progress. Customize freely. -->
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, user-scalable=no">
  <title>@NAME@</title>
  <style>
    html, body {
      margin: 0;
      padding: 0;
      width: 100%;
      height: 100%;
      background: #101418;
      color: #e0e0e0;
      font-family: monospace;
      overflow: hidden;
    }
    #canvas {
      display: block;
      width: 100vw;
      height: 100vh;
      image-rendering: pixelated;
    }
    #status {
      position: absolute;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      font-size: 14px;
      pointer-events: none;
    }
  </style>
</head>
<body>
  <canvas id="canvas" oncontextmenu="event.preventDefault()" tabindex="-1"></canvas>
  <div id="status">loading @NAME@…</div>
  <script>
    var statusElement = document.getElementById('status');
    var Module = {
      canvas: document.getElementById('canvas'),
      setStatus: function (text) {
        statusElement.textContent = text;
        statusElement.style.display = text ? 'block' : 'none';
      },
      onRuntimeInitialized: function () {
        Module.setStatus('');
      }
    };
    Module.setStatus('loading @NAME@…');
  </script>
  {{{ SCRIPT }}}
</body>
</html>
"""


def _web_shell_html(ctx: _Context) -> str:
    return _SHELL_HTML.replace("@NAME@", ctx.name)
