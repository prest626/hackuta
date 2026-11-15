---
name: hackathon-idea-prd
description: >-
  Use when the user wants a hackathon or product idea stress-tested and turned
  into an engineering-ready PRD: prior art, SWOT, how it works, tech stack, team
  work split, demo script.
---
# Hackathon idea to PRD

Turns one project idea into a researched, engineering-ready Product Requirements Document that system designers, product designers, and engineers can split up and build from.

## Gather context first
1. The idea in one or two sentences, plus the intended demo moment.
2. The event: name, dates, team size, hacking window, judging format and rubric (check the event site and its MLH or Devpost page).
3. Sponsor prize tracks and what each one asks for, from the event's prize page.
4. Hardware available on site (e.g. the MLH hardware lab list) and anything the team owns.
5. Any constraints the user gave (time, skills, must-use tech).
Look these up yourself with web search before asking the user.

## Research and write (hand to a background knowledge worker)
Give it a self-contained brief with all the context above and ask for a .docx plus a Markdown copy under /workspace/prd/. Require real research with inline cited sources, no invented data, and estimates labeled as estimates. Required sections:
1. Executive summary, one-line pitch, and a problem statement with cited stats.
2. First-principles analysis: what judges reward, why this wins, the demo moment.
3. Prior art: academic work, commercial products, regulatory status where relevant, and past hackathon projects (search Devpost). For each, what it does and in what setting, and how this project differs. Be honest about what has been done and name the defensible novel angle.
4. SWOT table.
5. How it actually works, step by step, including accuracy or technical limits and mitigations.
6. System architecture with mermaid diagrams.
7. Specific tech stack with versions and reasons, repo structure, data schemas, APIs.
8. Personas, user stories, functional and non-functional requirements, MVP vs stretch cut lines.
9. Work breakdown by role with an hour-by-hour timeline, milestones, dependencies, and handoff checkpoints.
10. A demo script that fits the pitch length, likely judge Q&A with answers, and a fallback if the live demo fails.
11. Risks, ethics, privacy, and a validation plan.
12. A sponsor track mapping table: track, how we use it, what that track's judges want.
13. Sources.
Ask it to report the file paths, the five most important findings (especially prior art and the novel angle), and anything it could not verify.

## Deliver
Attach the .docx, then in a short message lead with the biggest finding (usually whether it has been done before and the angle that still wins), plus the few things the team must act on today. Pass along the unverified items plainly.
