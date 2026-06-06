'use client';
import { Icon } from './Icon';

interface Props {
  text: string;
}

export function OnTrack({ text }: Props) {
  return (
    <section className="ontrack anim" style={{ animationDelay: '.26s' }}>
      <span className="ot-check">
        <Icon name="check" size={14} />
      </span>
      <p>{text}</p>
    </section>
  );
}
