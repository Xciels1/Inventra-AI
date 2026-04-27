/**
 * src/utils/helpers.js
 * ====================
 * Fungsi utilitas dan konstanta untuk Inventra AI Dashboard.
 */

// ─────────────────────────────────────────────────────────────
// Konstanta UI
// ─────────────────────────────────────────────────────────────

export const SEVERITY_CONFIG = {
  Normal:   { color: '#22c55e', bg: '#22c55e20', label: 'Normal',   order: 4 },
  Low:      { color: '#eab308', bg: '#eab30820', label: 'Low',      order: 3 },
  Medium:   { color: '#f97316', bg: '#f9731620', label: 'Medium',   order: 2 },
  High:     { color: '#f0485a', bg: '#f0485a20', label: 'High',     order: 1 },
  Critical: { color: '#a78bfa', bg: '#a78bfa20', label: 'Critical', order: 0 },
};

export const ACTION_CONFIG = {
  RESTOCKING:  { color: '#4a9eff', bg: '#4a9eff20', icon: '📦', label: 'Restocking' },
  HOLD:        { color: '#f0485a', bg: '#f0485a20', icon: '🛑', label: 'Hold' },
  REDISTRIBUSI:{ color: '#f5a623', bg: '#f5a62320', icon: '🔄', label: 'Redistribusi' },
  MONITOR:     { color: '#22c55e', bg: '#22c55e20', icon: '👁',  label: 'Monitor' },
};

export const RISK_CONFIG = {
  Kritis: { color: '#a78bfa', bg: '#a78bfa20' },
  Tinggi: { color: '#f0485a', bg: '#f0485a20' },
  Sedang: { color: '#f5a623', bg: '#f5a62320' },
  Rendah: { color: '#22c55e', bg: '#22c55e20' },
};

export const PRIORITY_ORDER = {
  'Segera': 0, 'Dalam 3 Hari': 1, 'Minggu Ini': 2, 'Opsional': 3,
};

// ─────────────────────────────────────────────────────────────
// Format utilities
// ─────────────────────────────────────────────────────────────

/** Format angka dengan separator ribuan (Rp 1.234.567) */
export function formatRupiah(value) {
  if (value == null) return '—';
  return `Rp ${Math.round(value).toLocaleString('id-ID')}`;
}

/** Format angka dengan unit */
export function formatUnit(value, unit = 'unit') {
  if (value == null) return '—';
  return `${Math.round(value).toLocaleString('id-ID')} ${unit}`;
}

/** Format persentase */
export function formatPercent(value, decimals = 1) {
  if (value == null) return '—';
  return `${(value * 100).toFixed(decimals)}%`;
}

/** Format tanggal ke bahasa Indonesia */
export function formatDate(dateStr) {
  if (!dateStr) return '—';
  const d = new Date(dateStr);
  return d.toLocaleDateString('id-ID', { day: 'numeric', month: 'short', year: 'numeric' });
}

/** Format timestamp singkat */
export function formatTime(isoStr) {
  if (!isoStr) return '—';
  return new Date(isoStr).toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' });
}

/** Format hari (3 hari, 14 hari, dst) */
export function formatDays(days) {
  if (days == null) return '—';
  if (days === 0) return 'Hari ini';
  if (days === 1) return '1 hari';
  return `${days} hari`;
}

// ─────────────────────────────────────────────────────────────
// Color helpers
// ─────────────────────────────────────────────────────────────

/** Warna berdasarkan confidence score */
export function confidenceColor(score) {
  if (score >= 80) return '#22c55e';
  if (score >= 60) return '#f5a623';
  return '#f0485a';
}

/** Warna berdasarkan hari tersisa */
export function daysColor(days) {
  if (days == null) return '#22c55e';
  if (days <= 7)  return '#f0485a';
  if (days <= 14) return '#f5a623';
  return '#22c55e';
}

/** Health score → warna */
export function healthColor(score) {
  if (score >= 70) return '#22c55e';
  if (score >= 40) return '#f5a623';
  return '#f0485a';
}

// ─────────────────────────────────────────────────────────────
// Sort helpers
// ─────────────────────────────────────────────────────────────

/** Urutkan SKU berdasarkan severity (kritis dulu) */
export function sortBySeverity(items, severityKey = 'severity') {
  return [...items].sort((a, b) => {
    const orderA = SEVERITY_CONFIG[a[severityKey]]?.order ?? 5;
    const orderB = SEVERITY_CONFIG[b[severityKey]]?.order ?? 5;
    return orderA - orderB;
  });
}

/** Urutkan keputusan berdasarkan prioritas dan confidence */
export function sortByPriority(decisions) {
  return [...decisions].sort((a, b) => {
    const pA = PRIORITY_ORDER[a.action_priority] ?? 4;
    const pB = PRIORITY_ORDER[b.action_priority] ?? 4;
    if (pA !== pB) return pA - pB;
    return b.confidence_score - a.confidence_score;
  });
}

// ─────────────────────────────────────────────────────────────
// Misc
// ─────────────────────────────────────────────────────────────

/** Dapatkan shift berdasarkan jam */
export function getCurrentShift() {
  const hour = new Date().getHours();
  if (hour >= 6  && hour < 14) return 'Shift Pagi';
  if (hour >= 14 && hour < 22) return 'Shift Siang';
  return 'Shift Malam';
}

/** Truncate teks panjang */
export function truncate(str, max = 60) {
  if (!str) return '';
  return str.length > max ? str.slice(0, max) + '…' : str;
}

/** Debounce function */
export function debounce(fn, delay = 300) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}
