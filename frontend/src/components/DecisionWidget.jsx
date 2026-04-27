/**
 * src/components/DecisionWidget.jsx
 * ====================================
 * Komponen AI Decision Recommendation dengan Explainable AI.
 * Menampilkan: aksi, confidence score, reasoning trail, key factors, feedback loop.
 */

import React, { useState } from 'react';
import { ACTION_CONFIG, RISK_CONFIG, confidenceColor, formatPercent } from '../utils/helpers';

// ─────────────────────────────────────────────────────────────
// Confidence Bar
// ─────────────────────────────────────────────────────────────

function ConfidenceBar({ score }) {
  const color = confidenceColor(score);
  return (
    <div style={{ flex: 1 }}>
      <div style={{ fontSize: 9, color: 'var(--text3)', fontFamily: 'var(--font-mono)',
        textTransform: 'uppercase', letterSpacing: '.6px', marginBottom: 5 }}>
        Confidence Score
      </div>
      <div style={{ height: 6, background: 'var(--bg0)', borderRadius: 3, overflow: 'hidden' }}>
        <div style={{
          height: '100%', borderRadius: 3, width: `${score}%`,
          background: color, transition: 'width .6s ease',
          boxShadow: `0 0 8px ${color}60`,
        }} />
      </div>
      <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color, marginTop: 4 }}>
        {score.toFixed(1)}%
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Reasoning Trail
// ─────────────────────────────────────────────────────────────

