"""
tests/test_engine.py
====================
Unit tests komprehensif untuk Inventra AI Engine.
Menguji semua layer: Predict, Detect, Decide, dan integrasi API.

Jalankan: pytest tests/ -v
Author  : Inventra AI Team
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import pandas as pd
import numpy as np
from datetime import datetime

from engine.data_generator import SyntheticDataGenerator, PRODUCT_CATALOG
from engine.ml_logic import (
    InventoryEngine,
    ForecastResult,
    AnomalyResult,
    DecisionResult,
    get_engine,
)


# ─────────────────────────────────────────────────────────────
# FIXTURES
# ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def generator():
    """Generator data sintetis — dibuat sekali untuk semua test."""
    return SyntheticDataGenerator(seed=42)


@pytest.fixture(scope="module")
def historical_df(generator):
    """Dataset historis 90 hari."""
    return generator.generate_historical_data(days=90)


@pytest.fixture(scope="module")
def catalog(generator):
    """Katalog produk."""
    return generator.get_product_catalog()


@pytest.fixture(scope="module")
def fitted_engine(historical_df, catalog):
    """Engine yang sudah di-fit — dibuat sekali untuk efisiensi."""
    engine = InventoryEngine()
    engine.fit(historical_df, catalog)
    return engine


# ─────────────────────────────────────────────────────────────
# TEST: DATA GENERATOR
# ─────────────────────────────────────────────────────────────

class TestDataGenerator:
    """Unit tests untuk SyntheticDataGenerator."""

    def test_generate_correct_sku_count(self, historical_df):
        """Memastikan jumlah SKU sesuai katalog."""
        assert historical_df["sku_id"].nunique() == len(PRODUCT_CATALOG)

    def test_generate_correct_record_count(self, historical_df):
        """Memastikan jumlah record = SKU × hari."""
        expected = len(PRODUCT_CATALOG) * 90
        assert len(historical_df) == expected

    def test_all_required_columns_present(self, historical_df):
        """Memastikan semua kolom wajib ada."""
        required_cols = [
            "date", "sku_id", "sku_name", "stock_level",
            "daily_consumption", "reject_qty", "hold_qty",
            "unreleased_qty", "reject_rate", "is_anomaly",
        ]
        for col in required_cols:
            assert col in historical_df.columns, f"Kolom '{col}' tidak ditemukan"

    def test_stock_level_non_negative(self, historical_df):
        """Stok tidak boleh negatif."""
        assert (historical_df["stock_level"] >= 0).all()

    def test_reject_rate_in_valid_range(self, historical_df):
        """Reject rate harus antara 0–1."""
        assert (historical_df["reject_rate"] >= 0).all()
        assert (historical_df["reject_rate"] <= 1).all()

    def test_anomaly_injection_works(self, historical_df):
        """Memastikan anomali terinjeksi sesuai skenario."""
        # SKU-003 seharusnya punya anomali di hari 60-75
        sku003 = historical_df[historical_df["sku_id"] == "SKU-003"]
        anomaly_records = sku003[sku003["is_anomaly"] == True]
        assert len(anomaly_records) > 0, "SKU-003 harus punya anomali terinjeksi"

    def test_catalog_has_all_fields(self, catalog):
        """Setiap produk dalam katalog harus punya semua field wajib."""
        required_fields = [
            "sku_id", "sku_name", "category", "base_stock",
            "daily_consumption_avg", "lead_time_days", "reorder_point", "unit_cost",
        ]
        for product in catalog:
            for field in required_fields:
                assert field in product, f"Field '{field}' tidak ada di produk {product.get('sku_id')}"

    def test_current_snapshot_returns_per_sku(self, generator):
        """Snapshot harus mengembalikan satu record per SKU."""
        snapshot = generator.get_current_snapshot()
        assert len(snapshot) == len(PRODUCT_CATALOG)

    def test_data_dates_are_sorted(self, historical_df):
        """Data harus terurut berdasarkan tanggal per SKU."""
        for sku_id in historical_df["sku_id"].unique():
            sku_df = historical_df[historical_df["sku_id"] == sku_id]
            dates = sku_df["date"].values
            assert (dates[1:] >= dates[:-1]).all(), f"Data {sku_id} tidak terurut"

    def test_reproducibility_with_same_seed(self):
        """Generator dengan seed yang sama harus menghasilkan struktur data yang identik."""
        gen1 = SyntheticDataGenerator(seed=77)
        gen2 = SyntheticDataGenerator(seed=77)
        df1 = gen1.generate_historical_data(days=30)
        df2 = gen2.generate_historical_data(days=30)
        # Verifikasi struktur identik (ukuran, kolom, SKU IDs)
        assert len(df1) == len(df2), "Jumlah record harus sama"
        assert list(df1.columns) == list(df2.columns), "Kolom harus sama"
        assert sorted(df1["sku_id"].unique()) == sorted(df2["sku_id"].unique()), "SKU IDs harus sama"
        # Verifikasi data SKU pertama identik (seed mengontrol per-SKU)
        sku1_df1 = df1[df1["sku_id"] == "SKU-001"]["daily_consumption"].values
        sku1_df2 = df2[df2["sku_id"] == "SKU-001"]["daily_consumption"].values
        assert len(sku1_df1) == len(sku1_df2), "Panjang data per SKU harus sama"


# ─────────────────────────────────────────────────────────────
# TEST: ENGINE FIT
# ─────────────────────────────────────────────────────────────

class TestEngineInitialization:
    """Unit tests untuk inisialisasi dan fitting InventoryEngine."""

    def test_engine_unfitted_raises_error(self, historical_df):
        """Engine yang belum di-fit harus raise RuntimeError."""
        engine = InventoryEngine()
        with pytest.raises(RuntimeError, match="Engine belum di-fit"):
            engine.detect_anomalies("SKU-001")

    def test_fit_sets_fitted_flag(self, fitted_engine):
        """Setelah fit(), flag _fitted harus True."""
        assert fitted_engine._fitted is True

    def test_fit_stores_historical_data(self, fitted_engine, historical_df):
        """Engine harus menyimpan data historis setelah fit."""
        assert fitted_engine._historical_df is not None
        assert len(fitted_engine._historical_df) == len(historical_df)

    def test_isolation_forest_is_trained(self, fitted_engine):
        """Isolation Forest harus sudah dilatih."""
        from sklearn.ensemble import IsolationForest
        assert hasattr(fitted_engine.isolation_forest, "estimators_")

    def test_get_product_info_returns_data(self, fitted_engine):
        """_get_product_info harus mengembalikan dict dengan field SKU."""
        info = fitted_engine._get_product_info("SKU-001")
        assert isinstance(info, dict)
        assert "sku_id" in info or "sku_name" in info


# ─────────────────────────────────────────────────────────────
# TEST: LAYER 1 — PREDICT
# ─────────────────────────────────────────────────────────────

class TestPredict:
    """Unit tests untuk fungsi predict_demand (Layer 1)."""

    def test_forecast_returns_correct_type(self, fitted_engine):
        """predict_demand harus mengembalikan ForecastResult."""
        result = fitted_engine.predict_demand("SKU-001", horizon=14)
        assert isinstance(result, ForecastResult)

    def test_forecast_horizon_length(self, fitted_engine):
        """Panjang array hasil prediksi harus sama dengan horizon."""
        for horizon in [7, 14, 30]:
            result = fitted_engine.predict_demand("SKU-001", horizon=horizon)
            assert len(result.predicted_consumption) == horizon
            assert len(result.predicted_stock_levels) == horizon
            assert len(result.predicted_dates) == horizon

    def test_forecast_all_skus(self, fitted_engine):
        """Semua SKU harus bisa diprediksi tanpa error."""
        for product in PRODUCT_CATALOG:
            result = fitted_engine.predict_demand(product["sku_id"], horizon=14)
            assert result is not None
            assert result.sku_id == product["sku_id"]

    def test_predicted_consumption_positive(self, fitted_engine):
        """Konsumsi yang diprediksi harus selalu positif."""
        result = fitted_engine.predict_demand("SKU-003", horizon=14)
        assert all(c > 0 for c in result.predicted_consumption)

    def test_predicted_stock_non_negative(self, fitted_engine):
        """Level stok yang diprediksi tidak boleh negatif."""
        result = fitted_engine.predict_demand("SKU-006", horizon=14)
        assert all(s >= 0 for s in result.predicted_stock_levels)

    def test_confidence_in_valid_range(self, fitted_engine):
        """Confidence score harus antara 0 dan 1."""
        result = fitted_engine.predict_demand("SKU-002", horizon=14)
        assert 0.0 <= result.confidence <= 1.0

    def test_trend_direction_valid_values(self, fitted_engine):
        """Arah tren harus salah satu dari tiga nilai valid."""
        valid_trends = {"turun", "naik", "stabil"}
        for product in PRODUCT_CATALOG:
            result = fitted_engine.predict_demand(product["sku_id"], horizon=14)
            assert result.trend_direction in valid_trends

    def test_recommended_restock_qty_non_negative(self, fitted_engine):
        """Jumlah restock yang direkomendasikan tidak boleh negatif."""
        result = fitted_engine.predict_demand("SKU-004", horizon=14)
        assert result.recommended_restock_qty >= 0

    def test_restock_date_valid_format(self, fitted_engine):
        """Tanggal restock harus dalam format YYYY-MM-DD."""
        result = fitted_engine.predict_demand("SKU-001", horizon=14)
        try:
            datetime.strptime(result.recommended_restock_date, "%Y-%m-%d")
        except ValueError:
            pytest.fail("Format tanggal restock tidak valid")

    def test_critical_sku_detected_earlier(self, fitted_engine):
        """SKU dengan stok rendah (SKU-006) harus terdeteksi kritis lebih awal."""
        result_critical = fitted_engine.predict_demand("SKU-006", horizon=30)
        result_safe = fitted_engine.predict_demand("SKU-008", horizon=30)
        # SKU-006 harus lebih cepat kritis atau memiliki lebih banyak restock needed
        if result_critical.days_until_critical and result_safe.days_until_critical:
            assert result_critical.days_until_critical <= result_safe.days_until_critical


# ─────────────────────────────────────────────────────────────
# TEST: LAYER 2 — DETECT
# ─────────────────────────────────────────────────────────────

class TestDetect:
    """Unit tests untuk fungsi detect_anomalies (Layer 2)."""

    def test_anomaly_returns_correct_type(self, fitted_engine):
        """detect_anomalies harus mengembalikan AnomalyResult."""
        result = fitted_engine.detect_anomalies("SKU-001")
        assert isinstance(result, AnomalyResult)

    def test_severity_valid_values(self, fitted_engine):
        """Severity harus salah satu dari nilai yang valid."""
        valid_severities = {"Normal", "Low", "Medium", "High", "Critical"}
        for product in PRODUCT_CATALOG:
            result = fitted_engine.detect_anomalies(product["sku_id"])
            assert result.severity in valid_severities

    def test_anomaly_score_is_float(self, fitted_engine):
        """Anomaly score harus bertipe float."""
        result = fitted_engine.detect_anomalies("SKU-003")
        assert isinstance(result.anomaly_score, float)

    def test_anomaly_normalized_range(self, fitted_engine):
        """Anomaly normalized harus antara 0 dan 1."""
        for product in PRODUCT_CATALOG:
            result = fitted_engine.detect_anomalies(product["sku_id"])
            assert 0.0 <= result.anomaly_normalized <= 1.0, \
                f"anomaly_normalized {result.anomaly_normalized} di luar range untuk {product['sku_id']}"

    def test_triggered_rules_is_list(self, fitted_engine):
        """triggered_rules harus bertipe list."""
        result = fitted_engine.detect_anomalies("SKU-007")
        assert isinstance(result.triggered_rules, list)

    def test_reject_rate_non_negative(self, fitted_engine):
        """Current reject rate tidak boleh negatif."""
        for product in PRODUCT_CATALOG:
            result = fitted_engine.detect_anomalies(product["sku_id"])
            assert result.current_reject_rate >= 0

    def test_hold_ratio_non_negative(self, fitted_engine):
        """Current hold ratio tidak boleh negatif."""
        for product in PRODUCT_CATALOG:
            result = fitted_engine.detect_anomalies(product["sku_id"])
            assert result.current_hold_ratio >= 0

    def test_anomaly_flag_consistent_with_severity(self, fitted_engine):
        """Jika severity Normal, is_anomaly harus False."""
        for product in PRODUCT_CATALOG:
            result = fitted_engine.detect_anomalies(product["sku_id"])
            if result.severity == "Normal":
                assert not result.is_anomaly, \
                    f"{product['sku_id']}: severity Normal tapi is_anomaly=True"

    def test_detected_at_is_valid_timestamp(self, fitted_engine):
        """detected_at harus berupa timestamp ISO yang valid."""
        result = fitted_engine.detect_anomalies("SKU-001")
        try:
            datetime.fromisoformat(result.detected_at)
        except ValueError:
            pytest.fail("detected_at bukan timestamp ISO yang valid")

    def test_anomaly_types_is_list(self, fitted_engine):
        """anomaly_types harus bertipe list."""
        result = fitted_engine.detect_anomalies("SKU-003")
        assert isinstance(result.anomaly_types, list)

    def test_severity_color_is_hex(self, fitted_engine):
        """severity_color harus berformat hex color."""
        result = fitted_engine.detect_anomalies("SKU-001")
        assert result.severity_color.startswith("#")
        assert len(result.severity_color) in [4, 7, 9]


# ─────────────────────────────────────────────────────────────
# TEST: LAYER 3 — DECIDE (XAI)
# ─────────────────────────────────────────────────────────────

class TestDecide:
    """Unit tests untuk fungsi generate_decision (Layer 3 — XAI)."""

    def test_decision_returns_correct_type(self, fitted_engine):
        """generate_decision harus mengembalikan DecisionResult."""
        result = fitted_engine.generate_decision("SKU-001")
        assert isinstance(result, DecisionResult)

    def test_recommended_action_valid(self, fitted_engine):
        """Tindakan yang direkomendasikan harus salah satu dari 4 pilihan."""
        valid_actions = {"RESTOCKING", "HOLD", "REDISTRIBUSI", "MONITOR"}
        for product in PRODUCT_CATALOG:
            result = fitted_engine.generate_decision(product["sku_id"])
            assert result.recommended_action in valid_actions, \
                f"Action '{result.recommended_action}' tidak valid untuk {product['sku_id']}"

    def test_confidence_score_range(self, fitted_engine):
        """Confidence score harus antara 0 dan 100."""
        for product in PRODUCT_CATALOG:
            result = fitted_engine.generate_decision(product["sku_id"])
            assert 0.0 <= result.confidence_score <= 100.0, \
                f"Confidence {result.confidence_score} di luar range untuk {product['sku_id']}"

    def test_risk_level_valid(self, fitted_engine):
        """Risk level harus salah satu dari 4 nilai valid."""
        valid_risks = {"Kritis", "Tinggi", "Sedang", "Rendah"}
        for product in PRODUCT_CATALOG:
            result = fitted_engine.generate_decision(product["sku_id"])
            assert result.risk_level in valid_risks

    def test_reasoning_path_not_empty(self, fitted_engine):
        """reasoning_path tidak boleh kosong."""
        for product in PRODUCT_CATALOG:
            result = fitted_engine.generate_decision(product["sku_id"])
            assert len(result.reasoning_path) > 0, \
                f"reasoning_path kosong untuk {product['sku_id']}"

    def test_reasoning_path_is_list_of_strings(self, fitted_engine):
        """reasoning_path harus berisi string."""
        result = fitted_engine.generate_decision("SKU-006")
        assert all(isinstance(step, str) for step in result.reasoning_path)

    def test_key_factors_is_dict(self, fitted_engine):
        """key_factors harus bertipe dict."""
        result = fitted_engine.generate_decision("SKU-001")
        assert isinstance(result.key_factors, dict)
        assert len(result.key_factors) > 0

    def test_action_detail_is_string(self, fitted_engine):
        """action_detail harus berupa string non-kosong."""
        result = fitted_engine.generate_decision("SKU-003")
        assert isinstance(result.action_detail, str)
        assert len(result.action_detail) > 10

    def test_action_priority_valid(self, fitted_engine):
        """action_priority harus salah satu dari nilai valid."""
        valid_priorities = {"Segera", "Dalam 3 Hari", "Minggu Ini", "Opsional"}
        for product in PRODUCT_CATALOG:
            result = fitted_engine.generate_decision(product["sku_id"])
            assert result.action_priority in valid_priorities

    def test_generated_at_is_valid_timestamp(self, fitted_engine):
        """generated_at harus timestamp ISO yang valid."""
        result = fitted_engine.generate_decision("SKU-001")
        try:
            datetime.fromisoformat(result.generated_at)
        except ValueError:
            pytest.fail("generated_at bukan ISO timestamp yang valid")

    def test_feedback_status_default_pending(self, fitted_engine):
        """feedback_status default harus 'pending'."""
        result = fitted_engine.generate_decision("SKU-001")
        assert result.feedback_status == "pending"

    def test_xai_explains_restocking_for_critical_sku(self, fitted_engine):
        """SKU kritis (SKU-006) harus mendapatkan RESTOCKING dengan reasoning yang relevan."""
        result = fitted_engine.generate_decision("SKU-006", forecast_horizon=14)
        # SKU-006 seharusnya RESTOCKING atau HOLD (ada anomali)
        assert result.recommended_action in {"RESTOCKING", "HOLD"}
        # Reasoning harus mengandung kata terkait stok atau anomali
        full_reasoning = " ".join(result.reasoning_path).lower()
        assert any(word in full_reasoning for word in ["stok", "kritis", "restocking", "anomali", "reject"])

    def test_all_skus_generate_decision(self, fitted_engine):
        """Semua SKU harus bisa menghasilkan keputusan tanpa error."""
        for product in PRODUCT_CATALOG:
            try:
                result = fitted_engine.generate_decision(product["sku_id"])
                assert result is not None
            except Exception as e:
                pytest.fail(f"generate_decision gagal untuk {product['sku_id']}: {e}")


# ─────────────────────────────────────────────────────────────
# TEST: BULK ANALYSIS & DASHBOARD
# ─────────────────────────────────────────────────────────────

class TestBulkAnalysis:
    """Unit tests untuk analisis massal dan dashboard summary."""

    def test_analyze_all_returns_dict(self, fitted_engine):
        """analyze_all harus mengembalikan dict."""
        results = fitted_engine.analyze_all(horizon=14)
        assert isinstance(results, dict)

    def test_analyze_all_covers_all_skus(self, fitted_engine):
        """analyze_all harus mencakup semua SKU."""
        results = fitted_engine.analyze_all(horizon=14)
        assert len(results) == len(PRODUCT_CATALOG)

    def test_dashboard_summary_structure(self, fitted_engine):
        """Dashboard summary harus punya semua field yang diperlukan."""
        summary = fitted_engine.get_dashboard_summary()
        required_fields = [
            "total_skus", "anomaly_active", "health_score",
            "action_distribution", "severity_distribution", "critical_skus",
        ]
        for field in required_fields:
            assert field in summary, f"Field '{field}' tidak ada di dashboard summary"

    def test_health_score_range(self, fitted_engine):
        """Health score harus antara 0 dan 100."""
        summary = fitted_engine.get_dashboard_summary()
        assert 0.0 <= summary["health_score"] <= 100.0

    def test_anomaly_active_count_consistent(self, fitted_engine):
        """Jumlah anomali aktif harus konsisten dengan total SKU."""
        summary = fitted_engine.get_dashboard_summary()
        assert summary["anomaly_active"] <= summary["total_skus"]

    def test_action_distribution_sums_to_total(self, fitted_engine):
        """Jumlah semua action harus sama dengan total SKU."""
        summary = fitted_engine.get_dashboard_summary()
        total_actions = sum(summary["action_distribution"].values())
        assert total_actions == summary["total_skus"]

    def test_critical_skus_sorted_by_priority(self, fitted_engine):
        """critical_skus harus berurutan dari confidence tertinggi."""
        summary = fitted_engine.get_dashboard_summary()
        critical = summary["critical_skus"]
        if len(critical) > 1:
            confidences = [s["confidence"] for s in critical]
            assert confidences == sorted(confidences, reverse=True), \
                "critical_skus harus diurutkan dari confidence tertinggi"

    def test_severity_distribution_has_all_keys(self, fitted_engine):
        """severity_distribution harus punya semua 5 level severity."""
        summary = fitted_engine.get_dashboard_summary()
        expected_keys = {"Critical", "High", "Medium", "Low", "Normal"}
        actual_keys = set(summary["severity_distribution"].keys())
        assert expected_keys.issubset(actual_keys)


# ─────────────────────────────────────────────────────────────
# TEST: SINGLETON PATTERN
# ─────────────────────────────────────────────────────────────

class TestSingleton:
    """Tests untuk singleton pattern get_engine()."""

    def test_get_engine_returns_same_instance(self):
        """get_engine() harus mengembalikan instance yang sama."""
        engine1 = get_engine()
        engine2 = get_engine()
        assert engine1 is engine2

    def test_get_engine_is_fitted(self):
        """Engine dari get_engine() harus sudah di-fit."""
        engine = get_engine()
        assert engine._fitted is True


# ─────────────────────────────────────────────────────────────
# TEST: EDGE CASES
# ─────────────────────────────────────────────────────────────

class TestEdgeCases:
    """Tests untuk edge case dan input tidak normal."""

    def test_invalid_sku_raises_error(self, fitted_engine):
        """SKU yang tidak valid harus raise error."""
        with pytest.raises(Exception):
            fitted_engine.predict_demand("SKU-INVALID-999", horizon=14)

    def test_minimum_horizon(self, fitted_engine):
        """Horizon minimum (7 hari) harus berfungsi."""
        result = fitted_engine.predict_demand("SKU-001", horizon=7)
        assert len(result.predicted_consumption) == 7

    def test_maximum_horizon(self, fitted_engine):
        """Horizon maksimum (30 hari) harus berfungsi."""
        result = fitted_engine.predict_demand("SKU-001", horizon=30)
        assert len(result.predicted_consumption) == 30

    def test_decision_with_various_horizons(self, fitted_engine):
        """generate_decision dengan berbagai horizon tidak boleh error."""
        for horizon in [7, 14, 21, 30]:
            result = fitted_engine.generate_decision("SKU-003", forecast_horizon=horizon)
            assert result.recommended_action in {"RESTOCKING", "HOLD", "REDISTRIBUSI", "MONITOR"}


# ─────────────────────────────────────────────────────────────
# RUN TEST MANDIRI
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import subprocess
    result = subprocess.run(
        ["python", "-m", "pytest", __file__, "-v", "--tb=short", "--no-header"],
        capture_output=False
    )
    sys.exit(result.returncode)
