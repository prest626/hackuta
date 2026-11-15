// Care-team page. Polls the API. A nurse name is required before Approve.

export function sparkline(points) {
  const nums = (points || []).filter((n) => Number.isFinite(n));
  if (!nums.length) return "";
  const w = 120;
  const h = 32;
  const min = Math.min(...nums);
  const max = Math.max(...nums);
  const span = max - min || 1;
  const d = nums
    .map((v, i) => {
      const x = nums.length === 1 ? w / 2 : (i / (nums.length - 1)) * w;
      const y = h - ((v - min) / span) * (h - 2) - 1;
      return `${i ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(" ");
  return `<svg viewBox="0 0 ${w} ${h}" role="img"><path d="${d}" fill="none" stroke="currentColor" stroke-width="2"/></svg>`;
}

const POLL_MS = 2000;
let selected = null;
let painting = false;

function headers(json) {
  const h = {};
  if (json) h["Content-Type"] = "application/json";
  // shortcut: dashboard token is a shared secret in localStorage, upgrade = SSO
  const token = localStorage.getItem("dashboard_token");
  if (token) h.Authorization = `Bearer ${token}`;
  return h;
}

async function get(path) {
  const res = await fetch(path, { headers: headers(false) });
  if (res.status === 204) return null;
  if (!res.ok) throw new Error(String(res.status));
  return res.json();
}

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[ch]));
}

function strip(calls, results) {
  const cells = [];
  for (let day = 1; day <= 4; day += 1) {
    const call = (calls || []).find((row) => row.day_index === day);
    const result = call && (results || []).find((row) => row.call_id === call.id);
    let label = "—";
    if (result) label = result.status === "no_answer" ? "no answer" : result.tier || "—";
    else if (call && call.status === "in_call") label = "in call";
    else if (call && (call.status === "dialing" || call.status === "ringing")) label = "dialing";
    else if (call && call.status === "no_answer") label = "no answer";
    else if (call) label = "scheduled";
    cells.push(`<span class="cell ${esc(label)}">d${day} ${esc(label)}</span>`);
  }
  return `<div class="strip">${cells.join("")}</div>`;
}

function quotes(result) {
  const lines = (result.symptoms || []).filter((item) => item.quote);
  if (!lines.length) return "<p>not captured</p>";
  return lines.map((item) => `<p class="quote">“${esc(item.quote)}”</p>`).join("");
}

function breathing(result) {
  const b = result.breathing;
  if (!b || b.mode === "skipped" || b.rate_per_min == null) return "<p>Wellness check: not captured</p>";
  return `<p>Wellness check: ${esc(b.rate_per_min)} breaths/min</p>`;
}

function snapshot(result) {
  const v = result.vitals_snapshot;
  if (!v || v.hr_median_60s == null) return "<p>Vitals: not captured</p>";
  return `<p>Vitals snapshot: heart rate ${esc(v.hr_median_60s)}</p>`;
}

async function liveLine(id) {
  const live = await get(`/v1/patients/${id}/vitals/live`);
  const samples = await get(`/v1/patients/${id}/vitals?metric=hr`);
  if (!live || live.hr_median_60s == null) return "Live HR: not captured";
  const replay = samples[0] && samples[0].source === "mock_replay" ? " replay" : "";
  return `Live HR: ${live.hr_median_60s}${replay}`;
}

async function detail(patient, timeline) {
  const box = document.querySelector("#detail");
  const results = timeline.results || [];
  const latest = results[0];
  const hr = await liveLine(patient.id);
  if (!latest) {
    box.innerHTML = `<h2>${esc(patient.display_name)}</h2><p>${esc(hr)}</p><p>not captured</p>`;
    return;
  }
  const reasons = (timeline.flags || [])
    .filter((flag) => flag.call_id === latest.call_id)
    .map((flag) => esc(flag.reason));
  const proof = latest.proof_url
    ? `<img class="proof" alt="Pill organizer photo from the call" src="${esc(latest.proof_url)}">`
    : "<p>Pill photo: not captured</p>";
  const since = new Date(Date.now() - 7 * 864e5).toISOString();
  const rhr = await get(`/v1/patients/${patient.id}/vitals?metric=rhr&since=${encodeURIComponent(since)}`);
  const points = (rhr || []).map((sample) => sample.value).reverse();
  const listed = results
    .map((row) => `<li>Day ${esc(row.day_index)} ${esc(row.tier || "")} ${esc(row.status || "")}</li>`)
    .join("");
  box.innerHTML = `
    <h2>${esc(patient.display_name)}</h2>
    <p>${esc(hr)}</p>
    <p>Latest call: ${esc(latest.tier || "not captured")}</p>
    <p>${reasons.length ? reasons.join("; ") : "not captured"}</p>
    ${proof}
    ${quotes(latest)}
    ${breathing(latest)}
    ${snapshot(latest)}
    <p>Resting HR, 7 days</p>
    ${sparkline(points) || "<p>not captured</p>"}
    <ul>${listed}</ul>`;
}

async function paintPatients(patients) {
  const box = document.querySelector("#patients");
  const blocks = [];
  for (const patient of patients) {
    const timeline = await get(`/v1/patients/${patient.id}/timeline`);
    const hr = await liveLine(patient.id);
    blocks.push({ patient, timeline, hr });
  }
  box.innerHTML = blocks
    .map(({ patient, timeline, hr }) => `
      <button class="row" type="button" data-id="${esc(patient.id)}" aria-current="${patient.id === selected}">
        <strong>${esc(patient.display_name)}</strong>
        <span>day ${esc(patient.day_index)}</span>
        <span>${esc(patient.open_approvals)} open</span>
        <span>${esc(hr)}</span>
        ${strip(timeline.scheduled_calls, timeline.results)}
      </button>`)
    .join("");
  box.querySelectorAll(".row").forEach((btn) => {
    btn.addEventListener("click", () => {
      selected = btn.getAttribute("data-id");
      paint();
    });
  });
  const current = blocks.find((item) => item.patient.id === selected) || blocks[0];
  if (!current) {
    document.querySelector("#detail").textContent = "No mock patients yet.";
    return;
  }
  selected = current.patient.id;
  await detail(current.patient, current.timeline);
}

function actionField(row) {
  const options = ["nurse_callback", "clinician_group_call", "family_group_call", "family_imessage"];
  const opts = options
    .map((name) => `<option value="${name}"${name === row.action ? " selected" : ""}>${name}</option>`)
    .join("");
  return `<label>Proposed action <select data-action>${opts}</select></label>`;
}

async function paintQueue(names) {
  const box = document.querySelector("#queue");
  if (box.contains(document.activeElement)) return;
  const rows = await get("/v1/approvals?status=pending");
  const flags = await get("/v1/flags?status=open");
  const ranked = (rows || []).slice().sort((a, b) => {
    const rank = (row) => (row.tier === "RED" ? 0 : 1);
    return rank(a) - rank(b) || String(a.created_at).localeCompare(String(b.created_at));
  });
  box.innerHTML = ranked.length
    ? ranked.map((row) => {
        const reasons = (flags || [])
          .filter((flag) => (row.flag_ids || []).includes(flag.id))
          .map((flag) => esc(flag.reason))
          .join("; ");
        return `
          <article class="card" data-id="${esc(row.id)}">
            <p><strong>${esc(names[row.patient_id] || row.patient_id)}</strong> ${esc(row.tier)}</p>
            <p>${reasons || "not captured"}</p>
            ${actionField(row)}
            <p>${esc(row.brief_text)}</p>
            <label>Reason to deny <input data-reason name="reason"></label>
            <button type="button" data-decision="approve">Approve</button>
            <button type="button" data-decision="reject">Deny</button>
            <p data-status></p>
          </article>`;
      }).join("")
    : "<p>No pending escalations.</p>";
  box.querySelectorAll("button").forEach((btn) => {
    btn.addEventListener("click", () => decide(btn));
  });
}

async function watchStatus(id, node) {
  try {
    for (let i = 0; i < 8; i += 1) {
      const row = await get(`/v1/approvals/${id}`);
      node.textContent = row.status;
      if (["rejected", "executing", "executed", "failed"].includes(row.status)) return;
      await new Promise((resolve) => setTimeout(resolve, 1000));
    }
  } catch {
    return;
  }
}

async function decide(btn) {
  const card = btn.closest("article");
  const id = card.getAttribute("data-id");
  const nurse = document.querySelector("#nurse-name").value.trim();
  const note = card.querySelector("[data-reason]").value.trim();
  const action = card.querySelector("[data-action]").value;
  const res = await fetch(`/v1/approvals/${id}/decision`, {
    method: "POST",
    headers: headers(true),
    body: JSON.stringify({
      decision: btn.getAttribute("data-decision"),
      nurse_name: nurse,
      note: note || null,
      action_override: action,
      decided_at: new Date().toISOString(),
    }),
  });
  const node = card.querySelector("[data-status]");
  if (!res.ok) {
    node.textContent = res.status === 422 ? "Nurse name and a deny reason are required." : `Error ${res.status}`;
    return;
  }
  const body = await res.json();
  node.textContent = body.status;
  watchStatus(id, node);
}

async function paint() {
  if (painting || typeof document === "undefined") return;
  painting = true;
  try {
    const active = await get("/v1/calls/active");
    const patients = await get("/v1/patients");
    const names = {};
    (patients || []).forEach((patient) => {
      names[patient.id] = patient.display_name;
    });
    await paintPatients(patients || []);
    await paintQueue(names);
    document.querySelector("#active").textContent = active ? `Live call: ${active.state}` : "No live call";
  } catch (err) {
    document.querySelector("#patients").textContent = "The list could not be loaded.";
  } finally {
    painting = false;
  }
}

if (typeof document !== "undefined") {
  const nameInput = document.querySelector("#nurse-name");
  nameInput.value = localStorage.getItem("nurse_name") || "";
  nameInput.addEventListener("input", () => localStorage.setItem("nurse_name", nameInput.value));
  paint();
  setInterval(paint, POLL_MS);
}
