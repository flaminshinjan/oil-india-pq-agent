'use client';
/**
 * Voice control for the chat panel.
 *
 * Idle  → mic icon, click starts a Pipecat voice session.
 * Live  → red dot + pulsing ring, click stops.
 * Speaking → ring oscillates while Strata speaks.
 * Error → reverts to idle and surfaces a tooltip.
 *
 * Backend availability is probed once via /api/voice/status — if the
 * voice keys aren't configured we just hide the button entirely.
 */
import { useEffect, useRef, useState } from 'react';

import { Icon } from './Icon';
import { startVoiceSession, voiceWsUrl, type VoiceSession, type VoiceState } from '@/lib/voice';

interface Props {
  /** Fires for every transcript event from the live voice session — both
   *  the user's recognised speech and Strata's spoken reply. The parent
   *  uses this to mirror the conversation into the chat thread. */
  onTranscript?: (text: string, role: 'user' | 'ai', final: boolean) => void;
  /** Currently active dashboard. Sent to the voice WS so the LLM has
   *  the same context the user sees. */
  domain?: string;
}

export function VoiceButton({ onTranscript, domain }: Props = {}) {
  const [available, setAvailable] = useState<boolean | null>(null);
  const [state, setState] = useState<VoiceState>({ kind: 'idle' });
  const sessionRef = useRef<VoiceSession | null>(null);

  // Probe availability once.
  useEffect(() => {
    fetch('/api/voice/status')
      .then(r => r.json())
      .then(d => setAvailable(!!d?.available))
      .catch(() => setAvailable(false));
  }, []);

  // Clean up on unmount.
  useEffect(() => () => { sessionRef.current?.stop(); }, []);

  if (available === null) return null;       // probing
  if (available === false) return null;       // keys not set on server

  const isLive = state.kind === 'live' || state.kind === 'connecting';

  async function toggle() {
    if (isLive) {
      await sessionRef.current?.stop();
      sessionRef.current = null;
      return;
    }
    try {
      sessionRef.current = await startVoiceSession({
        wsUrl: voiceWsUrl(domain),
        onState: setState,
        onTranscript,
      });
    } catch {
      sessionRef.current = null;
      setState({ kind: 'idle' });
    }
  }

  let label = 'Talk to Strata';
  if (state.kind === 'connecting') label = 'Connecting…';
  else if (state.kind === 'live') label = state.speaking ? 'Strata is speaking' : 'Listening…';
  else if (state.kind === 'ending') label = 'Stopping…';

  return (
    <button
      className={
        'voice-btn ' +
        (state.kind === 'live'
          ? state.speaking ? 'voice-speaking' : 'voice-listening'
          : state.kind === 'connecting' ? 'voice-connecting'
          : '')
      }
      onClick={toggle}
      title={label}
      aria-label={label}
      aria-pressed={isLive}
    >
      <span className="voice-btn-ring" aria-hidden />
      <span className="voice-btn-glyph">
        {isLive ? <Icon name="close" size={15} /> : <MicIcon />}
      </span>
    </button>
  );
}

function MicIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none"
         stroke="currentColor" strokeWidth="1.6"
         strokeLinecap="round" strokeLinejoin="round">
      <rect x="9" y="3" width="6" height="11" rx="3" />
      <path d="M5 11a7 7 0 0 0 14 0" />
      <line x1="12" y1="18" x2="12" y2="21" />
      <line x1="9" y1="21" x2="15" y2="21" />
    </svg>
  );
}
