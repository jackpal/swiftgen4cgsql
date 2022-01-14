#!/bin/bash
set -euo pipefail

echo "Testing...."

CGSQL_SOURCES=../CG-SQL/sources
CQL="$CGSQL_SOURCES/out/cql"
SWIFTGEN="./SwiftGen.py"
PACKAGEGEN="./PackageGen.py"

if [ ! -d "$CGSQL_SOURCES" ]; then
  echo "CG-SQL sources directory does not exist:  $CGSQL_SOURCES"
  exit 1
fi

if [ ! -f "$CQL" ]; then
  echo "CQL compiler does not exist:  $CQL"
  exit 1
fi

OUT_DIR=out

rm -rf "$OUT_DIR"

"$PACKAGEGEN" -c "$CQL" -d "$CGSQL_SOURCES" --in tests/TestGen/TestGen.sql -o "$OUT_DIR" -p TestGen -s "$SWIFTGEN" -t tests/TestGen/TestGenTests.swift
pushd "$OUT_DIR"/TestGen
swift test
popd

# Also build examples

"$PACKAGEGEN" -c "$CQL" -d "$CGSQL_SOURCES" --in examples/Todo/Todo.sql -o "$OUT_DIR" -p Todo -s "$SWIFTGEN" -t examples/Todo/TodoTests.swift
pushd "$OUT_DIR"/Todo
swift test
popd
