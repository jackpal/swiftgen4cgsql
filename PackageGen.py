#!/usr/bin/env python3

import io
import json
import os
import shutil
import subprocess
import sys
from argparse import ArgumentParser
from pathlib import Path


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def parse_args():
    parser = ArgumentParser()
    parser.add_argument("-c", "--cql_compiler", dest="cql_compiler_path",
                        help="Path to the CQL compiler.", metavar="PATH", required=True)
    parser.add_argument("-d", "--cgsql_sources", dest="cgsql_sources_dir",
                        help="Read CG-SQL runtime sources from this directory.", metavar="DIR", required=True)
    parser.add_argument("-i", "--in", dest="file_sql",
                        help="Read cg-sql input from this file", metavar="FILE", required=True)
    parser.add_argument("-o", "--out", dest="out_dir",
                        help="Directory to generate code to", metavar="DIR",
                        default="out")
    parser.add_argument("-p", "--package_name",
                        dest="package_name", metavar="NAME",
                        help="Swift Package Name", required=True)
    parser.add_argument("-s", "--swift-generator", dest="swift_generator_path",
                        help="Path to the Swift code generator.", metavar="PATH", required=True)
    parser.add_argument("-t", "--test",
                        action='append',
                        dest="test_files", metavar="FILE",
                        help="Swift Package unit test file. Can be supplied multiple times.")
    parser.add_argument("-v", "--verbose",
                        action="store_true", dest="verbose", default=False,
                        help="print verbose status messages to stdout")
    args = parser.parse_args()
    return args


ARGS = parse_args()


def cql_gen_c(cql_compiler_path, file_sql, out_dir):
    if ARGS.verbose:
        eprint(f'Generating C')

    file_stem = file_sql.stem

    file_h_name = f"{file_stem}.h"
    file_c_name = f"{file_stem}.c"

    file_h = out_dir / file_h_name
    file_c = out_dir / file_c_name

    absolute_file_sql = file_sql.resolve(True)

    old_cwd = os.getcwd()

    try:
        os.chdir(out_dir)
        result = subprocess.run([cql_compiler_path, "--in", absolute_file_sql,
                                 "--cg", file_h_name, file_c_name, '--cqlrt', 'cqlrt_cf.h'])
        if result.returncode != 0:
            raise ValueError(
                f'Could not generate c code from {file_sql}. Return code {result.returncode}')
    finally:
        os.chdir(old_cwd)

    return (file_h, file_c)


def cql_gen_objc(cql_compiler_path, file_sql, out_dir):
    if ARGS.verbose:
        eprint(f'Generating Obj-C')

    file_stem = file_sql.stem

    file_h_name = f"{file_stem}.h"
    file_objc_h_name = f"{file_stem}_objc.h"

    file_h = out_dir / file_h_name
    file_objc_h = out_dir / file_objc_h_name

    result = subprocess.run([cql_compiler_path, "--in", file_sql,
                             "--cg", file_objc_h, '--rt', 'objc_mit', '--objc_c_include_path',  file_h_name, '--cqlrt', 'cqlrt_cf.h'])
    if result.returncode != 0:
        raise ValueError(
            f'Could not generate objc code from {file_sql}. Return code {result.returncode}')

    return (file_objc_h)


def cql_gen_json_schema(cql_compiler_path, file_sql, out_dir):
    if ARGS.verbose:
        eprint(f'Generating json')

    file_stem = file_sql.stem
    file_json = out_dir / (file_stem + ".json")

    result = subprocess.run([cql_compiler_path, "--in", file_sql, "--rt",
                             "json_schema", "--cg", file_json])
    if result.returncode != 0:
        raise ValueError(
            f'Could not generate c code from {file_sql}. Return code {result.returncode}')

    return file_json


def parse_json_schema(file_json):
    if ARGS.verbose:
        eprint(f'Parsing json schema')

    with open(file_json) as f:
        text = f.read()
    return json.loads(text)


