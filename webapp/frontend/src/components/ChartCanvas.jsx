import { useEffect, useRef } from 'react';
import Chart from 'chart.js/auto';
// rebuild the chart whenever data or options change

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
