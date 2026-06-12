'use client';
/**
 * Digby · intelligence OS — landing page.
 *
 * Editorial in tone, rich in visuals. Same design tokens as the dashboard
 * so the product feels like one thing.
 *
 * Sections:
 *   1.  Sticky brand bar  ← always-on CTA to /dashboard
 *   2.  Hero              ← serif headline, animated dot, two CTAs, source thumbs
 *   3.  Brief preview     ← embedded mock of the dashboard's morning brief
 *   4.  Capabilities      ← six-card grid, one per domain agent
 *   5.  Voice showcase    ← speech-bubble flow demonstrating the voice loop
 *   6.  Bottom CTA band
 *   7.  Footer
 */
import Link from 'next/link';
import { useEffect, useState } from 'react';

interface Health {
  status?: string;
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

const SOURCE_THUMBS = [
  { ext: 'XLSX', label: '10-yr Production & Reserves', kind: 'xl' },
  { ext: 'XLSX', label: 'FY2025-26 MIS', kind: 'xlb' },
  { ext: 'DOCX', label: 'Reserves & Discoveries', kind: 'doc' },
  { ext: 'PDF / PQ', label: 'Annual Reports · BRSR · ESG · Parliamentary replies', kind: 'pdf' },
];

export default function Landing() {
  const [health, setHealth] = useState<Health | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch('/api/health').then(r => r.json()).catch(() => null).then(h => {
      if (cancelled) return;
      if (h) setHealth(h);
    });
    return () => { cancelled = true; };
  }, []);

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

      {/* --- Hero (Digboi scene) — centered stack --- */}
      <section className="lh-hero">
        <div className="lh-hero-bg" aria-hidden />
        <div className="lh-hero-veil" aria-hidden />

        <div className="lh-hero-in">
          {/* brand */}
          <div className="lh-brand-stack">
            <span className="lh-brand-tile" aria-hidden>
              <img src="/oil-logo.png" alt="Digby" className="lh-brand-tile-logo" />
            </span>
            <span className="lh-brand-name">DIGBY</span>
            <span className="lh-brand-sub">intelligence OS · Oil India</span>
          </div>

          <span className="lh-pill">
            <span className={`lh-dot ${ready ? 'is-ok' : 'is-warn'}`} />
            {ready ? 'Live · ' + fyLabel : 'Booting · ' + fyLabel}
            <span className="lh-pill-sep">·</span>
            <span className="lh-pill-quiet">Advisory only</span>
          </span>

          <h1 className="serif lh-h1">
            Hi, I’m <span className="lh-h1-accent">Digby</span> —<br />
            named after the town where<br />
            <span className="lh-h1-accent">Asia’s oil story</span> began.
          </h1>
          <p className="lh-subline">How can I help you today?</p>

          <div className="lh-cta-row">
            <Link href="/dashboard" className="lh-cta lh-cta-primary">
              Let’s talk <span aria-hidden>→</span>
            </Link>
            <Link href="/dashboard" className="lh-cta lh-cta-ghost">
              What can you do?
            </Link>
          </div>

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

          {/* source thumbnails — what Digby is grounded in */}
          <div className="lh-sources">
            <span className="lh-sources-eyebrow">Grounded in trusted sources</span>
            <div className="lh-sources-row">
              {SOURCE_THUMBS.map(s => (
                <div className={`lh-thumb lh-thumb-${s.kind}`} key={s.label} title={s.label}>
                  <span className="lh-thumb-ico" aria-hidden>
                    <svg viewBox="0 0 24 24" width="20" height="20" fill="none"
                         stroke="currentColor" strokeWidth="1.7" strokeLinecap="round"
                         strokeLinejoin="round">
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" />
                      <path d="M14 2v6h6" />
                      <path d="M8 13h8M8 17h8M8 9h2" />
                    </svg>
                  </span>
                  <span className="lh-thumb-text">
                    <span className="lh-thumb-ext">{s.ext}</span>
                    <span className="lh-thumb-label">{s.label}</span>
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
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

