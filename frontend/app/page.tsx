'use client';
/**
 * Digby · intelligence OS — landing page.
 *
 * Editorial in tone, rich in visuals. Same design tokens as the dashboard
 * so the product feels like one thing.
 *
 * Sections:
 *   1.  Sticky brand bar  ← always-on CTA to /dashboard
 *   2.  Hero              ← serif headline, animated dot, two CTAs
 *   3.  Live stats strip  ← real numbers from /api/{health,voice/status,sources/list}
 *                            counters animate from 0 → actual value
 *   4.  Brief preview     ← embedded mock of the dashboard's morning brief
 *   5.  Capabilities      ← six-card grid, one per domain agent
 *   6.  Voice showcase    ← speech-bubble flow demonstrating the voice loop
 *   7.  Architecture      ← stack row (LangGraph + Anthropic + Chroma + …)
 *   8.  Bottom CTA band
 *   9.  Footer
 */
import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';

interface Health {
  status?: string;
  vector_store?: { pq?: number; db?: number };
}

interface VoiceStatus {
  available?: boolean;
  stt?: string | null;
  tts?: string | null;
}

const CAPABILITIES = [
  {
    eyebrow: 'Reserves & Production',
    title: 'Crude, gas, and the gap to plan',
    body: 'Tracks 10 years of crude (MMT), gas (MMSCM/BCM), RRR and accretion. Surfaces the FY plan vs achievement live from the latest annexure.',
    icon: '⛽',
  },
  {
    eyebrow: 'Exploration & Drilling',
    title: 'Wells drilled vs wells planned',
    body: 'Exploratory and development drilling progress, 2P reserves trend, Andaman context — pulled directly from OIL’s performance annexures.',
    icon: '◉',
  },
  {
    eyebrow: 'HSE · Safety',
    title: 'Live PPE feed alongside LTIFR',
    body: 'CV-pipeline detections per site / shift / type, plus rolling 7-day windows. Cross-checked against BRSR Principle 3 disclosures.',
    icon: '⚠',
  },
  {
    eyebrow: 'HR · Workforce',
    title: 'Headcount, attrition, time-to-fill',
    body: 'Per-function TTM attrition vs 5-yr baseline, open requisitions, median weeks-to-fill — flags drift before it shows up in board packs.',
    icon: '✦',
  },
  {
    eyebrow: 'Parliamentary Replies',
    title: 'Cites the PQ before you ask',
    body: 'Indexed Lok Sabha + Rajya Sabha replies. Every numeric answer is traced back to the source filename.',
    icon: '§',
  },
];

