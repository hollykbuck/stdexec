import os
from conan import ConanFile
from conan.tools.build.cppstd import check_min_cppstd
from conan.tools.cmake import CMake, CMakeDeps, CMakeToolchain, cmake_layout
from conan.tools.files import copy, download, save
from conan.tools.scm import Git

# Versions / hashes used by rapids-cmake (rapids-cmake/cpm/detail/download.cmake)
_CPM_VERSION = "0.38.5"
_CPM_MD5 = "c98d14a13dfd1952e115979c095f6794"
_CPM_URL = ("https://github.com/cpm-cmake/CPM.cmake/releases/"
            f"download/v{_CPM_VERSION}/CPM.cmake")

# rapids-cmake archive (branch-24.02)
_RAPIDS_CMAKE_BRANCH = "branch-24.02"
_RAPIDS_CMAKE_SCRIPT_URL = ("https://raw.githubusercontent.com/rapidsai/"
                            f"rapids-cmake/{_RAPIDS_CMAKE_BRANCH}/RAPIDS.cmake")
_RAPIDS_CMAKE_ARCHIVE_URL = ("https://github.com/rapidsai/rapids-cmake/"
                             f"archive/refs/heads/{_RAPIDS_CMAKE_BRANCH}.zip")

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

  def _stage_rapids_cmake(self):
    """Download RAPIDS.cmake and patch it to use a local archive."""
    script_path = os.path.join(self.build_folder, "RAPIDS.cmake")
    if os.path.exists(script_path):
      return script_path

    archive_path = self._stage_rapids_cmake_archive()
    local_path = archive_path.replace("\\", "/")

    # Obtain raw RAPIDS.cmake – prefer a manual copy in the source tree.
    src_script = os.path.join(self.source_folder, "cmake", "RAPIDS.cmake")
    if os.path.exists(src_script):
      raw = open(src_script, "r").read()
    else:
      download(self, _RAPIDS_CMAKE_SCRIPT_URL, script_path + ".tmp")
      raw = open(script_path + ".tmp", "r").read()

    # Prepend our local path *before* the first `if(NOT rapids-cmake-url)`,
    # so that block becomes dead code and FetchContent uses the local archive.
    marker = "# Allow users to control the exact URL passed to FetchContent"
    override = (
      "# [conan override]\n"
      'set(rapids-cmake-url "' + local_path + '")\n'
    )
    raw = raw.replace(marker, override + marker)

    with open(script_path, "w") as f:
      f.write(raw)
    return script_path

  def _stage_rapids_cmake_archive(self):
    """Download rapids-cmake zip so cmake FetchContent can use a local file."""
    archive_dir = os.path.join(self.build_folder, "_rapids_cmake")
    os.makedirs(archive_dir, exist_ok=True)
    archive_path = os.path.join(archive_dir, "rapids-cmake.zip")
    if os.path.exists(archive_path):
      return archive_path

    src_archive = os.path.join(self.source_folder, "cmake", "rapids-cmake.zip")
    if os.path.exists(src_archive):
      copy(self, src_archive, archive_dir)
      return archive_path

    download(self, _RAPIDS_CMAKE_ARCHIVE_URL, archive_path)
    return archive_path

  def _stage_cpm(self):
    """Pre-download CPM.cmake so rapids_cpm_download() doesn't hit github.com."""
    dest_dir = os.path.join(self.build_folder, "cmake")
    os.makedirs(dest_dir, exist_ok=True)
    dest_path = os.path.join(dest_dir, f"CPM_{_CPM_VERSION}.cmake")
    if os.path.exists(dest_path):
      return dest_path

    src_cpm = os.path.join(self.source_folder, "cmake", f"CPM_{_CPM_VERSION}.cmake")
    if os.path.exists(src_cpm):
      copy(self, src_cpm, dest_dir)
      return dest_path

    download(self, _CPM_URL, dest_path)
    return dest_path

  def _stage_execution_bs(self):
    """Pre-download execution.bs (version source) to avoid CMake file(DOWNLOAD) failure."""
    dest_path = os.path.join(self.build_folder, "execution.bs")
    if os.path.exists(dest_path):
      return dest_path
    src_bs = os.path.join(self.source_folder, "cmake", "execution.bs")
    if os.path.exists(src_bs):
      copy(self, src_bs, self.build_folder)
      return dest_path
    download(
      self,
      "https://raw.githubusercontent.com/cplusplus/sender-receiver/main/execution.bs",
      dest_path,
    )
    return dest_path

  def _stage_icm(self):
    """Pre-download icm so CPM doesn't need network access."""
    icm_version = "1.5.0"
    icm_dir = os.path.join(self.build_folder, "_cpm_deps", "icm")
    stamp = os.path.join(icm_dir, ".conan_staged")
    if os.path.exists(stamp):
      return icm_dir

    archive_name = f"v{icm_version}.zip"
    archive_path = os.path.join(self.build_folder, "_cpm_deps", archive_name)
    os.makedirs(os.path.dirname(archive_path), exist_ok=True)

    if not os.path.exists(archive_path):
      src_archive = os.path.join(
        self.source_folder, "cmake", archive_name
      )
      if os.path.exists(src_archive):
        copy(self, src_archive, os.path.dirname(archive_path))
      else:
        url = (f"https://github.com/iboB/icm/archive/refs/tags/"
               f"{archive_name}")
        download(self, url, archive_path)

    if not os.path.exists(icm_dir):
      import zipfile
      with zipfile.ZipFile(archive_path, "r") as zf:
        top_level = {p.split("/")[0] for p in zf.namelist()}
        zf.extractall(icm_dir)
        for d in top_level:
          src = os.path.join(icm_dir, d)
          if os.path.isdir(src) and src != icm_dir:
            for item in os.listdir(src):
              os.rename(os.path.join(src, item), os.path.join(icm_dir, item))
            os.rmdir(src)

    patch_path = os.path.join(self.source_folder, "cmake", "cpm", "patches",
                              "icm", "regex-build-error.diff")
    if os.path.exists(patch_path):
      import subprocess
      try:
        subprocess.run(
          ["git", "apply", "--directory=" + icm_dir.replace("\\", "/"),
           patch_path.replace("\\", "/")],
          cwd=icm_dir, capture_output=True, timeout=30,
        )
      except Exception:
        pass

    with open(stamp, "w") as f:
      f.write("staged")
    return icm_dir

  def _stage_catch2(self):
    """Pre-download Catch2 so CPM doesn't need network access."""
    catch2_version = "3.14.0"
    catch2_dir = os.path.join(self.build_folder, "_cpm_deps", "catch2")
    stamp = os.path.join(catch2_dir, ".conan_staged")
    if os.path.exists(stamp):
      return catch2_dir

    archive_name = f"v{catch2_version}.zip"
    archive_path = os.path.join(self.build_folder, "_cpm_deps", archive_name)
    os.makedirs(os.path.dirname(archive_path), exist_ok=True)

    if not os.path.exists(archive_path):
      src_archive = os.path.join(self.source_folder, "cmake", archive_name)
      if os.path.exists(src_archive):
        copy(self, src_archive, os.path.dirname(archive_path))
      else:
        url = (f"https://github.com/catchorg/Catch2/archive/refs/tags/"
               f"{archive_name}")
        download(self, url, archive_path)

    if not os.path.exists(catch2_dir):
      import zipfile
      with zipfile.ZipFile(archive_path, "r") as zf:
        top_level = {p.split("/")[0] for p in zf.namelist()}
        zf.extractall(catch2_dir)
        for d in top_level:
          src = os.path.join(catch2_dir, d)
          if os.path.isdir(src) and src != catch2_dir:
            for item in os.listdir(src):
              os.rename(os.path.join(src, item), os.path.join(catch2_dir, item))
            os.rmdir(src)

    with open(stamp, "w") as f:
      f.write("staged")
    return catch2_dir

  def generate(self):
    if self.options.parallel_scheduler:
      self._stage_rapids_cmake()
      self._stage_cpm()
      self._stage_execution_bs()
      icm_dir = self._stage_icm()
      catch2_dir = self._stage_catch2()

    tc = CMakeToolchain(self)
    tc.user_presets_path = False
    if self.options.parallel_scheduler:
      tc.variables["CPM_icm_SOURCE"] = icm_dir.replace("\\", "/")
      tc.variables["CPM_Catch2_SOURCE"] = catch2_dir.replace("\\", "/")
    tc.generate()
    deps = CMakeDeps(self)
    deps.generate()

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

    flags = []
    if self.settings.compiler == "msvc":
      flags = ["/Zc:__cplusplus", "/Zc:preprocessor", "/Zc:externConstexpr", "/bigobj"]
    elif self.settings.compiler == "gcc":
      flags = ["-fcoroutines"]

    if self.options.parallel_scheduler or self.options.enable_asio:
      self.cpp_info.components["stdexec"].set_property("cmake_target_name", "STDEXEC::stdexec")
      self.cpp_info.components["stdexec"].set_property("cmake_target_aliases", ["P2300::P2300"])
      self.cpp_info.components["stdexec"].cxxflags.extend(flags)
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
      self.cpp_info.cxxflags.extend(flags)
