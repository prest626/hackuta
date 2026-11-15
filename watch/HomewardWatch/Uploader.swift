import Combine
import Foundation

@MainActor
final class Uploader: ObservableObject {
    @Published var status = "idle"
    private var pending: [HrSample] = []
    private var sending = false
    private var notBefore = Date.distantPast
    private var pump: Task<Void, Never>?
    private let session: URLSession = {
        let config = URLSessionConfiguration.ephemeral
        config.timeoutIntervalForRequest = 10
        config.waitsForConnectivity = false
        return URLSession(configuration: config)
    }()

    init() {
        pump = Task { [weak self] in
            while !Task.isCancelled {
                try? await Task.sleep(for: .seconds(1))
                await self?.tick()
            }
        }
    }

    func enqueue(_ sample: HrSample) {
        pending.append(sample)
        pending = Batching.prune(pending, now: Date())
        Task { await tick() }
    }

    private func tick() async {
        guard !sending, Date() >= notBefore else { return }
        sending = true
        defer { sending = false }
        while true {
            let (batch, rest) = Batching.nextBatch(pending, now: Date())
            pending = rest
            guard !batch.isEmpty else { return }
            if await post(batch) {
                status = "posted \(batch.count)"
            } else {
                pending = Batching.prune(batch + pending, now: Date())
                status = "not posted"
                notBefore = Date().addingTimeInterval(Batching.batchSeconds)
                return
            }
        }
    }

    private func endpoint() -> URL? {
        var base = Config.API_BASE
        while base.hasSuffix("/") { base.removeLast() }
        return URL(string: base + "/v1/watch/hr")
    }

    private func post(_ samples: [HrSample]) async -> Bool {
        guard let url = endpoint() else { return false }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(Config.deviceToken)", forHTTPHeaderField: "Authorization")
        do {
            request.httpBody = try Batching.encodePost(deviceId: Config.deviceId, samples: samples)
            let (_, response) = try await session.data(for: request)
            let code = (response as? HTTPURLResponse)?.statusCode ?? 0
            return (200..<300).contains(code)
        } catch {
            return false
        }
    }
}
