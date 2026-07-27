cppboot is a program to make it easy to bootstrap a competent, professional-grade C++ project.

cppboot takes a single input, which is the output program name.
CLI arg: --name -n
If no value is provided, cppboot prompts the user for the name interactively.

cppboot should have other arguments:
--help -h
--version
--verbose -v
--license

Most behavior is self explanatory.
For --license, the value should be one of a selection of the most common licenses.
If absent, apache v2 should be the default.
At runtime, the script should download the license from somewhere authoritative, and write it to the root of the project as common convention.

cppboot is highly opinionated
cppboot assumes / requires your build system to be cmake.
We can add a --build-system flag to cppboot, but only cmake will be supported initially.
on bootstrap, cppboot creates a folder structure that is built to scale.
Every C++ needs directories for:
 - headers (directories should serve as a namespace_
 - source files
 - tests

cppboot should treat every project as a combination of a main / entrypoint, a library module (default static, with option for shared), and tests.

cppboot should include a trivial calc class which serves as the shared library layer
cppboot should include a unit test from google test
cppboot should include a performance test from google bench
cppboot should include a mock with google mock

while cppboot generates a cmake build, it should also include an idiomatic GNU makefile that essentially wraps the cmake build.

'make' should build everything in debug mode, with no optimization plus debug symbols
'make release' should build everything in release mode w/ optimization and strip debug symbols if possible

'make test' should invoke all unit tests
'make fmt' should invoke clang-format on all source files (cppboot should write .clang-format in Microsoft style)

'make clean' should clean the local build environment
'make doc' should generate doxygen documentation in a clean folder
To that point, the cppboot output source files should be in idiomatic doxygen format
The C++ code itself should follow the Google C++ style guide


The CLI should include an option to structure the project around modern C++ modules:
--with-modules

Without this flag, structure the project around C++ headers

CMake project should be cross platform friendly for Windows, macOS, and Linux.

cppboot should be written in python for now.

cppboot should git init the project by default

cppboot should offer to create an upstream git repo if possible (probably requires the gh client)

generally speaking, cppboot should prompt interactively for mandatory information

cppboot should follow solid principles
cppboot code should be very simple and direct - avoid syntactic sugar
follow idiomatic python convention for professional projects distributed on pypi

