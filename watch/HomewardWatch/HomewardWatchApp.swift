import SwiftUI

@main
struct HomewardWatchApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
    }
}

struct ContentView: View {
    @StateObject private var workout = WorkoutManager()

    var body: some View {
        CheckInScreen(workout: workout, uploader: workout.uploader)
    }
}

private struct CheckInScreen: View {
    @ObservedObject var workout: WorkoutManager
    @ObservedObject var uploader: Uploader

    var body: some View {
        VStack(spacing: 8) {
            Text(workout.lastBpm.map { "\($0) bpm" } ?? "— bpm")
                .font(.title2)
            Text(uploader.status)
                .font(.footnote)
            Button(workout.running ? "Stop check-in mode" : "Start check-in mode") {
                if workout.running { workout.stop() } else { workout.start() }
            }
            .minimumScaleFactor(0.5)
            Text("Prototype · not a medical device")
                .font(.caption2)
                .multilineTextAlignment(.center)
        }
        .padding()
    }
}
