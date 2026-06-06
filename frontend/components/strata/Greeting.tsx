'use client';

interface Props {
  salutation: string;        // "Chairman", "CFO", etc.
  state: string;             // "The business is steady"
  attentionCount: number;
}

export function Greeting({ salutation, state, attentionCount }: Props) {
  return (
    <section className="greeting anim">
      <h1 className="serif greet-h">Good morning, {salutation}.</h1>
      <p className="greet-sub">
        {state} —{' '}
        {attentionCount === 0 ? (
          <span className="greet-em">you&rsquo;re all clear</span>
        ) : (
          <span className="greet-em">
            {attentionCount} {attentionCount === 1 ? 'thing needs' : 'things need'} your attention
          </span>
        )}{' '}
        today.
      </p>
    </section>
  );
}
