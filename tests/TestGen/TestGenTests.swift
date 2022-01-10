import XCTest
import TestGen

import SQLite3

final class TestGenTests: XCTestCase {
    func testExample() throws {
        var db: OpaquePointer!
        let rc = sqlite3_open(":memory:", &db)
        XCTAssertEqual(rc, SQLITE_OK)
        defer { sqlite3_close(db) }
        try todoCreateTables(db:db)

        let blob = "Hi!".data(using: .utf8)!
        for t in ["Buy milk", "Walk dog", "Write code"] {
            try aAdd(db:db, t:t, b: false, i: 17, l: 77, r: 3.14159, bl: blob)
            try bAdd(db:db, t:t, b: false, i: 17, l: 77, r: 3.14159, bl: blob)
        }
        try bAdd(db:db, t:nil, b: nil, i: nil, l: nil, r: nil, bl: nil)

        try aSetB(db:db, rowid:2, b:true)
        try aDelete(db:db, rowid:1)

        for (i,task) in try AllA(db:db).enumerated() {
            XCTAssertEqual(task, task)
            print("\(i): rowid: \(task.rowid) t: \(task.t) b: \(task.b) i: \(task.i) l: \(task.l) r: \(task.r) bl:\(task.bl)")
        }

        for (i,task) in try AllB(db:db).enumerated() {
            print("\(i): rowid: \(task.rowid) t: \(task.t ?? "nil") b: \(task.b ?? false) i: \(task.i ?? -1) l: \(task.l ?? -1) r: \(task.r ?? -1) bl:\(task.bl ?? "null".data(using: .utf8)!)")
        }
    }

    func testOut() {
        XCTAssertEqual(TestOut(outputRow:true)!.value, 17)
        XCTAssertNil(TestOut(outputRow:false))
    }

    func testOutUnion() {
        XCTAssertEqual(FetchRange(n:6).reduce(0){ $0 + $1.value }, 15)
    }

    func testTestObjects() {
        var dest: Unmanaged<AnyObject>?
        var dest2: Unmanaged<AnyObject>?
        let src = NSNumber(1)
        let src2 = NSNumber(2)
        testObjects(dest:&dest, dest2:&dest2, src:src, src2:src2)
        XCTAssertEqual(dest!.takeRetainedValue() as! NSNumber,src)
        XCTAssertEqual(dest2!.takeRetainedValue() as! NSNumber, src2)
    }
}
