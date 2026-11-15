import Combine
import HealthKit

@MainActor
final class WorkoutManager: NSObject, ObservableObject {
    @Published var lastBpm: Int?
    @Published var running = false
    let uploader = Uploader()

    private let healthStore = HKHealthStore()
    private var session: HKWorkoutSession?
    private var builder: HKLiveWorkoutBuilder?
    private var starting = false

    func start() {
        guard session == nil, !starting else { return }
        starting = true
        let share: Set<HKSampleType> = [HKObjectType.workoutType()]
        let read: Set<HKObjectType> = [HKQuantityType.quantityType(forIdentifier: .heartRate)!]
        healthStore.requestAuthorization(toShare: share, read: read) { [weak self] _, _ in
            Task { @MainActor in
                self?.starting = false
                self?.beginSession()
            }
        }
    }

    func stop() {
        let session = self.session
        let builder = self.builder
        self.session = nil
        self.builder = nil
        running = false
        let end = Date()
        session?.stopActivity(with: end)
        session?.end()
        builder?.endCollection(withEnd: end) { _, _ in
            builder?.discardWorkout()
        }
    }

    private func beginSession() {
        guard session == nil else { return }
        let configuration = HKWorkoutConfiguration()
        configuration.activityType = .other
        configuration.locationType = .indoor
        do {
            let session = try HKWorkoutSession(healthStore: healthStore, configuration: configuration)
            let builder = session.associatedWorkoutBuilder()
            let source = HKLiveWorkoutDataSource(healthStore: healthStore, workoutConfiguration: configuration)
            if let hr = HKQuantityType.quantityType(forIdentifier: .heartRate) {
                source.enableCollection(for: hr, predicate: nil)
            }
            builder.dataSource = source
            session.delegate = self
            builder.delegate = self
            self.session = session
            self.builder = builder
            let start = Date()
            session.startActivity(with: start)
            running = true
            builder.beginCollection(withStart: start) { [weak self] ok, _ in
                Task { @MainActor in
                    if !ok {
                        self?.running = false
                        self?.uploader.status = "check-in stopped"
                    }
                }
            }
        } catch {
            running = false
            uploader.status = "check-in stopped"
        }
    }

    private func record(bpm: Double, at end: Date) {
        lastBpm = Int(bpm.rounded())
        uploader.enqueue(HrSample(t_end: Batching.iso8601(end), bpm: bpm))
    }
}

extension WorkoutManager: HKWorkoutSessionDelegate {
    nonisolated func workoutSession(
        _ workoutSession: HKWorkoutSession,
        didChangeTo toState: HKWorkoutSessionState,
        from fromState: HKWorkoutSessionState,
        date: Date
    ) {
        let ended = toState == .ended
        Task { @MainActor in
            if toState == .running { self.running = true }
            if ended { self.running = false }
        }
    }

    nonisolated func workoutSession(_ workoutSession: HKWorkoutSession, didFailWithError error: Error) {
        Task { @MainActor in
            self.running = false
            self.uploader.status = "check-in stopped"
        }
    }
}

extension WorkoutManager: HKLiveWorkoutBuilderDelegate {
    nonisolated func workoutBuilder(
        _ workoutBuilder: HKLiveWorkoutBuilder,
        didCollectDataOf collectedTypes: Set<HKSampleType>
    ) {
        guard let hr = HKQuantityType.quantityType(forIdentifier: .heartRate),
              collectedTypes.contains(hr),
              let stats = workoutBuilder.statistics(for: hr),
              let qty = stats.mostRecentQuantity()
        else { return }
        let unit = HKUnit.count().unitDivided(by: .minute())
        let bpm = qty.doubleValue(for: unit)
        let end = stats.mostRecentQuantityDateInterval()?.end ?? Date()
        Task { @MainActor in
            self.record(bpm: bpm, at: end)
        }
    }

    nonisolated func workoutBuilderDidCollectEvent(_ workoutBuilder: HKLiveWorkoutBuilder) {}
}
