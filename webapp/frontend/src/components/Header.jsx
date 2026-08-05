import StatusDot from './StatusDot.jsx';

// onMenuClick is only passed by pages that have an off-canvas sidebar
// (currently just Chat, for the conversation list) - the hamburger
// button only renders when there's something for it to toggle, and
// only becomes visible at all below the mobile breakpoint (see
// shared.css's .hamburger-btn, hidden by default on desktop).
export default function Header({ title, subtitle, navHref, navLabel, right, onMenuClick }) {
  return (
    <header className="app-header">
      <div className="header-left">
        {onMenuClick && (
          <button
            type="button"
            className="hamburger-btn"
            aria-label="Toggle conversations"
            onClick={onMenuClick}
          >
            <span />
            <span />
            <span />
          </button>
        )}
        <div className="title-block">
          <StatusDot />
          <div>
            <h1>{title}</h1>
            <p>{subtitle}</p>
          </div>
        </div>
      </div>
      <div className="header-right">
        {right}
        {navHref ? (
          <a className="nav-link" href={navHref}>
            {navLabel}
          </a>
        ) : null}
      </div>
    </header>
  );
}
