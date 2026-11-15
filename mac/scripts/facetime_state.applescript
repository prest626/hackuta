-- Print FaceTime window titles and button names, one fact per line.
-- window=<title>
-- button=<name>
-- An incoming call may show only as a Notification Center banner (the FaceTime window
-- can disappear on ring), so the banner's buttons and Accept action are listed too.
-- By hand: osascript mac/scripts/facetime_state.applescript
-- The window title can be a phone number. Do not paste this output into GitHub.

-- Every button under el at any depth, by name or, failing that, description.
on buttonsIn(el)
	set out to ""
	tell application "System Events"
		try
			set kids to entire contents of el
		on error
			return ""
		end try
		repeat with k in kids
			try
				if role of k is "AXButton" then
					set n to name of k
					if n is missing value or (n as text) is "" then set n to description of k
					if n is not missing value and (n as text) is not "" then set out to out & "button=" & (n as text) & linefeed
				end if
			end try
			-- Banners can expose Accept as a custom action instead of a button.
			try
				repeat with a in actions of k
					if (name of a as text) contains "Accept" then set out to out & "button=Accept" & linefeed
				end repeat
			end try
		end repeat
	end tell
	return out
end buttonsIn

set out to ""
tell application "System Events"
	if exists process "FaceTime" then
		repeat with w in windows of process "FaceTime"
			try
				set out to out & "window=" & (name of w as text) & linefeed
			end try
			set out to out & my buttonsIn(w)
		end repeat
	end if
	if exists process "NotificationCenter" then
		repeat with w in windows of process "NotificationCenter"
			set out to out & my buttonsIn(w)
		end repeat
	end if
end tell
return out
