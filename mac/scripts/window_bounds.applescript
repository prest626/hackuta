-- Print x,y,w,h of FaceTime window 1.
-- By hand: osascript mac/scripts/window_bounds.applescript
tell application "System Events"
	tell process "FaceTime"
		set p to position of window 1
		set s to size of window 1
		return ((item 1 of p) as text) & "," & ((item 2 of p) as text) & "," & ((item 1 of s) as text) & "," & ((item 2 of s) as text)
	end tell
end tell
