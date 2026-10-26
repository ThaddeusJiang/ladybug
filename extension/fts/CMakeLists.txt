# Rust links the extension into its library. Read the bundled dictionaries as
# source inputs instead of copying them into Cargo's watched extension tree.
if(LBUG_RUST_OUT_OF_SOURCE)
    add_compile_definitions(LBUG_JIEBA_DICT_DIRECTORY="${PROJECT_SOURCE_DIR}/third_party/cppjieba/dict")
endif()

include_directories(
        ${PROJECT_SOURCE_DIR}/src/include
        ${CMAKE_BINARY_DIR}/src/include
        src/include
        third_party/snowball/libstemmer
        ${PROJECT_SOURCE_DIR}/third_party/cppjieba/include
        ${PROJECT_SOURCE_DIR}/third_party/cppjieba/deps/limonp/include)

add_subdirectory(src/catalog)
add_subdirectory(src/function)
add_subdirectory(src/main)
add_subdirectory(test)
add_subdirectory(src/index)
add_subdirectory(src/utils)

add_subdirectory(third_party/snowball)

build_extension_lib(${BUILD_STATIC_EXTENSION} "fts")

target_link_libraries(lbug_${EXTENSION_LIB_NAME}_extension
        PRIVATE
        snowball
        re2
        cppjieba)

# Other build surfaces keep dictionaries next to the extension.
if(NOT LBUG_RUST_OUT_OF_SOURCE)
    add_custom_command(TARGET lbug_${EXTENSION_LIB_NAME}_extension POST_BUILD
            COMMAND ${CMAKE_COMMAND} -E copy_directory
            ${PROJECT_SOURCE_DIR}/third_party/cppjieba/dict
            ${PROJECT_SOURCE_DIR}/extension/fts/build/dict)
endif()
