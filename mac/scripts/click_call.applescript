-- Click FaceTime's Call button on the outgoing confirmation.
-- By hand: osascript mac/scripts/click_call.applescript
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

tell application "System Events"
	if not (exists process "FaceTime") then return "missing"
	tell process "FaceTime"
		set frontmost to true
		repeat with w in windows
			if my clickLabel(w, "Call") then return "clicked"
			try
				repeat with s in sheets of w
					if my clickLabel(s, "Call") then return "clicked"
				end repeat
			end try
		end repeat
	end tell
end tell
return "missing"
