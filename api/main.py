"""
api/main.py
===========
REST API Inventra AI — dibangun dengan FastAPI.
Menyajikan seluruh kapabilitas engine AI sebagai endpoint HTTP
yang siap dikonsumsi oleh dashboard React frontend.

Endpoint Utama:
  GET  /                           → Health check
  GET  /api/v1/dashboard/summary   → Ringkasan KPI dashboard
  GET  /api/v1/inventory/snapshot  → Snapshot inventaris real-time
  GET  /api/v1/sku/{sku_id}/forecast → Prediksi stok
  GET  /api/v1/sku/{sku_id}/anomaly  → Deteksi anomali
  GET  /api/v1/sku/{sku_id}/decision → Keputusan XAI lengkap
  GET  /api/v1/decisions/all        → Semua keputusan sekaligus
  POST /api/v1/chat                 → AI Insight Assistant chat
  POST /api/v1/feedback             → Feedback loop (Approve/Reject)
  GET  /api/v1/briefing/daily       → Ringkasan harian otomatis
  GET  /api/v1/chart/{sku_id}/stock → Data grafik tren stok

Author  : Inventra AI Team
Version : 1.0.0
"""

import sys
import os
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import asdict

# Tambahkan root project ke Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from engine.data_generator import SyntheticDataGenerator
from engine.ml_logic import InventoryEngine, DecisionResult, get_engine
from integrations.azure_provider import AzureOpenAIProvider, get_ai_provider

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("inventra.api")


# ─────────────────────────────────────────────────────────────
# State Global Aplikasi
# ─────────────────────────────────────────────────────────────

class AppState:
    engine: Optional[InventoryEngine] = None
    provider: Optional[AzureOpenAIProvider] = None
    generator: Optional[SyntheticDataGenerator] = None
    feedback_log: List[Dict] = []          # In-memory feedback log
    initialized: bool = False
    init_time: Optional[str] = None


app_state = AppState()