export default function Landing() {
  const [health, setHealth] = useState<Health | null>(null);
  const [voice, setVoice] = useState<VoiceStatus | null>(null);
  const [sourceCount, setSourceCount] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      fetch('/api/health').then(r => r.json()).catch(() => null),
      fetch('/api/voice/status').then(r => r.json()).catch(() => null),
      fetch('/api/sources/list').then(r => r.json()).catch(() => null),
    ]).then(([h, v, s]) => {
      if (cancelled) return;
      if (h) setHealth(h);
      if (v) setVoice(v);
      if (s && typeof s.count === 'number') setSourceCount(s.count);
    });
    return () => { cancelled = true; };
  }, []);

  const pqChunks = health?.vector_store?.pq ?? null;
  const dbChunks = health?.vector_store?.db ?? null;
  const ready = health?.status === 'ok';

  const fyLabel = (() => {
    const now = new Date();
    const y = now.getFullYear();
    const m = now.getMonth() + 1;
    const start = m >= 4 ? y : y - 1;
    return `FY ${start}-${String((start + 1) % 100).padStart(2, '0')}`;
  })();

  return (
    <div className="landing">
      {/* ambient orbs floating behind the hero */}
      <div className="lh-orbs" aria-hidden>
        <span className="lh-orb lh-orb-a" />
        <span className="lh-orb lh-orb-b" />
        <span className="lh-orb lh-orb-c" />
      </div>

      {/* --- Sticky brand bar --- */}
      <header className="lh-bar">
        <div className="lh-bar-in">
          <Link href="/" className="lh-brand">
            <span className="lh-brand-mark" aria-hidden>
              <img src="/oil-logo.png" alt="Digby" className="lh-brand-logo" />
            </span>
            <span className="lh-brand-text">
              <span className="lh-brand-name">DIGBY</span>
              <span className="lh-brand-sub">intelligence OS · Oil India</span>
            </span>
          </Link>
          <nav className="lh-bar-nav">
            <a className="lh-bar-link" href="#preview">Preview</a>
            <a className="lh-bar-link" href="#capabilities">Capabilities</a>
            <a className="lh-bar-link" href="#voice">Voice</a>
            <Link href="/dashboard" className="lh-cta">
              Open dashboard <span aria-hidden>→</span>
            </Link>
          </nav>
        </div>
      </header>

      {/* --- Hero (Digboi scene) --- */}
      <section className="lh-hero">
        <div className="lh-hero-bg" aria-hidden />
        <div className="lh-hero-veil" aria-hidden />

        {/* 1889 Digboi stamp */}
        <div className="lh-stamp" aria-hidden>
          <svg viewBox="0 0 140 140" className="lh-stamp-svg">
            <circle cx="70" cy="70" r="66" className="lh-stamp-ring" />
            <circle cx="70" cy="70" r="57" className="lh-stamp-ring lh-stamp-ring-2" />
            <defs>
              <path id="stampTop" d="M 22,70 A 48,48 0 0 1 118,70" />
              <path id="stampBot" d="M 26,70 A 44,44 0 0 0 114,70" />
            </defs>
            <text className="lh-stamp-arc">
              <textPath href="#stampTop" startOffset="50%" textAnchor="middle">
                DIGBOI, ASSAM
              </textPath>
            </text>
            <text className="lh-stamp-arc">
              <textPath href="#stampBot" startOffset="50%" textAnchor="middle">
                ASIA’S OIL STORY BEGAN
              </textPath>
            </text>
            <text x="70" y="84" textAnchor="middle" className="lh-stamp-year">1889</text>
          </svg>
        </div>

        <div className="lh-hero-in">
          <span className="lh-pill">
            <span className={`lh-dot ${ready ? 'is-ok' : 'is-warn'}`} />
            {ready ? 'Live · ' + fyLabel : 'Booting · ' + fyLabel}
            <span className="lh-pill-sep">·</span>
            <span className="lh-pill-quiet">Advisory only</span>
          </span>

          <h1 className="serif lh-h1">
            Hi, I’m <span className="lh-h1-accent">Digby</span> —<br />
            named after the town where<br />
            <span className="lh-h1-accent">Asia’s oil story began.</span>
          </h1>
          <p className="lh-subline">How can I help you today?</p>

          <div className="lh-demo-card">
            <span className="lh-demo-ico" aria-hidden>
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none"
                   stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"
                   strokeLinejoin="round">
                <path d="M22 10 12 5 2 10l10 5 10-5Z" />
                <path d="M6 12v5c0 1 2.7 2.5 6 2.5s6-1.5 6-2.5v-5" />
              </svg>
            </span>
            <p>
              For this demo, I’ve been trained on just a limited set of
              resources shared with us and Oil India’s public data — only
              enough to show you what my capabilities are.
            </p>
          </div>

          <div className="lh-cta-row">
            <Link href="/dashboard" className="lh-cta lh-cta-primary">
              Let’s talk <span aria-hidden>→</span>
            </Link>
            <Link href="/dashboard" className="lh-cta lh-cta-ghost">
              What can you do?
            </Link>
          </div>

          <div className="lh-trust">
            <span className="lh-trust-eyebrow">Trusted patterns</span>
            <span className="lh-trust-bullet">Read-only</span>
            <span className="lh-trust-bullet">Source-cited</span>
            <span className="lh-trust-bullet">Streaming first</span>
            <span className="lh-trust-bullet">Voice native</span>
          </div>
        </div>

        {/* location pin */}
        <div className="lh-pin" aria-hidden>
          <span className="lh-pin-ico">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor">
              <path d="M12 2C8 2 5 5 5 9c0 5 7 13 7 13s7-8 7-13c0-4-3-7-7-7Zm0 9.5A2.5 2.5 0 1 1 12 6a2.5 2.5 0 0 1 0 5.5Z" />
            </svg>
          </span>
          <span className="lh-pin-text">
            <b>Digboi</b><br />Where Asia’s oil journey began.
          </span>
        </div>
      </section>

      {/* --- Live numbers strip --- */}
      <section className="lh-stats">
        <Stat label="PQ replies indexed"
              value={pqChunks}
              fallback="—"
              sub="vector chunks · live count" />
        <Stat label="Report chunks indexed"
              value={dbChunks}
              fallback="—"
              sub="annual · BRSR · ESG · 10-yr" />
        <Stat label="Source PDFs bundled"
              value={sourceCount}
              fallback="—"
              sub="cited and preview-able" />
        <Stat label="Voice pipeline"
              valueText={voice?.available ? 'Live' : '—'}
              sub={voice?.available
                   ? `${voice.stt} → Anthropic → ${voice.tts}`
                   : 'starting up'} />
      </section>

      {/* --- Brief preview --- */}
      <section className="lh-section" id="preview">
        <div className="lh-section-head">
          <span className="eyebrow">What lands on the screen</span>
          <h2 className="serif lh-h2">
            The morning brief writes itself.
          </h2>
          <p className="lh-section-lead">
            Three signals out of dozens, ranked by what actually needs the
            leadership’s attention — each with a so-what, a recommended
            next step, and the underlying source one click away.
          </p>
        </div>
        <div className="lh-preview">
          <div className="lh-preview-frame">
            <div className="lh-preview-bar">
              <span className="lh-preview-dot lh-preview-dot-r" />
              <span className="lh-preview-dot lh-preview-dot-y" />
              <span className="lh-preview-dot lh-preview-dot-g" />
              <span className="lh-preview-url">oil-india-pq-frontend.fly.dev/dashboard</span>
            </div>
            <div className="lh-preview-body">
              <div className="lh-preview-greet">
                <div className="lh-preview-greet-h serif">Good morning.</div>
                <div className="lh-preview-greet-sub">
                  The business is steady — <strong>3 things</strong> need your attention today.
                </div>
              </div>
              <div className="lh-preview-grid">
                <PreviewCard
                  tag="Reserves · Drilling"
                  title="Reserve depletion accelerating"
                  body="RRR has slipped to 0.94 from 1.16 five years ago — production now outpaces accretion."
                  step="Review the 9 deferred development wells."
                  amber
                />
                <PreviewCard
                  tag="HSE · Safety"
                  title="Duliajan WO Yard: 12 PPE flags this week"
                  body="Most recent: no-hardhat detected 9 min ago at WO Rig #4, shift B."
                  step="Brief shift-B supervisors today."
                  amber
                />
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* --- Capabilities --- */}
      <section className="lh-section lh-section-dim" id="capabilities">
        <div className="lh-section-head">
          <span className="eyebrow">Capabilities</span>
          <h2 className="serif lh-h2">Six domain agents. One conversation.</h2>
          <p className="lh-section-lead">
            Each agent owns its data sources, derives its own signals, and
            cites them with the report filename and section. The brief on
            the home page is whichever signals matter most today — no
            curation, no human in the loop.
          </p>
        </div>
        <div className="lh-grid">
          {CAPABILITIES.map(c => (
            <article className="lh-card" key={c.eyebrow}>
              <span className="lh-card-icon">{c.icon}</span>
              <span className="eyebrow lh-card-eyebrow">{c.eyebrow}</span>
              <h3 className="serif lh-card-title">{c.title}</h3>
              <p className="lh-card-body">{c.body}</p>
            </article>
          ))}
        </div>
      </section>

      {/* --- Voice showcase --- */}
      <section className="lh-section" id="voice">
        <div className="lh-section-head">
          <span className="eyebrow">Voice native</span>
          <h2 className="serif lh-h2">
            Talk to the dashboard. It talks back.
          </h2>
          <p className="lh-section-lead">
            Sub-second end-to-end loop — Deepgram speech-to-text, Anthropic
            Haiku reasoning over the same Chroma index the chat uses,
            Cartesia voice back. Every exchange shows up in the chat
            history with a small voice tag so the conversation feels
            continuous.
          </p>
        </div>
        <div className="lh-voice-flow">
          <Bubble side="user" voice>How are we tracking against the 4 MMT crude target?</Bubble>
          <Bubble side="ai" voice>
            <strong>Crude is at 3.45 MMT FY25-26 — 86% of plan.</strong> The
            shortfall sits mostly in Assam fields; Arunachal and Rajasthan
            are ahead of their cuts.
          </Bubble>
          <Bubble side="user" voice>What about exploration wells?</Bubble>
          <Bubble side="ai" voice>
            44 of the 54 exploratory wells are done — <strong>81% of the FY plan</strong> —
            though meterage is actually a touch ahead of budget at 194,842 m vs 188,666 m.
          </Bubble>
        </div>
      </section>

      {/* --- Bottom CTA --- */}
      <section className="lh-cta-band">
        <h2 className="serif lh-h2">Ready to see today’s brief?</h2>
        <p className="lh-section-lead">
          Open the dashboard — the three things needing your attention are
          already on the screen.
        </p>
        <Link href="/dashboard" className="lh-cta lh-cta-primary">
          Open the dashboard <span aria-hidden>→</span>
        </Link>
      </section>

      <footer className="lh-foot">
        <div className="lh-foot-in">
          <div className="lh-foot-brand">
            <span className="lh-brand-mark" aria-hidden>
              <img src="/oil-logo.png" alt="Digby" className="lh-brand-logo" />
            </span>
            DIGBY
          </div>
          <div className="lh-foot-meta">
            Advisory only · never acts without you. Built for Oil India Limited.
          </div>
        </div>
      </footer>
    </div>
  );
}

