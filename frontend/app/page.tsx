'use client';

import Link from 'next/link';
import { useEffect, useRef } from 'react';

const HERO_WORDS_1 = ['Draft', 'parliamentary', 'replies'];
const HERO_WORDS_2 = ['that', 'always', 'cite', 'their', 'source.'];

export default function Landing() {
  // Reveal-on-scroll for sections marked .reveal
  const observer = useRef<IntersectionObserver | null>(null);
  useEffect(() => {
    if (typeof window === 'undefined') return;
    observer.current = new IntersectionObserver(
      entries => {
        entries.forEach(e => {
          if (e.isIntersecting) {
            e.target.classList.add('reveal-in');
            observer.current?.unobserve(e.target);
          }
        });
      },
      { threshold: 0.12, rootMargin: '0px 0px -60px 0px' },
    );
    document.querySelectorAll('.reveal').forEach(el => observer.current!.observe(el));
    return () => observer.current?.disconnect();
  }, []);

  return (
    <div className="landing">
      {/* Floating background orbs */}
      <div className="bg-orbs" aria-hidden="true">
        <span className="orb orb-1" />
        <span className="orb orb-2" />
        <span className="orb orb-3" />
        <span className="grid-overlay" />
      </div>

      {/* Top nav */}
      <nav className="landing-nav">
        <div className="brand reveal-quick">
          <div className="brand-mark">OI</div>
          <div className="brand-text">
            <div className="brand-name">Oil India</div>
            <div className="brand-sub">PQ Assistant</div>
          </div>
        </div>
        <div className="nav-right">
          <a href="#how" className="nav-link">How it works</a>
          <a href="#stack" className="nav-link">Under the hood</a>
          <Link href="/chat" className="btn btn-primary btn-sm">
            Open app <ArrowRight />
          </Link>
        </div>
      </nav>

      {/* Hero */}
      <section className="hero">
        <div className="hero-pill reveal-quick" style={{ animationDelay: '.05s' }}>
          <span className="pill-dot" />
          <span>Grounded in OIL's parliamentary archive · 3,065 indexed excerpts</span>
        </div>

        <h1 className="hero-title">
          <span className="hero-line">
            {HERO_WORDS_1.map((w, i) => (
              <span
                key={i}
                className="word"
                style={{ animationDelay: `${0.15 + i * 0.08}s` }}
              >
                {w}
              </span>
            ))}
          </span>
          <br />
          <span className="hero-line hero-line-accent">
            {HERO_WORDS_2.map((w, i) => (
              <span
                key={i}
                className="word"
                style={{ animationDelay: `${0.4 + i * 0.08}s` }}
              >
                {w}
              </span>
            ))}
          </span>
        </h1>

        <p className="hero-sub reveal-quick" style={{ animationDelay: '.85s' }}>
          An AI assistant for Oil India Limited that searches past parliamentary
          Q&amp;A, pulls facts from production, drilling, and reserves data, and
          <strong> never makes anything up</strong>. Every figure carries an
          inline citation.
        </p>

        <div className="hero-cta reveal-quick" style={{ animationDelay: '1.05s' }}>
          <Link href="/chat" className="btn btn-primary btn-lg">
            Try now <ArrowRight />
          </Link>
          <a href="#demo" className="btn btn-ghost btn-lg">
            See a live example
          </a>
        </div>

        <div className="hero-stats reveal-quick" style={{ animationDelay: '1.25s' }}>
          <Stat n="3,065" l="PQ excerpts indexed" />
          <Stat n="881" l="source documents" />
          <Stat n="3" l="grounded tools" />
          <Stat n="0" l="hallucinations" />
        </div>
      </section>

      {/* Demo preview */}
      <section className="demo-section reveal" id="demo">
        <div className="section-label">Live preview</div>
        <h2 className="section-title">A reply, fully sourced.</h2>
        <p className="section-sub">
          Ask in plain English. The agent retrieves, reasons, and cites — every
          time.
        </p>

        <div className="demo-frame">
          <div className="demo-window">
            <div className="demo-titlebar">
              <span className="dot dot-r" />
              <span className="dot dot-y" />
              <span className="dot dot-g" />
              <span className="demo-titlebar-label">Oil India · PQ Assistant</span>
            </div>

            <div className="demo-body">
              <div className="demo-msg demo-msg-user demo-anim" style={{ animationDelay: '.15s' }}>
                <div className="demo-bubble demo-bubble-user">
                  What is OIL's crude oil production for FY 2024-25?
                </div>
              </div>

              <div className="demo-msg demo-msg-asst demo-anim" style={{ animationDelay: '.55s' }}>
                <div className="demo-avatar">OI</div>
                <div className="demo-body-col">
                  <div className="demo-tool-row demo-anim" style={{ animationDelay: '.85s' }}>
                    <span className="demo-chip">
                      <span className="demo-chip-dot" />
                      Oil India data <span className="demo-chip-count">5</span>
                    </span>
                    <span className="demo-chip">
                      <span className="demo-chip-dot" />
                      Parliamentary archive <span className="demo-chip-count">4</span>
                    </span>
                  </div>

                  <div className="demo-text demo-anim" style={{ animationDelay: '1.15s' }}>
                    Oil India Limited achieved{' '}
                    <strong className="hl">3.46 MMT</strong> of crude oil
                    production in FY 2024-25 — the{' '}
                    <strong>highest in the past decade</strong>, representing a{' '}
                    <strong>16.7% increase</strong> from FY 2020-21.
                  </div>

                  <div className="demo-table demo-anim" style={{ animationDelay: '1.35s' }}>
                    <DemoTable />
                  </div>

                  <div className="demo-citations demo-anim" style={{ animationDelay: '1.55s' }}>
                    <span className="demo-cit-label">Sources</span>
                    <span className="demo-cit">10 Years Production.xlsx</span>
                    <span className="demo-cit demo-cit-muted">+2 more</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="how" id="how">
        <div className="reveal">
          <div className="section-label">How it works</div>
          <h2 className="section-title">Three tools. One principle.</h2>
          <p className="section-sub">
            Search what's there. Quote what's there. Decline what isn't.
          </p>
        </div>
        <div className="how-grid">
          <Feature
            tag="search_pq_archive"
            title="Past PQ archive"
            body="3,065 indexed excerpts of how OIL has answered parliamentary questions across Budget, Monsoon, and Winter sessions. Used for precedent and phrasing."
            delay={0}
          />
          <Feature
            tag="search_oil_india_data"
            title="Operational data"
            body="Production, drilling, workover, reserves, discoveries — pulled directly from OIL's own spreadsheets and reference docs. The canonical numbers."
            delay={80}
          />
          <Feature
            tag="list_available_sources"
            title="Directory"
            body="Before guessing, the agent can list every document in the corpus. If the topic isn't there, you get a clean ‘I don't have data on this’ — not a fabricated answer."
            delay={160}
          />
        </div>
      </section>

      {/* Tech stack strip */}
      <section className="stack" id="stack">
        <div className="reveal">
          <div className="section-label">Under the hood</div>
          <h2 className="section-title">Built to be auditable.</h2>
        </div>
        <div className="stack-grid reveal">
          <Tech name="LangGraph" sub="agent state machine" />
          <Tech name="Claude" sub="Anthropic Sonnet 4.5" />
          <Tech name="Chroma" sub="vector store" />
          <Tech name="FastAPI" sub="streaming backend" />
          <Tech name="Next.js" sub="this UI" />
        </div>
      </section>

      {/* CTA strip */}
      <section className="cta-strip reveal">
        <h2>Draft your next reply in minutes.</h2>
        <p>The corpus is loaded. The agent is up. Try a real question.</p>
        <Link href="/chat" className="btn btn-primary btn-lg">
          Try now <ArrowRight />
        </Link>
      </section>

      <footer className="landing-footer">
        <span>Oil India · Parliamentary Response Assistant</span>
        <span className="landing-footer-meta">Built with LangGraph + Claude</span>
      </footer>
    </div>
  );
}

