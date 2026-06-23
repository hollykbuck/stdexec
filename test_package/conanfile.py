from conan import ConanFile
from conan.tools.cmake import CMake, CMakeDeps, CMakeToolchain, cmake_layout
from conan.tools.build import can_run

class StdexecTestPackage(ConanFile):
  settings = "os", "arch", "compiler", "build_type"

  def requirements(self):
    self.requires(self.tested_reference_str)

  def generate(self):
    tc = CMakeToolchain(self)
    tc.user_presets_path = False
    tc.generate()
    deps = CMakeDeps(self)
    deps.generate()

  def build(self):
    cmake = CMake(self)
    cmake.configure()
    cmake.build()
    cmake.test()

  def layout(self):
    cmake_layout(self)

  def test(self):
    if can_run(self):
      CMake(self).test()
