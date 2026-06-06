'use client';
/**
 * Strata · intelligence OS — home page.
 *
 * Wiring:
 *   - /api/os/brief    → headline + per-agent signals (cards)
 *   - /api/os/metrics  → 4-up Key Metrics strip (live from the spreadsheets)
 *   - /api/chat        → the embedded "Ask Strata" chat dock streams here
 *
 * The page itself is a thin orchestration layer; every visual piece is its
 * own component under components/strata/.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';

import { TopBar } from '@/components/strata/TopBar';
import { Greeting } from '@/components/strata/Greeting';
import { MetricsStrip, type Metric } from '@/components/strata/MetricsStrip';
import { BriefSection } from '@/components/strata/BriefSection';
import { OnTrack } from '@/components/strata/OnTrack';
import { ChatPanel } from '@/components/strata/ChatPanel';
import { Drilldown, type DrilldownData } from '@/components/strata/Drilldown';
import type { BriefCardData } from '@/components/strata/BriefCard';

import {
  briefToCards,
  buildDrilldown,
  buildOnTrack,
  type BackendMetric,
  type Brief,
} from '@/lib/strata';

const SUGGESTION_CHIPS = [
  'How are we tracking vs target?',
  'Where are we losing against plan?',
  'Biggest risk to reserves?',
];

const METRICS_PEEK = 'Crude, gas, reserves & safety — all current';

export default function StrataHome() {
  const [brief, setBrief] = useState<Brief | null>(null);
  const [metrics, setMetrics] = useState<Metric[]>([]);
  const [loading, setLoading] = useState(true);
  const [cardState, setCardState] = useState<Record<string, 'pinned' | 'muted' | undefined>>({});
  const [drillKey, setDrillKey] = useState<string | null>(null);

  // Load brief + metrics in parallel on mount.
  useEffect(() => {
    let cancelled = false;
    Promise.all([
      fetch('/api/os/brief').then(r => r.json()).catch(() => null),
      fetch('/api/os/metrics').then(r => r.json()).catch(() => null),
    ])
      .then(([b, m]) => {
        if (cancelled) return;
        if (b) setBrief(b as Brief);
        if (m && Array.isArray(m.metrics)) {
          setMetrics(
            (m.metrics as BackendMetric[]).map(x => ({
              id: x.id,
              label: x.label,
              value: x.value,
              unit: x.unit,
              note: x.note,
              amber: !!x.amber,
            })),
          );
        }
        setLoading(false);
      })
      .catch(() => setLoading(false));
    return () => { cancelled = true; };
  }, []);

  const cards: BriefCardData[] = useMemo(
    () => (brief ? briefToCards(brief) : []),
    [brief],
  );

  const onTrackText = useMemo(
    () => (brief ? buildOnTrack(brief, cards) : ''),
    [brief, cards],
  );

  const attentionCount = useMemo(
    () => cards.filter(c => cardState[c.id] !== 'muted').length,
    [cards, cardState],
  );

  const togglePin = useCallback((id: string) => {
    setCardState(s => ({ ...s, [id]: s[id] === 'pinned' ? undefined : 'pinned' }));
  }, []);
  const toggleMute = useCallback((id: string) => {
    setCardState(s => ({ ...s, [id]: s[id] === 'muted' ? undefined : 'muted' }));
  }, []);

  const handleWhy = useCallback((card: BriefCardData) => {
    if (card.whyKey) setDrillKey(card.whyKey);
  }, []);

  const drilldown: DrilldownData | null = useMemo(
    () => (drillKey && brief ? buildDrilldown(brief, drillKey) : null),
    [drillKey, brief],
  );

  const dateStr = useMemo(() => {
    const now = new Date();
    return now.toLocaleDateString('en-GB', {
      weekday: 'long',
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    });
  }, []);

  return (
    <div className="app split-app">
      <TopBar dateStr={dateStr} />

      <div className="split">
        <ChatPanel chips={SUGGESTION_CHIPS} />

        <main className="analytics-pane">
          <div className="col">
            {loading || !brief ? (
              <div className="greeting">
                <h1 className="serif greet-h">Good morning, Chairman.</h1>
                <p className="greet-sub">Loading today&rsquo;s brief…</p>
              </div>
            ) : (
              <>
                <Greeting
                  salutation="Chairman"
                  state="The business is steady"
                  attentionCount={attentionCount}
                />
                {metrics.length > 0 && (
                  <MetricsStrip metrics={metrics} peek={METRICS_PEEK} />
                )}
                <BriefSection
                  cards={cards}
                  cardState={cardState}
                  onWhy={handleWhy}
                  onPin={togglePin}
                  onMute={toggleMute}
                />
                {onTrackText && <OnTrack text={onTrackText} />}
              </>
            )}
          </div>
        </main>
      </div>

      {drilldown && (
        <Drilldown data={drilldown} onClose={() => setDrillKey(null)} />
      )}
    </div>
  );
}
