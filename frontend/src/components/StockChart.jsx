/**
 * src/components/StockChart.jsx
 * ==============================
 * Komponen grafik tren stok interaktif menggunakan Chart.js.
 * Menampilkan: historis aktual + proyeksi forecast + reorder point.
 */

import React, { useEffect, useRef } from 'react';
import { formatUnit, daysColor } from '../utils/helpers';

export default function StockChart({ data, skuName, loading }) {
  const canvasRef = useRef(null);
  const chartRef  = useRef(null);

  useEffect(() => {
    if (!data || !canvasRef.current) return;

    // Hancurkan chart lama sebelum membuat yang baru
    if (chartRef.current) {
      chartRef.current.destroy();
      chartRef.current = null;
    }

    const { historical = [], forecast = [], reorder_point = 0 } = data;
    const allPoints = [...historical, ...forecast];
    const labels    = allPoints.map(d => d.date.slice(5));   // MM-DD
    const splitIdx  = historical.length;

    // Dataset: Stok Aktual (historis saja)
    const stockActual = [
      ...historical.map(d => d.stock_level),
      ...Array(forecast.length).fill(null),
    ];

    // Dataset: Proyeksi Stok (forecast saja)
    const stockForecast = [
      ...Array(historical.length).fill(null),
      ...forecast.map(d => d.stock_level),
    ];

    // Dataset: Konsumsi harian (semua)
    const consumption = allPoints.map(d => d.daily_consumption);

    // Dataset: Reorder Point (garis datar)
    const reorderLine = Array(allPoints.length).fill(reorder_point);

    // Tandai zona kritis pada forecast
    const criticalZone = allPoints.map((d, i) =>
      i >= splitIdx && d.stock_level <= reorder_point ? d.stock_level : null
    );

    chartRef.current = new window.Chart(canvasRef.current, {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label: 'Stok Aktual',
            data: stockActual,
            borderColor: '#00d4aa',
            backgroundColor: 'rgba(0, 212, 170, 0.08)',
            fill: true,
            tension: 0.35,
            borderWidth: 2.5,
            pointRadius: 0,
            pointHoverRadius: 5,
            pointHoverBackgroundColor: '#00d4aa',
          },
          {
            label: 'Proyeksi Stok',
            data: stockForecast,
            borderColor: '#4a9eff',
            backgroundColor: 'rgba(74, 158, 255, 0.06)',
            fill: true,
            tension: 0.35,
            borderWidth: 2,
            borderDash: [6, 4],
            pointRadius: 0,
            pointHoverRadius: 5,
            pointHoverBackgroundColor: '#4a9eff',
          },
          {
            label: 'Zona Kritis',
            data: criticalZone,
            borderColor: '#f0485a',
            backgroundColor: 'rgba(240, 72, 90, 0.15)',
            fill: true,
            tension: 0.35,
            borderWidth: 0,
            pointRadius: 0,
          },
          {
            label: 'Konsumsi/Hari',
            data: consumption,
            borderColor: '#f5a623',
            backgroundColor: 'transparent',
            tension: 0.3,
            borderWidth: 1.5,
            pointRadius: 0,
            pointHoverRadius: 4,
            yAxisID: 'y2',
          },
          {
            label: 'Reorder Point',
            data: reorderLine,
            borderColor: '#f0485a',
            backgroundColor: 'transparent',
            borderWidth: 1.5,
            borderDash: [4, 3],
            pointRadius: 0,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        animation: { duration: 400 },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: '#0d1626',
            borderColor: '#1e3050',
            borderWidth: 1,
            titleColor: '#8da0b8',
            bodyColor: '#e8edf5',
            padding: 12,
            callbacks: {
              title: ctx => `Tanggal: ${ctx[0].label}`,
              label: ctx => {
                if (ctx.raw == null) return null;
                const icons = {
                  'Stok Aktual': '📦',
                  'Proyeksi Stok': '🔮',
                  'Konsumsi/Hari': '⚡',
                  'Reorder Point': '🔴',
                  'Zona Kritis': null,
                };
                const icon = icons[ctx.dataset.label];
                if (!icon) return null;
                return ` ${icon} ${ctx.dataset.label}: ${Math.round(ctx.raw).toLocaleString('id')} unit`;
              },
            },
          },
        },
        scales: {
          x: {
            grid: { color: 'rgba(30, 48, 80, 0.5)' },
            ticks: {
              color: '#4d6480',
              font: { size: 10, family: 'JetBrains Mono, monospace' },
              maxTicksLimit: 9,
            },
          },
          y: {
            grid: { color: 'rgba(30, 48, 80, 0.4)' },
            ticks: {
              color: '#4d6480',
              font: { size: 10, family: 'JetBrains Mono, monospace' },
              callback: val => val.toLocaleString('id'),
            },
            title: {
              display: true,
              text: 'Level Stok (unit)',
              color: '#4d6480',
              font: { size: 10 },
            },
          },
          y2: {
            position: 'right',
            grid: { display: false },
            ticks: {
              color: '#4d6480',
              font: { size: 10 },
            },
            title: {
              display: true,
              text: 'Konsumsi',
              color: '#4d6480',
              font: { size: 10 },
            },
          },
        },
      },
    });

    return () => {
      if (chartRef.current) {
        chartRef.current.destroy();
        chartRef.current = null;
      }
    };
  }, [data]);

  if (loading) {
    return (
      <div style={{ height: 220, display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: 'var(--text3)', fontFamily: 'var(--font-mono)', fontSize: 12, gap: 10 }}>
        <div style={{ width: 16, height: 16, border: '2px solid var(--border)',
          borderTopColor: 'var(--teal)', borderRadius: '50%', animation: 'spin .6s linear infinite' }} />
        Memuat data chart...
      </div>
    );
  }

  if (!data) return null;

  // ── Metadata ringkas di bawah chart ──
  const hist = data.historical || [];
  const lastStock = hist.slice(-1)[0]?.stock_level ?? 0;
  const avgCons   = Math.round(hist.reduce((a, d) => a + d.daily_consumption, 0) / Math.max(hist.length, 1));
  const daysLeft  = avgCons > 0 ? Math.round(lastStock / avgCons) : 0;
  const maxReject = Math.max(...hist.map(d => d.reject_qty || 0));

  return (
    <div style={{ padding: '16px 20px' }}>
      {/* Legend */}
      <div style={{ display: 'flex', gap: 14, marginBottom: 12, flexWrap: 'wrap' }}>
        {[
          ['#00d4aa', 'Stok Aktual'],
          ['#4a9eff', 'Proyeksi'],
          ['#f5a623', 'Konsumsi/Hari'],
          ['#f0485a', 'Reorder Point'],
        ].map(([color, label]) => (
          <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 5,
            fontSize: 11, color: 'var(--text3)' }}>
            <div style={{ width: 8, height: 8, borderRadius: 2, background: color }} />
            {label}
          </div>
        ))}
      </div>

      {/* Canvas */}
      <div style={{ position: 'relative', height: 210 }}>
        <canvas ref={canvasRef} role="img" aria-label={`Grafik tren stok ${skuName}`} />
      </div>

      {/* Meta stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 10,
        marginTop: 16, paddingTop: 16, borderTop: '1px solid var(--border)' }}>
        {[
          { val: lastStock.toLocaleString('id'), lbl: 'Stok Saat Ini', color: 'var(--teal)' },
          { val: `${avgCons}/hari`, lbl: 'Avg Konsumsi', color: 'var(--amber)' },
          { val: `${daysLeft} hari`, lbl: 'Estimasi Tersisa', color: daysColor(daysLeft) },
          { val: maxReject.toLocaleString('id'), lbl: 'Max Reject (30hr)', color: 'var(--red)' },
        ].map(({ val, lbl, color }) => (
          <div key={lbl} style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 16, fontWeight: 700, fontFamily: 'var(--font-mono)', color }}>{val}</div>
            <div style={{ fontSize: 10, color: 'var(--text3)', textTransform: 'uppercase',
              letterSpacing: '.5px', marginTop: 3 }}>{lbl}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