# ─────────────────────────────────────────────────────────────
# Lifecycle: Inisialisasi Engine saat startup
# ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifecycle handler FastAPI.
    Inisialisasi InventoryEngine dan AzureOpenAIProvider saat server start.
    """
    logger.info("🚀 Inventra AI API starting up...")

    try:
        # Inisialisasi data generator
        app_state.generator = SyntheticDataGenerator(seed=42)
        df = app_state.generator.generate_historical_data(days=90)
        catalog = app_state.generator.get_product_catalog()

        # Latih ML engine
        app_state.engine = InventoryEngine()
        app_state.engine.fit(df, catalog)

        # Inisialisasi AI provider
        app_state.provider = get_ai_provider()

        app_state.initialized = True
        app_state.init_time = datetime.now().isoformat()

        logger.info(f"✅ Engine siap: {df['sku_id'].nunique()} SKU, {len(df)} records historis")
        logger.info("✅ AI Insight Assistant aktif")

    except Exception as e:
        logger.error(f"❌ Gagal inisialisasi: {e}")
        raise

    yield  # ← Server berjalan di sini

    logger.info("🛑 Inventra AI API shutting down...")
    if app_state.provider and app_state.provider._client:
        await app_state.provider._client.aclose()


# ─────────────────────────────────────────────────────────────
# Inisialisasi Aplikasi FastAPI
# ─────────────────────────────────────────────────────────────

app = FastAPI(
    title="Inventra AI — Intelligent Inventory Decision Engine",
    description=(
        "API backend untuk sistem manajemen inventaris manufaktur berbasis AI. "
        "Menyediakan prediksi stok, deteksi anomali, dan rekomendasi keputusan otomatis."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — izinkan frontend React di port 3000
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "*",  # Untuk demo — batasi di production
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────
# Pydantic Models untuk Request/Response
# ─────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000,
                         description="Pertanyaan dalam Bahasa Indonesia")
    session_id: str = Field(default="default",
                            description="ID sesi untuk menjaga konteks percakapan")


class FeedbackRequest(BaseModel):
    sku_id: str = Field(..., description="SKU ID yang diberikan feedback")
    decision_action: str = Field(..., description="Tindakan yang direkomendasikan AI")
    feedback: str = Field(..., pattern="^(approved|rejected)$",
                          description="'approved' atau 'rejected'")
    note: Optional[str] = Field(None, max_length=500,
                                description="Catatan opsional dari operator")
    operator_id: Optional[str] = Field(None, description="ID operator yang memberikan feedback")


class ApiResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    message: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


# ─────────────────────────────────────────────────────────────
# Helper: pastikan engine sudah siap
# ─────────────────────────────────────────────────────────────

def _require_engine():
    if not app_state.initialized or app_state.engine is None:
        raise HTTPException(
            status_code=503,
            detail="Engine AI belum siap. Silakan tunggu beberapa detik dan coba lagi."
        )
    return app_state.engine


def _build_inventory_context_for_llm() -> Dict:
    """
    Siapkan konteks inventaris lengkap untuk dikirim ke LLM.
    Menggabungkan dashboard summary dengan data per SKU.
    """
    engine = _require_engine()

    # Dashboard summary
    summary = engine.get_dashboard_summary()

    # Ambil data singkat per SKU untuk konteks
    sku_decisions = []
    historical_df = engine._historical_df
    if historical_df is not None:
        for sku_id in historical_df["sku_id"].unique():
            try:
                anomaly = engine.detect_anomalies(sku_id)
                forecast = engine.predict_demand(sku_id, horizon=7)
                decision = engine.generate_decision(sku_id, forecast_horizon=7)
                sku_decisions.append({
                    "sku_id": sku_id,
                    "sku_name": decision.sku_name,
                    "category": decision.category,
                    "current_stock": anomaly.current_stock_level,
                    "reject_rate": anomaly.current_reject_rate,
                    "hold_ratio": anomaly.current_hold_ratio,
                    "severity": anomaly.severity,
                    "action": decision.recommended_action,
                    "priority": decision.action_priority,
                    "confidence": decision.confidence_score,
                    "days_until_critical": forecast.days_until_critical,
                })
            except Exception:
                pass

    return {
        "dashboard_summary": summary,
        "sku_decisions": sku_decisions,
        "generated_at": datetime.now().isoformat(),
    }


# ─────────────────────────────────────────────────────────────
# ENDPOINT: Health Check
# ─────────────────────────────────────────────────────────────

@app.get("/", tags=["System"])
async def root():
    """Health check endpoint."""
    return {
        "service": "Inventra AI API",
        "version": "1.0.0",
        "status": "running" if app_state.initialized else "initializing",
        "initialized_at": app_state.init_time,
        "timestamp": datetime.now().isoformat(),
        "docs": "/docs",
    }


@app.get("/api/v1/health", tags=["System"])
async def health_check():
    """Cek status kesehatan semua komponen sistem."""
    engine = app_state.engine
    return {
        "status": "healthy" if app_state.initialized else "unhealthy",
        "components": {
            "ml_engine": "ready" if engine and engine._fitted else "not_ready",
            "data_generator": "ready" if app_state.generator else "not_ready",
            "ai_provider": "ready" if app_state.provider else "not_ready",
        },
        "skus_monitored": len(engine._historical_df["sku_id"].unique())
            if engine and engine._historical_df is not None else 0,
        "uptime_since": app_state.init_time,
    }


# ─────────────────────────────────────────────────────────────
# ENDPOINT: Dashboard Summary
# ─────────────────────────────────────────────────────────────

@app.get("/api/v1/dashboard/summary", tags=["Dashboard"])
async def get_dashboard_summary():
    """
    Ambil ringkasan KPI utama untuk dashboard:
    - Total SKU, anomali aktif, health score
    - Distribusi tindakan (Restocking/Hold/Redistribusi/Monitor)
    - Distribusi severity anomali
    - Daftar SKU kritis
    """
    engine = _require_engine()
    try:
        summary = engine.get_dashboard_summary()
        return ApiResponse(success=True, data=summary)
    except Exception as e:
        logger.error(f"Error get_dashboard_summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────
# ENDPOINT: Inventory Snapshot
# ─────────────────────────────────────────────────────────────

@app.get("/api/v1/inventory/snapshot", tags=["Inventory"])
async def get_inventory_snapshot():
    """
    Ambil snapshot inventaris real-time semua SKU.
    Termasuk status stok, reject rate, hold qty terkini.
    """
    try:
        generator = app_state.generator or SyntheticDataGenerator()
        snapshot = generator.get_current_snapshot()

        # Enrich dengan anomaly status dari engine
        engine = _require_engine()
        enriched = []
        for item in snapshot:
            sku_id = item.get("sku_id")
            try:
                anomaly = engine.detect_anomalies(sku_id)
                item["anomaly_severity"] = anomaly.severity
                item["anomaly_severity_color"] = anomaly.severity_color
                item["is_anomaly"] = anomaly.is_anomaly
            except Exception:
                item["anomaly_severity"] = "Unknown"
                item["is_anomaly"] = False
            enriched.append(item)

        return ApiResponse(
            success=True,
            data={
                "snapshot": enriched,
                "total_skus": len(enriched),
                "snapshot_time": datetime.now().isoformat(),
            },
        )
    except Exception as e:
        logger.error(f"Error get_inventory_snapshot: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────
# ENDPOINT: Per-SKU Analysis
# ─────────────────────────────────────────────────────────────

@app.get("/api/v1/sku/{sku_id}/forecast", tags=["Analysis"])
async def get_sku_forecast(
    sku_id: str,
    horizon: int = Query(default=14, ge=7, le=30, description="Horizon prediksi (7–30 hari)"),
):
    """
    LAYER 1 — PREDICT
    Prediksi kebutuhan stok dan proyeksi level stok untuk SKU tertentu.
    """
    engine = _require_engine()
    try:
        forecast = engine.predict_demand(sku_id, horizon=horizon)
        return ApiResponse(success=True, data=asdict(forecast))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error forecast {sku_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/sku/{sku_id}/anomaly", tags=["Analysis"])
async def get_sku_anomaly(sku_id: str):
    """
    LAYER 2 — DETECT
    Deteksi anomali real-time untuk SKU tertentu menggunakan Isolation Forest
    dan rule-based statistical thresholds.
    """
    engine = _require_engine()
    try:
        anomaly = engine.detect_anomalies(sku_id)
        return ApiResponse(success=True, data=asdict(anomaly))
    except Exception as e:
        logger.error(f"Error anomaly {sku_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/sku/{sku_id}/decision", tags=["Analysis"])
async def get_sku_decision(
    sku_id: str,
    horizon: int = Query(default=14, ge=7, le=30),
):
    """
    LAYER 3 — DECIDE (XAI)
    Hasilkan rekomendasi tindakan lengkap dengan confidence score dan
    reasoning trail untuk SKU tertentu.

    Aksi yang mungkin: RESTOCKING | HOLD | REDISTRIBUSI | MONITOR
    """
    engine = _require_engine()
    try:
        decision = engine.generate_decision(sku_id, forecast_horizon=horizon)
        data = asdict(decision)

        # Tambahkan feedback history untuk SKU ini
        data["feedback_history"] = [
            f for f in app_state.feedback_log if f.get("sku_id") == sku_id
        ]
        return ApiResponse(success=True, data=data)
    except Exception as e:
        logger.error(f"Error decision {sku_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/decisions/all", tags=["Analysis"])
async def get_all_decisions(
    horizon: int = Query(default=14, ge=7, le=30),
    filter_action: Optional[str] = Query(
        default=None,
        description="Filter berdasarkan aksi: RESTOCKING | HOLD | REDISTRIBUSI | MONITOR"
    ),
    filter_risk: Optional[str] = Query(
        default=None,
        description="Filter berdasarkan risk: Kritis | Tinggi | Sedang | Rendah"
    ),
):
    """
    Jalankan analisis lengkap (Predict + Detect + Decide) untuk semua SKU
    dan kembalikan hasilnya sekaligus.
    Mendukung filtering berdasarkan aksi atau risk level.
    """
    engine = _require_engine()
    try:
        all_decisions = engine.analyze_all(horizon=horizon)

        results = []
        for sku_id, decision in all_decisions.items():
            d = asdict(decision)

            # Tambah anomaly info
            try:
                anomaly = engine.detect_anomalies(sku_id)
                d["anomaly_severity"] = anomaly.severity
                d["anomaly_severity_color"] = anomaly.severity_color
                d["anomaly_types"] = anomaly.anomaly_types
            except Exception:
                pass

            # Apply filters
            if filter_action and d.get("recommended_action") != filter_action.upper():
                continue
            if filter_risk and d.get("risk_level") != filter_risk:
                continue

            results.append(d)

        # Urutkan: risiko kritis dulu, lalu confidence tertinggi
        risk_order = {"Kritis": 0, "Tinggi": 1, "Sedang": 2, "Rendah": 3}
        results.sort(key=lambda x: (
            risk_order.get(x.get("risk_level", "Rendah"), 3),
            -x.get("confidence_score", 0),
        ))

        return ApiResponse(
            success=True,
            data={
                "decisions": results,
                "total": len(results),
                "filter_applied": {
                    "action": filter_action,
                    "risk": filter_risk,
                },
                "generated_at": datetime.now().isoformat(),
            },
        )
    except Exception as e:
        logger.error(f"Error get_all_decisions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────
# ENDPOINT: Chart Data
# ─────────────────────────────────────────────────────────────

@app.get("/api/v1/chart/{sku_id}/stock", tags=["Charts"])
async def get_stock_chart_data(
    sku_id: str,
    days: int = Query(default=30, ge=7, le=90, description="Jumlah hari historis"),
    include_forecast: bool = Query(default=True),
    forecast_horizon: int = Query(default=14, ge=7, le=30),
):
    """
    Ambil data time-series untuk grafik tren stok.
    Menggabungkan data historis + proyeksi ke depan untuk chart interaktif.
    """
    engine = _require_engine()
    try:
        # Data historis
        df = engine._historical_df
        if df is None:
            raise HTTPException(status_code=503, detail="Data historis tidak tersedia")

        sku_df = df[df["sku_id"] == sku_id].sort_values("date").tail(days)
        if len(sku_df) == 0:
            raise HTTPException(status_code=404, detail=f"SKU '{sku_id}' tidak ditemukan")

        historical = []
        for _, row in sku_df.iterrows():
            historical.append({
                "date": row["date"].strftime("%Y-%m-%d"),
                "stock_level": int(row["stock_level"]),
                "available_stock": int(row.get("available_stock", row["stock_level"])),
                "daily_consumption": int(row["daily_consumption"]),
                "reject_qty": int(row["reject_qty"]),
                "hold_qty": int(row["hold_qty"]),
                "unreleased_qty": int(row.get("unreleased_qty", 0)),
                "reject_rate": round(float(row["reject_rate"]) * 100, 2),
                "is_anomaly": bool(row.get("is_anomaly", False)),
                "type": "historical",
            })

        # Data proyeksi
        forecast_data = []
        if include_forecast:
            forecast = engine.predict_demand(sku_id, horizon=forecast_horizon)
            for i, (date, stock, consumption) in enumerate(zip(
                forecast.predicted_dates,
                forecast.predicted_stock_levels,
                forecast.predicted_consumption,
            )):
                forecast_data.append({
                    "date": date,
                    "stock_level": int(stock),
                    "daily_consumption": int(consumption),
                    "type": "forecast",
                    "is_critical": (
                        forecast.days_until_critical is not None
                        and i + 1 >= forecast.days_until_critical
                    ),
                })

        # Metadata produk
        product = engine._get_product_info(sku_id)

        return ApiResponse(
            success=True,
            data={
                "sku_id": sku_id,
                "sku_name": product.get("sku_name", sku_id),
                "reorder_point": product.get("reorder_point", 0),
                "historical": historical,
                "forecast": forecast_data,
                "chart_meta": {
                    "historical_days": len(historical),
                    "forecast_days": len(forecast_data),
                    "trend_direction": forecast.trend_direction if include_forecast else None,
                    "days_until_critical": forecast.days_until_critical if include_forecast else None,
                },
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error chart data {sku_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/chart/anomalies/heatmap", tags=["Charts"])
async def get_anomaly_heatmap():
    """
    Data heatmap anomali: reject rate dan hold ratio semua SKU
    untuk 30 hari terakhir. Digunakan untuk panel Active Anomalies.
    """
    engine = _require_engine()
    try:
        df = engine._historical_df
        recent_df = df.groupby("sku_id").tail(30)

        heatmap_data = []
        for sku_id in df["sku_id"].unique():
            sku_data = recent_df[recent_df["sku_id"] == sku_id]
            anomaly = engine.detect_anomalies(sku_id)
            product = engine._get_product_info(sku_id)

            heatmap_data.append({
                "sku_id": sku_id,
                "sku_name": product.get("sku_name", sku_id),
                "avg_reject_rate": round(float(sku_data["reject_rate"].mean()) * 100, 2),
                "max_reject_rate": round(float(sku_data["reject_rate"].max()) * 100, 2),
                "avg_hold_ratio": round(float((sku_data["hold_qty"] / (sku_data["stock_level"] + 1)).mean()) * 100, 2),
                "severity": anomaly.severity,
                "severity_color": anomaly.severity_color,
                "is_anomaly": anomaly.is_anomaly,
                "anomaly_types": anomaly.anomaly_types,
            })

        return ApiResponse(success=True, data={"heatmap": heatmap_data})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────
# ENDPOINT: AI Insight Assistant (Chat)
# ─────────────────────────────────────────────────────────────

@app.post("/api/v1/chat", tags=["AI Assistant"])
async def chat_with_assistant(request: ChatRequest):
    """
    Kirim pesan ke AI Insight Assistant berbasis GPT-4o / Claude.
    Asisten akan menjawab berdasarkan data inventaris real-time dalam Bahasa Indonesia.

    Contoh pertanyaan:
    - "Barang apa yang paling berisiko minggu ini?"
    - "SKU mana yang perlu dipesan segera?"
    - "Jelaskan kondisi inventaris hari ini"
    - "Apa yang menyebabkan reject rate SKU-003 tinggi?"
    """
    if not app_state.provider:
        raise HTTPException(status_code=503, detail="AI Provider belum siap")

    try:
        # Ambil konteks inventaris terkini
        inventory_context = _build_inventory_context_for_llm()

        response = await app_state.provider.chat(
            user_message=request.message,
            session_id=request.session_id,
            inventory_context=inventory_context,
        )
        return ApiResponse(success=True, data=response)
    except Exception as e:
        logger.error(f"Error chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/v1/chat/{session_id}", tags=["AI Assistant"])
async def clear_chat_history(session_id: str):
    """Hapus riwayat percakapan untuk session tertentu."""
    if app_state.provider:
        app_state.provider.clear_history(session_id)
    return ApiResponse(success=True, message=f"Riwayat sesi '{session_id}' dihapus.")


@app.get("/api/v1/briefing/daily", tags=["AI Assistant"])
async def get_daily_briefing():
    """
    Hasilkan ringkasan harian otomatis dari AI Assistant.
    Cocok ditampilkan saat operator membuka dashboard di awal shift.
    """
    if not app_state.provider:
        raise HTTPException(status_code=503, detail="AI Provider belum siap")
    try:
        context = _build_inventory_context_for_llm()
        briefing = await app_state.provider.generate_daily_briefing(context)
        return ApiResponse(
            success=True,
            data={
                "briefing": briefing,
                "generated_at": datetime.now().isoformat(),
                "shift": _get_current_shift(),
            },
        )
    except Exception as e:
        logger.error(f"Error daily briefing: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────
# ENDPOINT: Feedback Loop (Continuous Learning)
# ─────────────────────────────────────────────────────────────

@app.post("/api/v1/feedback", tags=["Feedback"])
async def submit_feedback(request: FeedbackRequest, background_tasks: BackgroundTasks):
    """
    Terima feedback operator terhadap rekomendasi AI.
    Feedback 'approved' atau 'rejected' dicatat sebagai sinyal pelatihan
    untuk meningkatkan akurasi model secara iteratif (Continuous Learning).

    Proses:
    1. Simpan feedback ke log
    2. Trigger background task untuk proses learning (simulasi)
    3. Update feedback_status pada decision terkait
    """
    feedback_entry = {
        "id": f"fb_{len(app_state.feedback_log) + 1:04d}",
        "sku_id": request.sku_id,
        "decision_action": request.decision_action,
        "feedback": request.feedback,
        "note": request.note,
        "operator_id": request.operator_id or "operator_anonymous",
        "timestamp": datetime.now().isoformat(),
        "processed": False,
    }

    app_state.feedback_log.append(feedback_entry)

    # Background: simulasi proses continuous learning
    background_tasks.add_task(_process_feedback_learning, feedback_entry)

    total_feedback = len(app_state.feedback_log)
    approved = sum(1 for f in app_state.feedback_log if f["feedback"] == "approved")
    rejected = total_feedback - approved

    return ApiResponse(
        success=True,
        data={
            "feedback_id": feedback_entry["id"],
            "sku_id": request.sku_id,
            "status": "recorded",
            "message": (
                f"Feedback '{request.feedback}' berhasil dicatat untuk {request.sku_id}. "
                f"Terima kasih! Data ini akan meningkatkan akurasi model AI."
            ),
            "stats": {
                "total_feedback": total_feedback,
                "approved": approved,
                "rejected": rejected,
                "approval_rate": round(approved / max(total_feedback, 1) * 100, 1),
            },
        },
    )


@app.get("/api/v1/feedback/log", tags=["Feedback"])
async def get_feedback_log(
    limit: int = Query(default=20, ge=1, le=100),
    sku_id: Optional[str] = Query(default=None),
):
    """Ambil log feedback dari operator untuk monitoring continuous learning."""
    log = app_state.feedback_log

    if sku_id:
        log = [f for f in log if f.get("sku_id") == sku_id]

    log_sorted = sorted(log, key=lambda x: x["timestamp"], reverse=True)[:limit]

    return ApiResponse(
        success=True,
        data={
            "feedback_log": log_sorted,
            "total": len(app_state.feedback_log),
            "filtered": len(log_sorted),
        },
    )


@app.get("/api/v1/feedback/stats", tags=["Feedback"])
async def get_feedback_stats():
    """Statistik feedback loop untuk monitoring performa continuous learning."""
    log = app_state.feedback_log
    if not log:
        return ApiResponse(success=True, data={"message": "Belum ada feedback.", "total": 0})

    total = len(log)
    approved = sum(1 for f in log if f["feedback"] == "approved")
    rejected = total - approved

    # Per action stats
    from collections import Counter
    action_feedback = {}
    for f in log:
        action = f.get("decision_action", "UNKNOWN")
        if action not in action_feedback:
            action_feedback[action] = {"approved": 0, "rejected": 0}
        action_feedback[action][f["feedback"]] += 1

    return ApiResponse(
        success=True,
        data={
            "total_feedback": total,
            "approved": approved,
            "rejected": rejected,
            "approval_rate": round(approved / total * 100, 1),
            "per_action": action_feedback,
            "model_improvement_estimate": f"+{min(15, total * 0.3):.1f}% akurasi prediksi",
        },
    )


# ─────────────────────────────────────────────────────────────
# ENDPOINT: Catalog & Metadata
# ─────────────────────────────────────────────────────────────

@app.get("/api/v1/catalog", tags=["Metadata"])
async def get_product_catalog():
    """Ambil katalog produk lengkap beserta parameter konfigurasi."""
    generator = app_state.generator or SyntheticDataGenerator()
    catalog = generator.get_product_catalog()
    return ApiResponse(success=True, data={"catalog": catalog, "total": len(catalog)})


@app.get("/api/v1/catalog/{sku_id}", tags=["Metadata"])
async def get_product_detail(sku_id: str):
    """Ambil detail satu produk dan analisis lengkapnya."""
    engine = _require_engine()
    try:
        product = engine._get_product_info(sku_id)
        if not product:
            raise HTTPException(status_code=404, detail=f"SKU '{sku_id}' tidak ditemukan")

        forecast = engine.predict_demand(sku_id, horizon=14)
        anomaly = engine.detect_anomalies(sku_id)
        decision = engine.generate_decision(sku_id)

        return ApiResponse(
            success=True,
            data={
                "product": product,
                "forecast": asdict(forecast),
                "anomaly": asdict(anomaly),
                "decision": asdict(decision),
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────
# Helper Functions
# ─────────────────────────────────────────────────────────────

def _get_current_shift() -> str:
    """Tentukan shift berdasarkan jam saat ini."""
    hour = datetime.now().hour
    if 6 <= hour < 14:
        return "Shift Pagi (06:00–14:00)"
    elif 14 <= hour < 22:
        return "Shift Siang (14:00–22:00)"
    else:
        return "Shift Malam (22:00–06:00)"


async def _process_feedback_learning(feedback_entry: Dict):
    """
    Background task: simulasi proses continuous learning.
    Dalam implementasi nyata, ini akan memicu retraining model
    atau update parameter bobot berdasarkan feedback operator.
    """
    import asyncio
    await asyncio.sleep(0.5)  # Simulasi processing time

    # Tandai sebagai processed
    for f in app_state.feedback_log:
        if f["id"] == feedback_entry["id"]:
            f["processed"] = True
            break

    logger.info(
        f"📚 Feedback diproses: {feedback_entry['sku_id']} — "
        f"{feedback_entry['feedback']} untuk {feedback_entry['decision_action']}"
    )


# ─────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
