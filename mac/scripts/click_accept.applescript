-- Click Accept on an incoming FaceTime call (app window or notification).
-- By hand: osascript mac/scripts/click_accept.applescript
-- Prints "clicked" or "missing".

on clickLabel(el, labelName)
	try
		if exists (button labelName of el) then
			click button labelName of el
			return true
		end if
	end try
	try
		repeat with g in (UI elements of el)
			try
				if role of g is "AXButton" and name of g is labelName then
					click g
					return true
				end if
			end try
			try
				if exists (button labelName of g) then
					click button labelName of g
					return true
				end if
			end try
		end repeat
	end try
	return false
end clickLabel

on clickProcess(procName)
	tell application "System Events"
		if not (exists process procName) then return false
		tell process procName
			repeat with w in windows
				if my clickLabel(w, "Accept") then return true
				try
					repeat with s in sheets of w
						if my clickLabel(s, "Accept") then return true
					end repeat
				end try
			end repeat
		end tell
	end tell
	return false
end clickProcess

tell application "System Events"
	if exists process "FaceTime" then
		tell process "FaceTime" to set frontmost to true
	end if
end tell
if clickProcess("FaceTime") then return "clicked"
if clickProcess("NotificationCenter") then return "clicked"
if clickProcess("Notification Center") then return "clicked"
return "missing"