def gen_swift_package(package_name, out_dir):
    old_cwd = os.getcwd()
    try:
        os.chdir(out_dir)
        Path(package_name).mkdir(parents=True, exist_ok=True)
        os.chdir(package_name)
        subprocess.run(["swift", "package", "init"])
        return (Path(out_dir) / package_name)
    finally:
        os.chdir(old_cwd)


def update_package_swift_file(package_name, package_dir, c_lib_name, generate_test_target):
    if ARGS.verbose:
        eprint(f'update_package_swift_file {package_name} {c_lib_name}')
    package_file_path = Path(package_dir) / "Package.swift"
    package_file_contents = package_file_path.read_text().split("\n")
    out = []

    def find_target_dependencies(target_keyword, package_name):
        for i, line in enumerate(package_file_contents):
            if line.strip().startswith(target_keyword):
                if i+2 < len(package_file_contents):
                    next_line = package_file_contents[i+1]
                    if next_line.strip().startswith(f'name: \"{package_name}\",'):
                        dep_line = package_file_contents[i+2]
                        if dep_line.strip().startswith('dependencies: ['):
                            return i+2
        return None
    splice_index = find_target_dependencies(".target", package_name)
    if splice_index:
        package_file_contents[splice_index] = package_file_contents[splice_index].replace(
            "[])", f"[\"{c_lib_name}\"]")
        package_file_contents.insert(
            splice_index+1, f"            cSettings: [.define(\"CQL_EMIT_OBJC_INTERFACES\")]),")
        package_file_contents.insert(splice_index+2, f"        .target(")
        package_file_contents.insert(
            splice_index+3, f"            name: \"{c_lib_name}\",")
        package_file_contents.insert(
            splice_index+4, f"            dependencies: [],")
        package_file_contents.insert(
            splice_index+5, f"            // cqlrt_common.c is included inside cqlrt_cf.c")
        package_file_contents.insert(
            splice_index+6, f"            exclude: [\"cqlrt_common.c\"],")
        # Define CQL_EMIT_OBJC_INTERFACES so that Swift can import the result set Obj-C class.
        package_file_contents.insert(
            splice_index+7, f"            cSettings: [.define(\"CQL_EMIT_OBJC_INTERFACES\")]),")
    else:
        raise f"Could not splice target {package_name}."

    if generate_test_target:
        splice_index = find_target_dependencies(
            ".testTarget", f"{package_name}Tests")
        if splice_index:
            package_file_contents[splice_index] = package_file_contents[splice_index].replace(
                "]),", "],")
            package_file_contents.insert(
                splice_index+1, f"            cSettings: [.define(\"CQL_EMIT_OBJC_INTERFACES\")]),")
        else:
            raise f"Could not splice testTarget {package_name}."

    package_file_path.write_text('\n'.join(package_file_contents))


def make_c_lib(package_name, package_dir, cql_sources, file_h, file_c, file_objc_h, generate_test_target):
    if ARGS.verbose:
        eprint(f'make_c_lib {package_name}')

    c_lib_name = f"lib{package_name}"
    c_lib_path = Path(package_dir) / "Sources" / c_lib_name
    c_lib_path.mkdir()
    c_lib_include_path = c_lib_path / "include"
    c_lib_include_path.mkdir()
    cql_sources = Path(cql_sources)

    def cp(src, to_dir):
        name = Path(src).name
        dest = Path(to_dir) / name
        if ARGS.verbose:
            eprint("copying ", src, " to ", dest)
        shutil.copy(src, dest)
    copy_dict = {
        c_lib_path: [
            file_c,
            cql_sources / "cqlrt_common.c",
            cql_sources / "cqlrt_cf" / "cqlholder.m",
            cql_sources / "cqlrt_cf" / "cqlrt_cf.c"
        ],
        c_lib_include_path: [
            file_h,
            file_objc_h,
            cql_sources / "cqlrt_common.h",
            cql_sources / "cqlrt_cf" / "cqlrt_cf.h"
        ]
    }
    for dest, files in copy_dict.items():
        for file in files:
            cp(file, dest)
    update_package_swift_file(
        package_name, package_dir, c_lib_name, generate_test_target)
    return (c_lib_name)


