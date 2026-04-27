/**
 * src/pages/Dashboard.jsx
 * ========================
 * Halaman utama Dashboard Inventra AI.
 * Mengintegrasikan semua komponen: KPI, Chart, Anomaly, Decision, Chat, Table.
 */

import React, { useState, useCallback } from 'react';
import KPICards from '../components/KPICards';
import StockChart from '../components/StockChart';
import DecisionWidget from '../components/DecisionWidget';
import {
  useDashboardSummary, useInventorySnapshot, useStockChart,
  useSkuDecision, useChat, useFeedback, useBackendHealth,
} from '../hooks/useInventraAPI';
import {
  SEVERITY_CONFIG, ACTION_CONFIG, sortBySeverity,
  sortByPriority, formatPercent, getCurrentShift,
} from '../utils/helpers';

// ─────────────────────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────────────────────

const QUICK_MESSAGES = [
  'Barang apa yang paling berisiko?',
  'Status inventaris hari ini?',
  'SKU mana yang perlu dipesan?',
  'Anomali apa yang sedang aktif?',
];

// ─────────────────────────────────────────────────────────────
// Header Component
// ─────────────────────────────────────────────────────────────

function Header({ healthScore, isOnline, onRefresh }) {
  const dotColor = isOnline ? '#22c55e' : '#f5a623';
  const hColor   = healthScore >= 70 ? '#22c55e' : healthScore >= 40 ? '#f5a623' : '#f0485a';

  return (
    <header style={{
      background: 'var(--bg1)', borderBottom: '1px solid var(--border)',
      padding: '0 24px', height: 56, display: 'flex', alignItems: 'center',
      justifyContent: 'space-between', position: 'sticky', top: 0, zIndex: 100,
    }}>
      {/* Brand */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <div style={{
          width: 32, height: 32, background: 'var(--teal)', borderRadius: 9,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: 13, color: '#000',
        }}>IA</div>
        <div>
          <div style={{ fontSize: 15, fontWeight: 600 }}>Inventra AI</div>
          <div style={{ fontSize: 10, color: 'var(--text3)', fontFamily: 'var(--font-mono)' }}>
            Intelligent Inventory Decision Engine
          </div>
        </div>
      </div>

      {/* Right side */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
        {/* Health pill */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, background: 'var(--bg2)',
          border: '1px solid var(--border)', borderRadius: 20, padding: '4px 12px' }}>
          <div style={{ width: 7, height: 7, borderRadius: '50%', background: hColor,
            boxShadow: `0 0 6px ${hColor}` }} />
          <span style={{ fontSize: 11, color: 'var(--text2)', fontFamily: 'var(--font-mono)' }}>
            System Health
          </span>
          <span style={{ fontSize: 13, fontWeight: 700, fontFamily: 'var(--font-mono)', color: hColor }}>
            {healthScore ?? '—'}%
          </span>
        </div>

        {/* API status */}
        <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', padding: '3px 8px',
          borderRadius: 4, background: isOnline ? '#22c55e20' : '#f5a62320',
          color: isOnline ? '#22c55e' : '#f5a623', border: `1px solid ${dotColor}33` }}>
          ● {isOnline ? 'API Connected' : 'Demo Mode'}
        </span>

        {/* Shift */}
        <span style={{ fontSize: 10, color: 'var(--text3)', fontFamily: 'var(--font-mono)' }}>
          {getCurrentShift()} · {new Date().toLocaleTimeString('id-ID')}
        </span>

        {/* Refresh */}
        <button onClick={onRefresh} style={{
          background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 8,
          padding: '5px 12px', color: 'var(--text2)', fontSize: 12, cursor: 'pointer',
          display: 'flex', alignItems: 'center', gap: 5, transition: 'all .15s',
        }}
          onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--teal)'; e.currentTarget.style.color = 'var(--teal)'; }}
          onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.color = 'var(--text2)'; }}>
          ↻ Refresh
        </button>
      </div>
    </header>
  );
}

