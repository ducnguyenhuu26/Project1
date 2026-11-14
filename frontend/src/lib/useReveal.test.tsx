// @vitest-environment jsdom
import { useState } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { useReveal } from './useReveal';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('useReveal', () => {
  it('reveals content added after the section first mounted', async () => {
    class ObserverMock {
      constructor(private callback: IntersectionObserverCallback) {}
      observe = (target: Element) => {
        queueMicrotask(() => this.callback(
          [{ target, isIntersecting: true } as IntersectionObserverEntry],
          this as unknown as IntersectionObserver,
        ));
      };
      unobserve = vi.fn();
      disconnect = vi.fn();
    }
    vi.stubGlobal('matchMedia', () => ({ matches: false }));
    vi.stubGlobal('IntersectionObserver', ObserverMock);

    function Example() {
      const ref = useReveal<HTMLDivElement>();
      const [loaded, setLoaded] = useState(false);
      return <div ref={ref}>
        <button onClick={() => setLoaded(true)}>Load library</button>
        {loaded && <p className="reveal" data-testid="loaded-library">Library items</p>}
      </div>;
    }

    render(<Example />);
    fireEvent.click(screen.getByRole('button', { name: 'Load library' }));
    await waitFor(() => expect(screen.getByTestId('loaded-library').classList.contains('shown')).toBe(true));
  });
});