def gen_swift_target(swift_code_generator_path, json_schema_path, c_lib_name, output_file_path):
    if ARGS.verbose:
        eprint(f'Generating swift code {output_file_path}')
    subprocess.run([swift_code_generator_path, "--input", json_schema_path,
                   "--module", c_lib_name, "--output", output_file_path])


def gen_swift_test_target(package_name, package_dir, test_files):
    if ARGS.verbose:
        eprint(
            f'Generating swift test target for {package_name} files {test_files}')
    for test_file in test_files:
        test_name = f"{package_name}Tests"
        test_file_text = Path(test_file).read_text()
        swift_test_file = Path(package_dir) / "Tests" / \
            test_name / f"{test_name}.swift"
        swift_test_file.write_text(test_file_text)


def gen_read_me(package_name, package_dir):
    if ARGS.verbose:
        eprint(f'Generating README.md for {package_name}')
    out = io.StringIO()
    out.write(f'# {package_name}\n')
    out.write('\n')
    out.write('A set of stored procedures. Generated by gen.py.\n')

    read_me_file = Path(package_dir) / "README.md"
    read_me_file.write_text(out.getvalue())


def gen_project(swift_code_generator_path, cql_compiler_path, cgsql_sources_dir, file_sql, package_name, out_dir, test_files):
    if ARGS.verbose:
        eprint(f'Generating project {out_dir}')
    # Generate the schema first because it can use relative paths,
    # so the cql error messages are nice and short.
    file_json_schema = cql_gen_json_schema(
        cql_compiler_path, file_sql, out_dir)
    file_h, file_c = cql_gen_c(cql_compiler_path, file_sql, out_dir)
    file_objc_h = cql_gen_objc(cql_compiler_path, file_sql, out_dir)
    json_schema = parse_json_schema(file_json_schema)
    if ARGS.verbose:
        eprint(json.dumps(json_schema, indent=4, sort_keys=True))
    package_dir = gen_swift_package(package_name, out_dir)
    generate_test_target = len(test_files) > 0
    c_lib_name = make_c_lib(package_name, package_dir,
                            cgsql_sources_dir, file_h, file_c, file_objc_h, generate_test_target)
    swift_file = Path(package_dir) / "Sources" / \
        package_name / f"{package_name}.swift"
    gen_swift_target(swift_code_generator_path,
                     file_json_schema, c_lib_name, swift_file)
    gen_swift_test_target(package_name, package_dir, test_files)
    gen_read_me(package_name, package_dir)


def initialize_output_dir(out_dir):
    if ARGS.verbose:
        eprint(f'Initializing output directory {out_dir}')
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)


def usage(str):
    eprint(str)
    eprint("Use argument --help for detailed help.")
    exit(1)


def main():
    if ARGS.verbose:
        eprint(ARGS)

    swift_code_generator_path = Path(ARGS.swift_generator_path).resolve(True)
    cql_compiler_path = Path(ARGS.cql_compiler_path).resolve(True)
    cgsql_sources_dir = Path(ARGS.cgsql_sources_dir).resolve(True)
    if not cgsql_sources_dir.is_dir():
        usage(
            f'CG-SQL sources directory does not exist: {ARGS.cgsql_sources_dir}')
    file_sql = Path(ARGS.file_sql)
    if not file_sql.is_file():
        usage(f'sql input is not a file: {ARGS.file_sql}')
    out_dir = Path(ARGS.out_dir).resolve(False)
    package_name = ARGS.package_name
    test_files = [] if ARGS.test_files is None else ARGS.test_files

    initialize_output_dir(out_dir)
    gen_project(swift_code_generator_path, cql_compiler_path,
                cgsql_sources_dir, file_sql, package_name, out_dir, test_files)


if __name__ == "__main__":
    main()
