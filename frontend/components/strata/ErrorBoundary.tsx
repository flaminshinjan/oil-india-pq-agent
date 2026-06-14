'use client';
/**
 * Contains render-time exceptions so one broken section never white-screens the
 * whole dashboard ("Application error: a client-side exception"). Shows a small
 * inline message and a retry; the rest of the app (chat, other tabs) keeps
 * working. `resetKey` re-mounts the boundary when it changes (e.g. switching
 * domain tabs) so a previously-failed view can recover.
 */
import { Component, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
  resetKey?: string | number;
  label?: string;
}
interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidUpdate(prev: Props) {
    if (prev.resetKey !== this.props.resetKey && this.state.error) {
      this.setState({ error: null });
    }
  }

  componentDidCatch(error: Error) {
    // Surface to the console so it's debuggable in prod.
    // eslint-disable-next-line no-console
    console.error('[dashboard] render error', this.props.label ?? '', error);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="domain-view">
          <div className="domain-empty">
            <h2 className="serif domain-title">This view hit a snag</h2>
            <p className="domain-empty-sub">
              Something in {this.props.label ?? 'this panel'} failed to render. Try another tab,
              or reload. The rest of Digby still works.
            </p>
            <button
              type="button"
              className="lh-cta"
              style={{ marginTop: 14 }}
              onClick={() => this.setState({ error: null })}
            >
              Retry
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
