import Foundation

/// Compiled into the watch app. make watch-url sets API_BASE.
/// deviceToken is local. Never commit Config.swift or a real token.
enum Config {
    /// No trailing slash. Spare Mac quick-tunnel URL (make watch-url).
    static let API_BASE = "http://127.0.0.1:8000"
    /// Same string as WATCH_DEVICE_TOKEN on the Mac. Not a real token.
    static let deviceToken = "PLACEHOLDER"
    /// contracts/examples/patient.json watch_device_id (mock Rosa).
    static let deviceId = "watch_team01"
}
