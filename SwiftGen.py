#!/usr/bin/env python3

import io
import json
import os
import re
import shutil
import subprocess
import sys
from argparse import ArgumentParser
from pathlib import Path

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

def parse_args():
    parser = ArgumentParser()
    parser.add_argument("-c", "--cql_compiler", dest="cql_compiler_path", help="Path to the CQL compiler.", metavar="PATH", required=True)
    parser.add_argument("-d", "--cgsql_sources", dest="cgsql_sources_dir", help="Read CG-SQL runtime sources from this directory.", metavar="DIR", required=True)
    parser.add_argument("-i", "--in", dest="file_sql",
                        help="Read cg-sql input from this file", metavar="FILE", required=True)
    parser.add_argument("-o", "--out", dest="out_dir",
                        help="Directory to generate code to", metavar="DIR",
                        default="out")
    parser.add_argument("-p", "--package_name",
                        dest="package_name", metavar="NAME",
                        help="Swift Package Name", required=True)
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


def cql_gen_c(file_sql, out_dir):
    if ARGS.verbose:
        print(f'Generating C')

    file_stem = file_sql.stem

    file_h_name = f"{file_stem}.h"
    file_c_name = f"{file_stem}.c"

    file_h = out_dir / file_h_name
    file_c = out_dir / file_c_name

    global cql_compiler_path

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


def cql_gen_objc(file_sql, out_dir):
    if ARGS.verbose:
        print(f'Generating Obj-C')

    file_stem = file_sql.stem

    file_h_name = f"{file_stem}.h"
    file_objc_h_name = f"{file_stem}_objc.h"

    file_h = out_dir / file_h_name
    file_objc_h = out_dir / file_objc_h_name

    global cql_compiler_path

    result = subprocess.run([cql_compiler_path, "--in", file_sql,
                                "--cg", file_objc_h, '--rt', 'objc_mit', '--objc_c_include_path',  file_h_name, '--cqlrt', 'cqlrt_cf.h'])
    if result.returncode != 0:
        raise ValueError(
            f'Could not generate objc code from {file_sql}. Return code {result.returncode}')

    return (file_objc_h)


def cql_gen_json_schema(file_sql, out_dir):
    if ARGS.verbose:
        print(f'Generating json')

    file_stem = file_sql.stem
    file_json = out_dir / (file_stem + ".json")
    
    global cql_compiler_path

    result = subprocess.run([cql_compiler_path, "--in", file_sql, "--rt",
                             "json_schema", "--cg", file_json])
    if result.returncode != 0:
        raise ValueError(
            f'Could not generate c code from {file_sql}. Return code {result.returncode}')

    return file_json


def parse_json_schema(file_json):
    if ARGS.verbose:
        print(f'Parsing json schema')

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


def get_fetcher_decls(file_c, json_schema):
    lines = Path(file_c).read_text().split('\n')

    def is_fetcher_decl(line):
        return line.startswith("extern CQL_WARN_UNUSED cql_code ") and "_result_stmt" in line
    return [line for line in lines if is_fetcher_decl(line)]


def update_package_swift_file(package_name, package_dir, c_lib_name, generate_test_target):
    if ARGS.verbose:
        print(f'update_package_swift_file {package_name} {c_lib_name}')
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
        print(f'make_c_lib {package_name}')

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
            print("copying ", src, " to ", dest)
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
    update_package_swift_file(package_name, package_dir, c_lib_name, generate_test_target)
    return (c_lib_name)


def snake_case_to_camel_case(c_name, capitalize=False):
    start = 0 if capitalize else 1

    def capitalize(s):
        if len(s) == 0:
            return s
        c = s[0]
        C = c.capitalize()
        return C + s[1:]

    parts = c_name.split('_')
    for i in range(start, len(parts)):
        parts[i] = capitalize(parts[i])
    return ''.join(parts)


def swift_name(c_name, capitalize=False):
    return snake_case_to_camel_case(c_name, capitalize)


NULLABLE_TYPE_STRUCT = {
    'bool': 'cql_nullable_bool',
    'integer': 'cql_nullable_int32',
    'long': 'cql_nullable_int64',
    'real': 'cql_nullable_double',
}

NULLABLE_TYPE_ZERO = {
    'bool': 'false',
    'integer': '0',
    'long': '0',
    'real': '0.0',
}

