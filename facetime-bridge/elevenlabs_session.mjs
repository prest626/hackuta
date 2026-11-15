// Protocol only: no sockets, sox, or env. elevenlabs.mjs owns the wire.
export const ENGLISH = '\n\nAlways speak English unless the caller asks for another language.';

export function initMessage(instructions, firstMessage) {
  return {
    type: 'conversation_initiation_client_data',
    conversation_config_override: {
      agent: {
        prompt: { prompt: instructions + ENGLISH },
        first_message: firstMessage,
      },
    },
  };
}

export function createSession({ agent, send, play, interrupt, speakFixed, log = console.log }) {
  const session = {
    holding: false,
    async onMessage(event) {
      const type = event?.type;
      if (type === 'conversation_initiation_metadata') {
        const meta = event.conversation_initiation_metadata_event || {};
        log(`[bridge] formats in=${meta.user_input_audio_format} out=${meta.agent_output_audio_format}`);
        if (meta.user_input_audio_format !== 'pcm_16000' || meta.agent_output_audio_format !== 'pcm_16000') {
          log('[bridge] warning: expected pcm_16000');
        }
        return;
      }
      if (type === 'audio') {
        if (session.holding) return;
        const b64 = event.audio_event?.audio_base_64;
        if (b64) play(Buffer.from(b64, 'base64'));
        return;
      }
      if (type === 'interruption') {
        interrupt();
        return;
      }
      if (type === 'ping') {
        send({ type: 'pong', event_id: event.ping_event?.event_id });
        return;
      }
      if (type === 'user_transcript') {
        const said = event.user_transcription_event?.user_transcript || '';
        log(`[bridge] caller: ${said}`);
        const line = agent.onTranscript(said);
        if (line) await speakFixed(line);
        return;
      }
      if (type === 'agent_response') {
        log(`[bridge] agent: ${event.agent_response_event?.agent_response ?? ''}`);
        return;
      }
      if (type === 'agent_response_correction') {
        log(`[bridge] agent: ${event.agent_response_correction_event?.corrected_agent_response ?? ''}`);
        return;
      }
      if (type === 'client_tool_call') {
        const call = event.client_tool_call || {};
        log(`[bridge] tool ${call.tool_name}`);
        const result = await agent.onToolCall(call.tool_name, call.parameters);
        let parsed = null;
        try {
          parsed = JSON.parse(result);
        } catch {
          parsed = null;
        }
        send({
          type: 'client_tool_result',
          tool_call_id: call.tool_call_id,
          result,
          is_error: !parsed?.ok,
        });
        if (parsed?.fixed && parsed.say) await speakFixed(parsed.say);
        return;
      }
      if (type === 'client_error') {
        log(`[bridge] client_error: ${event.message || event.client_error_event?.message || ''}`);
      }
    },
  };
  return session;
}
