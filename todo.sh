#!/bin/bash
set -euo pipefail

echo "Building Todo example...."

CGSQL_SOURCES=../CG-SQL/sources
CQL="$CGSQL_SOURCES/out/cql"
SWIFTGEN="./SwiftGen.py"

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

"$SWIFTGEN" -c "$CQL" -d "$CGSQL_SOURCES" --in examples/Todo/Todo.sql -o "$OUT_DIR" -p Todo -t examples/Todo/TodoTests.swift
pushd "$OUT_DIR"/Todo
swift test
popd
