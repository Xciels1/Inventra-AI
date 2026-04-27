/**
 * src/hooks/useInventraAPI.js
 * ===========================
 * Custom React hooks untuk mengambil data dari Inventra AI Backend API.
 * Handles loading states, error handling, dan auto-refresh.
 */

import { useState, useEffect, useCallback, useRef } from 'react';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// ─────────────────────────────────────────────────────────────
// Core fetch utility
// ─────────────────────────────────────────────────────────────

async function apiFetch(path, options = {}) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);

  try {
    const response = await fetch(`${API_BASE}${path}`, {
      signal: controller.signal,
      method: options.method || 'GET',
      headers: { 'Content-Type': 'application/json' },
      body: options.body,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const json = await response.json();
    return json.data ?? json;
  } catch (err) {
    clearTimeout(timeoutId);
    throw err;
  }
}

// ─────────────────────────────────────────────────────────────
// Generic data fetching hook
// ─────────────────────────────────────────────────────────────

function useFetch(path, { deps = [], autoRefresh = 0 } = {}) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const intervalRef = useRef(null);

  const fetch = useCallback(async () => {
    if (!path) return;
    setLoading(true);
    setError(null);
    try {
      const result = await apiFetch(path);
      setData(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [path, ...deps]);

  useEffect(() => {
    fetch();
    if (autoRefresh > 0) {
      intervalRef.current = setInterval(fetch, autoRefresh);
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [fetch, autoRefresh]);

  return { data, loading, error, refetch: fetch };
}

// ─────────────────────────────────────────────────────────────
// Dashboard hooks
// ─────────────────────────────────────────────────────────────

/** Hook untuk KPI dashboard summary — auto-refresh setiap 30 detik */
export function useDashboardSummary() {
  return useFetch('/api/v1/dashboard/summary', { autoRefresh: 30000 });
}

/** Hook untuk inventory snapshot real-time */
export function useInventorySnapshot() {
  return useFetch('/api/v1/inventory/snapshot', { autoRefresh: 60000 });
}

// ─────────────────────────────────────────────────────────────
// Per-SKU hooks
// ─────────────────────────────────────────────────────────────

/** Hook untuk forecast satu SKU */
export function useSkuForecast(skuId, horizon = 14) {
  return useFetch(
    skuId ? `/api/v1/sku/${skuId}/forecast?horizon=${horizon}` : null,
    { deps: [skuId, horizon] }
  );
}

/** Hook untuk anomaly detection satu SKU */
export function useSkuAnomaly(skuId) {
  return useFetch(
    skuId ? `/api/v1/sku/${skuId}/anomaly` : null,
    { deps: [skuId] }
  );
}

/** Hook untuk XAI decision satu SKU */
export function useSkuDecision(skuId, horizon = 14) {
  return useFetch(
    skuId ? `/api/v1/sku/${skuId}/decision?horizon=${horizon}` : null,
    { deps: [skuId, horizon] }
  );
}

/** Hook untuk semua keputusan sekaligus */
export function useAllDecisions(filterAction = null, filterRisk = null) {
  let path = '/api/v1/decisions/all';
  const params = [];
  if (filterAction) params.push(`filter_action=${filterAction}`);
  if (filterRisk) params.push(`filter_risk=${filterRisk}`);
  if (params.length) path += '?' + params.join('&');

  return useFetch(path, { deps: [filterAction, filterRisk] });
}

// ─────────────────────────────────────────────────────────────
// Chart data hook
// ─────────────────────────────────────────────────────────────

/** Hook untuk time-series chart data */
export function useStockChart(skuId, days = 30, forecastHorizon = 14) {
  return useFetch(
    skuId
      ? `/api/v1/chart/${skuId}/stock?days=${days}&include_forecast=true&forecast_horizon=${forecastHorizon}`
      : null,
    { deps: [skuId, days, forecastHorizon] }
  );
}

/** Hook untuk anomaly heatmap data */
export function useAnomalyHeatmap() {
  return useFetch('/api/v1/chart/anomalies/heatmap', { autoRefresh: 60000 });
}

// ─────────────────────────────────────────────────────────────
// Catalog hook
// ─────────────────────────────────────────────────────────────

/** Hook untuk katalog produk */
export function useProductCatalog() {
  return useFetch('/api/v1/catalog');
}

// ─────────────────────────────────────────────────────────────
// Chat hook
// ─────────────────────────────────────────────────────────────

/**
 * Hook untuk AI Insight Assistant chat.
 * Mengelola riwayat percakapan dan session ID.
 */
export function useChat() {
  const [messages, setMessages] = useState([
    {
      role: 'bot',
      text: 'Selamat datang! Saya Inventra AI Assistant. Silakan ajukan pertanyaan tentang inventaris manufaktur Anda dalam Bahasa Indonesia. 👋',
      timestamp: new Date().toISOString(),
    },
  ]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const sessionId = useRef(`session_${Date.now()}`);

  const sendMessage = useCallback(async (text) => {
    if (!text.trim() || loading) return;

    const userMsg = { role: 'user', text, timestamp: new Date().toISOString() };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);
    setError(null);

    try {
      const result = await apiFetch('/api/v1/chat', {
        method: 'POST',
        body: JSON.stringify({ message: text, session_id: sessionId.current }),
      });

      const botMsg = {
        role: 'bot',
        text: result.message,
        source: result.source,
        timestamp: result.timestamp,
      };
      setMessages((prev) => [...prev, botMsg]);
    } catch (err) {
      setError('Gagal menghubungi asisten. Pastikan backend berjalan.');
      setMessages((prev) => [
        ...prev,
        {
          role: 'bot',
          text: 'Maaf, terjadi kesalahan koneksi. Pastikan backend API berjalan di port 8000.',
          timestamp: new Date().toISOString(),
        },
      ]);
    } finally {
      setLoading(false);
    }
  }, [loading]);

  const clearHistory = useCallback(async () => {
    try {
      await apiFetch(`/api/v1/chat/${sessionId.current}`, { method: 'DELETE' });
    } catch {}
    sessionId.current = `session_${Date.now()}`;
    setMessages([{
      role: 'bot',
      text: 'Percakapan direset. Ada yang bisa saya bantu?',
      timestamp: new Date().toISOString(),
    }]);
  }, []);

  return { messages, loading, error, sendMessage, clearHistory };
}

// ─────────────────────────────────────────────────────────────
// Feedback hook
// ─────────────────────────────────────────────────────────────

/**
 * Hook untuk mengirim feedback loop operator.
 */
export function useFeedback() {
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState({});  // { [skuId]: 'approved'|'rejected' }

  const submitFeedback = useCallback(async ({ skuId, action, feedback, note, operatorId }) => {
    setSubmitting(true);
    try {
      await apiFetch('/api/v1/feedback', {
        method: 'POST',
        body: JSON.stringify({
          sku_id: skuId,
          decision_action: action,
          feedback,
          note,
          operator_id: operatorId || 'operator_demo',
        }),
      });
      setSubmitted((prev) => ({ ...prev, [skuId]: feedback }));
      return true;
    } catch (err) {
      console.error('Gagal mengirim feedback:', err);
      return false;
    } finally {
      setSubmitting(false);
    }
  }, []);

  return { submitFeedback, submitting, submitted };
}

// ─────────────────────────────────────────────────────────────
// Backend health check hook
// ─────────────────────────────────────────────────────────────

/**
 * Hook untuk memeriksa apakah backend API tersedia.
 * Auto-retry setiap 10 detik jika offline.
 */
export function useBackendHealth() {
  const [isOnline, setIsOnline] = useState(null);
  const [checking, setChecking] = useState(true);

  const check = useCallback(async () => {
    setChecking(true);
    try {
      const result = await apiFetch('/api/v1/health');
      setIsOnline(result.status === 'healthy');
    } catch {
      setIsOnline(false);
    } finally {
      setChecking(false);
    }
  }, []);

  useEffect(() => {
    check();
    const interval = setInterval(check, 10000);
    return () => clearInterval(interval);
  }, [check]);

  return { isOnline, checking, retry: check };
}

export { apiFetch };
