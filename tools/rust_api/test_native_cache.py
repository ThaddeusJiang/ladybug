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
        fts = (ROOT / "extension/fts/CMakeLists.txt").read_text()
        definitions = fts[:fts.index("include_directories(")]
        post_build = fts[fts.index("# Other build surfaces"):]
        header = (ROOT / "extension/fts/src/include/function/fts_config.h").read_text()
        info_start = header.index("struct TokenizerInfo {")
        tokenizer_info = header[info_start:header.index("struct FTSConfig;", info_start)]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            src, build = root / "source", root / "output"
            src.mkdir()
            (src / "extension/fts").mkdir(parents=True)
            (src / "fixture.c").write_text("int fixture(void) { return 1; }\n")
            dictionaries = src / "third_party/cppjieba/dict"
            dictionaries.mkdir(parents=True)
            (dictionaries / "fixture.dict").write_text("dictionary-content")
            (src / "read_dict.cpp").write_text(
                '#include <fstream>\n#include <iostream>\n#include <string>\n'
                'namespace common { std::string stringFormat(const char*, const char* root) '
                '{ return std::string(root) + "/extension/fts/build/dict"; } }\n'
                'struct Tokenizer { static constexpr const char* DEFAULT_VALUE = "simple"; };\n'
                + tokenizer_info
                + '\nint main() { std::ifstream f(TokenizerInfo{}.jiebaDictDir + "/fixture.dict"); '
                'std::string value; std::getline(f, value); std::cout << value; return !f; }\n'
            )
            (src / "CMakeLists.txt").write_text(
                "cmake_minimum_required(VERSION 3.20)\nproject(cache_fixture C CXX)\n"
                + f"set(LBUG_RUST_OUT_OF_SOURCE {'ON' if rust_api else 'OFF'})\n"
                + definitions
                + function
                + '\nadd_compile_definitions(LBUG_ROOT_DIRECTORY="${PROJECT_SOURCE_DIR}")\n'
                + "set(EXTENSION_LIB_NAME fts)\n"
                + "add_library(lbug_fts_extension STATIC fixture.c)\n"
                + "set_extension_properties(lbug_fts_extension fts_static fts)\n"
                + post_build
                + "\nadd_executable(read_dict read_dict.cpp)\n"
            )
            for command in [[CMAKE, "-S", str(src), "-B", str(build)],
                            [CMAKE, "--build", str(build), "--parallel", "2"]]:
                result = subprocess.run(command, text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            binary = next(path for path in build.rglob("read_dict*")
                          if path.is_file() and path.name in {"read_dict", "read_dict.exe"})
            result = subprocess.run([str(binary)], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "dictionary-content")
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
