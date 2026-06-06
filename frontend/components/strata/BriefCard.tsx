'use client';
import { Icon } from './Icon';

export interface BriefCardData {
  id: string;            // signal id (or "headline")
  domain: string;        // "Reserves · Drilling"
  headline: string;
  soWhat: string;
  step?: string;         // "Review the 9 deferred development wells."
  cta?: string;          // "show me why"
  whyKey?: string;       // identifier for the drilldown view
}

interface Props {
  card: BriefCardData;
  index: number;
  state?: 'pinned' | 'muted';
  onWhy?: (card: BriefCardData) => void;
  onPin?: (id: string) => void;
  onMute?: (id: string) => void;
}

export function BriefCard({ card, index, state, onWhy, onPin, onMute }: Props) {
  const muted = state === 'muted';
  const pinned = state === 'pinned';
  return (
    <article
      className={'brief-card anim' + (muted ? ' is-muted' : '') + (pinned ? ' is-pinned' : '')}
      style={{ animationDelay: `${0.1 + index * 0.07}s` }}
    >
      <div className="bc-top">
        <span className="pill pill-amber">
          <span className="dot" />Needs attention
        </span>
        <span className="tag">{card.domain}</span>
        {pinned && (
          <span className="pinned-flag">
            <Icon name="pin" size={12} /> Pinned
          </span>
        )}
        <span className="bc-actions">
          {onPin && (
            <button
              className="ghost-btn"
              title={pinned ? 'Unpin' : 'Pin to top'}
              onClick={() => onPin(card.id)}
            >
              <Icon name="pin" size={15} />
            </button>
          )}
          {onMute && (
            <button
              className="ghost-btn"
              title={muted ? 'Unmute' : 'Mute for today'}
              onClick={() => onMute(card.id)}
            >
              <Icon name="mute" size={15} />
            </button>
          )}
        </span>
      </div>

      <h2 className="serif bc-head">{card.headline}</h2>

      {!muted && (
        <>
          <p className="bc-sowhat">{card.soWhat}</p>
          <div className="bc-foot">
            {card.step && (
              <div className="bc-step">
                <span className="step-label">Recommended</span>
                <span className="step-text">{card.step}</span>
              </div>
            )}
            {card.cta && onWhy && (
              <button className="qlink" onClick={() => onWhy(card)}>
                {card.cta}{' '}
                <span className="arr">
                  <Icon name="arrow" size={15} />
                </span>
              </button>
            )}
          </div>
        </>
      )}
      {muted && onMute && (
        <p className="bc-muted-note">
          Muted for today ·{' '}
          <button className="link-quiet" onClick={() => onMute(card.id)}>
            bring back
          </button>
        </p>
      )}
    </article>
  );
}
