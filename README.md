# SwiftGen: A Swift code generator for CG-SQL

SwiftGen generate Swift wrappers for [CG-SQL](https://cgsql.dev/) code.

## Introduction

This tool generates Swift wrappers for the CG-SQL language.

+ Supports the full CG-SQL language.
+ Generates idiomatic Swift.
+ Generates Swift Package Manager packages.

## Example

This is a CG-SQL file for a toy Todo List app.

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

create proc tasks_set_done(rowid_ integer not null, done_ bool not null)
begin
  update tasks set done = done_ where rowid == rowid_;
end;

create proc tasks_delete(rowid_ integer not null)
begin
  delete from tasks where rowid == rowid_;
end;
```

This is the generated Swift API:

```swift
public func tasksCreateTables(db: OpaquePointer) throws
public func tasksAdd(db: OpaquePointer, description: String, done: Bool) throws 
public func tasksSetDone(db: OpaquePointer, rowid: Int32, done: Bool) throws 
public func tasksDelete(db: OpaquePointer, rowid: Int32) throws

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

The SwiftGen.py file can be placed anywhere you like. You use it like this:

```
usage: SwiftGen.py [-h] -c PATH -d DIR -i FILE [-o DIR] -p NAME [-t FILE] [-v]

required arguments:
  -c PATH, --cql_compiler PATH
                        Path to the CQL compiler
  -d DIR, --cgsql_sources DIR
                        Read CG-SQL runtime sources from this directory
  -i FILE, --in FILE    Read cg-sql input from this file.
  -o DIR, --out DIR     Directory to generate code to
  -p NAME, --package_name NAME
                        Swift Package Name

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

SwiftGen.py generates a Swift Package Manager package from the CG-SQL input file. You
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
