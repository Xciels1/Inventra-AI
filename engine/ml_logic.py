"""
engine/ml_logic.py
==================
Inti dari Inventra AI — Intelligent Inventory Decision Engine.
Mengimplementasikan tiga lapis intelijen:

  1. PREDICT  → Forecasting kebutuhan stok 7–30 hari ke depan
                (algoritma: moving average + trend decomposition + seasonality)
  2. DETECT   → Deteksi anomali real-time
                (algoritma: Isolation Forest + statistical thresholds)
  3. DECIDE   → XAI Decision Engine: Restocking / Hold / Redistribusi
                (output: action, confidence_score, reasoning_path, risk_level)

Catatan: Untuk demo kompetisi, forecasting menggunakan pendekatan
lightweight berbasis NumPy/Pandas yang mensimulasikan perilaku Prophet/LSTM
tanpa memerlukan training time yang panjang.

Author  : Inventra AI Team
Version : 1.0.0
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
import warnings
import logging

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("inventra.ml_logic")


# ─────────────────────────────────────────────────────────────
# Data Classes untuk Output Terstruktur
# ─────────────────────────────────────────────────────────────

@dataclass
class ForecastResult:
    """Hasil prediksi kebutuhan stok."""
    sku_id: str
    sku_name: str
    forecast_horizon_days: int
    predicted_consumption: List[float]          # konsumsi per hari
    predicted_stock_levels: List[float]         # proyeksi stok per hari
    predicted_dates: List[str]                   # tanggal proyeksi
    days_until_critical: Optional[int]          # berapa hari sampai stok kritis
    recommended_restock_qty: int                 # jumlah unit yang perlu dipesan
    recommended_restock_date: str               # tanggal ideal pemesanan
    confidence: float                            # 0.0 – 1.0
    trend_direction: str                         # "turun" | "naik" | "stabil"
    model_used: str = "MovingAverage+Trend"


@dataclass
class AnomalyResult:
    """Hasil deteksi anomali untuk satu SKU."""
    sku_id: str
    sku_name: str
    is_anomaly: bool
    anomaly_score: float                         # makin negatif = makin anomali (IF convention)
    anomaly_normalized: float                    # 0.0 – 1.0 (makin tinggi = makin anomali)
    severity: str                                # "Normal" | "Low" | "Medium" | "High" | "Critical"
    severity_color: str                          # warna untuk UI
    anomaly_types: List[str]                     # daftar jenis anomali terdeteksi
    triggered_rules: List[str]                   # aturan statistik yang terlewati
    current_reject_rate: float
    current_hold_ratio: float
    current_stock_level: int
    detected_at: str


@dataclass
class DecisionResult:
    """Output lengkap AI Decision Engine dengan Explainable AI."""
    sku_id: str
    sku_name: str
    category: str

    # ── Keputusan Utama ──
    recommended_action: str                      # "RESTOCKING" | "HOLD" | "REDISTRIBUSI" | "MONITOR"
    action_priority: str                         # "Segera" | "Dalam 3 Hari" | "Minggu Ini" | "Opsional"
    confidence_score: float                      # 0 – 100 (%)
    risk_level: str                              # "Kritis" | "Tinggi" | "Sedang" | "Rendah"

    # ── Explainable AI ──
    reasoning_path: List[str]                    # langkah-langkah logika AI
    key_factors: Dict[str, str]                  # faktor kunci dan nilainya
    supporting_evidence: List[str]               # bukti pendukung dari data

    # ── Konteks Tindakan ──
    action_detail: str                           # instruksi tindakan spesifik
    estimated_impact: str                        # dampak jika tindakan diambil
    estimated_loss_if_ignored: Optional[str]     # kerugian jika diabaikan

    # ── Sumber Data ──
    forecast_summary: str
    anomaly_summary: str
    generated_at: str

    # ── Feedback Loop ──
    feedback_status: str = "pending"             # "pending" | "approved" | "rejected"
    feedback_note: Optional[str] = None


# ─────────────────────────────────────────────────────────────
# Kelas Utama: InventoryEngine
# ─────────────────────────────────────────────────────────────

class InventoryEngine:
    """
    Engine AI utama Inventra AI.
    Mengorkestrasi tiga lapis analisis: Predict → Detect → Decide.

    Cara penggunaan:
        engine = InventoryEngine()
        engine.fit(historical_df)

        forecast = engine.predict_demand("SKU-001", horizon=14)
        anomaly  = engine.detect_anomalies("SKU-001")
        decision = engine.generate_decision("SKU-001")
    """

    # Ambang batas untuk klasifikasi reject rate
    REJECT_THRESHOLDS = {
        "critical": 0.15,   # ≥15% reject → kritis
        "high":     0.08,   # ≥8% → tinggi
        "medium":   0.05,   # ≥5% → sedang
        "low":      0.03,   # ≥3% → rendah
    }

    # Ambang batas untuk hold ratio
    HOLD_THRESHOLDS = {
        "critical": 0.25,
        "high":     0.15,
        "medium":   0.08,
        "low":      0.04,
    }

    # Ambang batas hari tersisa sebelum stok kritis
    CRITICAL_DAYS_THRESHOLD = 7
    WARNING_DAYS_THRESHOLD = 14

    def __init__(self):
        self.scaler = StandardScaler()
        self.isolation_forest = IsolationForest(
            n_estimators=150,
            contamination=0.08,         # ~8% data diasumsikan anomali
            random_state=42,
            max_samples="auto",
        )
        self._fitted = False
        self._historical_df: Optional[pd.DataFrame] = None
        self._product_catalog: Optional[List[Dict]] = None
        logger.info("InventoryEngine diinisialisasi.")

    # ──────────────────────────────────────────────────
    # FIT: Latih model dengan data historis
    # ──────────────────────────────────────────────────

    def fit(self, historical_df: pd.DataFrame, product_catalog: Optional[List] = None):
        """
        Latih model anomali dengan data historis inventaris.

        Args:
            historical_df: DataFrame dengan kolom inventaris lengkap.
            product_catalog: Katalog produk dari data_generator.
        """
        self._historical_df = historical_df.copy()
        self._product_catalog = product_catalog

        # Fitur untuk Isolation Forest
        features_df = historical_df[[
            "stock_level",
            "daily_consumption",
            "reject_qty",
            "hold_qty",
            "unreleased_qty",
            "reject_rate",
        ]].fillna(0)

        scaled = self.scaler.fit_transform(features_df)
        self.isolation_forest.fit(scaled)
        self._fitted = True
        logger.info(f"Model dilatih dengan {len(historical_df)} records dari "
                    f"{historical_df['sku_id'].nunique()} SKU.")

    def _get_sku_data(self, sku_id: str) -> pd.DataFrame:
        """Ambil data historis untuk satu SKU, diurutkan berdasarkan tanggal."""
        if self._historical_df is None:
            raise RuntimeError("Engine belum di-fit. Panggil fit() terlebih dahulu.")
        df = self._historical_df[self._historical_df["sku_id"] == sku_id].copy()
        df = df.sort_values("date").reset_index(drop=True)
        return df

    def _get_product_info(self, sku_id: str) -> Dict:
        """Ambil informasi produk dari katalog."""
        if self._product_catalog:
            for p in self._product_catalog:
                if p["sku_id"] == sku_id:
                    return p
        # Fallback: ekstrak dari historical data
        df = self._get_sku_data(sku_id)
        if len(df) > 0:
            row = df.iloc[-1]
            return {
                "sku_id": sku_id,
                "sku_name": row.get("sku_name", sku_id),
                "category": row.get("category", "Unknown"),
                "lead_time_days": int(row.get("lead_time_days", 14)),
                "reorder_point": int(row.get("reorder_point", 100)),
                "unit_cost": int(row.get("unit_cost", 0)),
            }
        return {}

    # ──────────────────────────────────────────────────
    # LAYER 1: PREDICT — Forecasting Kebutuhan Stok
    # ──────────────────────────────────────────────────

    def predict_demand(
        self, sku_id: str, horizon: int = 14
    ) -> ForecastResult:
        """
        LAYER 1 — PREDICT
        Prediksi kebutuhan stok dan proyeksi level stok untuk N hari ke depan.

        Metodologi:
        - Dekomposisi tren (regresi linear)
        - Seasonality mingguan (Fourier terms sederhana)
        - Moving average sebagai baseline
        - Confidence band berdasarkan volatilitas historis

        Args:
            sku_id  : ID SKU yang akan dianalisis
            horizon : Horizon prediksi dalam hari (default 14)

        Returns:
            ForecastResult dengan proyeksi lengkap
        """
        df = self._get_sku_data(sku_id)
        product = self._get_product_info(sku_id)

        if len(df) < 10:
            raise ValueError(f"Data tidak cukup untuk SKU {sku_id}. Minimal 10 hari.")

        # ── 1. Ekstrak series konsumsi historis ──
        consumption_series = df["daily_consumption"].values.astype(float)
        stock_series = df["stock_level"].values.astype(float)
        n = len(consumption_series)

        # ── 2. Hitung trend menggunakan regresi linear ──
        x = np.arange(n)
        trend_coeff = np.polyfit(x, consumption_series, 1)  # [slope, intercept]
        trend_slope = trend_coeff[0]

        # ── 3. Hitung seasonality mingguan (moving mean per hari-dalam-minggu) ──
        day_of_week_means = np.array([
            consumption_series[i::7].mean() if len(consumption_series[i::7]) > 0 else consumption_series.mean()
            for i in range(7)
        ])
        overall_mean = consumption_series.mean()
        seasonal_factors = day_of_week_means / (overall_mean + 1e-10)

        # ── 4. Moving average (window 7 hari) sebagai baseline ──
        window = min(7, n)
        moving_avg = np.convolve(
            consumption_series, np.ones(window) / window, mode="valid"
        )
        last_ma = moving_avg[-1] if len(moving_avg) > 0 else overall_mean

        # ── 5. Proyeksikan ke depan ──
        last_day_index = n - 1
        future_consumption = []
        future_dates = []
        today = datetime.now()

        for i in range(1, horizon + 1):
            future_date = today + timedelta(days=i)
            dow = future_date.weekday()  # 0=Senin, 6=Minggu

            # Gabungkan: MA + trend + seasonality
            trend_component = trend_slope * (last_day_index + i)
            seasonal_component = seasonal_factors[dow % 7] * last_ma
            blended = 0.6 * seasonal_component + 0.4 * (last_ma + trend_component * 0.1)
            blended = max(1.0, blended + np.random.normal(0, last_ma * 0.05))

            future_consumption.append(round(blended, 1))
            future_dates.append(future_date.strftime("%Y-%m-%d"))

        # ── 6. Proyeksikan level stok ke depan ──
        current_stock = float(stock_series[-1])
        lead_time = int(product.get("lead_time_days", 14))
        reorder_point = int(product.get("reorder_point", 100))

        future_stocks = []
        temp_stock = current_stock
        days_until_critical = None

        for i, c in enumerate(future_consumption):
            temp_stock = max(0.0, temp_stock - c)
            future_stocks.append(round(temp_stock, 0))
            if days_until_critical is None and temp_stock <= reorder_point:
                days_until_critical = i + 1

        # ── 7. Hitung rekomendasi restock ──
        total_projected_consumption = sum(future_consumption)
        safety_stock = last_ma * lead_time * 1.2
        recommended_restock_qty = max(
            0,
            int(total_projected_consumption + safety_stock - current_stock),
        )

        # Tanggal pemesanan ideal: (hari kritis - lead time)
        if days_until_critical and days_until_critical > lead_time:
            restock_date = today + timedelta(days=days_until_critical - lead_time)
        elif days_until_critical:
            restock_date = today  # segera
        else:
            restock_date = today + timedelta(days=max(1, horizon - lead_time))

        # ── 8. Tentukan arah tren ──
        avg_first_half = np.mean(stock_series[: n // 2])
        avg_second_half = np.mean(stock_series[n // 2 :])
        if avg_second_half < avg_first_half * 0.9:
            trend_direction = "turun"
        elif avg_second_half > avg_first_half * 1.1:
            trend_direction = "naik"
        else:
            trend_direction = "stabil"

        # ── 9. Confidence berdasarkan volatilitas data ──
        cv = np.std(consumption_series) / (np.mean(consumption_series) + 1e-10)
        confidence = max(0.55, min(0.95, 1.0 - cv * 0.6))

        return ForecastResult(
            sku_id=sku_id,
            sku_name=product.get("sku_name", sku_id),
            forecast_horizon_days=horizon,
            predicted_consumption=future_consumption,
            predicted_stock_levels=[float(s) for s in future_stocks],
            predicted_dates=future_dates,
            days_until_critical=days_until_critical,
            recommended_restock_qty=recommended_restock_qty,
            recommended_restock_date=restock_date.strftime("%Y-%m-%d"),
            confidence=round(confidence, 3),
            trend_direction=trend_direction,
        )

    # ──────────────────────────────────────────────────
    # LAYER 2: DETECT — Deteksi Anomali Real-time
    # ──────────────────────────────────────────────────

    def detect_anomalies(self, sku_id: str) -> AnomalyResult:
        """
        LAYER 2 — DETECT
        Deteksi anomali inventaris menggunakan kombinasi:
        - Isolation Forest (ML-based, unsupervised)
        - Rule-based statistical thresholds

        Mendeteksi: reject spike, hold anomaly, critical stock,
        abnormal consumption pattern.

        Args:
            sku_id: ID SKU yang akan dianalisis

        Returns:
            AnomalyResult dengan severity dan triggered rules
        """
        if not self._fitted:
            raise RuntimeError("Engine belum di-fit. Panggil fit() terlebih dahulu.")

        df = self._get_sku_data(sku_id)
        product = self._get_product_info(sku_id)

        # Ambil data terbaru (7 hari terakhir untuk analisis)
        recent = df.tail(7).copy()
        latest = df.iloc[-1]

        current_reject_rate = float(latest.get("reject_rate", 0))
        current_hold_qty = float(latest.get("hold_qty", 0))
        current_stock = float(latest.get("stock_level", 0))
        available_stock = float(latest.get("available_stock", current_stock))
        current_hold_ratio = current_hold_qty / (current_stock + 1e-10)

        # ── 1. Isolation Forest Score ──
        feature_row = np.array([[
            current_stock,
            float(latest.get("daily_consumption", 0)),
            float(latest.get("reject_qty", 0)),
            current_hold_qty,
            float(latest.get("unreleased_qty", 0)),
            current_reject_rate,
        ]])
        scaled_row = self.scaler.transform(feature_row)
        if_score = float(self.isolation_forest.score_samples(scaled_row)[0])
        # Normalisasi IF score → 0-1 (makin tinggi makin anomali)
        anomaly_normalized = max(0.0, min(1.0, (-if_score - 0.3) / 0.7))

        # ── 2. Rule-based detection ──
        triggered_rules: List[str] = []
        anomaly_types: List[str] = []

        # Reject Rate spike
        historical_avg_reject = float(df["reject_rate"].mean())
        if current_reject_rate >= self.REJECT_THRESHOLDS["critical"]:
            triggered_rules.append(
                f"Reject rate {current_reject_rate*100:.1f}% melampaui ambang kritis (≥15%)"
            )
            anomaly_types.append("reject_critical")
        elif current_reject_rate >= self.REJECT_THRESHOLDS["high"]:
            triggered_rules.append(
                f"Reject rate {current_reject_rate*100:.1f}% melampaui ambang tinggi (≥8%)"
            )
            anomaly_types.append("reject_high")
        elif current_reject_rate > historical_avg_reject * 2.5:
            triggered_rules.append(
                f"Reject rate {current_reject_rate*100:.1f}% melebihi 2.5× rata-rata historis "
                f"({historical_avg_reject*100:.1f}%)"
            )
            anomaly_types.append("reject_spike")

        # Hold Ratio anomali
        if current_hold_ratio >= self.HOLD_THRESHOLDS["critical"]:
            triggered_rules.append(
                f"Rasio hold {current_hold_ratio*100:.1f}% melampaui ambang kritis (≥25%)"
            )
            anomaly_types.append("hold_critical")
        elif current_hold_ratio >= self.HOLD_THRESHOLDS["high"]:
            triggered_rules.append(
                f"Rasio hold {current_hold_ratio*100:.1f}% di atas normal (≥15%)"
            )
            anomaly_types.append("hold_high")

        # Stok kritis
        reorder_point = int(product.get("reorder_point", 100))
        if current_stock <= reorder_point * 0.5:
            triggered_rules.append(
                f"Stok ({int(current_stock)}) di bawah 50% reorder point ({reorder_point})"
            )
            anomaly_types.append("critical_stock")
        elif current_stock <= reorder_point:
            triggered_rules.append(
                f"Stok ({int(current_stock)}) menyentuh reorder point ({reorder_point})"
            )
            anomaly_types.append("low_stock")

        # Lonjakan konsumsi tak normal
        recent_consumption = recent["daily_consumption"].values
        if len(recent_consumption) >= 3:
            recent_avg = np.mean(recent_consumption[:-1])
            latest_consumption = recent_consumption[-1]
            if latest_consumption > recent_avg * 1.8:
                triggered_rules.append(
                    f"Konsumsi harian ({int(latest_consumption)}) melonjak "
                    f"{((latest_consumption/recent_avg)-1)*100:.0f}% di atas rata-rata 7 hari"
                )
                anomaly_types.append("consumption_spike")

        # ── 3. Tentukan apakah ini anomali dan severity-nya ──
        is_anomaly = len(triggered_rules) > 0 or anomaly_normalized > 0.5

        # Hitung severity gabungan (IF score + rule count)
        combined_score = anomaly_normalized * 0.4 + min(1.0, len(triggered_rules) * 0.2) * 0.6

        if not is_anomaly:
            severity = "Normal"
            severity_color = "#22c55e"  # hijau
        elif combined_score >= 0.75 or any(t in anomaly_types for t in ["reject_critical", "hold_critical", "critical_stock"]):
            severity = "Critical"
            severity_color = "#7c3aed"  # ungu
        elif combined_score >= 0.55 or any(t in anomaly_types for t in ["reject_high", "hold_high"]):
            severity = "High"
            severity_color = "#ef4444"  # merah
        elif combined_score >= 0.35:
            severity = "Medium"
            severity_color = "#f97316"  # oranye
        else:
            severity = "Low"
            severity_color = "#eab308"  # kuning

        return AnomalyResult(
            sku_id=sku_id,
            sku_name=product.get("sku_name", sku_id),
            is_anomaly=is_anomaly,
            anomaly_score=round(if_score, 4),
            anomaly_normalized=round(anomaly_normalized, 3),
            severity=severity,
            severity_color=severity_color,
            anomaly_types=anomaly_types,
            triggered_rules=triggered_rules,
            current_reject_rate=round(current_reject_rate, 4),
            current_hold_ratio=round(current_hold_ratio, 4),
            current_stock_level=int(current_stock),
            detected_at=datetime.now().isoformat(),
        )

    # ──────────────────────────────────────────────────
    # LAYER 3: DECIDE — XAI Decision Engine
    # ──────────────────────────────────────────────────

    def generate_decision(
        self,
        sku_id: str,
        forecast_horizon: int = 14,
    ) -> DecisionResult:
        """
        LAYER 3 — DECIDE (Explainable AI)
        Mengintegrasikan output PREDICT dan DETECT menjadi rekomendasi tindakan
        dengan confidence score dan reasoning trail yang dapat diaudit.

        Aksi yang mungkin direkomendasikan:
        - RESTOCKING   : Segera lakukan pemesanan ulang stok
        - HOLD         : Tahan pengiriman/penggunaan sampai investigasi selesai
        - REDISTRIBUSI : Pindahkan stok antar gudang/lini produksi
        - MONITOR      : Pantau saja, kondisi masih aman

        Args:
            sku_id           : ID SKU yang akan dianalisis
            forecast_horizon : Horizon prediksi (hari)

        Returns:
            DecisionResult dengan penjelasan XAI lengkap
        """
        product = self._get_product_info(sku_id)
        sku_name = product.get("sku_name", sku_id)
        category = product.get("category", "Unknown")
        unit_cost = int(product.get("unit_cost", 0))
        lead_time = int(product.get("lead_time_days", 14))

        # ── Jalankan kedua layer sebelumnya ──
        forecast = self.predict_demand(sku_id, horizon=forecast_horizon)
        anomaly  = self.detect_anomalies(sku_id)

        # ── Kumpulkan sinyal keputusan ──
        signals: Dict[str, float] = {}
        reasoning_path: List[str] = []
        supporting_evidence: List[str] = []

        # ── Sinyal 1: Stok kritis berdasarkan forecast ──
        if forecast.days_until_critical is not None:
            days_left = forecast.days_until_critical
            if days_left <= self.CRITICAL_DAYS_THRESHOLD:
                signals["critical_stock"] = 1.0
                reasoning_path.append(
                    f"📉 Stok diprediksi akan menyentuh reorder point dalam "
                    f"{days_left} hari — melebihi batas kritis ({self.CRITICAL_DAYS_THRESHOLD} hari)."
                )
                supporting_evidence.append(
                    f"Proyeksi stok pada hari ke-{days_left}: "
                    f"{forecast.predicted_stock_levels[min(days_left-1, len(forecast.predicted_stock_levels)-1)]:.0f} unit"
                )
            elif days_left <= self.WARNING_DAYS_THRESHOLD:
                signals["low_stock"] = 0.65
                reasoning_path.append(
                    f"⚠️ Stok diprediksi akan mendekati reorder point dalam "
                    f"{days_left} hari — masuk zona peringatan ({self.WARNING_DAYS_THRESHOLD} hari)."
                )
        else:
            signals["sufficient_stock"] = 0.1
            reasoning_path.append(
                f"✅ Proyeksi stok dalam {forecast_horizon} hari ke depan masih "
                f"di atas reorder point — tidak ada urgensi restocking."
            )

        # ── Sinyal 2: Tren konsumsi ──
        if forecast.trend_direction == "turun":
            signals["downward_trend"] = 0.3
            reasoning_path.append(
                "📊 Tren level stok menunjukkan penurunan konsisten dalam 30 hari terakhir."
            )
        elif forecast.trend_direction == "naik":
            signals["upward_trend"] = -0.1  # tren naik = kondisi membaik
            reasoning_path.append(
                "📈 Tren level stok menunjukkan pemulihan — konsumsi melambat."
            )

        # ── Sinyal 3: Anomali terdeteksi ──
        if anomaly.is_anomaly:
            severity_weight = {
                "Critical": 1.0, "High": 0.8, "Medium": 0.55, "Low": 0.3
            }.get(anomaly.severity, 0.1)
            signals["anomaly_detected"] = severity_weight

            for rule in anomaly.triggered_rules:
                reasoning_path.append(f"🚨 Anomali terdeteksi: {rule}")
                supporting_evidence.append(rule)
        else:
            reasoning_path.append(
                f"✅ Tidak ada anomali terdeteksi — reject rate "
                f"{anomaly.current_reject_rate*100:.1f}%, "
                f"hold ratio {anomaly.current_hold_ratio*100:.1f}%."
            )

        # ── Sinyal 4: Hold/Reject tinggi ──
        has_reject_issue = any(
            t in anomaly.anomaly_types
            for t in ["reject_critical", "reject_high", "reject_spike"]
        )
        has_hold_issue = any(
            t in anomaly.anomaly_types
            for t in ["hold_critical", "hold_high"]
        )

        if has_reject_issue:
            signals["reject_issue"] = 0.85
        if has_hold_issue:
            signals["hold_issue"] = 0.75

        # ─────────────────────────────────────────
        # LOGIKA KEPUTUSAN UTAMA
        # Prioritas: Critical Stock > Reject/Hold > Low Stock > Monitor
        # ─────────────────────────────────────────

        action = "MONITOR"
        action_priority = "Opsional"
        risk_level = "Rendah"

        # Rule 1: Reject kritis + stok cukup → HOLD untuk investigasi
        if has_reject_issue and signals.get("critical_stock", 0) < 0.8:
            action = "HOLD"
            action_priority = "Segera"
            risk_level = "Tinggi"
            reasoning_path.append(
                "🔴 KEPUTUSAN: HOLD dipilih karena tingkat reject tinggi mengindikasikan "
                "masalah kualitas aktif. Penggunaan stok saat ini berisiko memperparah "
                "pemborosan tanpa investigasi akar masalah."
            )

        # Rule 2: Hold anomali → REDISTRIBUSI ke lini yang tidak terpengaruh
        elif has_hold_issue and not has_reject_issue:
            action = "REDISTRIBUSI"
            action_priority = "Dalam 3 Hari"
            risk_level = "Sedang"
            reasoning_path.append(
                "🟡 KEPUTUSAN: REDISTRIBUSI dipilih karena penumpukan barang hold "
                "mengindikasikan bottleneck pada satu titik proses. Redistribusi ke "
                "lini produksi alternatif dapat mencegah idle production."
            )

        # Rule 3: Stok kritis → RESTOCKING segera
        elif signals.get("critical_stock", 0) >= 0.8:
            action = "RESTOCKING"
            action_priority = "Segera"
            risk_level = "Kritis"
            reasoning_path.append(
                "🔴 KEPUTUSAN: RESTOCKING SEGERA dipilih karena proyeksi stok akan "
                f"mencapai titik kritis dalam {forecast.days_until_critical} hari — "
                f"lebih pendek dari lead time supplier ({lead_time} hari)."
            )

        # Rule 4: Stok rendah + anomali sedang → RESTOCKING terencana
        elif signals.get("low_stock", 0) >= 0.5 or signals.get("downward_trend", 0) >= 0.25:
            action = "RESTOCKING"
            action_priority = "Minggu Ini"
            risk_level = "Sedang"
            reasoning_path.append(
                "🟡 KEPUTUSAN: RESTOCKING TERENCANA dipilih karena kombinasi "
                "stok mendekati reorder point dan tren konsumsi yang meningkat."
            )

        # Rule 5: Semua kondisi normal
        else:
            action = "MONITOR"
            action_priority = "Opsional"
            risk_level = "Rendah"
            reasoning_path.append(
                "🟢 KEPUTUSAN: MONITOR — semua indikator dalam batas normal. "
                "Pantau secara rutin sesuai jadwal review mingguan."
            )

        # ── Hitung Confidence Score ──
        total_signal_strength = sum(abs(v) for v in signals.values())
        forecast_confidence = forecast.confidence
        anomaly_contribution = anomaly.anomaly_normalized * 0.3

        raw_confidence = (
            forecast_confidence * 0.4
            + min(1.0, total_signal_strength / 2.0) * 0.3
            + (1.0 - anomaly_contribution) * 0.15
            + 0.15  # base confidence
        )
        confidence_score = round(min(97.0, max(55.0, raw_confidence * 100)), 1)

        # ── Buat key_factors ──
        key_factors = {
            "Stok Saat Ini": f"{anomaly.current_stock_level:,} unit",
            "Reject Rate": f"{anomaly.current_reject_rate*100:.1f}%",
            "Rasio Hold": f"{anomaly.current_hold_ratio*100:.1f}%",
            "Hari Hingga Kritis": f"{forecast.days_until_critical or '>'+str(forecast_horizon)} hari",
            "Rekomendasi Restock": f"{forecast.recommended_restock_qty:,} unit",
            "Tren Stok": forecast.trend_direction.capitalize(),
            "Anomali Severity": anomaly.severity,
            "Lead Time Supplier": f"{lead_time} hari",
            "Akurasi Prediksi": f"{forecast.confidence*100:.0f}%",
        }

        # ── Detail tindakan spesifik ──
        action_details = {
            "RESTOCKING": (
                f"Segera buat purchase order untuk {forecast.recommended_restock_qty:,} unit "
                f"{sku_name}. Jadwalkan pengiriman sebelum {forecast.recommended_restock_date} "
                f"untuk memenuhi lead time {lead_time} hari."
            ),
            "HOLD": (
                f"Tahan seluruh penggunaan {sku_name} dari lini produksi. "
                f"Lakukan inspeksi QC menyeluruh terhadap batch aktif. "
                f"Koordinasi dengan tim Quality Assurance untuk investigasi akar masalah."
            ),
            "REDISTRIBUSI": (
                f"Identifikasi gudang atau lini produksi dengan kebutuhan {sku_name} aktif. "
                f"Prioritaskan redistribusi dari lokasi dengan hold tertinggi ke lini yang "
                f"membutuhkan — target selesai dalam 2×24 jam."
            ),
            "MONITOR": (
                f"Tidak ada tindakan segera. Jadwalkan review rutin {sku_name} "
                f"pada checkpoint mingguan berikutnya. Pantau tren reject rate."
            ),
        }

        # ── Estimasi dampak finansial ──
        daily_loss_if_ignored = None
        if action in ("RESTOCKING", "HOLD"):
            daily_consumption_est = sum(forecast.predicted_consumption) / len(forecast.predicted_consumption)
            potential_loss_per_day = daily_consumption_est * unit_cost
            if action == "RESTOCKING":
                daily_loss_if_ignored = (
                    f"Estimasi kerugian produksi ≈ Rp {potential_loss_per_day:,.0f}/hari "
                    f"akibat stock-out"
                )
            else:
                reject_loss = anomaly.current_stock_level * anomaly.current_reject_rate * unit_cost
                daily_loss_if_ignored = (
                    f"Estimasi kerugian dari material reject ≈ Rp {reject_loss:,.0f} "
                    f"jika tidak segera ditangani"
                )

        # ── Ringkasan forecast dan anomali ──
        forecast_summary = (
            f"Prediksi konsumsi {forecast_horizon} hari: "
            f"{sum(forecast.predicted_consumption):.0f} unit total. "
            f"Stok kritis dalam {forecast.days_until_critical or 'tidak ada'} hari."
        )
        anomaly_summary = (
            f"{len(anomaly.triggered_rules)} aturan anomali terpicu. "
            f"Severity: {anomaly.severity}."
            if anomaly.is_anomaly
            else "Tidak ada anomali aktif terdeteksi."
        )

        return DecisionResult(
            sku_id=sku_id,
            sku_name=sku_name,
            category=category,
            recommended_action=action,
            action_priority=action_priority,
            confidence_score=confidence_score,
            risk_level=risk_level,
            reasoning_path=reasoning_path,
            key_factors=key_factors,
            supporting_evidence=supporting_evidence,
            action_detail=action_details[action],
            estimated_impact=(
                f"Mengambil tindakan ini dapat mencegah gangguan produksi dan "
                f"menghemat estimasi Rp {unit_cost * forecast.recommended_restock_qty:,.0f} "
                f"dari potensi kerugian."
            ),
            estimated_loss_if_ignored=daily_loss_if_ignored,
            forecast_summary=forecast_summary,
            anomaly_summary=anomaly_summary,
            generated_at=datetime.now().isoformat(),
        )

    # ──────────────────────────────────────────────────
    # BULK: Analisis semua SKU sekaligus
    # ──────────────────────────────────────────────────

    def analyze_all(self, horizon: int = 14) -> Dict[str, DecisionResult]:
        """
        Jalankan analisis lengkap (Predict + Detect + Decide) untuk semua SKU.

        Returns:
            Dict berisi DecisionResult per SKU ID.
        """
        if self._historical_df is None:
            raise RuntimeError("Engine belum di-fit.")

        results = {}
        sku_ids = self._historical_df["sku_id"].unique()

        for sku_id in sku_ids:
            try:
                results[sku_id] = self.generate_decision(sku_id, horizon)
                logger.info(f"✅ Analisis selesai: {sku_id} → {results[sku_id].recommended_action}")
            except Exception as e:
                logger.warning(f"⚠️ Gagal analisis {sku_id}: {e}")

        return results

    def get_dashboard_summary(self) -> Dict:
        """
        Hitung ringkasan dashboard: total SKU, anomali aktif, distribusi tindakan.
        """
        all_decisions = self.analyze_all()

        action_counts = {"RESTOCKING": 0, "HOLD": 0, "REDISTRIBUSI": 0, "MONITOR": 0}
        severity_counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0, "Normal": 0}
        critical_skus = []

        for sku_id, decision in all_decisions.items():
            action_counts[decision.recommended_action] = (
                action_counts.get(decision.recommended_action, 0) + 1
            )
            anomaly = self.detect_anomalies(sku_id)
            severity_counts[anomaly.severity] = severity_counts.get(anomaly.severity, 0) + 1

            if decision.risk_level in ("Kritis", "Tinggi"):
                critical_skus.append({
                    "sku_id": sku_id,
                    "sku_name": decision.sku_name,
                    "action": decision.recommended_action,
                    "priority": decision.action_priority,
                    "risk": decision.risk_level,
                    "confidence": decision.confidence_score,
                })

        total_skus = len(all_decisions)
        anomaly_count = sum(1 for s, c in severity_counts.items() if s != "Normal" for _ in range(c))

        return {
            "total_skus": total_skus,
            "anomaly_active": anomaly_count,
            "health_score": round((1 - anomaly_count / max(total_skus, 1)) * 100, 1),
            "action_distribution": action_counts,
            "severity_distribution": severity_counts,
            "critical_skus": sorted(critical_skus, key=lambda x: x["confidence"], reverse=True),
            "generated_at": datetime.now().isoformat(),
        }


# ─────────────────────────────────────────────────────────────
# Singleton global engine (lazy-init di api/main.py)
# ─────────────────────────────────────────────────────────────

_engine_instance: Optional[InventoryEngine] = None


def get_engine() -> InventoryEngine:
    """
    Kembalikan singleton InventoryEngine yang sudah di-fit.
    Digunakan oleh FastAPI sebagai dependency injection.
    """
    global _engine_instance
    if _engine_instance is None:
        from engine.data_generator import SyntheticDataGenerator
        logger.info("Inisialisasi InventoryEngine...")
        gen = SyntheticDataGenerator()
        df = gen.generate_historical_data(days=90)
        catalog = gen.get_product_catalog()

        _engine_instance = InventoryEngine()
        _engine_instance.fit(df, catalog)
        logger.info("InventoryEngine siap digunakan.")
    return _engine_instance


# ─────────────────────────────────────────────────────────────
# Testing mandiri
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from engine.data_generator import SyntheticDataGenerator

    gen = SyntheticDataGenerator()
    df = gen.generate_historical_data(days=90)
    catalog = gen.get_product_catalog()

    engine = InventoryEngine()
    engine.fit(df, catalog)

    print("\n" + "=" * 60)
    print("🔮 LAYER 1: PREDICT")
    forecast = engine.predict_demand("SKU-004", horizon=14)
    print(f"SKU: {forecast.sku_name}")
    print(f"Tren: {forecast.trend_direction}")
    print(f"Hari hingga kritis: {forecast.days_until_critical}")
    print(f"Rekomendasi restock: {forecast.recommended_restock_qty} unit")
    print(f"Confidence: {forecast.confidence*100:.1f}%")

    print("\n" + "=" * 60)
    print("🔍 LAYER 2: DETECT")
    anomaly = engine.detect_anomalies("SKU-003")
    print(f"SKU: {anomaly.sku_name}")
    print(f"Anomali: {anomaly.is_anomaly} | Severity: {anomaly.severity}")
    print(f"Triggered rules: {anomaly.triggered_rules}")

    print("\n" + "=" * 60)
    print("🧠 LAYER 3: DECIDE (XAI)")
    decision = engine.generate_decision("SKU-003")
    print(f"Tindakan: {decision.recommended_action} ({decision.action_priority})")
    print(f"Confidence: {decision.confidence_score}% | Risk: {decision.risk_level}")
    print("Reasoning Path:")
    for step in decision.reasoning_path:
        print(f"  {step}")
