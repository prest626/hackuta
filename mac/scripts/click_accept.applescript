-- Click Accept on an incoming FaceTime call: the FaceTime window, or the
-- Notification Center banner (the FaceTime window can disappear on ring).
-- By hand: osascript mac/scripts/click_accept.applescript
-- Prints "clicked" or "missing".

-- Press the first Accept under el at any depth: a button named or described Accept,
-- or an element with a custom Accept action (how banners expose it).
on pressAccept(el)
	tell application "System Events"
		try
			set kids to entire contents of el
		on error
			return false
		end try
		repeat with k in kids
			try
				if role of k is "AXButton" then
					set n to name of k
					if n is missing value or (n as text) is "" then set n to description of k
					if (n as text) is "Accept" or (n as text) is "Answer" then
						try
							perform action "AXPress" of k
							return true
						on error errText number errNum
							log "answer AXPress failed code=" & errNum
						end try
						try
							click k
							return true
						on error errText number errNum
							log "answer click failed code=" & errNum
						end try
					end if
				end if
			end try
			try
				repeat with a in actions of k
					if (name of a as text) contains "Accept" or (name of a as text) contains "Answer" then
						perform a
						return true
					end if
				end repeat
			end try
		end repeat
	end tell
	return false
end pressAccept

on acceptIn(procName)
	tell application "System Events"
		if not (exists process procName) then return false
		set ws to windows of process procName
	end tell
	repeat with w in ws
		if my pressAccept(w) then return true
	end repeat
	return false
end acceptIn

if acceptIn("NotificationCenter") then return "clicked"
if acceptIn("FaceTime") then return "clicked"
return "missing"
