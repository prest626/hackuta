import Foundation

/// Compiled into the watch app. Preston edits the two strings below for a run.
/// Commit only these placeholders. Never commit a real token.
enum Config {
    /// No trailing slash. https tunnel, or http://<mac-lan-ip>:8000.
    static let API_BASE = "http://127.0.0.1:8000"
    /// Same string as WATCH_DEVICE_TOKEN on the Mac. Not a real token.
    static let deviceToken = "PLACEHOLDER"
    /// contracts/examples/patient.json watch_device_id (mock Rosa).
    static let deviceId = "watch_team01"
}
