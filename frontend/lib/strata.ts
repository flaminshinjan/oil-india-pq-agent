/**
 * Mapping helpers from the Atlas backend brief/signals shape into the
 * Strata UI's card data shape.
 *
 * Keeps the components decoupled from API field names — change the
 * backend wire format and only this file moves.
 */

import type { BriefCardData } from '@/components/strata/BriefCard';

export interface Ref {
  filename?: string;
  source?: string;
  section?: string;
}

export interface Signal {
  id: number;
  agent: string;
  severity: 'info' | 'low' | 'med' | 'high' | 'critical';
  title: string;
  body: string;
  refs: Ref[];
  metric: Record<string, unknown> | null;
  ts: number;
  status: 'open' | 'acked' | 'resolved';
}

export interface Brief {
  headline: {
    title: string;
    body: string;
    severity?: string;
    refs?: Ref[];
    metric?: Record<string, unknown> | null;
    linked_signal_ids?: (number | null)[];
  };
  signals: Signal[];
  refreshed_at: number;
}

export interface BackendMetric {
  id: string;
  label: string;
  value: string;
  unit: string;
  note: string;
  amber: boolean;
  fy?: string | null;
}

/** Friendly domain labels per agent. */
const DOMAIN_LABEL: Record<string, string> = {
  production:  'Reserves',
  drilling:    'Drilling',
  hse:         'HSE · Safety',
  procurement: 'Procurement',
  workforce:   'Workforce',
  pq:          'Parliamentary',
};

/**
 * Trim the LLM signal body into a 1–3 sentence "so what" line — the body
 * field is already short, but it sometimes wraps with markdown emphasis
 * markers that we let through.
 */
function shorten(body: string, max = 260): string {
  const s = body.replace(/\s+/g, ' ').trim();
  if (s.length <= max) return s;
  // Try to cut on a sentence boundary
  const slice = s.slice(0, max);
  const lastDot = Math.max(slice.lastIndexOf('. '), slice.lastIndexOf('? '), slice.lastIndexOf('! '));
  return (lastDot > 80 ? slice.slice(0, lastDot + 1) : slice).trim() + '…';
}

function domainFromAgents(agents: string[]): string {
  const labels = Array.from(new Set(agents.map(a => DOMAIN_LABEL[a] ?? a)));
  return labels.join(' · ') || 'Brief';
}

function recommendedStep(s: Signal): string | undefined {
  // Many LLM signals don't have an explicit recommendation; we pick the
  // last sentence of the body as a proxy when it sounds actionable.
  const sentences = s.body.split(/(?<=[.!?])\s+/).filter(Boolean);
  const last = sentences[sentences.length - 1] || '';
  if (/recommend|consider|review|escalate|next step|suggest|approve/i.test(last)) {
    return last.replace(/^\*+|\*+$/g, '').trim();
  }
  return undefined;
}

/**
 * Build the Strata card stream from a backend brief. Logic:
 *   - Card 1 = the LLM headline. Domains = the linked agents.
 *   - Cards 2..N = the next 1–2 highest-severity NON-production/drilling
 *     signals (so we don't repeat the headline's source agents).
 */
export function briefToCards(brief: Brief): BriefCardData[] {
  if (!brief) return [];

  const headlineLinked = (brief.headline.linked_signal_ids ?? []).filter(
    (x): x is number => typeof x === 'number',
  );

  const headlineCard: BriefCardData = {
    id: 'headline',
    domain: domainFromAgents(
      brief.signals.filter(s => headlineLinked.includes(s.id)).map(s => s.agent)
    ) || 'Reserves · Drilling',
    headline: brief.headline.title,
    soWhat: shorten(brief.headline.body, 320),
    step: brief.signals
      .filter(s => headlineLinked.includes(s.id))
      .map(recommendedStep)
      .find(Boolean) || 'Review the linked operational signals.',
    cta: 'show me why',
    whyKey: 'headline',
  };

  const isHeadlineAgent = (a: string) => a === 'production' || a === 'drilling';
  const eligible = brief.signals.filter(s => !isHeadlineAgent(s.agent));
  const rank = { critical: 4, high: 3, med: 2, low: 1, info: 0 } as const;
  eligible.sort(
    (a, b) =>
      (rank[b.severity as keyof typeof rank] ?? 0) -
        (rank[a.severity as keyof typeof rank] ?? 0) ||
      b.ts - a.ts,
  );

  const extra = eligible.slice(0, 2).map<BriefCardData>((s, i) => {
    const cardId = String(s.id ?? `sig-${i}`);
    return {
      id: cardId,
      domain: DOMAIN_LABEL[s.agent] ?? s.agent,
      headline: s.title.replace(/\.+$/, '') + '.',
      soWhat: shorten(s.body),
      step: recommendedStep(s),
      // Always show the CTA — even without external refs, the drilldown
      // renders the full LLM body + any sibling signals from the same agent.
      cta: 'open detail',
      // The drilldown helper resolves by signal-id first, falling back to
      // the agent's most recent signal. Either path lands on rich content.
      whyKey: cardId,
    };
  });

  return [headlineCard, ...extra];
}

