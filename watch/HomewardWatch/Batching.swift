import Foundation

// JSON keys match contracts/vitals.schema.json WatchHrPost. source is omitted; the server defaults it to workout.

struct HrSample: Codable, Equatable {
    var t_end: String
    var bpm: Double
}

struct WatchHrPost: Codable, Equatable {
    var device_id: String
    var samples: [HrSample]
}

enum Batching {
    static let batchCount = 5
    static let batchSeconds: TimeInterval = 5
    static let queueSeconds: TimeInterval = 10 * 60
    static let maxPost = 50

    static func iso8601(_ date: Date) -> String {
        formatter().string(from: date)
    }

    static func shouldFlush(samples: [HrSample], now: Date) -> Bool {
        guard let oldest = oldest(samples) else { return false }
        return samples.count >= batchCount || now.timeIntervalSince(oldest) >= batchSeconds
    }

    static func prune(_ samples: [HrSample], now: Date) -> [HrSample] {
        samples.filter { sample in
            guard let t = date(from: sample.t_end) else { return false }
            return now.timeIntervalSince(t) <= queueSeconds
        }
    }

    /// Oldest-first. Sends when 5 samples or 5 s have piled up, at most 50 (schema max).
    static func nextBatch(_ samples: [HrSample], now: Date) -> (batch: [HrSample], rest: [HrSample]) {
        let kept = prune(samples, now: now)
        guard shouldFlush(samples: kept, now: now) else { return ([], kept) }
        let n = min(maxPost, kept.count)
        return (Array(kept.prefix(n)), Array(kept.dropFirst(n)))
    }

    static func encodePost(deviceId: String, samples: [HrSample]) throws -> Data {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys]
        return try encoder.encode(WatchHrPost(device_id: deviceId, samples: samples))
    }

    private static func oldest(_ samples: [HrSample]) -> Date? {
        samples.compactMap { date(from: $0.t_end) }.min()
    }

    private static func date(from iso: String) -> Date? {
        formatter().date(from: iso)
    }

    private static func formatter() -> ISO8601DateFormatter {
        let f = ISO8601DateFormatter()
        f.timeZone = TimeZone(secondsFromGMT: 0)
        f.formatOptions = [.withInternetDateTime]
        return f
    }
}
