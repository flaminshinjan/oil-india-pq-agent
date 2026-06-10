/**
 * Browser-side audio plumbing for the Pipecat voice session.
 *
 * Input  : capture mic via getUserMedia → ScriptProcessor / AudioWorklet →
 *          16 kHz PCM 16-bit mono → send raw binary frames over WebSocket.
 * Output : binary frames from server are 24 kHz PCM 16-bit mono → push into
 *          an AudioContext destination via a streaming source so playback
 *          starts immediately.
 *
 * The matching wire format is what Pipecat's `FastAPIWebsocketTransport`
 * expects when `add_wav_header=False` and the sample rates above are set
 * in `PipelineParams`.
 */

const MIC_SAMPLE_RATE = 16_000;   // sent to server
const TTS_SAMPLE_RATE = 24_000;   // received from server

export type VoiceState =
  | { kind: 'idle' }
  | { kind: 'connecting' }
  | { kind: 'live'; speaking: boolean }
  | { kind: 'ending' }
  | { kind: 'error'; message: string };

export interface VoiceSession {
  stop(): Promise<void>;
}

interface StartOpts {
  wsUrl: string;
  onState: (s: VoiceState) => void;
  onTranscript?: (text: string, role: 'user' | 'ai', final: boolean) => void;
}

/** Open a voice session. Resolves once the WebSocket is connected. */
export async function startVoiceSession(opts: StartOpts): Promise<VoiceSession> {
  opts.onState({ kind: 'connecting' });

  // 1. Mic stream
  let mediaStream: MediaStream;
  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        sampleRate: MIC_SAMPLE_RATE,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    });
  } catch (e: any) {
    opts.onState({ kind: 'error', message: 'Mic permission denied' });
    throw e;
  }

  // 2. AudioContext for capture + playback. We REQUEST 16 kHz, but many
  // browsers (esp. Safari/iOS and some Chrome configs) silently use the
  // device's native rate (usually 48 kHz) and ignore the constructor arg.
  // We check the actual rate and downsample on the fly so what reaches
  // Deepgram is always genuine 16 kHz PCM.
  const Ctx: typeof AudioContext =
    (window as any).AudioContext || (window as any).webkitAudioContext;
  const captureCtx = new Ctx({ sampleRate: MIC_SAMPLE_RATE });
  const playbackCtx = new Ctx({ sampleRate: TTS_SAMPLE_RATE });
  let nextPlaybackTime = playbackCtx.currentTime;

  const actualMicRate = captureCtx.sampleRate;
  const downsample = actualMicRate / MIC_SAMPLE_RATE; // 1 if honoured, ~3 on 48 kHz
  // eslint-disable-next-line no-console
  console.log(
    `[voice] capture rate requested=${MIC_SAMPLE_RATE} actual=${actualMicRate}` +
    ` downsample=${downsample.toFixed(3)}`
  );

  const source = captureCtx.createMediaStreamSource(mediaStream);

  // 3. Mic → Float32 → Int16 LE → WS binary
  // ScriptProcessorNode is deprecated but works everywhere; AudioWorklet
  // is the modern path but requires a separate worklet file.
  const proc = captureCtx.createScriptProcessor(4096, 1, 1);
  source.connect(proc);
  proc.connect(captureCtx.destination); // required by some browsers to fire

  // 4. WebSocket — connect to backend
  const ws = new WebSocket(opts.wsUrl);
  ws.binaryType = 'arraybuffer';

  proc.onaudioprocess = (ev: AudioProcessingEvent) => {
    if (ws.readyState !== WebSocket.OPEN) return;
    const ch = ev.inputBuffer.getChannelData(0);
    const outLen = Math.max(1, Math.floor(ch.length / downsample));
    const pcm = new Int16Array(outLen);
    // Nearest-neighbour downsample — adequate for speech and cheaper than
    // a proper FIR. For downsample === 1 this is a no-op resample.
    for (let i = 0; i < outLen; i++) {
      const srcIdx = Math.floor(i * downsample);
      const v = Math.max(-1, Math.min(1, ch[srcIdx]));
      pcm[i] = v < 0 ? v * 0x8000 : v * 0x7fff;
    }
    ws.send(pcm.buffer);
  };

  ws.onopen = () => {
    opts.onState({ kind: 'live', speaking: false });
  };

  ws.onmessage = (ev: MessageEvent) => {
    if (typeof ev.data === 'string') {
      // Pipecat may send JSON control frames (transcripts, state) —
      // surface them via the optional callback.
      try {
        const m = JSON.parse(ev.data) as any;
        if (m?.type === 'transcript' && typeof m.text === 'string') {
          opts.onTranscript?.(m.text, m.role || 'ai', !!m.final);
        }
      } catch {/* ignore */}
      return;
    }
    if (ev.data instanceof ArrayBuffer) {
      schedulePCM(ev.data);
    }
  };

  ws.onerror = () => {
    opts.onState({ kind: 'error', message: 'Connection error' });
  };

  ws.onclose = () => {
    opts.onState({ kind: 'idle' });
  };

  /** Schedule a chunk of 16-bit PCM (server → speaker), back-to-back so
   *  playback is gapless. */
  function schedulePCM(buf: ArrayBuffer) {
    const pcm = new Int16Array(buf);
    const f32 = new Float32Array(pcm.length);
    for (let i = 0; i < pcm.length; i++) f32[i] = pcm[i] / 0x8000;

    const audioBuf = playbackCtx.createBuffer(1, f32.length, TTS_SAMPLE_RATE);
    audioBuf.copyToChannel(f32, 0);
    const src = playbackCtx.createBufferSource();
    src.buffer = audioBuf;
    src.connect(playbackCtx.destination);

    const now = playbackCtx.currentTime;
    const startAt = Math.max(now, nextPlaybackTime);
    src.start(startAt);
    nextPlaybackTime = startAt + audioBuf.duration;

    opts.onState({ kind: 'live', speaking: true });
    src.onended = () => {
      if (playbackCtx.currentTime + 0.05 >= nextPlaybackTime) {
        opts.onState({ kind: 'live', speaking: false });
      }
    };
  }

  return {
    async stop() {
      opts.onState({ kind: 'ending' });
      try {
        ws.close();
      } catch {/* ignore */}
      proc.disconnect();
      source.disconnect();
      mediaStream.getTracks().forEach(t => t.stop());
      try {
        await captureCtx.close();
      } catch {/* ignore */}
      try {
        await playbackCtx.close();
      } catch {/* ignore */}
      opts.onState({ kind: 'idle' });
    },
  };
}

/** Resolve the WebSocket URL relative to the current origin.
 *
 *  Optional `domain` query param hints to the server which dashboard the
 *  user is currently viewing — the RAG injector boosts that domain's
 *  signals so "what about this quarter?" can resolve in context.
 */
export function voiceWsUrl(domain?: string): string {
  if (typeof window === 'undefined') return '';
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const qs = domain ? `?domain=${encodeURIComponent(domain)}` : '';
  return `${proto}//${window.location.host}/api/voice/ws${qs}`;
}
