-- Press Answer/Accept on an incoming FaceTime call: the Notification Center banner, or the
-- FaceTime window. The FaceTime app may not even be running while it rings (live probe, #85).
-- By hand: osascript mac/scripts/click_accept.applescript
-- Prints "clicked" or "missing".
--
-- Speed: the live banner labels Answer through the button's *description* (name is missing value).
-- Reading only role + label per element keeps a scan near a second; listing every element's
-- actions took ~9 s on the spare Mac. Scope: only a window that also has a Decline button is a call
-- banner, so another app's notification can't be accepted by mistake.

-- AXButton label: description, else name. "" for anything else.
on labelOf(k)
	tell application "System Events"
		if role of k is not "AXButton" then return ""
		set lbl to description of k
		if lbl is missing value or (lbl as text) is "" then set lbl to name of k
		if lbl is missing value then return ""
		return lbl as text
	end tell
end labelOf

on pressIn(w)
	tell application "System Events"
		try
			set kids to entire contents of w
		on error
			return false
		end try
		set target to missing value
		set isCall to false
		repeat with k in kids
			try
				set lbl to my labelOf(k)
				if lbl is "Answer" or lbl is "Accept" then
					if target is missing value then set target to contents of k
				else if lbl is "Decline" then
					set isCall to true
				end if
				if isCall and target is not missing value then exit repeat
			end try
		end repeat
		if target is missing value or not isCall then return false
		try
			perform action "AXPress" of target
			return true
		on error errText number errNum
			log "answer AXPress failed code=" & errNum
		end try
		try
			click target
			return true
		on error errText number errNum
			log "answer click failed code=" & errNum
		end try
	end tell
	return false
end pressIn

on acceptIn(procName)
	tell application "System Events"
		if not (exists process procName) then return false
		set ws to windows of process procName
	end tell
	repeat with w in ws
		if my pressIn(w) then return true
	end repeat
	return false
end acceptIn

if acceptIn("NotificationCenter") then return "clicked"
if acceptIn("FaceTime") then return "clicked"
return "missing"