/* ---------------- subcomponents ---------------- */

interface StatProps {
  label: string;
  value?: number | null;
  valueText?: string;
  fallback?: string;
  sub: string;
}

function Stat({ label, value, valueText, fallback = '—', sub }: StatProps) {
  const display = valueText ?? useAnimatedNumber(value ?? null, fallback);
  return (
    <div className="lh-stat">
      <div className="lh-stat-label">{label}</div>
      <div className="lh-stat-value serif num">{display}</div>
      <div className="lh-stat-sub">{sub}</div>
    </div>
  );
}

/** Ease a number from 0 to `target` over ~900 ms. Returns the formatted
 *  string each frame for display. */
function useAnimatedNumber(target: number | null, fallback: string): string {
  const [shown, setShown] = useState<number | null>(null);
  const frameRef = useRef<number | null>(null);

  useEffect(() => {
    if (target == null) {
      setShown(null);
      return;
    }
    const start = performance.now();
    const dur = 900;
    const from = 0;
    const to = target;
    const tick = (t: number) => {
      const p = Math.min(1, (t - start) / dur);
      const eased = 1 - Math.pow(1 - p, 3);
      setShown(Math.round(from + (to - from) * eased));
      if (p < 1) frameRef.current = requestAnimationFrame(tick);
    };
    frameRef.current = requestAnimationFrame(tick);
    return () => {
      if (frameRef.current != null) cancelAnimationFrame(frameRef.current);
    };
  }, [target]);

  if (shown == null) return fallback;
  return shown.toLocaleString();
}