PRIMITIVE_TYPE_TO_C_TYPE = {
    'bool': 'cql_bool',
    'integer': 'cql_int32',
    'long': 'cql_int64',
    'real': 'cql_double',
}


def cast_primitive_type_to_c_type(ty, swift_name):
    return f"{PRIMITIVE_TYPE_TO_C_TYPE[ty]}({swift_name})"


def initialize_nullable_primitive_type(ty, swift_name):
    nullable_type_struct = NULLABLE_TYPE_STRUCT[ty]
    nullable_type_zero = NULLABLE_TYPE_ZERO[ty]
    value = cast_primitive_type_to_c_type(
        ty, f"({swift_name} ?? {nullable_type_zero})")
    code = f"    let _1_{swift_name} = {nullable_type_struct}(is_null:"
    code += f"DarwinBoolean({swift_name} == nil), value:{value})\n"
    return code


class Arg:
    def __init__(self, arg):
        self.arg = arg
        self.local_swift_name = self.public_swift_name()

    def is_nullable(self):
        return self.arg['isNotNull'] == 0

    def is_out_or_in_out(self):
        if 'binding' in self.arg:
            binding = self.arg['binding']
            return binding in ['inout', 'out']
        return False

    def swift_arg_declaration(self):
        arg_type = self.swift_type()
        if self.is_out_or_in_out():
            if self.arg['type'] == 'object':
                arg_type = f'Unmanaged<AnyObject>?'
            arg_type = f'inout {arg_type}'
        local_name_decl = ''
        public_swift_name = self.public_swift_name()
        local_swift_name = self.swift_name()
        if public_swift_name != local_swift_name:
            local_name_decl = f' {local_swift_name}'
        return f"{self.public_swift_name()}{local_name_decl}: {arg_type}"

    def c_arg(self):
        def base_arg():
            ty = self.arg['type']
            swift_name = self.swift_name()
            opt_q = '?' if self.is_nullable() else ''
            if ty == 'text':
                return f"{swift_name} as NSString{opt_q}"
            elif ty == 'blob':
                return f"{swift_name} as NSData{opt_q}"
            elif ty == 'object':
                return swift_name
            elif not self.is_nullable():
                return swift_name
            else:
                return f"_1_{swift_name}"
        opt_binding = '&' if self.is_out_or_in_out() else ''
        return f'{opt_binding}{base_arg()}'

    def prepare_c_arg(self):
        ty = self.arg['type']
        swift_name = self.swift_name()
        c_arg = self.c_arg()
        if self.is_nullable():
            if ty in ['text', 'blob', 'object']:
                return ""
            else:
                return initialize_nullable_primitive_type(ty, swift_name)
        else:
            return ""

    def c_name(self):
        return self.arg['name']

    def swift_name(self):
        return self.local_swift_name

    def public_swift_name(self):
        return snake_case_to_camel_case(self.c_name())

    def swift_type(self):
        ty = self.arg['type']
        map = {
            'text': 'String',
            'integer': 'Int32',
            'long': "Int64",
            'bool': 'Bool',
            'real': 'Double',
            'blob': 'Data',
            'object': 'AnyObject',
        }
        if ty in map:
            ty = map[ty]
        if self.is_nullable():
            ty += '?'
        return ty


def lookup(dict, key, default=0):
    if key in dict:
        return dict[key]
    return default


def gen_swift_query_projection_column_getter(out, c_query_name, column, has_row):
    col = Arg(column)
    if ARGS.verbose:
        print(
            f'Generating swift query projection column getter {col.swift_name()} for {c_query_name}')

    out.write(f'public var {col.swift_arg_declaration()} {{\n')
    ty = column['type']
    row_arg = ', row' if has_row else ''
    result_set = 'resultSet.result_set' if has_row else 'result_set'
    if col.is_nullable():
        if ty == 'text':
            out.write(
                f'    CGS_{c_query_name}_get_{col.c_name()}({result_set}{row_arg}) as String?\n')
        elif ty == 'blob':
            out.write(
                f'    CGS_{c_query_name}_get_{col.c_name()}({result_set}{row_arg}) as Data?\n')
        else:
            # Use C API instead of Objective-C API to avoid creating
            # NSNumbers.
            out.write(
                f'    if {c_query_name}_get_{col.c_name()}_is_null({c_query_name}_from_CGS_{c_query_name}({result_set}).takeUnretainedValue(){row_arg}) {{\n')
            out.write('        return nil\n')
            out.write('     }\n')
            out.write(
                f'    return {c_query_name}_get_{col.c_name()}_value({c_query_name}_from_CGS_{c_query_name}({result_set}).takeUnretainedValue(){row_arg})\n')
    else:
        out.write(
            f'    CGS_{c_query_name}_get_{col.c_name()}({result_set}{row_arg})\n')
    out.write('}\n')


