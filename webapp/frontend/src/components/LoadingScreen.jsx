import { useEffect, useRef, useState } from 'react';
import gsap from 'gsap';
import './loadingScreen.css';
// splash screen until the page has its first api response

export default function LoadingScreen({ ready, label = 'Loading…', children }) {
  const [phase, setPhase] = useState('loading');
  const splashRef = useRef(null);
  const contentRef = useRef(null);
  const ringRef = useRef(null);

  useEffect(() => {
    if (!ringRef.current) return;
    const spin = gsap.to(ringRef.current, {
      rotate: 360,
      duration: 1,
      repeat: -1,
      ease: 'linear',
    });
    return () => spin.kill();
  }, []);

  useEffect(() => {
    if (!ready || phase === 'ready' || !splashRef.current) return;
    const tl = gsap.timeline({ onComplete: () => setPhase('ready') });
    tl.to(splashRef.current, { opacity: 0, duration: 0.35, ease: 'power2.out' });
  }, [ready, phase]);

  useEffect(() => {
    if (phase !== 'ready' || !contentRef.current) return;
    gsap.fromTo(
      contentRef.current,
      { opacity: 0, y: 14 },
      { opacity: 1, y: 0, duration: 0.5, ease: 'power2.out' }
    );
  }, [phase]);

  return (
    <>
      {phase !== 'ready' && (
        <div className="loading-screen" ref={splashRef}>
          <div className="loading-ring" ref={ringRef} />
          <p>{label}</p>
        </div>
      )}
      {phase === 'ready' && (
        <div className="loading-screen-content" ref={contentRef}>
          {children}
        </div>
      )}
    </>
  );
}