function PreviewCard({ tag, title, body, step, amber }:
  { tag: string; title: string; body: string; step: string; amber?: boolean }) {
  return (
    <article className={'lh-pc' + (amber ? ' is-amber' : '')}>
      <div className="lh-pc-top">
        <span className="lh-pc-pill">
          <span className="lh-pc-dot" /> Needs attention
        </span>
        <span className="lh-pc-tag">{tag}</span>
      </div>
      <h3 className="serif lh-pc-title">{title}</h3>
      <p className="lh-pc-body">{body}</p>
      <div className="lh-pc-step">
        <span className="lh-pc-step-eyebrow">Recommended</span>
        <span className="lh-pc-step-text">{step}</span>
      </div>
    </article>
  );
}

function Bubble({ side, voice, children }:
  { side: 'user' | 'ai'; voice?: boolean; children: React.ReactNode }) {
  return (
    <div className={`lh-bubble lh-bubble-${side}`}>
      <div className="lh-bubble-mark" aria-hidden>{side === 'ai' ? '✦' : '◯'}</div>
      <div className="lh-bubble-body">
        {voice && (
          <span className="lh-bubble-voice">
            <span className="lh-bubble-voice-dot" /> voice
          </span>
        )}
        <div className="lh-bubble-text">{children}</div>
      </div>
    </div>
  );
}

