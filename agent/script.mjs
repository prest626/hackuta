// Demo length, not a platform cap: wrap the patient at 4:15 and hang up at 5:00.
export const MARKS = [
  ['greet', 10_000],
  ['vitals', 30_000],
  ['pill', 105_000],
  ['symptoms', 180_000],
  ['breathing', 225_000],
  ['wrap', 255_000],
  ['stop', 300_000],
];

export const WRAP_MS = 255_000;
export const STOP_MS = 300_000;
export const WRAP_LINE = "Let's wrap up.";
export const CLOSE_LINE = "I'll leave the details on the dashboard.";

let handles = [];

export function stepAt(ms) {
  for (const [name, end] of MARKS) {
    if (ms < end) return name;
  }
  return 'stop';
}

export function arm({ say, finish, schedule = setTimeout, cancel = clearTimeout } = {}) {
  disarm(cancel);
  const wrap = schedule(() => say(WRAP_LINE), WRAP_MS);
  const stop = schedule(() => finish({ status: 'partial', end_reason: 'hard_stop' }), STOP_MS);
  if (wrap?.unref) wrap.unref();
  if (stop?.unref) stop.unref();
  handles = [
    [wrap, cancel],
    [stop, cancel],
  ];
}

export function disarm(cancel = clearTimeout) {
  for (const [handle, cancelHandle] of handles) {
    try {
      (cancelHandle || cancel)(handle);
    } catch {
      // a fake timer handle is not a real timeout
    }
  }
  handles = [];
}

// brief_text is capped at 400 characters; 280 keeps the spoken brief near 20 seconds.
export function escalationLines(approval, patient) {
  const fromContact = patient?.contacts?.find((contact) => contact.role === 'nurse')?.name;
  const nurse = approval?.decision?.nurse_name || fromContact || 'the nurse';
  const raw = String(approval?.brief_text || '').trim();
  const brief = raw.length <= 280 ? raw : `${raw.slice(0, 277)}...`;
  return {
    brief,
    opening: [brief, `Is this ${nurse}?`].filter(Boolean).join(' '),
    close: CLOSE_LINE,
  };
}
