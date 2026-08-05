import { useEffect, useRef, useState } from 'react';
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

function ChartBox({ title, full, children }) {
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
      <h2>{title}</h2>
      {children}
    </div>
  );
}

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    getDashboardSummary()
      .then(setData)
      .catch(() => setError(true));
  }, []);

  const ready = !!data || error;

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

        {data && (
          <main>
            <div className="cards">
              <Card value={data.total_nodes} label="DAM nodes" />
              <Card value={data.total_responsibilities} label="Responsibilities extracted" />
              <Card value={data.distinct_roles} label="Distinct roles" />
              <Card value={data.graph.total_edges} label="Graph edges" />
              <Card
                value={(data.unresolved_rate * 100).toFixed(1) + '%'}
                label="Unresolved role rate"
                warn={data.unresolved_rate > 0.02}
              />
            </div>

            <div className="charts">
              <ChartBox title="Nodes by type">
                <ChartCanvas
                  type="bar"
                  data={{
                    labels: Object.keys(data.node_counts_by_type),
                    datasets: [
                      { data: Object.values(data.node_counts_by_type), backgroundColor: GREEN },
                    ],
                  }}
                  options={{
                    plugins: { legend: { display: false } },
                    scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
                  }}
                />
              </ChartBox>

              <ChartBox title="Top 15 roles by responsibility count">
                <ChartCanvas
                  type="bar"
                  data={{
                    labels: data.top_roles.map((r) =>
                      r.role.length > 28 ? r.role.slice(0, 26) + '…' : r.role
                    ),
                    datasets: [
                      {
                        data: data.top_roles.map((r) => r.count),
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

              <ChartBox title="Action code distribution" full>
                <ChartCanvas
                  type="bar"
                  data={{
                    labels: topN(data.action_counts, 10).map(([code]) => code),
                    datasets: [
                      {
                        data: topN(data.action_counts, 10).map(([, c]) => c),
                        backgroundColor: topN(data.action_counts, 10).map(
                          (_, i) => PALETTE[i % PALETTE.length]
                        ),
                      },
                    ],
                  }}
                  options={{
                    plugins: { legend: { display: false } },
                    scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
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
