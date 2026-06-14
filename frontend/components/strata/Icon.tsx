/**
 * Minimal-stroke icon set used across the Strata surface. Ported verbatim
 * from the reference design's `home.jsx`. Stroke-only, currentColor, so
 * any wrapper sets the color via CSS.
 */
type IconName =
  | 'sliders' | 'chevron' | 'check' | 'pin' | 'mute'
  | 'arrow' | 'send' | 'spark' | 'plus' | 'clock'
  | 'close' | 'copy' | 'trash' | 'back' | 'image';

interface IconProps {
  name: IconName;
  size?: number;
}

export function Icon({ name, size = 16 }: IconProps) {
  const s = {
    width: size,
    height: size,
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.5,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
  };
  switch (name) {
    case 'sliders':
      return (<svg viewBox="0 0 24 24" {...s}><line x1="4" y1="8" x2="20" y2="8"/><circle cx="9" cy="8" r="2.4" fill="var(--surface)"/><line x1="4" y1="16" x2="20" y2="16"/><circle cx="15" cy="16" r="2.4" fill="var(--surface)"/></svg>);
    case 'chevron':
      return (<svg viewBox="0 0 24 24" {...s}><polyline points="6 9 12 15 18 9"/></svg>);
    case 'check':
      return (<svg viewBox="0 0 24 24" {...s}><polyline points="20 6 9 17 4 12"/></svg>);
    case 'pin':
      return (<svg viewBox="0 0 24 24" {...s}><path d="M12 17v5"/><path d="M9 3h6l-1 7 3 3H7l3-3-1-7z"/></svg>);
    case 'mute':
      return (<svg viewBox="0 0 24 24" {...s}><path d="M11 5 6 9H3v6h3l5 4V5z"/><line x1="22" y1="9" x2="16" y2="15"/><line x1="16" y1="9" x2="22" y2="15"/></svg>);
    case 'arrow':
    case 'send':
      return (<svg viewBox="0 0 24 24" {...s}><line x1="5" y1="12" x2="18" y2="12"/><polyline points="13 7 18 12 13 17"/></svg>);
    case 'spark':
      return (<svg viewBox="0 0 24 24" {...s}><path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M18 6l-2.5 2.5M8.5 15.5 6 18"/></svg>);
    case 'plus':
      return (<svg viewBox="0 0 24 24" {...s}><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>);
    case 'clock':
      return (<svg viewBox="0 0 24 24" {...s}><circle cx="12" cy="12" r="8.5"/><polyline points="12 7.5 12 12 15 13.5"/></svg>);
    case 'close':
      return (<svg viewBox="0 0 24 24" {...s}><line x1="6" y1="6" x2="18" y2="18"/><line x1="18" y1="6" x2="6" y2="18"/></svg>);
    case 'copy':
      return (<svg viewBox="0 0 24 24" {...s}><rect x="9" y="9" width="11" height="11" rx="2.5"/><path d="M5 15V6a2 2 0 0 1 2-2h8"/></svg>);
    case 'trash':
      return (<svg viewBox="0 0 24 24" {...s}><polyline points="4 7 20 7"/><path d="M9 7V5a1.5 1.5 0 0 1 1.5-1.5h3A1.5 1.5 0 0 1 15 5v2"/><path d="M6 7l1 12.5a1.5 1.5 0 0 0 1.5 1.4h7a1.5 1.5 0 0 0 1.5-1.4L18 7"/></svg>);
    case 'back':
      return (<svg viewBox="0 0 24 24" {...s}><line x1="19" y1="12" x2="6" y2="12"/><polyline points="11 7 6 12 11 17"/></svg>);
    case 'image':
      return (<svg viewBox="0 0 24 24" {...s}><rect x="3" y="4" width="18" height="16" rx="2.5"/><circle cx="8.5" cy="9.5" r="1.6"/><path d="M21 16l-5-5L5 21"/></svg>);
    default:
      return null;
  }
}
