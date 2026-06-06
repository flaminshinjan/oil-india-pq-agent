'use client';
import { Icon } from './Icon';

interface Props {
  dateStr: string;
  onCustomise?: () => void;
  customiseOpen?: boolean;
}

export function TopBar({ dateStr, onCustomise, customiseOpen = false }: Props) {
  return (
    <header className="topbar">
      <div className="topbar-in">
        <div className="wordmark">
          <span className="mark" aria-hidden="true" />
          <span className="wm-name">Strata</span>
          <span className="wm-dot">·</span>
          <span className="wm-sub">intelligence OS</span>
        </div>
        <div className="topbar-right">
          <span className="date num">{dateStr}</span>
          {onCustomise && (
            <button
              className={'icon-btn' + (customiseOpen ? ' is-on' : '')}
              onClick={onCustomise}
              aria-label="Customise"
              title="Customise"
            >
              <Icon name="sliders" size={17} />
            </button>
          )}
        </div>
      </div>
    </header>
  );
}