def gen_swift_fetcher_init(out, query, single_result):
    c_query_name = query["name"]
    temp = io.StringIO()
    init_proc = query.copy()
    del init_proc["projection"]
    gen_swift_simple_proc(temp, init_proc)
    query_proc = temp.getvalue().strip().split('\n')
    # Format is:
    # public func SWIFT_NAME(db: OpaquePointerSWIFT_ARGS) throws {
    # try check(C_NAME(db)C_ARGS)
    # }
    #
    # Transform to:
    #     public init[1](db: OpaquePointerSWIFT_ARGS) throws {
    #       var result_set_ref: Unmanaged<C_NAME_result_set_ref>?
    #       try check(C_NAME_fetch_results(db, &result_set_refC_ARGS))
    #       result_set = CGS_C_NAME_from_C_NAME(result_set_ref!.takeUnretainedValue())
    #       cql_release(result_set_ref!.takeUnretainedValue()
    #       [2]if CGS_C_NAME_get_value(result_set) == 0 { return nil }
    #     }
    #
    # [1] is '?' if single_result
    # [2] only present if single_result_set

    q = '?' if single_result else ''
    query_proc[0] = query_proc[0].replace(
        f'func {swift_name(c_query_name)}', f'init{q}')
    call_line = len(query_proc)-2
    query_proc.insert(
        call_line, f'    var result_set_ref: Unmanaged<{c_query_name}_result_set_ref>?\n')
    call_line += 1

    if (not "usesDatabase" in query) or query["usesDatabase"]:
        query_proc[call_line] = query_proc[call_line].replace(
            '(db', '_fetch_results(db, &result_set_ref')
    else:
        # Complicated by there possibly being no arguments
        m = re.fullmatch('(.*)\((.*)\)(.*)', query_proc[call_line])
        if m:
            prefix, args, suffix = m.group(1), m.group(2), m.group(3)
            prefix += '_fetch_results'
            if len(args) == 0:
                args = '&result_set_ref'
            else:
                args = '&result_set_ref,' + args
            query_proc[call_line] = prefix + '(' + args + ')' + suffix
        else:
            raise ValueError(
                f'Could not generate swift initializer for query {c_query_name}')

    query_proc.insert(
        call_line+1, f'    result_set = CGS_{c_query_name}_from_{c_query_name}(result_set_ref!.takeUnretainedValue())')
    query_proc.insert(
        call_line+2, '    cql_release(result_set_ref!.takeUnretainedValue())')
    if single_result:
        query_proc.insert(
            call_line+3, f'    if CGS_{c_query_name}_get_value(result_set) == 0 {{ return nil }}')

    query_proc = [f'    {line}\n' for line in query_proc]
    out.write(''.join(query_proc))


def gen_swift_query(out, query):
    c_query_name = query["name"]
    swift_query_name = swift_name(c_query_name, True)

    if ARGS.verbose:
        print(f'Generating swift query {swift_query_name} for {c_query_name}')

    if lookup(query, "hasOutResult"):
        gen_swift_single_result_query(out, query)
    else:
        gen_swift_multi_result_query(out, query)


def indent_text(text, indent_spaces):
    indent_chars = ' ' * indent_spaces
    return '\n'.join([indent_chars + line for line in text.split('\n')])


def gen_projection_getters(out, query, use_row):
    c_query_name = query["name"]
    temp = io.StringIO()
    for column in query["projection"]:
        gen_swift_query_projection_column_getter(
            temp, c_query_name, column, use_row)
    indent_count = 8 if use_row else 4
    out.write(indent_text(temp.getvalue(), indent_count))