/* ---------- small subcomponents ---------- */

function Stat({ n, l }: { n: string; l: string }) {
  return (
    <div className="stat">
      <div className="stat-n">{n}</div>
      <div className="stat-l">{l}</div>
    </div>
  );
}

function Feature({
  tag,
  title,
  body,
  delay,
}: {
  tag: string;
  title: string;
  body: string;
  delay: number;
}) {
  return (
    <div className="feature reveal" style={{ transitionDelay: `${delay}ms` }}>
      <div className="feature-tag">{tag}</div>
      <div className="feature-title">{title}</div>
      <div className="feature-body">{body}</div>
    </div>
  );
}

function Tech({ name, sub }: { name: string; sub: string }) {
  return (
    <div className="tech">
      <div className="tech-name">{name}</div>
      <div className="tech-sub">{sub}</div>
    </div>
  );
}

function DemoTable() {
  const rows = [
    ['2020-21', '2.96', '−5.4%'],
    ['2021-22', '3.01', '+1.7%'],
    ['2022-23', '3.18', '+5.7%'],
    ['2023-24', '3.36', '+5.7%'],
    ['2024-25', '3.46', '+3.0%'],
  ];
  return (
    <table>
      <thead>
        <tr>
          <th>FY</th>
          <th>Crude Oil (MMT)</th>
          <th>YoY</th>
        </tr>
      </thead>
      <tbody>
        {rows.map(r => (
          <tr key={r[0]}>
            <td>{r[0]}</td>
            <td>{r[1]}</td>
            <td className={r[2].startsWith('+') ? 'pos' : 'neg'}>{r[2]}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function ArrowRight() {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.4"
      strokeLinecap="round"
      strokeLinejoin="round"
      style={{ marginLeft: 2 }}
    >
      <path d="M5 12h14" />
      <path d="m13 5 7 7-7 7" />
    </svg>
  );
}
