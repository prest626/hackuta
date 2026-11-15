import XCTest
@testable import HomewardWatch

final class BatchingTests: XCTestCase {
    func testISO8601IsUTC() {
        XCTAssertEqual(Batching.iso8601(Date(timeIntervalSince1970: 0)), "1970-01-01T00:00:00Z")
    }

    func testFlushOnCountOrFiveSeconds() {
        let t0 = Date(timeIntervalSince1970: 1_700_000_000)
        let one = [HrSample(t_end: Batching.iso8601(t0), bpm: 70)]
        XCTAssertFalse(Batching.shouldFlush(samples: one, now: t0.addingTimeInterval(4.9)))
        XCTAssertTrue(Batching.shouldFlush(samples: one, now: t0.addingTimeInterval(5)))
        let five = (0..<5).map { i in
            HrSample(t_end: Batching.iso8601(t0.addingTimeInterval(Double(i))), bpm: 70)
        }
        XCTAssertTrue(Batching.shouldFlush(samples: five, now: t0.addingTimeInterval(1)))
        XCTAssertFalse(Batching.shouldFlush(samples: Array(five.prefix(4)), now: t0.addingTimeInterval(1)))
    }

    func testPruneDropsSamplesOlderThanTenMinutes() {
        let now = Date(timeIntervalSince1970: 1_700_000_000)
        let old = HrSample(t_end: Batching.iso8601(now.addingTimeInterval(-601)), bpm: 60)
        let edge = HrSample(t_end: Batching.iso8601(now.addingTimeInterval(-600)), bpm: 61)
        let fresh = HrSample(t_end: Batching.iso8601(now.addingTimeInterval(-30)), bpm: 62)
        XCTAssertEqual(Batching.prune([old, edge, fresh], now: now).map(\.bpm), [61, 62])
    }

    func testNextBatchHoldsUntilFiveSamplesOrFiveSeconds() {
        let t0 = Date(timeIntervalSince1970: 1_700_000_000)
        let four = (0..<4).map { HrSample(t_end: Batching.iso8601(t0), bpm: Double(70 + $0)) }
        let (held, rest) = Batching.nextBatch(four, now: t0.addingTimeInterval(1))
        XCTAssertTrue(held.isEmpty)
        XCTAssertEqual(rest.count, 4)
        let (sent, left) = Batching.nextBatch(four, now: t0.addingTimeInterval(5))
        XCTAssertEqual(sent.count, 4)
        XCTAssertTrue(left.isEmpty)
    }

    func testNextBatchCapsAtFifty() {
        let now = Date(timeIntervalSince1970: 1_700_000_000)
        let samples = (0..<60).map { i in
            HrSample(t_end: Batching.iso8601(now.addingTimeInterval(Double(i))), bpm: 80)
        }
        let (batch, rest) = Batching.nextBatch(samples, now: now.addingTimeInterval(59))
        XCTAssertEqual(batch.count, 50)
        XCTAssertEqual(rest.count, 10)
    }

    func testEncodeOmitsSourceAndUsesSchemaKeys() throws {
        let samples = [
            HrSample(t_end: "2026-11-15T19:02:00Z", bpm: 80),
            HrSample(t_end: "2026-11-15T19:02:05Z", bpm: 81),
        ]
        let data = try Batching.encodePost(deviceId: "watch_team01", samples: samples)
        let obj = try JSONSerialization.jsonObject(with: data) as! [String: Any]
        XCTAssertEqual(obj["device_id"] as? String, "watch_team01")
        let rows = obj["samples"] as! [[String: Any]]
        XCTAssertEqual(rows.count, 2)
        XCTAssertEqual(rows[0]["t_end"] as? String, "2026-11-15T19:02:00Z")
        XCTAssertEqual(rows[0]["bpm"] as? Double, 80)
        XCTAssertNil(rows[0]["source"])
        XCTAssertNil(obj["source"])
    }
}
