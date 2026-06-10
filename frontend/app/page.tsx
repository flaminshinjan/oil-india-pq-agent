'use client';
/**
 * Strata · intelligence OS — landing page.
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
    eyebrow: 'Procurement',
    title: 'Bids ranked on the criteria that matter',
    body: 'Price, delivery, OEM rating, warranty, deviations — all weighed against the criteria you set on the PR.',
    icon: '◇',
  },
  {
    eyebrow: 'Parliamentary Replies',
    title: 'Cites the PQ before you ask',
    body: 'Indexed Lok Sabha + Rajya Sabha replies. Every numeric answer is traced back to the source filename.',
    icon: '§',
  },
];

const STACK = [
  { label: 'LangGraph',     hint: 'Agent orchestration' },
  { label: 'Anthropic Claude', hint: 'Reasoning · Haiku 4.5 / Sonnet 4.6' },
  { label: 'Chroma DB',     hint: 'Vector index over OIL reports' },
  { label: 'Pipecat',       hint: 'Real-time voice pipeline' },
  { label: 'Deepgram',      hint: 'Speech-to-text' },
  { label: 'Cartesia',      hint: 'Text-to-speech' },
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
              <BrandGlyph />
            </span>
            <span className="lh-brand-text">
              <span className="lh-brand-name">STRATA</span>
              <span className="lh-brand-sub">intelligence OS · Oil India</span>
            </span>
          </Link>
          <nav className="lh-bar-nav">
            <a className="lh-bar-link" href="#preview">Preview</a>
            <a className="lh-bar-link" href="#capabilities">Capabilities</a>
            <a className="lh-bar-link" href="#voice">Voice</a>
            <a className="lh-bar-link" href="#architecture">Stack</a>
            <Link href="/dashboard" className="lh-cta">
              Open dashboard <span aria-hidden>→</span>
            </Link>
          </nav>
        </div>
      </header>

      {/* --- Hero --- */}
      <section className="lh-hero">
        <div className="lh-hero-in">
          <span className="lh-pill">
            <span className={`lh-dot ${ready ? 'is-ok' : 'is-warn'}`} />
            {ready ? 'Live · ' + fyLabel : 'Booting · ' + fyLabel}
            <span className="lh-pill-sep">·</span>
            <span className="lh-pill-quiet">Advisory only</span>
          </span>
          <h1 className="serif lh-h1">
            One advisory layer for everything OIL
            <span className="lh-h1-accent"> ships, drills, and discloses.</span>
          </h1>
          <p className="lh-lead">
            Strata reads the annual report, the BRSR, the ESG data book, the
            10-year sheet, the parliamentary replies and the live HSE feed —
            and answers the question on top of the Chairman’s mind. In
            writing or out loud, in under a second.
          </p>
          <div className="lh-cta-row">
            <Link href="/dashboard" className="lh-cta lh-cta-primary">
              Open the dashboard <span aria-hidden>→</span>
            </Link>
            <a href="#preview" className="lh-cta lh-cta-ghost">
              See it work
            </a>
          </div>
          <div className="lh-trust">
            <span className="lh-trust-eyebrow">Trusted patterns</span>
            <span className="lh-trust-bullet">Read-only</span>
            <span className="lh-trust-bullet">Source-cited</span>
            <span className="lh-trust-bullet">Streaming first</span>
            <span className="lh-trust-bullet">Voice native</span>
          </div>
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
            Chairman’s attention — each with a so-what, a recommended next
            step, and the underlying source one click away.
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
                <div className="lh-preview-greet-h serif">Good morning, Chairman.</div>
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
                  tag="Procurement"
                  title="Weatherford bid contains high-severity deviation"
                  body="Liability cap proposed at 50% of contract value vs OIL’s standard 100%."
                  step="Recommend legal review before award."
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

      {/* --- Architecture --- */}
      <section className="lh-section lh-section-dim" id="architecture">
        <div className="lh-section-head">
          <span className="eyebrow">Under the hood</span>
          <h2 className="serif lh-h2">
            Open-source orchestration, frontier reasoning, bring-your-own data.
          </h2>
          <p className="lh-section-lead">
            Nothing about Strata is locked to a vendor. Swap the LLM for the
            next Anthropic / OpenAI / Gemini frontier model, point Chroma at
            a fresh corpus, change the voice — the orchestration graph
            stays the same.
          </p>
        </div>
        <div className="lh-stack-grid">
          {STACK.map(s => (
            <div className="lh-stack-card" key={s.label}>
              <div className="lh-stack-label">{s.label}</div>
              <div className="lh-stack-hint">{s.hint}</div>
            </div>
          ))}
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
            <span className="lh-brand-mark" aria-hidden><BrandGlyph /></span>
            STRATA
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

function BrandGlyph() {
  return (
    <svg width="22" height="22" viewBox="0 0 20 20" fill="none" aria-hidden>
      <rect width="20" height="20" rx="5" fill="var(--accent)" />
      <rect x="4" y="5"  width="12" height="2.2" rx="1.1" fill="var(--surface)" />
      <rect x="4" y="9"  width="12" height="2.2" rx="1.1" fill="var(--surface)" opacity="0.7" />
      <rect x="4" y="13" width="12" height="2.2" rx="1.1" fill="var(--surface)" opacity="0.45" />
    </svg>
  );
}
