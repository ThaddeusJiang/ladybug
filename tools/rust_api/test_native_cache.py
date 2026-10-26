"""Build a tiny extension through the production CMake output policy."""

from pathlib import Path
import os
import subprocess
import tempfile
import unittest


ROOT = (Path(os.environ["LBUG_CMAKE_SOURCE"]).resolve().parent
        if "LBUG_CMAKE_SOURCE" in os.environ else Path(__file__).resolve().parents[2])
CMAKE = os.environ.get("CMAKE_BINARY", "cmake")


class ExtensionOutputTest(unittest.TestCase):
    def build_extension(self, rust_api):
        source = (ROOT / "extension/CMakeLists.txt").read_text()
        start = source.index("function(set_extension_properties ")
        function = source[start:source.index("endfunction()", start) + len("endfunction()")]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            src, build = root / "source", root / "output"
            src.mkdir()
            (src / "extension/fts").mkdir(parents=True)
            (src / "fixture.c").write_text("int fixture(void) { return 1; }\n")
            (src / "CMakeLists.txt").write_text(
                "cmake_minimum_required(VERSION 3.20)\nproject(cache_fixture C)\n"
                + f"set(LBUG_RUST_OUT_OF_SOURCE {'ON' if rust_api else 'OFF'})\n"
                + function
                + "\nadd_library(fixture STATIC fixture.c)\n"
                + "set_extension_properties(fixture fts_static fts)\n"
            )
            for command in [[CMAKE, "-S", str(src), "-B", str(build)],
                            [CMAKE, "--build", str(build), "--parallel", "2"]]:
                result = subprocess.run(command, text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            archive = "libfts_static.lbug_extension"
            if rust_api:
                self.assertEqual(len(list((build / "extension/fts/artifacts").rglob(archive))), 1)
                self.assertFalse((src / "extension/fts/build").exists())
            else:
                self.assertEqual(len(list((src / "extension/fts/build").rglob(archive))), 1)

    def test_preserves_each_explicit_compiler_launcher(self):
        source = (ROOT / "CMakeLists.txt").read_text()
        start = source.index("find_program(CCACHE_PROGRAM ccache)")
        block = source[start:source.index("set(INSTALL_LIB_DIR", start)]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "launchers.txt"
            script = root / "launchers.cmake"
            script.write_text(
                'set(CCACHE_PROGRAM "/fixture/sccache")\n'
                'set(CMAKE_C_COMPILER_LAUNCHER "/fixture/mbx-c")\n'
                'set(CMAKE_CXX_COMPILER_LAUNCHER "")\n'
                + block
                + f'file(WRITE "{output.as_posix()}" "${{CMAKE_C_COMPILER_LAUNCHER}}|${{CMAKE_CXX_COMPILER_LAUNCHER}}")\n'
            )
            result = subprocess.run([CMAKE, "-P", str(script)], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(output.read_text(), "/fixture/mbx-c|")

    def test_rust_build_does_not_write_a_watched_source_directory(self):
        self.build_extension(True)

    def test_other_builds_keep_the_existing_extension_location(self):
        self.build_extension(False)


if __name__ == "__main__":
    unittest.main()