def gen_swift_single_result_query(out, query):
    c_query_name = query["name"]
    swift_query_name = swift_name(c_query_name, True)

    out.write(f'public struct {swift_query_name} : Hashable {{\n')

    gen_projection_getters(out, query, False)

    out.write('\n')

    out.write('    // Hashable\n')
    out.write(
        f'    public static func == (lhs: {swift_query_name}, rhs: {swift_query_name}) -> Bool {{\n')
    out.write(
        f'        CGS_{c_query_name}_equal(lhs.result_set,\n')
    out.write(
        '            rhs.result_set)\n')
    out.write('    }\n')
    out.write('\n')
    out.write('    public func hash(into hasher: inout Hasher) {\n')
    out.write(
        f'        hasher.combine(CGS_{c_query_name}_hash(result_set))\n')
    out.write('    }\n')
    out.write('\n')

    out.write(
        f'    private var result_set: CGS_{c_query_name}!\n')

    out.write('\n')
    gen_swift_fetcher_init(out, query, True)
    out.write('}\n')
    out.write('\n')


def gen_swift_multi_result_query(out, query):
    c_query_name = query["name"]
    swift_query_name = swift_name(c_query_name, True)

    out.write(
        f'public struct {swift_query_name} : RandomAccessCollection {{\n')
    out.write('    public struct Element : Hashable {\n')
    out.write(f'        let resultSet: {swift_query_name}\n')
    out.write('        let row: Int32\n')

    gen_projection_getters(out, query, True)

    out.write('\n')

    out.write('        // Hashable\n')
    out.write(
        '        public static func == (lhs: Element, rhs: Element) -> Bool {\n')
    out.write(
        f'            CGS_{c_query_name}_row_equal(lhs.resultSet.result_set, lhs.row,\n')
    out.write(
        '                rhs.resultSet.result_set, rhs.row)\n')
    out.write('        }\n')
    out.write('\n')
    out.write('        public func hash(into hasher: inout Hasher) {\n')
    out.write(
        f'            hasher.combine(CGS_{c_query_name}_row_hash(resultSet.result_set, row))\n')
    out.write('        }\n')
    out.write('\n')
    out.write('    }\n')
    out.write('\n')
    out.write('    // RandomAccessCollection\n')
    out.write('    public subscript(index: Int32) -> Element {\n')
    out.write('        get { Element(resultSet:self, row:index) }\n')
    out.write('    }\n')
    out.write('\n')
    out.write('    public var startIndex : Int32 { 0 }\n')
    out.write('    public var endIndex : Int32 {\n')
    out.write(f'        CGS_{c_query_name}_result_count(result_set)\n')
    out.write('    }\n')
    out.write('\n')

    out.write(f'    private var result_set: CGS_{c_query_name}!\n')

    out.write('\n')
    gen_swift_fetcher_init(out, query, False)
    out.write('}\n')
    out.write('\n')


def gen_swift_simple_proc(out, proc):
    c_proc_name = proc["name"]
    swift_proc_name = swift_name(c_proc_name)

    if ARGS.verbose:
        print(f'Generating swift proc {swift_proc_name} for {c_proc_name}')

    args_ = []
    # Procs use the database unless usesDataBase is false.
    uses_database = 'usesDatabase' not in proc or proc['usesDatabase']
    if uses_database:
        args_.append({'name': 'db', 'type': 'OpaquePointer', "isNotNull": 1})
    public_arg_start = len(args_)
    args_ += proc['args']

    args = [Arg(arg) for arg in args_]
    for i in range(public_arg_start, len(args)):
        local_name = args[i].local_swift_name
        if local_name.startswith('_a') or local_name in ["db", "statement", c_proc_name]:
            args[i].local_swift_name = f'_a{i}'

    swift_args = ', '.join([arg.swift_arg_declaration() for arg in args])
    c_args = ', '.join([arg.c_arg() for arg in args])

    throws = 'throws ' if uses_database else ''
    out.write(f'public func {swift_proc_name}({swift_args}) {throws}{{\n')
    for arg in args:
        out.write(arg.prepare_c_arg())
    invocation = f'{c_proc_name}({c_args})'
    if uses_database:
        invocation = f'try check({invocation})'
    out.write(f'    {invocation}\n')
    out.write('}\n')


def gen_swift_proc(out, proc):
    if "projection" in proc:
        gen_swift_query(out, proc)
    else:
        gen_swift_simple_proc(out, proc)


