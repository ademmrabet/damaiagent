import { useEffect, useMemo, useRef, useState } from 'react';
import gsap from 'gsap';
import Header from '../components/Header.jsx';
import LoadingScreen from '../components/LoadingScreen.jsx';
import ChartCanvas from '../components/ChartCanvas.jsx';
import { getDashboardSummary } from '../api.js';
import './dashboard.css';

const GREEN = '#228b22';
const GREEN_DARK = '#1c7a1c';
const PALETTE = [
  '#228b22', '#3aa73a', '#5cc25c', '#84d884', '#b3ecb3',
  '#1c7a1c', '#0f5c0f', '#c80815', '#e0524a', '#e88a84',
];

function topN(obj, n) {
  const entries = Object.entries(obj).sort((a, b) => b[1] - a[1]);
  const top = entries.slice(0, n);
  const rest = entries.slice(n).reduce((sum, [, v]) => sum + v, 0);
  if (rest > 0) top.push(['other', rest]);
  return top;
}

function Card({ value, label, warn }) {
  const ref = useRef(null);
  useEffect(() => {
    if (!ref.current) return;
    gsap.fromTo(
      ref.current,
      { opacity: 0, y: 16 },
      { opacity: 1, y: 0, duration: 0.4, ease: 'power2.out' }
    );
  }, []);
  return (
    <div className={'card' + (warn ? ' warn' : '')} ref={ref}>
      <div className="value">{value}</div>
      <div className="label">{label}</div>
    </div>
  );
}

