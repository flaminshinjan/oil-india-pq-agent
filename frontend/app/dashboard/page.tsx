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
import { TrajectoryWidget } from '@/components/strata/TrajectoryWidget';
import { HseAlertCard } from '@/components/strata/HseAlertCard';
import { Drilldown, type DrilldownData } from '@/components/strata/Drilldown';
import { DomainDashboard } from '@/components/strata/DomainDashboard';
import { SourcePreview } from '@/components/strata/SourcePreview';
import type { DomainKey } from '@/components/strata/DomainSelector';
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
  const [domain, setDomain] = useState<DomainKey>('brief');
  const [previewFile, setPreviewFile] = useState<string | null>(null);

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
      <TopBar
        dateStr={dateStr}
        domain={domain}
        onDomainChange={setDomain}
      />

      <div className="split">
        <ChatPanel
          chips={SUGGESTION_CHIPS}
          domain={domain}
          onOpenSource={setPreviewFile}
        />

        <main className="analytics-pane">
          <div className="col">
            {domain === 'brief' ? (
              loading || !brief ? (
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
                  <HseAlertCard
                    onOpen={signalId => setDrillKey(String(signalId))}
                    ltiDays={(() => {
                      const lti = metrics.find(m => m.id === 'lti');
                      return lti ? Number(lti.value) : undefined;
                    })()}
                  />
                  <TrajectoryWidget />
                  <BriefSection
                    cards={cards}
                    cardState={cardState}
                    onWhy={handleWhy}
                    onPin={togglePin}
                    onMute={toggleMute}
                  />
                  {onTrackText && <OnTrack text={onTrackText} />}
                </>
              )
            ) : (
              <DomainDashboard domain={domain} onOpenSource={setPreviewFile} />
            )}
          </div>
        </main>
      </div>

      {drilldown && (
        <Drilldown
          data={drilldown}
          onClose={() => setDrillKey(null)}
          onOpenSource={setPreviewFile}
        />
      )}

      <SourcePreview
        filename={previewFile}
        onClose={() => setPreviewFile(null)}
      />
    </div>
  );
}
