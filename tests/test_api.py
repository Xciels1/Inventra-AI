"""
tests/test_api.py
=================
Integration tests untuk FastAPI endpoints Inventra AI.
Menguji semua endpoint REST API menggunakan TestClient.

Jalankan: pytest tests/test_api.py -v
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    """FastAPI TestClient — dibuat sekali untuk semua test."""
    from api.main import app
    with TestClient(app) as c:
        yield c


# ─────────────────────────────────────────────────────────────
# TEST: System Endpoints
# ─────────────────────────────────────────────────────────────

class TestSystemEndpoints:

    def test_root_returns_200(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert "service" in r.json()

    def test_health_check(self, client):
        r = client.get("/api/v1/health")
        assert r.status_code == 200
        data = r.json()
        assert data["components"]["ml_engine"] == "ready"

    def test_docs_accessible(self, client):
        r = client.get("/docs")
        assert r.status_code == 200


# ─────────────────────────────────────────────────────────────
# TEST: Dashboard
# ─────────────────────────────────────────────────────────────

class TestDashboardEndpoints:

    def test_dashboard_summary(self, client):
        r = client.get("/api/v1/dashboard/summary")
        assert r.status_code == 200
        data = r.json()["data"]
        assert "total_skus" in data
        assert "health_score" in data
        assert data["total_skus"] == 8

    def test_inventory_snapshot(self, client):
        r = client.get("/api/v1/inventory/snapshot")
        assert r.status_code == 200
        data = r.json()["data"]
        assert "snapshot" in data
        assert len(data["snapshot"]) == 8


# ─────────────────────────────────────────────────────────────
# TEST: Per-SKU Analysis
# ─────────────────────────────────────────────────────────────

class TestSkuEndpoints:

    @pytest.mark.parametrize("sku_id", ["SKU-001", "SKU-003", "SKU-006", "SKU-008"])
    def test_forecast_endpoint(self, client, sku_id):
        r = client.get(f"/api/v1/sku/{sku_id}/forecast?horizon=14")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["sku_id"] == sku_id
        assert len(data["predicted_consumption"]) == 14
        assert 0.0 <= data["confidence"] <= 1.0

    @pytest.mark.parametrize("sku_id", ["SKU-001", "SKU-004", "SKU-007"])
    def test_anomaly_endpoint(self, client, sku_id):
        r = client.get(f"/api/v1/sku/{sku_id}/anomaly")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["sku_id"] == sku_id
        assert data["severity"] in {"Normal", "Low", "Medium", "High", "Critical"}

    @pytest.mark.parametrize("sku_id", ["SKU-001", "SKU-006"])
    def test_decision_endpoint(self, client, sku_id):
        r = client.get(f"/api/v1/sku/{sku_id}/decision")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["recommended_action"] in {"RESTOCKING", "HOLD", "REDISTRIBUSI", "MONITOR"}
        assert 0 <= data["confidence_score"] <= 100
        assert len(data["reasoning_path"]) > 0

    def test_forecast_invalid_sku_returns_error(self, client):
        r = client.get("/api/v1/sku/SKU-INVALID/forecast")
        assert r.status_code in {404, 500}

    def test_forecast_horizon_validation(self, client):
        """Horizon di luar 7–30 harus ditolak."""
        r = client.get("/api/v1/sku/SKU-001/forecast?horizon=5")
        assert r.status_code == 422

    def test_decisions_all_endpoint(self, client):
        r = client.get("/api/v1/decisions/all")
        assert r.status_code == 200
        data = r.json()["data"]
        assert "decisions" in data
        assert len(data["decisions"]) == 8

    def test_decisions_filter_by_action(self, client):
        r = client.get("/api/v1/decisions/all?filter_action=RESTOCKING")
        assert r.status_code == 200
        data = r.json()["data"]
        for d in data["decisions"]:
            assert d["recommended_action"] == "RESTOCKING"


# ─────────────────────────────────────────────────────────────
# TEST: Chart Data
# ─────────────────────────────────────────────────────────────

class TestChartEndpoints:

    def test_stock_chart_returns_historical(self, client):
        r = client.get("/api/v1/chart/SKU-001/stock?days=30")
        assert r.status_code == 200
        data = r.json()["data"]
        assert "historical" in data
        assert len(data["historical"]) > 0

    def test_stock_chart_with_forecast(self, client):
        r = client.get("/api/v1/chart/SKU-001/stock?include_forecast=true&forecast_horizon=14")
        assert r.status_code == 200
        data = r.json()["data"]
        assert len(data["forecast"]) == 14

    def test_anomaly_heatmap(self, client):
        r = client.get("/api/v1/chart/anomalies/heatmap")
        assert r.status_code == 200
        data = r.json()["data"]
        assert "heatmap" in data
        assert len(data["heatmap"]) == 8


# ─────────────────────────────────────────────────────────────
# TEST: Chat / AI Assistant
# ─────────────────────────────────────────────────────────────

class TestChatEndpoints:

    def test_chat_returns_message(self, client):
        r = client.post("/api/v1/chat", json={
            "message": "Barang apa yang paling berisiko?",
            "session_id": "test_session"
        })
        assert r.status_code == 200
        data = r.json()["data"]
        assert "message" in data
        assert len(data["message"]) > 10

    def test_chat_empty_message_rejected(self, client):
        r = client.post("/api/v1/chat", json={"message": "", "session_id": "test"})
        assert r.status_code == 422

    def test_chat_clears_history(self, client):
        r = client.delete("/api/v1/chat/test_session")
        assert r.status_code == 200

    def test_daily_briefing(self, client):
        r = client.get("/api/v1/briefing/daily")
        assert r.status_code == 200
        data = r.json()["data"]
        assert "briefing" in data
        assert len(data["briefing"]) > 20


# ─────────────────────────────────────────────────────────────
# TEST: Feedback Loop
# ─────────────────────────────────────────────────────────────

class TestFeedbackEndpoints:

    def test_submit_approved_feedback(self, client):
        r = client.post("/api/v1/feedback", json={
            "sku_id": "SKU-006",
            "decision_action": "RESTOCKING",
            "feedback": "approved",
            "note": "Setuju, stok memang kritis",
            "operator_id": "op_test_01"
        })
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["status"] == "recorded"
        assert "feedback_id" in data

    def test_submit_rejected_feedback(self, client):
        r = client.post("/api/v1/feedback", json={
            "sku_id": "SKU-003",
            "decision_action": "RESTOCKING",
            "feedback": "rejected",
            "note": "Kami punya safety stock tambahan"
        })
        assert r.status_code == 200

    def test_invalid_feedback_value_rejected(self, client):
        r = client.post("/api/v1/feedback", json={
            "sku_id": "SKU-001",
            "decision_action": "MONITOR",
            "feedback": "maybe"  # Tidak valid
        })
        assert r.status_code == 422

    def test_feedback_log_accessible(self, client):
        r = client.get("/api/v1/feedback/log")
        assert r.status_code == 200
        data = r.json()["data"]
        assert "feedback_log" in data
        assert data["total"] >= 0

    def test_feedback_stats_accessible(self, client):
        r = client.get("/api/v1/feedback/stats")
        assert r.status_code == 200


# ─────────────────────────────────────────────────────────────
# TEST: Catalog
# ─────────────────────────────────────────────────────────────

class TestCatalogEndpoints:

    def test_catalog_returns_all_products(self, client):
        r = client.get("/api/v1/catalog")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["total"] == 8

    def test_catalog_sku_detail(self, client):
        r = client.get("/api/v1/catalog/SKU-001")
        assert r.status_code == 200
        data = r.json()["data"]
        assert "product" in data
        assert "forecast" in data
        assert "anomaly" in data
        assert "decision" in data

    def test_catalog_invalid_sku(self, client):
        r = client.get("/api/v1/catalog/SKU-INVALID")
        assert r.status_code == 404


if __name__ == "__main__":
    import subprocess
    result = subprocess.run(
        ["python", "-m", "pytest", __file__, "-v", "--tb=short", "--no-header"],
        capture_output=False
    )
    sys.exit(result.returncode)