def gen_swift_target(package_name, package_dir, c_lib_name, json_schema):
    if ARGS.verbose:
        print(f'Generating swift target {package_name}')

    out = io.StringIO()
    out.write('import Foundation\n')
    out.write('\n')
    out.write(f'import {c_lib_name}\n')
    out.write('\n')
    out.write('fileprivate func check(_ code: Int32) throws {\n')
    out.write('    if code != SQLITE_OK {\n')
    out.write('        throw NSError(domain: "SwiftCQL", code: Int(code))\n')
    out.write('    }\n')
    out.write('}\n')
    out.write('\n')

    for proc in json_schema["general"]:
        gen_swift_proc(out, proc)
        out.write('\n')

    for proc in json_schema["inserts"]:
        gen_swift_proc(out, proc)
        out.write('\n')

    for proc in json_schema["updates"]:
        gen_swift_proc(out, proc)
        out.write('\n')

    for proc in json_schema["deletes"]:
        gen_swift_proc(out, proc)
        out.write('\n')

    for i, query in enumerate(json_schema["queries"]):
        if i > 0:
            out.write('\n')
        gen_swift_query(out, query)

    swift_file = Path(package_dir) / "Sources" / \
        package_name / f"{package_name}.swift"
    swift_file.write_text(out.getvalue())


def gen_swift_test_target(package_name, package_dir, test_files):
    if ARGS.verbose:
        print(f'Generating swift test target for {package_name} files {test_files}')
    for test_file in test_files:
        test_name = f"{package_name}Tests"
        test_file_text = Path(test_file).read_text()
        swift_test_file = Path(package_dir) / "Tests" / \
            test_name / f"{test_name}.swift"
        swift_test_file.write_text(test_file_text)


def gen_read_me(package_name, package_dir):
    if ARGS.verbose:
        print(f'Generating README.md for {package_name}')
    out = io.StringIO()
    out.write(f'# {package_name}\n')
    out.write('\n')
    out.write('A set of stored procedures. Generated by gen.py.\n')

    read_me_file = Path(package_dir) / "README.md"
    read_me_file.write_text(out.getvalue())


def gen_project(file_sql, package_name, out_dir, test_files):
    if ARGS.verbose:
        print(f'Generating project {out_dir}')
    # Generate the schema first because it can use relative paths,
    # so the cql error messages are nice and short.
    file_json_schema = cql_gen_json_schema(file_sql, out_dir)
    file_h, file_c = cql_gen_c(file_sql, out_dir)
    file_objc_h = cql_gen_objc(file_sql, out_dir)
    json_schema = parse_json_schema(file_json_schema)
    if ARGS.verbose:
        print(json.dumps(json_schema, indent=4, sort_keys=True))
    package_dir = gen_swift_package(package_name, out_dir)
    generate_test_target = len(test_files) > 0
    global cgsql_sources_dir
    c_lib_name = make_c_lib(package_name, package_dir,
                            cgsql_sources_dir, file_h, file_c, file_objc_h, generate_test_target)
    gen_swift_target(package_name, package_dir, c_lib_name, json_schema)
    gen_swift_test_target(package_name, package_dir, test_files)
    gen_read_me(package_name, package_dir)


def initialize_output_dir(out_dir):
    if ARGS.verbose:
        print(f'Initializing output directory {out_dir}')
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

def usage(str):
    eprint(str)
    eprint("Use argument --help for detailed help.")
    exit(1)

def main():
    if ARGS.verbose:
        print(ARGS)
    
    global cql_compiler_path
    cql_compiler_path = Path(ARGS.cql_compiler_path).resolve(True)
    global cgsql_sources_dir
    cgsql_sources_dir = Path(ARGS.cgsql_sources_dir).resolve(True)
    if not cgsql_sources_dir.is_dir():
        usage(f'CG-SQL sources directory does not exist: {ARGS.cgsql_sources_dir}')
    file_sql = Path(ARGS.file_sql)
    if not file_sql.is_file():
        usage(f'sql input is not a file: {ARGS.file_sql}')
    out_dir = Path(ARGS.out_dir).resolve(False)
    package_name = ARGS.package_name
    test_files = [] if ARGS.test_files is None else ARGS.test_files

    initialize_output_dir(out_dir)
    gen_project(file_sql, package_name, out_dir, test_files)


if __name__ == "__main__":
    main()
