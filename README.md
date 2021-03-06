# SwiftGen: A Swift code generator for CG-SQL

## Introduction

SwiftGen is a command-line tool that generates Swift wrappers for the [CG-SQL](https://cgsql.dev/) language.

+ Allows Swift code to call CG-SQL procedures and result sets in an idiomatic way.
+ Supports the full CG-SQL language.
+ Generates Swift Package Manager packages.

## Example

This is a CG-SQL file for a toy Todo List app:

```sql
create proc tasks_create_tables()
begin

  create table tasks (
    description text not null,
    done bool default false not null
  );

end;

create proc tasks_add(description text not null, done bool not null)
begin
  insert into tasks values(description, done);
end;

create proc tasks_all()
begin
  select rowid, description, done from tasks order by rowid;
end;

create proc tasks_set_done(rowid_ long not null, done_ bool not null)
begin
  update tasks set done = done_ where rowid == rowid_;
end;

create proc tasks_delete(rowid_ long not null)
begin
  delete from tasks where rowid == rowid_;
end;
```

This is the generated Swift API for that cg-sql:

```swift
public func tasksCreateTables(db: OpaquePointer) throws
public func tasksAdd(db: OpaquePointer, description: String, done: Bool) throws 
public func tasksSetDone(db: OpaquePointer, rowid: Int64, done: Bool) throws 
public func tasksDelete(db: OpaquePointer, rowid: Int64) throws

public struct TasksAll : RandomAccessCollection {
    public struct Element : Hashable {
        public var rowid: Int64 { get }
        public var description: String { get }
        public var done: Bool { get }
    }
    public init(db: OpaquePointer) throws
}
```

## Installation

SwiftGen depends upon

+ Python 3
+ Swift
+ The CG-SQL compiler and runtime source files.

Typically Python 3 will be already installed in your computer environment.

Swift can be installed from [Swift.org](https://www.swift.org/) or as part of
[Xcode](https://apps.apple.com/us/app/xcode/id497799835?mt=12).

The CG-SQL compiler and runtime source code is not currently 
packaged for distribution. You will have to build it from source. See the
[CG-SQL repo](https://github.com/facebookincubator/CG-SQL) for details.

## Usage

The SwiftGen.py script generates Swift code from the CG-SQL compiler's JSON
metadata description.

The PackageGen.py script creates a Swift Package Manager package that contains
the generated Swift code, along with the generated Objective-C code, the
generated C code, and the cg-sql runtime.

The PackageGen.py script will invoke the SwiftGen.py script to generate the
Swift code as needed.

The SwiftGen.py and PackageGen.py files can be placed anywhere you like.

You call PackageGen.py like this:

```
usage: PackageGen.py [-h] -c PATH -d DIR -i FILE [-o DIR] -p NAME -s PATH [-t FILE] [-v]

required arguments:
  -c PATH, --cql_compiler PATH
                        Path to the CQL compiler
  -d DIR, --cgsql_sources DIR
                        Read CG-SQL runtime sources from this directory
  -i FILE, --in FILE    Read cg-sql input from this file.
  -o DIR, --out DIR     Directory to generate code to
  -p NAME, --package_name NAME
                        Swift Package Name
  -s PATH, --swift-generator PATH
                        Path to the Swift code generator.
optional arguments:
  -h, --help            show this help message and exit
  -t FILE, --test FILE  Swift Package unit test file. Can be supplied multiple times.
  -v, --verbose         print verbose status messages to stdout
```

## Tests

You can test if the SwiftGen code generator is is working by running:

```bash
./test.sh
```

In order for this to work you will need:

+ Python installed so that the `/usr/bin/env python3` command line tool works. 
+ Swift installed so that the `swift` command line tool works.
+ The [CG-SQL repository](https://github.com/facebookincubator/CG-SQL) installed
  in the directory `..\CG-SQL`.

If you have a different configuration, you'll need to edit the `./test.sh` file to
match your configuration.

## Using the generated package

PackageGen.py generates a Swift Package Manager package from the CG-SQL input file. You
can use the output in several ways:

+ As a dependency for other Swift Package Manager packages.
+ As a dependency for an Xcode project.
+ As a collection of source files that are copied into another package or build system.

## Compatibility with SQL libraries

The generated Swift code should be compatible with most Swift SQL libraries. The
generated code uses the sqlite database connection pointer, which most Swift SQL
libraries expose in one form or another.

## Limitations

- SwiftGen.py has not been tested extensively.
- Some more obscure features of CG-SQL may not work.
- Swift Package Manager packages are not well supported by Xcode. You may
  encounter bugs and / or crashes when trying to use the generated Swift package
  with Xcode projects, and / or with Swift Playgrounds.