function ReasoningTrail({ steps }) {
  const [expanded, setExpanded] = useState(false);
  const displaySteps = expanded ? steps : steps.slice(0, 3);

  return (
    <div>
      <div style={{ fontSize: 9, color: 'var(--text3)', textTransform: 'uppercase',
        letterSpacing: '.7px', fontFamily: 'var(--font-mono)', marginBottom: 8 }}>
        Reasoning Trail (XAI) — {steps.length} langkah
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 5,
        maxHeight: expanded ? 'none' : 160, overflow: 'hidden' }}>
        {displaySteps.map((step, i) => (
          <div key={i} style={{
            display: 'flex', gap: 8, fontSize: 11, color: 'var(--text2)',
            lineHeight: 1.55, padding: '6px 8px', borderRadius: 6,
            background: 'var(--bg2)', border: '1px solid var(--border)',
          }}>
            <span style={{ color: 'var(--text3)', fontFamily: 'var(--font-mono)',
              fontSize: 9, flexShrink: 0, marginTop: 1 }}>
              {String(i + 1).padStart(2, '0')}
            </span>
            <span>{step}</span>
          </div>
        ))}
      </div>
      {steps.length > 3 && (
        <button onClick={() => setExpanded(e => !e)} style={{
          marginTop: 6, background: 'transparent', border: 'none',
          color: 'var(--teal)', fontSize: 11, cursor: 'pointer',
          fontFamily: 'var(--font-mono)', padding: 0,
        }}>
          {expanded ? '▲ Sembunyikan' : `▼ Lihat ${steps.length - 3} langkah lagi`}
        </button>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Key Factors Grid
// ─────────────────────────────────────────────────────────────

function KeyFactors({ factors }) {
  return (
    <div>
      <div style={{ fontSize: 9, color: 'var(--text3)', textTransform: 'uppercase',
        letterSpacing: '.7px', fontFamily: 'var(--font-mono)', marginBottom: 8 }}>
        Key Factors
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 5 }}>
        {Object.entries(factors || {}).slice(0, 8).map(([key, val]) => (
          <div key={key} style={{
            background: 'var(--bg2)', borderRadius: 6, padding: '7px 9px',
            border: '1px solid var(--border)',
          }}>
            <div style={{ fontSize: 9, color: 'var(--text3)', marginBottom: 2 }}>{key}</div>
            <div style={{ fontSize: 12, fontFamily: 'var(--font-mono)',
              color: 'var(--text)', fontWeight: 600 }}>{val}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Feedback Loop Buttons
// ─────────────────────────────────────────────────────────────

function FeedbackButtons({ skuId, action, onFeedback, submitted }) {
  const fb = submitted?.[skuId];

  return (
    <div>
      <div style={{ fontSize: 9, color: 'var(--text3)', textTransform: 'uppercase',
        letterSpacing: '.7px', fontFamily: 'var(--font-mono)', marginBottom: 8 }}>
        Feedback Loop — Continuous Learning
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
        {[
          { type: 'approved', label: '✓ Setuju', activeClass: 'green' },
          { type: 'rejected', label: '✗ Tolak',  activeClass: 'red' },
        ].map(({ type, label, activeClass }) => {
          const isActive = fb === type;
          const color = activeClass === 'green' ? '#22c55e' : '#f0485a';
          return (
            <button
              key={type}
              disabled={!!fb}
              onClick={() => onFeedback(skuId, action, type)}
              style={{
                flex: 1, padding: '8px 0', borderRadius: 8,
                border: `1px solid ${isActive ? color : color + '44'}`,
                background: isActive ? color + '20' : 'transparent',
                color, fontSize: 12, fontFamily: 'var(--font-mono)',
                cursor: fb ? 'not-allowed' : 'pointer',
                fontWeight: 600, transition: 'all .15s', opacity: fb && !isActive ? 0.4 : 1,
              }}
            >
              {isActive ? (type === 'approved' ? '✓ Disetujui' : '✗ Ditolak') : label}
            </button>
          );
        })}
      </div>
      {fb && (
        <div style={{ fontSize: 10, color: 'var(--text3)', marginTop: 6, textAlign: 'center' }}>
          Feedback dicatat. AI model akan ditingkatkan secara iteratif.
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Main Component
// ─────────────────────────────────────────────────────────────

export default function DecisionWidget({ decision, loading, onFeedback, submitted }) {
  if (loading) {
    return (
      <div style={{ padding: 20, display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: 'var(--text3)', fontFamily: 'var(--font-mono)', fontSize: 12, gap: 10, height: 200 }}>
        <div style={{ width: 16, height: 16, border: '2px solid var(--border)',
          borderTopColor: 'var(--purple)', borderRadius: '50%', animation: 'spin .6s linear infinite' }} />
        Memuat analisis XAI...
      </div>
    );
  }

  if (!decision) return null;

  const actionCfg = ACTION_CONFIG[decision.recommended_action] || ACTION_CONFIG.MONITOR;
  const riskCfg   = RISK_CONFIG[decision.risk_level] || RISK_CONFIG.Rendah;

  return (
    <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 14 }}>

      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <div style={{ fontSize: 9, color: 'var(--text3)', fontFamily: 'var(--font-mono)',
            textTransform: 'uppercase', letterSpacing: '.6px', marginBottom: 3 }}>
            Rekomendasi AI — DECIDE Layer
          </div>
          <div style={{ fontSize: 12, color: 'var(--text2)' }}>
            <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--teal)' }}>
              {decision.sku_id}
            </span>
            {' — '}
            <span style={{ color: 'var(--text)', fontWeight: 500 }}>{decision.sku_name}</span>
          </div>
          <div style={{ fontSize: 10, color: 'var(--text3)', marginTop: 2 }}>{decision.category}</div>
        </div>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
          <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', fontWeight: 600,
            padding: '3px 8px', borderRadius: 4, background: '#f5a62320', color: '#f5a623' }}>
            {decision.action_priority}
          </span>
          <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', fontWeight: 600,
            padding: '3px 8px', borderRadius: 4, background: riskCfg.bg, color: riskCfg.color }}>
            {decision.risk_level}
          </span>
        </div>
      </div>

      {/* Action + Confidence */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <div style={{
          padding: '6px 16px', borderRadius: 8, fontSize: 14,
          fontWeight: 800, fontFamily: 'var(--font-mono)', letterSpacing: '.5px',
          background: actionCfg.bg, color: actionCfg.color,
          border: `1px solid ${actionCfg.color}44`,
        }}>
          {actionCfg.icon} {decision.recommended_action}
        </div>
        <ConfidenceBar score={decision.confidence_score} />
      </div>

      {/* Action Detail */}
      <div style={{ fontSize: 12, color: 'var(--text2)', lineHeight: 1.65,
        padding: '10px 14px', background: 'var(--bg2)', borderRadius: 8,
        borderLeft: '3px solid var(--teal)' }}>
        {decision.action_detail}
      </div>

      {/* Loss warning */}
      {decision.estimated_loss_if_ignored && (
        <div style={{ fontSize: 11, color: '#f0485a', background: '#f0485a10',
          padding: '8px 12px', borderRadius: 6, borderLeft: '2px solid #f0485a' }}>
          ⚠ {decision.estimated_loss_if_ignored}
        </div>
      )}

      {/* Reasoning Trail */}
      <ReasoningTrail steps={decision.reasoning_path || []} />

      {/* Key Factors */}
      <KeyFactors factors={decision.key_factors} />

      {/* Divider */}
      <div style={{ height: 1, background: 'var(--border)' }} />

      {/* Feedback */}
      <FeedbackButtons
        skuId={decision.sku_id}
        action={decision.recommended_action}
        onFeedback={onFeedback}
        submitted={submitted}
      />
    </div>
  );
}
