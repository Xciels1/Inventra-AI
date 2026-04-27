# Inventra AI — Intelligent Inventory Decision Engine
> Dicoding AI Impact Challenge 2025 · Topik: Manufaktur & Energi

## Arsitektur Sistem

```
inventra-ai/
├── engine/
│   ├── data_generator.py   # Generator data sintetis manufaktur (8 SKU, 90 hari)
│   └── ml_logic.py         # InventoryEngine: Predict → Detect → Decide (XAI)
├── api/
│   └── main.py             # FastAPI REST API (15 endpoint)
├── integrations/
│   └── azure_provider.py   # Azure OpenAI / Anthropic wrapper untuk AI Assistant
├── frontend/
│   └── dashboard.html      # Dashboard industri (React, Chart.js, standalone)
├── requirements.txt
├── .env.example
└── README.md
```

## Cara Menjalankan

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Konfigurasi Environment (Opsional)
```bash
cp .env.example .env
# Edit .env — tambahkan ANTHROPIC_API_KEY atau AZURE_OPENAI_KEY
# Jika tidak diisi, AI Assistant menggunakan rule-based fallback
```

### 3. Jalankan Backend API
```bash
uvicorn api.main:app --reload --port 8000
# API Docs: http://localhost:8000/docs
```

### 4. Buka Dashboard
Buka file `frontend/dashboard.html` langsung di browser.
Dashboard otomatis terkoneksi ke backend di `localhost:8000`.
Jika backend tidak berjalan → mode demo offline dengan mock data.

---

## Tiga Lapis Intelijen

### Layer 1: PREDICT
- **Model**: Moving Average + Trend Decomposition + Seasonality Fourier
- **Output**: Proyeksi stok 7–30 hari, jadwal restock optimal, confidence score
- **Endpoint**: `GET /api/v1/sku/{sku_id}/forecast?horizon=14`

### Layer 2: DETECT
- **Model**: Isolation Forest (unsupervised) + 5 rule-based statistical thresholds
- **Deteksi**: Reject spike, Hold anomaly, Critical stock, Consumption surge
- **Severity**: Normal → Low → Medium → High → Critical
- **Endpoint**: `GET /api/v1/sku/{sku_id}/anomaly`

### Layer 3: DECIDE (Explainable AI)
- **Output**: RESTOCKING / HOLD / REDISTRIBUSI / MONITOR
- **XAI Fields**: `reasoning_path`, `confidence_score`, `key_factors`, `estimated_loss_if_ignored`
- **Endpoint**: `GET /api/v1/sku/{sku_id}/decision`

---

## API Reference

| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| GET | `/` | Health check |
| GET | `/api/v1/dashboard/summary` | KPI dashboard |
| GET | `/api/v1/inventory/snapshot` | Snapshot real-time semua SKU |
| GET | `/api/v1/sku/{id}/forecast` | Prediksi stok |
| GET | `/api/v1/sku/{id}/anomaly` | Deteksi anomali |
| GET | `/api/v1/sku/{id}/decision` | Keputusan XAI |
| GET | `/api/v1/decisions/all` | Semua keputusan (filter support) |
| GET | `/api/v1/chart/{id}/stock` | Data time-series untuk chart |
| GET | `/api/v1/chart/anomalies/heatmap` | Heatmap anomali |
| POST | `/api/v1/chat` | AI Insight Assistant |
| DELETE | `/api/v1/chat/{session_id}` | Hapus riwayat chat |
| GET | `/api/v1/briefing/daily` | Ringkasan harian otomatis |
| POST | `/api/v1/feedback` | Submit feedback (Approve/Reject) |
| GET | `/api/v1/feedback/log` | Log feedback operator |
| GET | `/api/v1/feedback/stats` | Statistik continuous learning |

---

## Tim Pengembang
| Nama | Email Dicoding |
|------|---------------|
| Hendrikus Lanang Ona | miwho014@gmail.com |
| Phillip Luis Nurcahyo | philipluisnurcahyo9@gmail.com |
| Hervian Paskah Pradana | kakhervian@gmail.com |
