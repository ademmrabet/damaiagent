import { useEffect, useRef, useState } from 'react';
import gsap from 'gsap';
import { checkHealth } from '../api.js';

const POLL_INTERVAL_MS = 8000;
// green/red dot showing if the backend is reachable

export default function StatusDot() {
  const [online, setOnline] = useState(null);
  const dotRef = useRef(null);

  useEffect(() => {
    let cancelled = false;

    async function poll() {
      try {
        await checkHealth();
        if (!cancelled) setOnline(true);
      } catch {
        if (!cancelled) setOnline(false);
      }
    }

    poll();
    const id = setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  useEffect(() => {
    if (online === null || !dotRef.current) return;
    gsap.fromTo(
      dotRef.current,
      { scale: 0.4 },
      { scale: 1, duration: 0.4, ease: 'back.out(3)' }
    );
  }, [online]);

  const title =
    online === null
      ? 'Checking server status…'
      : online
      ? 'Server is up'
      : 'Server is unreachable';

  return (
    <span
      ref={dotRef}
      className={
        'accent-dot' + (online === true ? ' online' : online === false ? ' offline' : '')
      }
      title={title}
    />
  );
}