// ─────────────────────────────────────────────────────────────
// SKU Tab Selector
// ─────────────────────────────────────────────────────────────

function SKUTabs({ skus, selectedSku, onSelect }) {
  return (
    <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap', padding: '10px 16px',
      borderBottom: '1px solid var(--border)', background: 'var(--bg2)' }}>
      {skus.map(s => {
        const sevColor = SEVERITY_CONFIG[s.anomaly_severity || 'Normal']?.color || '#22c55e';
        const isActive = s.sku_id === selectedSku;
        return (
          <button key={s.sku_id} onClick={() => onSelect(s.sku_id)} style={{
            padding: '4px 11px', borderRadius: 6, cursor: 'pointer', fontSize: 10,
            fontFamily: 'var(--font-mono)', transition: 'all .12s', whiteSpace: 'nowrap',
            background: isActive ? 'var(--teal)' : 'transparent',
            color: isActive ? '#000' : 'var(--text2)',
            border: isActive ? '1px solid var(--teal)' : '1px solid var(--border)',
            fontWeight: isActive ? 700 : 400,
          }}>
            <span style={{ color: isActive ? '#000' : sevColor, marginRight: 3, fontSize: 8 }}>●</span>
            {s.sku_id}
          </button>
        );
      })}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Anomaly Panel
// ─────────────────────────────────────────────────────────────

