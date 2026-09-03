import { useEffect, useRef } from 'react';
import Chart from 'chart.js/auto';

// Recreates the Chart.js instance whenever data/options/type change -
// the original version only ever built the chart once on mount (empty
// dependency array), so a chart fed new data after the first render
// silently kept showing the first render's numbers forever. That was
// never exercised before the dashboard rework (2026-08-06) added
// interactive filtering - nothing on the page used to change a
// chart's data after mount. Destroying and rebuilding on every change
// is simpler and safer than reaching into Chart.js's own incremental
// update API for a dataset this small (never more than 15 bars/slices).
export default function ChartCanvas({ type, data, options }) {
  const canvasRef = useRef(null);
  const chartRef = useRef(null);

  useEffect(() => {
    if (!canvasRef.current) return;
    chartRef.current = new Chart(canvasRef.current, { type, data, options });
    return () => chartRef.current?.destroy();
  }, [type, data, options]);

  return <canvas ref={canvasRef} />;
}
