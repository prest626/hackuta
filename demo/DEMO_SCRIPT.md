# Judge demo, about 3 minutes

Evidence Trail. One continuous call, with the dashboard in picture-in-picture. Rosa is the mock patient on day 3. The live take we show is YELLOW going to nurse review, then Approve. Say the tier the dashboard actually shows. Call 7 ended YELLOW.

Homeward is a prototype and not a medical device. Mock data only. A nurse approves every escalation.

Say no phone number, no tunnel host, and no key.

## Before the call

1. Leave `CHERT_FACE` unset. The face flag is off. Use `fallback` only if that mode was already tried on its own. This call does not test a face.
2. Run `make vision-test`. If it prints `vision key: MISSING`, the pill check is the photo fallback: hold up `vision/eval/photos/03-sat-pm.jpg`. Do not place a second call to chase a live pill read.
3. One Chert call. The worker is `python -m chert.agent`. `doctor` shows a check on `line` and `worker` first. If it does not, use the backup labeled simulated call. Do not dial from this page to find out.
4. Heart rate in this demo is a labeled mock replay unless a watch workout is actually on the wrist. Say that before any number.

## The call

The dashboard stays in picture-in-picture and updates when the backend posts. One call. Do not open a second check-in.

| Clock | Preston says | Phone | Dashboard picture-in-picture |
|---|---|---|---|
| 0:00 | "Homeward. A FaceTime check-in that looks, listens and asks, then waits for a nurse. This is a prototype, and not a medical device. Rosa is a mock patient, day 3 after a mock heart-failure stay." | FaceTime connects. | Rosa, day 3, mock. The page says it is not a medical device. |
| 0:20 | "In the Odyssey the nurse knows him by a scar. This call notices. A nurse decides." | Greeting on the current tree: "Hi, this is Homeward, a prototype, and not a medical device." | The day-3 call goes active. |
| 0:40 | "If you hear a number, it is a labeled mock replay, not a live watch reading, unless a workout is on the watch." | Watch workout only, and only when the recent samples are all from the watch: "Your watch shows {hr} right now." When the resting rate is high, add "Your resting heart rate has been a bit higher than your usual this week." Mock replay, once that sentence is in the agent: "The mock replay shows {hr}. It is not a live watch reading." Stale or missing: "I don't have a fresh watch reading right now." | Sparkline. Label it mock replay when that is the source. |
| 1:05 | "It looks. On this mock box, Saturday evening is still full. It asks. It does not tell her to change a dose." If `make vision-test` printed `vision key: MISSING`: "This pill check is the photo fallback." | Hold the mock organizer, or the fallback photo. Expected ask: "One compartment still has pills. Did you take those from somewhere else?" | The frame, labeled mock box or fixture. |
| 1:30 | Speak Rosa's mock words: a bit worse, the stairs are harder, ankles are puffy, weight about the same. "It stores her words. A nurse reads them." | Symptom questions. Confirm each yes once. | The quotes show up. |
| 1:55 | "Breathing is a local wellness check on frames this call already saved." If the agent asks her to sit, she sits. If it never asks, say the wellness check was not on this call. | When the tool is in the agent: "Please sit still, with your chest and shoulders in the frame, for about 20 seconds." Then one line only: "About {n} a minute. That's just a wellness check." or "We can skip the breathing wellness check." | The breathing mode on the result, or absent. Wellness only. |
| 2:25 | "It waits for a nurse. I am not approving from the phone." | "I've sent this to your care team. Your nurse will review it." Then "I'll leave the details on the dashboard." | Tier chip. We are showing YELLOW going to nurse review. If the card says another tier, read that word. |
| 2:40 | "Nurse Jordan (mock). Approve. People can't be added to this call. Approving is a separate 1:1, and only after this. The nurse decides." | This call stays the patient and Homeward. Hang up when it wraps. No second check-in. | Type `Nurse Jordan (mock)` and press Approve. Status becomes approved. |

Do not run a 911 drill on this call. Do not promise a callback time.

If breathing speaks the skip line, or the pill read is weak, hang up. Do not place a second call.

## Backup: simulated call

Label the screen and the first sentence **simulated call**.

Say: "This is a simulated call. Mock data. Not a live FaceTime call. Not a medical device. A nurse still approves every escalation."

```bash
make demo-sim
```

That runs the Rosa day-3 fixture offline, with `MAC_DRY_RUN=1` and canned vision. On this fixture the printed approval is RED, with the missed-dose and symptom flags, then a nurse callback scheduled. Say RED when that is what it prints. Do not call this take YELLOW. Approve with `Nurse Jordan (mock)`, or point at the approval the command prints. The dry run does not dial.
