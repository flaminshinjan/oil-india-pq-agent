'use client';
import { BriefCard, type BriefCardData } from './BriefCard';

interface Props {
  cards: BriefCardData[];
  cardState: Record<string, 'pinned' | 'muted' | undefined>;
  onWhy: (card: BriefCardData) => void;
  onPin: (id: string) => void;
  onMute: (id: string) => void;
}

export function BriefSection({ cards, cardState, onWhy, onPin, onMute }: Props) {
  const attentionCount = cards.filter(c => cardState[c.id] !== 'muted').length;

  // Order: pinned first → authored → muted last
  const ordered = [...cards].sort((a, b) => {
    const rank = (c: BriefCardData, idx: number) => {
      const s = cardState[c.id];
      return (s === 'muted' ? 100 : s === 'pinned' ? -100 : 0) + idx;
    };
    return rank(a, cards.indexOf(a)) - rank(b, cards.indexOf(b));
  });

  if (cards.length === 0) return null;

  return (
    <section className="brief">
      <div className="brief-rule">
        <span className="eyebrow">The brief</span>
        <span className="brief-count">{attentionCount} to review</span>
      </div>
      <div className={`brief-list cards-${cards.length}`}>
        {ordered.map((c, i) => (
          <BriefCard
            key={c.id}
            card={c}
            index={i}
            state={cardState[c.id]}
            onWhy={onWhy}
            onPin={onPin}
            onMute={onMute}
          />
        ))}
      </div>
    </section>
  );
}