function AnomalyPanel({ skus, selectedSku, onSelect }) {
  const sorted = sortBySeverity(skus, 'anomaly_severity');
  const countBySev = sev => skus.filter(s => s.anomaly_severity === sev).length;

  return (
    <div style={{ display: 'flex', flexDirection: 'column' }}>
      {/* Panel header */}
      <div style={{ padding: '13px 18px', borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 13,
          fontWeight: 600, color: 'var(--text)' }}>
          <div style={{ width: 7, height: 7, borderRadius: '50%', background: 'var(--red)',
            boxShadow: '0 0 6px var(--red)' }} />
          Active Anomalies
        </div>
        <div style={{ display: 'flex', gap: 5 }}>
          {[['Critical','#a78bfa'],['High','#f0485a'],['Medium','#f97316']].map(([sev, col]) => {
            const cnt = countBySev(sev);
            return cnt > 0 && (
              <span key={sev} style={{ fontSize: 9, fontFamily: 'var(--font-mono)',
                padding: '2px 6px', borderRadius: 3, background: col+'20', color: col }}>
                {cnt} {sev}
              </span>
            );
          })}
        </div>
      </div>

      {/* List */}
      <div style={{ overflow: 'auto', maxHeight: 420 }}>
        {sorted.map(s => {
          const sevCfg = SEVERITY_CONFIG[s.anomaly_severity || 'Normal'];
          const isSelected = s.sku_id === selectedSku;
          const rejectRate = ((s.reject_rate || 0) * 100).toFixed(1);
          const holdRatio  = ((s.hold_qty || 0) / Math.max(s.stock_level || 1, 1) * 100).toFixed(1);

          return (
            <div key={s.sku_id} onClick={() => onSelect(s.sku_id)} style={{
              padding: '11px 16px', cursor: 'pointer', borderBottom: '1px solid var(--border)',
              background: isSelected ? 'var(--bg2)' : 'transparent',
              transition: 'background .1s', display: 'grid',
              gridTemplateColumns: 'auto 1fr auto', gap: 9, alignItems: 'start',
            }}
              onMouseEnter={e => !isSelected && (e.currentTarget.style.background = 'var(--bg2)')}
              onMouseLeave={e => !isSelected && (e.currentTarget.style.background = 'transparent')}
            >
              {/* Severity badge */}
              <span style={{ padding: '2px 6px', borderRadius: 3, fontSize: 9,
                fontFamily: 'var(--font-mono)', fontWeight: 700, whiteSpace: 'nowrap',
                background: sevCfg?.bg, color: sevCfg?.color, alignSelf: 'start', marginTop: 2 }}>
                {s.anomaly_severity || 'Normal'}
              </span>

              {/* Info */}
              <div>
                <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--teal)' }}>
                  {s.sku_id}
                </div>
                <div style={{ fontSize: 11, color: 'var(--text)', fontWeight: 500, marginTop: 1 }}>
                  {s.sku_name}
                </div>
                <div style={{ display: 'flex', gap: 5, marginTop: 5, flexWrap: 'wrap' }}>
                  <span style={{ fontSize: 9, fontFamily: 'var(--font-mono)', padding: '1px 5px',
                    borderRadius: 3, background: 'var(--bg0)', border: '1px solid var(--border)',
                    color: '#f0485a' }}>
                    R:{rejectRate}%
                  </span>
                  <span style={{ fontSize: 9, fontFamily: 'var(--font-mono)', padding: '1px 5px',
                    borderRadius: 3, background: 'var(--bg0)', border: '1px solid var(--border)',
                    color: '#f5a623' }}>
                    H:{holdRatio}%
                  </span>
                  <span style={{ fontSize: 9, fontFamily: 'var(--font-mono)', padding: '1px 5px',
                    borderRadius: 3, background: 'var(--bg0)', border: '1px solid var(--border)',
                    color: 'var(--text3)' }}>
                    {(s.stock_level || 0).toLocaleString('id')} u
                  </span>
                </div>
              </div>

              {/* Category */}
              <div style={{ fontSize: 9, color: 'var(--text3)', marginTop: 2,
                textAlign: 'right', lineHeight: 1.3 }}>
                {s.category?.split(' ')[0] || ''}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Chat Window
// ─────────────────────────────────────────────────────────────

function ChatWindow() {
  const { messages, loading, sendMessage, clearHistory } = useChat();
  const [input, setInput] = useState('');
  const endRef = React.useRef(null);

  React.useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = () => {
    if (!input.trim()) return;
    sendMessage(input);
    setInput('');
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Messages */}
      <div style={{ flex: 1, overflowY: 'auto', padding: 14,
        display: 'flex', flexDirection: 'column', gap: 8, minHeight: 0 }}>
        {messages.map((m, i) => (
          <div key={i} style={{
            maxWidth: '88%', padding: '9px 13px', borderRadius: 10,
            fontSize: 12, lineHeight: 1.6, whiteSpace: 'pre-wrap',
            alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start',
            background: m.role === 'user' ? 'var(--teal)' : 'var(--bg2)',
            color: m.role === 'user' ? '#000' : 'var(--text)',
            fontWeight: m.role === 'user' ? 600 : 400,
            border: m.role === 'bot' ? '1px solid var(--border)' : 'none',
            borderBottomRightRadius: m.role === 'user' ? 3 : 10,
            borderBottomLeftRadius: m.role === 'bot' ? 3 : 10,
            animation: 'fadeUp .2s ease',
          }}>
            {m.text}
          </div>
        ))}
        {loading && (
          <div style={{ alignSelf: 'flex-start', fontSize: 11, color: 'var(--text3)',
            fontStyle: 'italic', padding: '6px 12px', background: 'var(--bg2)',
            border: '1px solid var(--border)', borderRadius: 10 }}>
            Menganalisis data inventaris...
          </div>
        )}
        <div ref={endRef} />
      </div>

      {/* Quick buttons */}
      <div style={{ display: 'flex', gap: 5, padding: '7px 12px',
        borderTop: '1px solid var(--border)', overflowX: 'auto', background: 'var(--bg1)',
        flexShrink: 0 }}>
        {QUICK_MESSAGES.map(q => (
          <button key={q} onClick={() => sendMessage(q)} style={{
            padding: '3px 9px', borderRadius: 10, border: '1px solid var(--border)',
            background: 'transparent', color: 'var(--text3)', fontSize: 10,
            cursor: 'pointer', whiteSpace: 'nowrap', flexShrink: 0, transition: 'all .1s',
          }}
            onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--teal)'; e.currentTarget.style.color = 'var(--teal)'; }}
            onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.color = 'var(--text3)'; }}>
            {q}
          </button>
        ))}
      </div>

      {/* Input row */}
      <div style={{ display: 'flex', gap: 7, padding: '10px 12px',
        borderTop: '1px solid var(--border)', background: 'var(--bg2)', flexShrink: 0 }}>
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSend()}
          placeholder="Tanyakan sesuatu tentang inventaris..."
          disabled={loading}
          style={{
            flex: 1, background: 'var(--bg0)', border: '1px solid var(--border)',
            borderRadius: 7, padding: '7px 11px', color: 'var(--text)',
            fontFamily: 'var(--font-ui)', fontSize: 12, outline: 'none',
          }}
        />
        <button onClick={handleSend} disabled={loading || !input.trim()} style={{
          background: 'var(--teal)', border: 'none', borderRadius: 7,
          padding: '7px 14px', color: '#000', fontWeight: 700, fontSize: 11,
          cursor: loading || !input.trim() ? 'not-allowed' : 'pointer',
          opacity: loading || !input.trim() ? .4 : 1, whiteSpace: 'nowrap',
        }}>
          Kirim
        </button>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// All SKU Table
// ─────────────────────────────────────────────────────────────

function AllSKUTable({ skus, onSelect }) {
  const sorted = sortBySeverity(skus, 'anomaly_severity');
  const acConfig = ACTION_CONFIG;
  const riskColors = {
    Kritis: '#a78bfa', Tinggi: '#f0485a', Sedang: '#f5a623', Rendah: '#22c55e',
  };

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
        <thead>
          <tr style={{ borderBottom: '1px solid var(--border)' }}>
            {['SKU ID','Nama Produk','Kategori','Severity','Tindakan','Prioritas','Risk','Confidence'].map(h => (
              <th key={h} style={{ padding: '10px 16px', textAlign: 'left',
                fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text3)',
                textTransform: 'uppercase', letterSpacing: '.6px', whiteSpace: 'nowrap' }}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map(s => {
            const sevCfg = SEVERITY_CONFIG[s.anomaly_severity || 'Normal'];
            // Simulasi decision untuk display tabel (data dari snapshot)
            const mockAction = s.anomaly_severity === 'Critical' ? 'RESTOCKING'
              : s.anomaly_severity === 'High' ? 'RESTOCKING'
              : s.anomaly_severity === 'Medium' ? 'RESTOCKING'
              : s.anomaly_severity === 'Low' ? 'MONITOR' : 'MONITOR';
            const mockPriority = s.anomaly_severity === 'Critical' ? 'Segera'
              : s.anomaly_severity === 'High' ? 'Dalam 3 Hari'
              : s.anomaly_severity === 'Medium' ? 'Minggu Ini' : 'Opsional';
            const mockRisk = s.anomaly_severity === 'Critical' ? 'Kritis'
              : s.anomaly_severity === 'High' ? 'Tinggi'
              : s.anomaly_severity === 'Medium' ? 'Sedang' : 'Rendah';
            const mockConf = s.anomaly_severity === 'Critical' ? 89.1
              : s.anomaly_severity === 'High' ? 77.3
              : s.anomaly_severity === 'Medium' ? 68.5 : 82.0;

            const aCfg = acConfig[mockAction];
            const confColor = mockConf >= 80 ? '#22c55e' : mockConf >= 60 ? '#f5a623' : '#f0485a';

            return (
              <tr key={s.sku_id} onClick={() => onSelect(s.sku_id)}
                style={{ borderBottom: '1px solid var(--border)', cursor: 'pointer', transition: 'background .1s' }}
                onMouseEnter={e => e.currentTarget.style.background = 'var(--bg2)'}
                onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                <td style={{ padding: '10px 16px', fontFamily: 'var(--font-mono)', color: 'var(--teal)', fontSize: 11 }}>
                  {s.sku_id}
                </td>
                <td style={{ padding: '10px 16px', color: 'var(--text)', fontWeight: 500 }}>
                  {s.sku_name}
                </td>
                <td style={{ padding: '10px 16px', color: 'var(--text2)' }}>
                  {s.category}
                </td>
                <td style={{ padding: '10px 16px' }}>
                  <span style={{ padding: '2px 6px', borderRadius: 3, fontSize: 9,
                    fontFamily: 'var(--font-mono)', fontWeight: 700,
                    background: sevCfg?.bg, color: sevCfg?.color }}>
                    {s.anomaly_severity || 'Normal'}
                  </span>
                </td>
                <td style={{ padding: '10px 16px' }}>
                  <span style={{ color: aCfg?.color, fontFamily: 'var(--font-mono)',
                    fontWeight: 700, fontSize: 10 }}>
                    {aCfg?.icon} {mockAction}
                  </span>
                </td>
                <td style={{ padding: '10px 16px', color: 'var(--text2)', fontSize: 10 }}>
                  {mockPriority}
                </td>
                <td style={{ padding: '10px 16px' }}>
                  <span style={{ color: riskColors[mockRisk] || 'var(--text2)',
                    fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: 10 }}>
                    {mockRisk}
                  </span>
                </td>
                <td style={{ padding: '10px 16px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <div style={{ flex: 1, height: 3, background: 'var(--bg0)',
                      borderRadius: 2, minWidth: 55 }}>
                      <div style={{ height: '100%', borderRadius: 2,
                        width: mockConf + '%', background: confColor }} />
                    </div>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text2)', minWidth: 38 }}>
                      {mockConf.toFixed(1)}%
                    </span>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Main Dashboard Page
// ─────────────────────────────────────────────────────────────

export default function Dashboard() {
  const [selectedSku, setSelectedSku] = useState('SKU-006');

  const { isOnline } = useBackendHealth();
  const { data: summaryData, loading: summaryLoading, refetch: refetchSummary } = useDashboardSummary();
  const { data: snapshotData, loading: snapshotLoading, refetch: refetchSnapshot } = useInventorySnapshot();
  const { data: chartData, loading: chartLoading } = useStockChart(selectedSku, 30, 14);
  const { data: decisionData, loading: decisionLoading } = useSkuDecision(selectedSku, 14);
  const { submitFeedback, submitted } = useFeedback();

  const skus = snapshotData?.snapshot || [];
  const summary = summaryData || {};

  const handleRefresh = useCallback(() => {
    refetchSummary();
    refetchSnapshot();
  }, [refetchSummary, refetchSnapshot]);

  const handleFeedback = useCallback(async (skuId, action, type) => {
    await submitFeedback({ skuId, action, feedback: type, operatorId: 'operator_demo' });
  }, [submitFeedback]);

  const panelStyle = {
    background: 'var(--bg1)', border: '1px solid var(--border)', borderRadius: 14, overflow: 'hidden',
  };

  const panelHeaderStyle = {
    padding: '13px 18px', borderBottom: '1px solid var(--border)',
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
  };

  const panelTitleStyle = {
    fontSize: 13, fontWeight: 600, color: 'var(--text)',
    display: 'flex', alignItems: 'center', gap: 7,
  };

  return (
    <div style={{ minHeight: '100vh' }}>
      <Header
        healthScore={summary.health_score}
        isOnline={isOnline}
        onRefresh={handleRefresh}
      />

      <main style={{ padding: '18px 24px', display: 'flex', flexDirection: 'column', gap: 18 }}>

        {/* KPI Row */}
        <KPICards summary={summary} loading={summaryLoading} />

        {/* Row 2: Chart + Anomaly */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 360px', gap: 16, alignItems: 'start' }}>
          {/* Stock Chart Panel */}
          <div style={panelStyle}>
            <div style={panelHeaderStyle}>
              <div style={panelTitleStyle}>
                <div style={{ width: 7, height: 7, borderRadius: '50%',
                  background: 'var(--teal)', boxShadow: '0 0 5px var(--teal)' }} />
                Tren Stok & Proyeksi 14 Hari
              </div>
              <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', padding: '2px 7px',
                borderRadius: 3, background: 'var(--teal-dim)', color: 'var(--teal)' }}>
                PREDICT Layer
              </span>
            </div>
            {skus.length > 0 && (
              <SKUTabs skus={skus} selectedSku={selectedSku} onSelect={setSelectedSku} />
            )}
            <StockChart
              data={chartData}
              skuName={skus.find(s => s.sku_id === selectedSku)?.sku_name || selectedSku}
              loading={chartLoading}
            />
          </div>

          {/* Anomaly Panel */}
          <div style={panelStyle}>
            <AnomalyPanel skus={skus} selectedSku={selectedSku} onSelect={setSelectedSku} />
          </div>
        </div>

        {/* Row 3: Decision + Chat */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, alignItems: 'start' }}>
          {/* Decision Widget */}
          <div style={panelStyle}>
            <div style={panelHeaderStyle}>
              <div style={panelTitleStyle}>
                <div style={{ width: 7, height: 7, borderRadius: '50%',
                  background: 'var(--purple)', boxShadow: '0 0 5px var(--purple)' }} />
                AI Decision Recommendation
              </div>
              <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', padding: '2px 7px',
                borderRadius: 3, background: 'var(--teal-dim)', color: 'var(--teal)' }}>
                DECIDE Layer · XAI
              </span>
            </div>
            <DecisionWidget
              decision={decisionData}
              loading={decisionLoading}
              onFeedback={handleFeedback}
              submitted={submitted}
            />
          </div>

          {/* Chat */}
          <div style={{ ...panelStyle, display: 'flex', flexDirection: 'column', minHeight: 420 }}>
            <div style={panelHeaderStyle}>
              <div style={panelTitleStyle}>
                <div style={{ width: 7, height: 7, borderRadius: '50%',
                  background: 'var(--teal)', boxShadow: '0 0 5px var(--teal)' }} />
                AI Insight Assistant
              </div>
              <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', padding: '2px 7px',
                borderRadius: 3, background: 'var(--teal-dim)', color: 'var(--teal)' }}>
                GPT-4o / Claude
              </span>
            </div>
            <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
              <ChatWindow />
            </div>
          </div>
        </div>

        {/* Row 4: Full SKU Table */}
        <div style={panelStyle}>
          <div style={panelHeaderStyle}>
            <div style={panelTitleStyle}>
              <div style={{ width: 7, height: 7, borderRadius: '50%', background: 'var(--amber)' }} />
              Daftar SKU — 3-Layer Intelligence Analysis
            </div>
            <span style={{ fontSize: 10, color: 'var(--text3)', fontFamily: 'var(--font-mono)' }}>
              Predict · Detect · Decide
            </span>
          </div>
          {skus.length > 0 && (
            <AllSKUTable skus={skus} onSelect={setSelectedSku} />
          )}
          {snapshotLoading && (
            <div style={{ padding: 20, textAlign: 'center', color: 'var(--text3)',
              fontFamily: 'var(--font-mono)', fontSize: 11 }}>
              Memuat data inventaris...
            </div>
          )}
        </div>

        {/* Footer */}
        <div style={{ textAlign: 'center', padding: '16px 0',
          borderTop: '1px solid var(--border)', fontFamily: 'var(--font-mono)',
          fontSize: 10, color: 'var(--text3)', display: 'flex',
          justifyContent: 'space-between' }}>
          <span>Inventra AI v1.0.0 — Intelligent Inventory Decision Engine</span>
          <span>Manufaktur & Energi · Dicoding AI Impact Challenge 2025</span>
          <span>Predict · Detect · Decide · Explain</span>
        </div>

      </main>
    </div>
  );
}
