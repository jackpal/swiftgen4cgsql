import XCTest
import Todo

import SQLite3

final class TodoTests: XCTestCase {
    func testExample() throws {
        var db: OpaquePointer!
        let rc = sqlite3_open(":memory:", &db)
        XCTAssertEqual(rc, SQLITE_OK)
        defer { sqlite3_close(db) }
        try tasksCreateTables(db:db)
        for description in ["Buy milk", "Walk dog", "Write code"] {
            try tasksAdd(db:db, description:description, done: false)
        }
        try tasksSetDone(db:db, rowid:2, done:true)
        try tasksDelete(db:db, rowid:1)

        for (i, task) in try TasksAll(db:db).enumerated() {
            XCTAssertTrue(task == task)
            XCTAssertEqual(task.hashValue, task.hashValue)
            print("\(i): rowid: \(task.rowid) description: \(task.description) done: \(task.done)")
        }
    }
}
