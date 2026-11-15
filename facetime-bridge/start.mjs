// Picks the voice backend. VOICE=elevenlabs in .env.local, otherwise OpenAI (bridge.mjs, unchanged).
await import(process.env.VOICE === 'elevenlabs' ? './elevenlabs.mjs' : './bridge.mjs');
