-- Print FaceTime window titles and button names, one fact per line.
-- window=<title>
-- button=<name>
-- By hand: osascript mac/scripts/facetime_state.applescript
-- The window title can be a phone number. Do not paste this output into GitHub.

on addButtons(el, soFar)
	try
		repeat with b in buttons of el
			try
				set n to name of b as text
				if n is not "missing value" and n is not "" then
					set soFar to soFar & "button=" & n & linefeed
				end if
			end try
		end repeat
	end try
	try
		repeat with g in UI elements of el
			try
				if role of g is "AXButton" then
					set n to name of g as text
					if n is not "missing value" and n is not "" then
						set soFar to soFar & "button=" & n & linefeed
					end if
				end if
			end try
		end repeat
	end try
	return soFar
end addButtons

tell application "System Events"
	if not (exists process "FaceTime") then return ""
	tell process "FaceTime"
		set out to ""
		repeat with w in windows
			try
				set out to out & "window=" & (name of w as text) & linefeed
			end try
			set out to my addButtons(w, out)
			try
				repeat with s in sheets of w
					set out to my addButtons(s, out)
				end repeat
			end try
		end repeat
		return out
	end tell
end tell
