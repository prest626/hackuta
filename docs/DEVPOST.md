<!--
devpost_final.md: the paste-ready Devpost draft. Drafted Sun Nov 15, 2026, about 3:25 AM CT.
Final-pass instructions (after phase 2 merges, about 6:30 AM CT, and before submitting by 12:00 PM CT):
  - Markers left below are live-call results only. For each one, keep the shipped sentence OR the Fallback sentence, never both, then delete the marker.
  - Code facts (greeting, breathing off the loop, the 80% vision gate, the drawn face, the Maya 1:1) are already written as shipped. Do not put Simli in the built-with line.
  - Health stats stay AHRQ HCUP SB #307 and Jencks 2009. The 80% line is the vision-test pass bar in code, not another health stat.
-->

# Homeward

**A FaceTime check-in that looks, listens and asks, then waits for a nurse.**

> Homeward is a hackathon prototype. It is not a medical device. It gives no diagnosis and no dosing or treatment advice, it uses mock patient data only, and a named human nurse approves every escalation.

## Inspiration

In the *Odyssey*, Odysseus survives the war and the sea, and the most dangerous stretch is the last leg home. Leaving the hospital is like that: more than 1 in 5 heart-failure hospital stays is followed by a readmission within 30 days (22.3 per 100 stays in 2020, [AHRQ HCUP Statistical Brief #307](https://hcup-us.ahrq.gov/reports/statbriefs/sb307-readmissions-2020.jsp)), and 19.6% of Medicare patients were rehospitalized within 30 days ([Jencks et al., NEJM 2009](https://www.nejm.org/doi/full/10.1056/NEJMsa0803563)). When Odysseus finally reaches home in disguise, the first person to recognize him is Eurycleia, his old nurse, who knows him by a scar. We built Homeward around that idea: a call that notices something is off at home, and a nurse who decides what happens next.

## What it does

Homeward is a care agent that calls a patient on FaceTime in the first days after discharge. We demo it with a mock patient, Rosa, on day 3 after a heart-failure stay. On the phone, the patient only needs FaceTime: there's no new app, portal, or login. (In this prototype, heart rate comes from a separate small watchOS app, or from a labeled mock replay. See below.)

FaceTime is the app. The parts of the call that matter use the camera:

- **Looks at the pillbox.** "Can you hold up your pill organizer?" The agent first says "Hold the organizer still, facing the camera, about a foot away," and calls the pill check only after the patient confirms it is up. It waits about two seconds, takes the sharpest frame from the last 1.5 seconds, sends that one frame to a vision model, and compares the single row of seven day compartments with Rosa's med schedule and the dose times that have passed: empty, still full, or unknown. Saturday evening is still full, so it **asks** ("Did you take those from somewhere else?") and records a *possible* missed dose for the nurse. It never names a pill and never tells the patient to take, skip, or change a dose.
  [VERIFY AT FREEZE: The pillbox read in the demo is live, from the FaceTime frame.
  Fallback: In the demo video, the pillbox read uses a canned fixture result, labeled on screen as a fixture; the live vision path is built and runs with an API key.]
- **Listens and asks.** A short structured symptom check from Rosa's mock discharge plan: better, same or worse? More breathless on the stairs? Swollen ankles? Weight up? The agent confirms every "yes" once and stores the patient's own words.
- **Breathing wellness check (wellness only).** The agent asks Rosa to sit still with her chest in frame for about 20 seconds. The estimate runs off the audio loop, over that 20 second window of frames the call already saved. A measured rate is spoken as "About N a minute. That's just a wellness check." A poor signal is spoken as "We can skip the breathing wellness check."
  [IF SHIPPED: A live call after this tool landed spoke the rate line.
  Fallback: No live call since the tool landed has confirmed a spoken rate. Call 7, before the tool existed, abstained while the caller was moving.]
- **Heart rate in context.** The agent mentions one number, the heart rate compared with the patient's own usual resting rate from a 60-day mock history. In the demo, this is a **labeled mock replay** of Rosa's data. A watchOS app that streams live heart rate is built, but it isn't used in the demo.
- **A result, not a diagnosis.** Each call ends as a structured record. A small set of deterministic rules turns it into GREEN, YELLOW, or RED. The thresholds are demo placeholders that a patient's clinician would set in a real deployment.
  [VERIFY AT FREEZE: Our recorded day-3 call came out RED (symptoms plus a resting heart-rate drift).
  Fallback: Our recorded live calls came out YELLOW and went to nurse review. RED is covered by the CI test suite and the simulated call.]

### A nurse approves every step

Nothing leaves the call without a person. A YELLOW or RED result lands on the care-team dashboard with the evidence attached: the reasons, the patient's own words, the annotated pillbox frame, and the heart-rate trend. Homeward only *proposes* an escalation. A named nurse reads the evidence and clicks **Approve**, or doesn't. The database and the tests require a named nurse approval before any escalation call can be placed, and there's exactly one place in the code that can dial. The language model can raise a concern, but it can't lower a tier, can't push breathing or its own concern above YELLOW, and can't call anyone.

After a named nurse approves, Homeward places a separate 1:1 call to the nurse, or to Maya, the mock emergency contact. Nothing dials before that name. The handoff, when the approved call is answered, starts "Hi, this is Homeward, an automated prototype from the care team."
[IF SHIPPED: The demo shows that separate call live.
Fallback: The callback is built and exercised in the simulated call. The demo has not yet shown the live ring.]

**Why a separate call?** Chert can start a group FaceTime call, but everyone has to be named when the call is placed. People can't be added to a live call, and group calling is turned on line by line. So after the nurse approves, Homeward places a separate 1:1 to the nurse or to Maya. It does not add a person to the live check-in. The patient's call never changes without a human decision.

### What's AI, and what isn't

- **AI:** the conversation (OpenAI Realtime, through LiveKit) and the pillbox read (gpt-4.1 by default, `OPENAI_VISION_MODEL` to override, returning structured JSON; Gemini 2.5 Flash is supported as an alternative).
- **Not AI:** the tier (a rules file), the approval gate, the call scheduler, and the safety-critical sentences. Those are fixed scripted lines spoken through text-to-speech, so the model can't paraphrase them. If a patient describes an emergency, the 911 line is chosen by code outside the model, and it's a fixed sentence.

### Safety, privacy and disclosure

- **Safety:** fixed scripted lines for anything safety-critical, plus a CI check that flags known dosing and diagnosis phrasing across the codebase. The database and the tests require a named nurse approval before any escalation call. The CI check is a backstop, not a guarantee. The primary controls are the fixed lines and the human gate.
- **Privacy:** only the single selected pillbox frame is sent to the vision model, not a video stream. The model's free-text reasoning is dropped, never spoken or stored. Only the structured result is kept. Every patient record in this project is mock data, and a test fails the build if a non-mock patient appears.
- **Disclosure and consent:** the agent introduces itself as an automated assistant for the care team ("Hi, I'm Homeward, an automated assistant for your care team. This is a prototype, and not a medical device."). It doesn't claim to be a doctor or a nurse. In a real deployment, patients would choose the call time and could opt out at any time.

## How we built it

- **FaceTime call:** [Chert](https://trychert.com/uta) bridges the FaceTime call into a LiveKit room, where a Python agent (`chert/agent.py`, `chert/homeward.py`, `chert/wire.py`, run as `python -m chert.agent`) runs the conversation on OpenAI Realtime. Chert has no tool calling, no transfer, and no avatar of its own, so the tools live in that LiveKit agent. Only one participant may publish audio. `chert/media.py` pulls video frames for vision. A second path, built as a fallback when the hosted line was unstable, runs FaceTime on our own spare Mac: BlackHole virtual audio pipes the call to OpenAI Realtime (`facetime-bridge/bridge.mjs`), and AppleScript answers and dials.
  The prompt adds one tone line: kind and straight to the point, one or two short sentences, warm, never cute. The greeting says it is an automated assistant for the care team, a prototype, and not a medical device. It does not claim to be a clinician.
  `CHERT_FACE` defaults off, so the call is voice only. `fallback` draws a face on the same participant and publishes no extra audio. `simli` is a guarded path that skips while the agent is publishing audio. We do not claim Simli works.
- **Vision:** `vision/pills.py` reads the pillbox compartments against the schedule and returns empty, not-empty, or unknown. `vision/breath.py` estimates the breathing rate locally with NumPy and OpenCV (frame motion, then an FFT, then a peak in the breathing band, abstaining on a low-quality signal). An offline eval harness scores the pill read on 14 synthetic pillbox images and 33 public, Creative Commons–licensed pillbox photos with our own labels.
  `make vision-test` is the demo gate. It scores real frames in `vision/eval/preston/` against `vision/eval/preston/labels.json` once those photos are on disk, and the pill line passes at 80% or better. The synthetic set under `vision/eval/photos` is a report only (`python -m vision.eval`), not the gate. It also prints an information-only breathing line from real call frames when those frames are on disk. That line does not decide pass or fail. Pill-read accuracy on real photos of our own is not yet measured. The 80% figure is the pass bar, not a score from a live run.
- **Backend:** FastAPI with SQLite: patients, schedules, calls, flags, approvals. A rules file (`api/rules.yaml`) with caps, a call scheduler, and an approvals module. JSON Schema contracts shared by every part of the system.
- **Heart rate:** a watchOS app (SwiftUI, workout session) posts heart rate through a Cloudflare tunnel to the ingest API. `python -m ingest.replay` posts labeled mock heart rate when the watch is off, from a 60-day mock history with a deliberate resting-rate drift for Rosa.
- **Dashboard:** plain HTML, CSS, and JavaScript: tier, reasons, quotes, pillbox frame, a heart-rate sparkline, and the Approve button.
- **Tests:** GitHub Actions CI runs the full unit suite and an end-to-end simulated Rosa day-3 call through every component with `MAC_DRY_RUN=1 VISION_FAKE=fixtures`, plus the safety audit. The full end-to-end flow has been proven in CI and the simulation. On live calls, we've run the parts the demo shows.

### How we used Cursor and Grok Bot

Homeward has one human developer, Preston, working with a team of AI agents:

- **A project-manager agent (watson, on Grok Bot)** wrote the PRD, broke it into GitHub issues, and coordinated everything on a pinned board issue (#1), assigning lanes, reviewing plans, and posting decisions.
- **Cursor cloud coding agents** each owned a lane (call agent, Chert wiring, vision, API, approvals and scheduler, dashboard, watch, demo tooling). They claimed issues and opened PRs.
- **Agents on two Macs** ran the parts that cloud agents can't reach: FaceTime, BlackHole audio, AppleScript, and the Xcode watch build. One of the Macs is the spare Mac that answers the calls.
- **Research and video agents** checked the hackathon rules and every citation, critiqued our pitch, and rendered the animated explainer.
- **Plan-first PRs:** every change starts as a plan PR, followed by its implementation PR. You can see the pattern throughout the commit history.
- **Safety-audit CI:** every PR runs the test suite, the simulated end-to-end call, and the safety audit (dosing and diagnosis phrasing, one dial caller, the approval gate, mock patients only) before it can merge.

## Challenges we ran into

- **Getting eyes and ears out of FaceTime.** FaceTime isn't an API. When the hosted Chert line was unstable during setup, we built our own spare-Mac bridge as a fallback. Both paths feed the same backend contract.
- **Choosing which frame to trust.** The pill read uses the sharpest frame from the last 1.5 seconds, after a short hold, and it answers "unknown" when the box is blurred, angled, or covered.
- **Keeping a realtime voice model on script.** It likes to paraphrase. Safety-critical lines go through fixed text-to-speech instead.
- **Being kind without playing doctor.** The agent asks; it never advises.
- An end reason outside the six allowed values is stored as `agent_hangup`, and a duplicate result is idempotent. Call 7 sent `check-in complete` and `finish_call` failed on that build.
  [VERIFY AT FREEZE: A live call after that coercion posted a result with no finish_call error.
  Fallback: No later live call has confirmed the coercion. Call 7 failed before it.]

## What call 7 taught us

Call 7 ended YELLOW, on the build before these tools. The markers left in this draft are live-call results only. Watson keeps the shipped sentence or the Fallback sentence, never both.

- Breathing did not run. That build registered `get_vitals`, `check_pillbox`, `record_answer`, and `finish_call` only. Frames did arrive, about 15 fps at 1280×720, under the call's frame directory. An offline wellness check on those frames abstained while the caller was moving. The agent now measures off the audio loop, over a 20 second window, and does not call `POST /v1/vision/breathing`. Whether a later live call speaks a rate is the marker above.
- The pill check raised `OpenAIError`. The API process had no vision key. A key that lives only beside the spare-Mac bridge does not reach that process. No key is written in this draft.
- `get_vitals` spoke a heart-rate number from a labeled mock replay as if it were the watch. A mock replay now says "The mock replay shows {hr}. It is not a live watch reading." A stale reading says "I don't have a fresh watch reading right now."
- `finish_call` was sent with an end reason outside the six allowed values. The code now stores `agent_hangup` for that case. A later live confirmation is the marker above.

## Accomplishments that we're proud of

- A FaceTime agent whose core checks need the camera, not just the microphone.
- A human-in-the-loop gate that's enforced by the database and the tests, not by a prompt.
- Two independent FaceTime paths into one backend.
- A complete simulated patient journey (days 1, 2 and 4 GREEN; day 3 escalated) that runs in CI on every PR.
- Built by one person plus a team of agents in 24 hours.

## What we learned

The reliable parts of an AI health tool are the deterministic ones: contracts, rules, fixed lines, and a named human. The model's job is the conversation. In this domain, the goal isn't "the agent decides". It's **"the agent notices, a nurse decides."**

## What's next

- Measure pill-read accuracy on real photos of our own, and report the unknown rate.
- Send the annotated pillbox back to the patient as the agent's own FaceTime video.
- Clinician-written question sets and thresholds per condition.
- iMessage reminders before each call.
- A supervised pilot, under proper clinical, privacy, and regulatory review, to measure alarm burden and time-to-callback. **We make no claim that Homeward reduces readmissions. That needs a study.**

## Prior art

AI follow-up calls after discharge already exist, voice only. Onset (Emory Hacks 2026) built a FaceTime health check-in on Chert, and Chert's own idea list includes medication setup. Our contribution is the combination: proactive check-ins in the first days home, a pillbox read against *this* patient's schedule, heart rate against the patient's own baseline, and a nurse approval on every escalation.

## Built with

`chert` · `facetime` · `livekit` · `livekit-agents` · `openai-realtime` · `openai` (gpt-4o-mini vision, TTS) · `google-genai` (Gemini 2.5 Flash, optional) · `python` · `fastapi` · `uvicorn` · `httpx` · `sqlite` · `pyyaml` · `numpy` · `opencv` · `pillow` · `json-schema` · `pytest` · `uv` · `node.js` · `ws` · `blackhole` · `applescript` · `swift` · `swiftui` · `watchos` · `cloudflare-tunnel` · `html` · `css` · `javascript` · `github-actions` · `cursor` · `grok-bot`

**Links:** GitHub: https://github.com/prest626/hackuta · Video: <PASTE URL>

---

## Track checklist (internal, don't paste)

- [ ] **Chert: Best Use of FaceTime.** Select "Best Use of FaceTime (Chert)" on Devpost. Built on Chert's FaceTime API ✔. The demo must include a live call (makes or takes a FaceTime call). Bring an iPhone. Lead with what the camera does live. Rules: https://trychert.com/uta
- [ ] **[MLH] Build Your Hackathon A-Team with SpaceXSI (Cursor + Grok Bot raffle).** The "How we used Cursor and Grok Bot" section above ✔. **Opt in to the raffle when you submit.** Rules: https://hackuta-8.devpost.com/
- [ ] **General Track.** Judged on Robustness, Theme (Homer's *Odyssey*) and Creativity. The Inspiration paragraph covers the theme. [UNVERIFIED whether it needs an explicit selection]
- [x] **Skip: Best Project Built with ElevenLabs.** The call voice isn't ElevenLabs. Don't make any ElevenLabs claim.
- [x] **Skip: Hardware, Gemini, and the other MLH tracks** (Gemini is optional and not in the demo path; there's no hardware build).
- [ ] Before submitting: the README describes the Chert → LiveKit path (not only the spare-Mac bridge); the video is 30 s–2:00 and uploaded; the GitHub URL is set; the remaining "[IF SHIPPED" and "[VERIFY" markers are resolved from the live demo, then deleted.
- [ ] Submit by **12:00 PM CT** (Devpost deadline, confirmed).