function ChartBox({ title, full, action, children }) {
  const ref = useRef(null);
  useEffect(() => {
    if (!ref.current) return;
    gsap.fromTo(
      ref.current,
      { opacity: 0, y: 20 },
      { opacity: 1, y: 0, duration: 0.5, ease: 'power2.out' }
    );
  }, []);
  return (
    <div className={'chart-box' + (full ? ' full' : '')} ref={ref}>
      <div className="chart-box-header">
        <h2>{title}</h2>
        {action}
      </div>
      {children}
    </div>
  );
}

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(false);
  const [selectedChapter, setSelectedChapter] = useState('all');
  const [selectedAction, setSelectedAction] = useState(null);

  useEffect(() => {
    getDashboardSummary()
      .then(setData)
      .catch(() => setError(true));
  }, []);

  const ready = !!data || error;

  // The chapter filter re-scopes every card and chart on the page -
  // "all" is the whole-DAM data already flattened at the top level of
  // the response (see webapp/dashboard_data.py), any other value
  // looks up that chapter's own breakdown instead. Graph structure
  // (total_graph_nodes/total_edges) deliberately stays whole-DAM-only
  // regardless of this filter - role/reference edges routinely cross
  // chapter boundaries, so a "chapter subgraph" would need its own,
  // more complex semantics that aren't worth it for what this
  // dashboard needs (see the backend docstring for the full reasoning).
  const scope = useMemo(() => {
    if (!data) return null;
    return selectedChapter === 'all' ? data : data.by_chapter[selectedChapter];
  }, [data, selectedChapter]);

  // An action selected under one chapter's breakdown may not exist at
  // all under another (or under "all") - clearing it on every chapter
  // change avoids pointing the roles chart at stale, chapter-specific
  // data that no longer matches what's on screen.
  function handleChapterChange(chapter) {
    setSelectedChapter(chapter);
    setSelectedAction(null);
  }

  const rolesChartSource =
    selectedAction && scope ? scope.roles_by_action[selectedAction] || [] : scope?.top_roles ?? [];
  const actionEntries = scope ? topN(scope.action_counts, 10) : [];

  return (
    <div className="dashboard-page">
      <Header
        title="DAM Dashboard"
        subtitle="Delegation of Authority Matrix · structure & coverage overview"
        navHref="/chat"
        navLabel="← Back to chat"
      />

      <LoadingScreen ready={ready} label="Loading summary…">
        {error && (
          <div className="dashboard-error">
            Could not reach the backend. Is the server running?
          </div>
        )}

        {data && scope && (
          <main>
            <div className="dashboard-filters">
              <label htmlFor="chapter-filter">Chapter</label>
              <select
                id="chapter-filter"
                value={selectedChapter}
                onChange={(e) => handleChapterChange(e.target.value)}
              >
                <option value="all">All chapters</option>
                {data.chapters.map((chapter) => (
                  <option key={chapter} value={chapter}>
                    Chapter {chapter}
                  </option>
                ))}
              </select>
              {selectedChapter !== 'all' && (
                <button
                  type="button"
                  className="clear-filter-btn"
                  onClick={() => handleChapterChange('all')}
                >
                  Clear filter &times;
                </button>
              )}
            </div>

            <div className="cards">
              <Card value={scope.total_nodes} label="DAM nodes" />
              <Card value={scope.total_responsibilities} label="Responsibilities extracted" />
              <Card value={scope.distinct_roles} label="Distinct roles" />
              <Card value={data.graph.total_edges} label="Graph edges (whole DAM)" />
              <Card
                value={(scope.unresolved_rate * 100).toFixed(1) + '%'}
                label="Unresolved role rate"
                warn={scope.unresolved_rate > 0.02}
              />
              <Card
                value={scope.avg_responsibilities_per_node}
                label="Avg. responsibilities per node"
              />
              <Card
                value={(scope.no_direct_responsibilities_rate * 100).toFixed(1) + '%'}
                label="Nodes with no direct responsibilities"
                warn={scope.no_direct_responsibilities_rate > 0.15}
              />
            </div>

            <div className="charts">
              <ChartBox title="Nodes by type">
                <ChartCanvas
                  key={'types-' + selectedChapter}
                  type="bar"
                  data={{
                    labels: Object.keys(scope.node_counts_by_type),
                    datasets: [
                      { data: Object.values(scope.node_counts_by_type), backgroundColor: GREEN },
                    ],
                  }}
                  options={{
                    plugins: { legend: { display: false } },
                    scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
                  }}
                />
              </ChartBox>

              <ChartBox
                title={
                  selectedAction
                    ? `Top roles for action "${selectedAction}"`
                    : 'Top 15 roles by responsibility count'
                }
                action={
                  selectedAction && (
                    <button
                      type="button"
                      className="clear-filter-btn"
                      onClick={() => setSelectedAction(null)}
                    >
                      Show all actions &times;
                    </button>
                  )
                }
              >
                <ChartCanvas
                  key={'roles-' + selectedChapter + '-' + (selectedAction || 'all')}
                  type="bar"
                  data={{
                    labels: rolesChartSource.map((r) =>
                      r.role.length > 28 ? r.role.slice(0, 26) + '…' : r.role
                    ),
                    datasets: [
                      {
                        data: rolesChartSource.map((r) => r.count),
                        backgroundColor: GREEN_DARK,
                      },
                    ],
                  }}
                  options={{
                    indexAxis: 'y',
                    plugins: { legend: { display: false } },
                    scales: { x: { beginAtZero: true, ticks: { precision: 0 } } },
                  }}
                />
              </ChartBox>

              <ChartBox
                title="Action code distribution — click a bar to filter roles"
                full
              >
                <ChartCanvas
                  key={'actions-' + selectedChapter}
                  type="bar"
                  data={{
                    labels: actionEntries.map(([code]) => code),
                    datasets: [
                      {
                        data: actionEntries.map(([, c]) => c),
                        backgroundColor: actionEntries.map(([code], i) =>
                          code === selectedAction ? GREEN_DARK : PALETTE[i % PALETTE.length]
                        ),
                      },
                    ],
                  }}
                  options={{
                    plugins: { legend: { display: false } },
                    scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
                    onClick: (_evt, elements) => {
                      if (!elements.length) return;
                      const code = actionEntries[elements[0].index][0];
                      // "other" is a rollup of everything past the top
                      // 10, not a real action code - nothing in
                      // roles_by_action to look it up against.
                      if (code === 'other') return;
                      setSelectedAction((current) => (current === code ? null : code));
                    },
                  }}
                />
              </ChartBox>
            </div>
          </main>
        )}
      </LoadingScreen>
    </div>
  );
}