/**
 * Build the drill-down payload for whichever card the user clicked.
 *
 *   whyKey === 'headline'   → fuse all linked signals + the headline body
 *   whyKey is an agent name → that agent's top signal's body + refs
 *
 * Nothing here is keyed off a fixed taxonomy; the LLM-generated signal
 * text flows straight through to the overlay.
 */
import type { DrilldownData, DrilldownSection } from '@/components/strata/Drilldown';

function uniqueFilenames(refs: Ref[]): string[] {
  return Array.from(new Set(refs.map(r => r.filename ?? '').filter(Boolean)));
}

export function buildDrilldown(brief: Brief, whyKey: string): DrilldownData | null {
  if (whyKey === 'headline') {
    const linkedIds = (brief.headline.linked_signal_ids ?? []).filter(
      (x): x is number => typeof x === 'number',
    );
    const linked = brief.signals.filter(s => linkedIds.includes(s.id));
    const sections: DrilldownSection[] = linked.map(s => ({
      eyebrow: DOMAIN_LABEL[s.agent] ?? s.agent,
      title: s.title,
      body: s.body,
      refs: s.refs,
    }));
    const allRefs: Ref[] = [
      ...(brief.headline.refs ?? []),
      ...linked.flatMap(s => s.refs ?? []),
    ];
    return {
      tag: domainFromAgents(linked.map(s => s.agent)) || 'Brief',
      eyebrow: 'Show me why',
      title: brief.headline.title.replace(/\.+$/, '') + '.',
      lead: brief.headline.body,
      sections,
      sources: uniqueFilenames(allRefs),
      // Most headline narratives weave Production + Drilling; not HSE.
      agent: linked.find(s => s.agent === 'hse') ? 'hse' : linked[0]?.agent,
    };
  }

  // Specific agent / signal — pick its top open signal.
  const isAgent = ['production', 'drilling', 'hse', 'procurement', 'workforce', 'pq'].includes(whyKey);
  if (isAgent) {
    const candidates = brief.signals.filter(s => s.agent === whyKey);
    if (candidates.length === 0) return null;
    candidates.sort((a, b) => b.ts - a.ts);
    const main = candidates[0];
    const sections: DrilldownSection[] = candidates.slice(1).map(s => ({
      eyebrow: 'Related signal',
      title: s.title,
      body: s.body,
      refs: s.refs,
    }));
    const allRefs = candidates.flatMap(s => s.refs ?? []);
    return {
      tag: DOMAIN_LABEL[main.agent] ?? main.agent,
      eyebrow: 'Open detail',
      title: main.title,
      lead: main.body,
      sections,
      sources: uniqueFilenames(allRefs),
      agent: main.agent,
    };
  }

  // Lookup by signal id (when a card's id IS the signal id).
  const sigById = brief.signals.find(s => String(s.id) === whyKey);
  if (sigById) {
    return {
      tag: DOMAIN_LABEL[sigById.agent] ?? sigById.agent,
      eyebrow: 'Open detail',
      title: sigById.title,
      lead: sigById.body,
      sections: [],
      sources: uniqueFilenames(sigById.refs ?? []),
      agent: sigById.agent,
    };
  }

  return null;
}

/**
 * If there ARE signals from these agents but none made it onto a card,
 * we say so in the "on-track" line at the bottom so the UI still
 * acknowledges them.
 */
export function buildOnTrack(brief: Brief, cards: BriefCardData[]): string {
  const surfacedAgents = new Set(
    cards.flatMap(c => c.domain.split(' · ').map(d => d.trim()))
  );
  const otherAgents = Array.from(new Set(brief.signals.map(s => s.agent)))
    .filter(a => !surfacedAgents.has(DOMAIN_LABEL[a] ?? a));
  const labels = otherAgents.map(a => DOMAIN_LABEL[a] ?? a).filter(Boolean);
  if (labels.length === 0) return "Nothing else needs you today.";
  if (labels.length === 1) return `${labels[0]} is on track. Nothing else needs you today.`;
  return `${labels.slice(0, -1).join(', ')} and ${labels.slice(-1)} are on track. Nothing else needs you today.`;
}
