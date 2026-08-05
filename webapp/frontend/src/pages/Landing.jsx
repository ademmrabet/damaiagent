import { useEffect, useRef, useState } from 'react';
import gsap from 'gsap';
import StatusDot from '../components/StatusDot.jsx';
import LoadingScreen from '../components/LoadingScreen.jsx';
import { checkHealth } from '../api.js';
import './landing.css';

function LandingContent() {
  const rootRef = useRef(null);

  useEffect(() => {
    const ctx = gsap.context(() => {
      const tl = gsap.timeline({ defaults: { ease: 'power3.out' } });
      tl.fromTo('.landing-badge', { opacity: 0, y: -10 }, { opacity: 1, y: 0, duration: 0.5 })
        .fromTo('.landing-title', { opacity: 0, y: 24 }, { opacity: 1, y: 0, duration: 0.7 }, '-=0.25')
        .fromTo('.landing-subtitle', { opacity: 0, y: 18 }, { opacity: 1, y: 0, duration: 0.6 }, '-=0.4')
        .fromTo(
          '.landing-card',
          { opacity: 0, y: 30, scale: 0.96 },
          { opacity: 1, y: 0, scale: 1, duration: 0.55, stagger: 0.12 },
          '-=0.3'
        )
        .fromTo('.landing-footnote', { opacity: 0 }, { opacity: 1, duration: 0.5 }, '-=0.2');

      // Slow-drifting background accents - the only continuous
      // animation on the page, kept subtle (low opacity, long
      // duration) so it reads as ambient motion, not distraction.
      gsap.to('.landing-blob-green', {
        x: 30,
        y: -20,
        duration: 9,
        repeat: -1,
        yoyo: true,
        ease: 'sine.inOut',
      });
      gsap.to('.landing-blob-red', {
        x: -24,
        y: 26,
        duration: 11,
        repeat: -1,
        yoyo: true,
        ease: 'sine.inOut',
      });
    }, rootRef);

    return () => ctx.revert();
  }, []);

  function onCardEnter(e) {
    gsap.to(e.currentTarget, { y: -6, duration: 0.25, ease: 'power2.out' });
  }
  function onCardLeave(e) {
    gsap.to(e.currentTarget, { y: 0, duration: 0.3, ease: 'power2.out' });
  }

  return (
    <div className="landing-root" ref={rootRef}>
      <div className="landing-blob landing-blob-green" />
      <div className="landing-blob landing-blob-red" />

      <div className="landing-status">
        <StatusDot />
        <span>Server status</span>
      </div>

      <main className="landing-main">
        <span className="landing-badge">Delegation of Authority Matrix</span>
        <h1 className="landing-title">DAM AI Agent</h1>
        <p className="landing-subtitle">
          Ask who approves, reviews, checks, initiates, or must be informed for any
          activity in the African Development Bank&rsquo;s Delegation of Authority
          Matrix &mdash; answered from a structured knowledge graph, not a document
          search.
        </p>

        <div className="landing-cards">
          <a
            className="landing-card"
            href="/chat"
            onMouseEnter={onCardEnter}
            onMouseLeave={onCardLeave}
          >
            <span className="landing-card-icon" aria-hidden="true">
              &#128172;
            </span>
            <h2>Chat with the Agent</h2>
            <p>Ask a question about any task, role, or authority code in the DAM.</p>
            <span className="landing-card-cta">Open chat &rarr;</span>
          </a>

          <a
            className="landing-card landing-card-alt"
            href="/dashboard"
            onMouseEnter={onCardEnter}
            onMouseLeave={onCardLeave}
          >
            <span className="landing-card-icon" aria-hidden="true">
              &#128202;
            </span>
            <h2>Open Dashboard</h2>
            <p>Structure and coverage overview of the whole matrix at a glance.</p>
            <span className="landing-card-cta">View dashboard &rarr;</span>
          </a>
        </div>

        <p className="landing-footnote">
          Facts are always retrieved from the DAM&rsquo;s own structure &mdash; an
          optional LLM mode only rephrases them, it never invents them.
        </p>
      </main>
    </div>
  );
}

export default function Landing() {
  const [bootChecked, setBootChecked] = useState(false);

  useEffect(() => {
    // Gated on a real signal (the first backend health probe), not a
    // fake timer - the splash means something ("is the DAM agent
    // actually reachable") instead of just padding out the load for
    // effect. Resolves either way (up or down); StatusDot keeps
    // polling and reflects the live state afterwards regardless.
    checkHealth()
      .catch(() => {})
      .finally(() => setBootChecked(true));
  }, []);

  return (
    <LoadingScreen ready={bootChecked} label="Connecting to the DAM Agent…">
      <LandingContent />
    </LoadingScreen>
  );
}
