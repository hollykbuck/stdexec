from conan import ConanFile
from conan.tools.build.cppstd import check_min_cppstd
from conan.tools.cmake import CMake, cmake_layout
from conan.tools.files import copy
from conan.tools.scm import Git

class StdexecPackage(ConanFile):
  name = "p2300"
  description = "std::execution"
  author = "Michał Dominiak, Lewis Baker, Lee Howes, Kirk Shoop, Michael Garland, Eric Niebler, Bryce Adelstein Lelbach"
  topics = ("WG21", "concurrency")
  homepage = "https://github.com/NVIDIA/stdexec"
  url = "https://github.com/NVIDIA/stdexec"
  license = "Apache 2.0"

  settings = "os", "arch", "compiler", "build_type"
  options = {
    # Legacy name for backward compatibility. Use parallel_scheduler instead.
    "system_context": [True, False],
    "parallel_scheduler": [True, False],
    "enable_asio": [True, False],
    "asio_implementation": ["boost", "standalone"],
  }
  default_options = {
    "system_context": False,
    "parallel_scheduler": False,
    "enable_asio": False,
    "asio_implementation": "boost",
  }
  exports_sources = (
    "include/*",
    "src/*",
    "test/*",
    "examples/*",
    "cmake/*",
    "CMakeLists.txt"
  )
  generators = "CMakeDeps", "CMakeToolchain"

  def configure(self):
    if self.options.system_context:
      self.options.parallel_scheduler = True
    if self.options.parallel_scheduler:
      self.package_type = "static-library"
    else:
      self.package_type = "header-library"

    if self.options.enable_asio and self.options.asio_implementation == "boost":
      self.options["boost"].without_cobalt = True

  def validate(self):
    check_min_cppstd(self, "20")

  def requirements(self):
    if self.options.enable_asio:
      if self.options.asio_implementation == "boost":
        self.requires("boost/1.91.0")
      elif self.options.asio_implementation == "standalone":
        self.requires("asio/1.31.0")

  def set_version(self):
    if not self.version:
      git = Git(self, self.recipe_folder)
      self.version = git.get_commit()

  def layout(self):
    cmake_layout(self)

  def build(self):
    tests = "OFF" if self.conf.get("tools.build:skip_test", default=False) else "ON"
    parallel_scheduler = "ON" if self.options.parallel_scheduler else "OFF"
    enable_asio = "ON" if self.options.enable_asio else "OFF"

    cmake = CMake(self)
    cmake.configure(variables={
      "STDEXEC_BUILD_TESTS": tests,
      "STDEXEC_BUILD_EXAMPLES": tests,
      "STDEXEC_BUILD_PARALLEL_SCHEDULER": parallel_scheduler,
      "STDEXEC_ENABLE_ASIO": enable_asio,
      "STDEXEC_ASIO_IMPLEMENTATION": str(self.options.asio_implementation),
    })
    cmake.build()
    cmake.test()

  def package_id(self):
    if not self.info.options.parallel_scheduler:
      # Clear settings because this package is header-only unless the compiled
      # parallel scheduler is enabled. Keep ASIO options because they change the
      # generated configuration header and exported targets.
      self.info.settings.clear()
      if not self.info.options.enable_asio:
        self.info.options.clear()

  def package(self):
    cmake = CMake(self)
    cmake.install()

  def package_info(self):
    self.cpp_info.set_property("cmake_file_name", "P2300")
    if self.options.parallel_scheduler or self.options.enable_asio:
      self.cpp_info.components["stdexec"].set_property("cmake_target_name", "STDEXEC::stdexec")
      self.cpp_info.components["stdexec"].set_property("cmake_target_aliases", ["P2300::P2300"])
      if self.options.parallel_scheduler:
        self.cpp_info.components["parallel_scheduler"].libs = ["parallel_scheduler"]
        self.cpp_info.components["parallel_scheduler"].set_property(
          "cmake_target_name", "STDEXEC::parallel_scheduler"
        )
        self.cpp_info.components["parallel_scheduler"].requires = ["stdexec"]
      if self.options.enable_asio:
        self.cpp_info.components["asioexec"].set_property(
          "cmake_target_name", "STDEXEC::asioexec"
        )
        self.cpp_info.components["asioexec"].requires = ["stdexec"]
        if self.options.asio_implementation == "boost":
          self.cpp_info.components["asioexec"].requires.append("boost::headers")
        elif self.options.asio_implementation == "standalone":
          self.cpp_info.components["asioexec"].requires.append("asio::asio")
    else:
      self.cpp_info.set_property("cmake_target_name", "P2300::P2300")
      self.cpp_info.set_property("cmake_target_aliases", ["STDEXEC::stdexec"])
