/**
 * src/components/KPICards.jsx
 * ============================
 * Komponen KPI Cards untuk menampilkan metrik utama dashboard.
 * Menampilkan: Total SKU, Anomali Aktif, Butuh Restocking, Health Score.
 */

import React from 'react';
import { healthColor, confidenceColor } from '../utils/helpers';

// ─────────────────────────────────────────────────────────────
// Single KPI Card
// ─────────────────────────────────────────────────────────────

function KPICard({ label, value, sub, accentColor, badge, badgeType, icon, onClick }) {
  return (
    <div
      onClick={onClick}
      style={{
        background: 'var(--bg1)',
        border: '1px solid var(--border)',
        borderRadius: 14,
        padding: '16px 20px',
        position: 'relative',
        overflow: 'hidden',
        cursor: onClick ? 'pointer' : 'default',
        transition: 'border-color .2s, transform .15s',
      }}
      onMouseEnter={e => onClick && (e.currentTarget.style.transform = 'translateY(-2px)')}
      onMouseLeave={e => onClick && (e.currentTarget.style.transform = 'translateY(0)')}
    >
      {/* Top accent bar */}
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 2, background: accentColor }} />

      {/* Label */}
      <div style={{
        fontSize: 10, color: 'var(--text3)', textTransform: 'uppercase',
        letterSpacing: '.7px', marginBottom: 10, fontFamily: 'var(--font-mono)',
        display: 'flex', alignItems: 'center', gap: 6,
      }}>
        {icon && <span>{icon}</span>}
        {label}
      </div>

      {/* Value */}
      <div style={{
        fontSize: 30, fontWeight: 700, fontFamily: 'var(--font-mono)',
        lineHeight: 1, color: accentColor,
      }}>
        {value ?? '—'}
      </div>

      {/* Sub text */}
      {sub && (
        <div style={{ fontSize: 11, color: 'var(--text3)', marginTop: 8, lineHeight: 1.4 }}>
          {sub}
        </div>
      )}

      {/* Badge */}
      {badge && (
        <div style={{
          display: 'inline-flex', alignItems: 'center', gap: 3,
          fontSize: 10, fontFamily: 'var(--font-mono)',
          padding: '2px 6px', borderRadius: 4, marginTop: 8,
          background: badgeType === 'ok' ? '#22c55e20' : badgeType === 'warn' ? '#f0485a20' : '#f5a62320',
          color: badgeType === 'ok' ? '#22c55e' : badgeType === 'warn' ? '#f0485a' : '#f5a623',
        }}>
          {badgeType === 'ok' ? '▲' : '▼'} {badge}
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// KPI Cards Row
// ─────────────────────────────────────────────────────────────

export default function KPICards({ summary, loading }) {
  if (loading || !summary) {
    return (
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 14 }}>
        {Array(4).fill(0).map((_, i) => (
          <div key={i} style={{
            background: 'var(--bg1)', border: '1px solid var(--border)',
            borderRadius: 14, padding: '16px 20px', height: 110,
            animation: 'pulse 1.5s ease infinite',
          }} />
        ))}
      </div>
    );
  }

  const {
    total_skus = 0,
    anomaly_active = 0,
    health_score = 0,
    action_distribution = {},
    severity_distribution = {},
  } = summary;

  const restockCount  = action_distribution.RESTOCKING  || 0;
  const holdCount     = action_distribution.HOLD        || 0;
  const redistCount   = action_distribution.REDISTRIBUSI|| 0;
  const criticalCount = severity_distribution.Critical  || 0;
  const highCount     = severity_distribution.High      || 0;

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 14 }}>
      <KPICard
        label="Total SKU Terpantau"
        value={total_skus}
        accentColor="var(--teal)"
        icon="📦"
        sub="Semua kategori inventaris aktif"
        badge="Aktif" badgeType="ok"
      />
      <KPICard
        label="Anomali Aktif"
        value={anomaly_active}
        accentColor="var(--red)"
        icon="🚨"
        sub={`${criticalCount} Critical · ${highCount} High · ${(severity_distribution.Medium||0)} Medium`}
        badge={anomaly_active > 0 ? 'Perlu Tindakan' : 'Aman'}
        badgeType={anomaly_active > 0 ? 'warn' : 'ok'}
      />
      <KPICard
        label="Butuh Restocking"
        value={restockCount}
        accentColor="var(--amber)"
        icon="🔄"
        sub={`+ ${redistCount} Redistribusi · ${holdCount} Hold`}
        badge={restockCount > 4 ? 'Kritis' : restockCount > 0 ? 'Perhatian' : 'Normal'}
        badgeType={restockCount > 4 ? 'warn' : restockCount > 0 ? 'amber' : 'ok'}
      />
      <KPICard
        label="System Health Score"
        value={`${health_score}%`}
        accentColor={healthColor(health_score)}
        icon="💊"
        sub={`${action_distribution.MONITOR || 0} SKU dalam monitoring`}
        badge={health_score >= 70 ? 'Sehat' : health_score >= 40 ? 'Waspada' : 'Kritis'}
        badgeType={health_score >= 70 ? 'ok' : 'warn'}
      />
    </div>
  );
}
