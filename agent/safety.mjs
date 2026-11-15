export const EMERGENCY_LINE = 'This could be serious. Please hang up and call 911 now.';

// shortcut: substring match with a one-word "not"/"no" skip, upgrade = a real negation parse
function negated(hay, at) {
  const before = hay.slice(Math.max(0, at - 4), at);
  return before.endsWith('not ') || before.endsWith('no ');
}

export function urgentLine(text, phrases) {
  if (!text || !phrases?.length) return null;
  const hay = String(text).toLowerCase();
  for (const phrase of phrases) {
    const needle = String(phrase).toLowerCase().trim();
    if (!needle) continue;
    let from = 0;
    while (from < hay.length) {
      const at = hay.indexOf(needle, from);
      if (at === -1) break;
      if (!negated(hay, at)) return EMERGENCY_LINE;
      from = at + needle.length;
    }
  }
  return null;
}
