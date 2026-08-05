import StatusDot from './StatusDot.jsx';

export default function Header({ title, subtitle, navHref, navLabel, right }) {
  return (
    <header className="app-header">
      <div className="title-block">
        <StatusDot />
        <div>
          <h1>{title}</h1>
          <p>{subtitle}</p>
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
