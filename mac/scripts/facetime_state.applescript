-- Print FaceTime window titles and button labels, one fact per line.
-- window=<title>
-- button=<label>
-- An incoming call may show only as a Notification Center banner (the FaceTime app may not be
-- running), so a banner that has both Answer/Accept and Decline is listed too.
-- Labels come from the button's description, else its name (the live banner has no names).
-- Only role + label are read per element: listing every element's actions took ~10 s.
-- By hand: osascript mac/scripts/facetime_state.applescript
-- The window title can be a phone number. Do not paste this output into GitHub.

on labelOf(k)
	tell application "System Events"
		if role of k is not "AXButton" then return ""
		set lbl to description of k
		if lbl is missing value or (lbl as text) is "" then set lbl to name of k
		if lbl is missing value then return ""
		return lbl as text
	end tell
end labelOf

-- Every button label under w, one per line.
on buttonsIn(w)
	set out to ""
	tell application "System Events"
		try
			set kids to entire contents of w
		on error
			return ""
		end try
		repeat with k in kids
			try
				set lbl to my labelOf(k)
				if lbl is not "" then set out to out & "button=" & lbl & linefeed
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
			-- Only a call banner (Answer/Accept plus Decline) counts; other notifications are ignored.
			set b to my buttonsIn(w)
			if (b contains "button=Answer" or b contains "button=Accept") and b contains "button=Decline" then set out to out & b
		end repeat
	end if
end tell
return out
