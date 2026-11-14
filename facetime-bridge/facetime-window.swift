import Foundation
import CoreGraphics

guard CGPreflightScreenCaptureAccess() else {
    fputs("Enable Screen & System Audio Recording for Terminal in System Settings, then restart Terminal.\n", stderr)
    exit(1)
}
let windows = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID) as? [[String: Any]] ?? []
let candidates = windows.filter {
    guard $0[kCGWindowOwnerName as String] as? String == "FaceTime",
          $0[kCGWindowLayer as String] as? Int == 0,
          let bounds = $0[kCGWindowBounds as String] as? [String: Any],
          let width = bounds["Width"] as? Double,
          let height = bounds["Height"] as? Double else { return false }
    return width >= 200 && height >= 200
}
func area(_ window: [String: Any]) -> Double {
    let bounds = window[kCGWindowBounds as String] as? [String: Any] ?? [:]
    return (bounds["Width"] as? Double ?? 0) * (bounds["Height"] as? Double ?? 0)
}
guard let window = candidates.max(by: { area($0) < area($1) }),
      let id = window[kCGWindowNumber as String] as? Int else {
    fputs("No visible FaceTime window. Open the video call window and keep it visible.\n", stderr)
    exit(1)
}
print(id)
