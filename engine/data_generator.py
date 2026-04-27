"""
engine/data_generator.py
========================
Generator data inventaris manufaktur sintetis untuk keperluan demo Inventra AI.
Mensimulasikan kondisi nyata pabrik: tren konsumsi, anomali reject/hold,
siklus mingguan, dan skenario kritis.

Author  : Inventra AI Team
Version : 1.0.0
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict
import random
import json


# ─────────────────────────────────────────────
# Konfigurasi Produk Simulasi
# ─────────────────────────────────────────────
PRODUCT_CATALOG: List[Dict] = [
    {
        "sku_id": "SKU-001",
        "sku_name": "Bearing Assembly Type A",
        "category": "Komponen Mesin",
        "unit": "pcs",
        "base_stock": 1500,
        "daily_consumption_avg": 35,
        "lead_time_days": 14,
        "reorder_point": 490,
        "unit_cost": 125000,
    },
    {
        "sku_id": "SKU-002",
        "sku_name": "Hydraulic Seal Kit",
        "category": "Suku Cadang",
        "unit": "set",
        "base_stock": 800,
        "daily_consumption_avg": 20,
        "lead_time_days": 10,
        "reorder_point": 280,
        "unit_cost": 87500,
    },
    {
        "sku_id": "SKU-003",
        "sku_name": "Steel Rod 12mm",
        "category": "Bahan Baku",
        "unit": "batang",
        "base_stock": 2000,
        "daily_consumption_avg": 55,
        "lead_time_days": 7,
        "reorder_point": 385,
        "unit_cost": 45000,
    },
    {
        "sku_id": "SKU-004",
        "sku_name": "Circuit Board Module",
        "category": "Elektronik",
        "unit": "pcs",
        "base_stock": 600,
        "daily_consumption_avg": 15,
        "lead_time_days": 21,
        "reorder_point": 315,
        "unit_cost": 350000,
    },
    {
        "sku_id": "SKU-005",
        "sku_name": "Aluminum Sheet 2mm",
        "category": "Bahan Baku",
        "unit": "lembar",
        "base_stock": 1800,
        "daily_consumption_avg": 45,
        "lead_time_days": 7,
        "reorder_point": 315,
        "unit_cost": 62000,
    },
    {
        "sku_id": "SKU-006",
        "sku_name": "Pneumatic Valve",
        "category": "Komponen Mesin",
        "unit": "pcs",
        "base_stock": 400,
        "daily_consumption_avg": 10,
        "lead_time_days": 18,
        "reorder_point": 180,
        "unit_cost": 215000,
    },
    {
        "sku_id": "SKU-007",
        "sku_name": "Rubber Gasket Set",
        "category": "Suku Cadang",
        "unit": "set",
        "base_stock": 1200,
        "daily_consumption_avg": 30,
        "lead_time_days": 5,
        "reorder_point": 150,
        "unit_cost": 32000,
    },
    {
        "sku_id": "SKU-008",
        "sku_name": "Stainless Bolt M8",
        "category": "Fastener",
        "unit": "pcs",
        "base_stock": 5000,
        "daily_consumption_avg": 120,
        "lead_time_days": 3,
        "reorder_point": 360,
        "unit_cost": 2500,
    },
]

# ─────────────────────────────────────────────
# Skenario Anomali yang Akan Diinjeksikan
# ─────────────────────────────────────────────
ANOMALY_SCENARIOS = {
    # SKU-003: Lonjakan reject karena material batch buruk (hari ke-60-70)
    "SKU-003": {
        "type": "reject_spike",
        "window": (60, 75),
        "reject_multiplier": 4.5,
        "description": "Lonjakan reject karena kualitas batch material buruk",
    },
    # SKU-004: Stok kritis menjelang habis (hari ke-75+)
    "SKU-004": {
        "type": "critical_stock",
        "window": (75, 90),
        "stock_multiplier": 0.25,
        "description": "Stok mendekati kritis akibat konsumsi tinggi tanpa restock",
    },
    # SKU-006: Reject spike karena masalah supplier
    "SKU-006": {
        "type": "reject_spike",
        "window": (55, 68),
        "reject_multiplier": 3.8,
        "description": "Reject meningkat karena perubahan supplier komponen",
    },
    # SKU-007: Hold anomali karena proses QC tertunda
    "SKU-007": {
        "type": "hold_anomaly",
        "window": (80, 90),
        "hold_multiplier": 5.0,
        "description": "Penumpukan barang hold akibat bottleneck proses QC",
    },
}


class SyntheticDataGenerator:
    """
    Generator data inventaris manufaktur sintetis.
    Menghasilkan data realistis dengan pola musiman, tren konsumsi,
    dan skenario anomali yang dapat dikonfigurasi.
    """

    def __init__(self, seed: int = 42):
        np.random.seed(seed)
        random.seed(seed)
        self.products = PRODUCT_CATALOG
        self.anomaly_scenarios = ANOMALY_SCENARIOS

    def _apply_seasonality(self, day: int, amplitude: float = 30.0) -> float:
        """
        Terapkan pola musiman mingguan (peak di awal minggu, rendah di akhir minggu)
        dan bulanan pada data inventaris.
        """
        weekly_pattern = amplitude * np.sin(2 * np.pi * day / 7)
        monthly_pattern = amplitude * 0.5 * np.sin(2 * np.pi * day / 30)
        return weekly_pattern + monthly_pattern

    def _calculate_reject_rate(
        self, sku_id: str, day: int, base_rate: float = 0.025
    ) -> float:
        """
        Hitung tingkat reject harian.
        Inject anomali reject jika sku dan hari masuk dalam skenario anomali.
        """
        scenario = self.anomaly_scenarios.get(sku_id)
        if (
            scenario
            and scenario["type"] in ("reject_spike",)
            and scenario["window"][0] <= day <= scenario["window"][1]
        ):
            # Tingkat reject anomali: jauh di atas normal
            return np.random.uniform(0.12, 0.22) * scenario.get("reject_multiplier", 1) / 4.5
        return base_rate + np.random.uniform(-0.01, 0.01)

    def _calculate_hold_qty(
        self, sku_id: str, day: int, stock: float
    ) -> int:
        """
        Hitung jumlah barang on-hold.
        Inject anomali hold jika masuk skenario QC bottleneck.
        """
        scenario = self.anomaly_scenarios.get(sku_id)
        base_hold_ratio = np.random.uniform(0.02, 0.06)

        if (
            scenario
            and scenario["type"] == "hold_anomaly"
            and scenario["window"][0] <= day <= scenario["window"][1]
        ):
            # Hold anomali: akumulasi progresif
            days_into_anomaly = day - scenario["window"][0]
            hold_ratio = min(0.40, base_hold_ratio + days_into_anomaly * 0.035)
            return int(stock * hold_ratio)

        return int(stock * base_hold_ratio)

    def generate_historical_data(self, days: int = 90) -> pd.DataFrame:
        """
        Generate dataset historis inventaris untuk semua SKU selama N hari.

        Returns:
            pd.DataFrame: DataFrame dengan kolom lengkap inventaris harian.
        """
        records = []
        base_date = datetime.now() - timedelta(days=days)

        for product in self.products:
            sku_id = product["sku_id"]
            base_stock = product["base_stock"]
            daily_avg = product["daily_consumption_avg"]
            lead_time = product["lead_time_days"]
            reorder_point = product["reorder_point"]

            current_stock = float(base_stock)
            cumulative_consumption = 0

            for day in range(days):
                date = base_date + timedelta(days=day)

                # ── Konsumsi harian dengan noise ──
                consumption_noise = np.random.normal(0, daily_avg * 0.15)
                seasonality = self._apply_seasonality(day, amplitude=daily_avg * 0.2)
                daily_consumption = max(
                    1, daily_avg + consumption_noise + seasonality * 0.3
                )

                # ── Stok kritis: inject skenario critical_stock ──
                scenario = self.anomaly_scenarios.get(sku_id, {})
                if (
                    scenario.get("type") == "critical_stock"
                    and scenario["window"][0] <= day <= scenario["window"][1]
                ):
                    stock_factor = scenario.get("stock_multiplier", 1.0)
                    current_stock = max(
                        20, current_stock * stock_factor + np.random.uniform(-10, 10)
                    )
                else:
                    # Simulasi restocking otomatis ketika menyentuh reorder point
                    if current_stock <= reorder_point and day % lead_time == 0:
                        restock_qty = base_stock * np.random.uniform(0.4, 0.6)
                        current_stock += restock_qty

                    current_stock = max(10, current_stock - daily_consumption)

                cumulative_consumption += daily_consumption

                # ── Kalkulasi Reject, Hold, Unreleased ──
                reject_rate = self._calculate_reject_rate(sku_id, day)
                reject_qty = int(current_stock * reject_rate)
                hold_qty = self._calculate_hold_qty(sku_id, day, current_stock)
                unreleased_qty = int(current_stock * np.random.uniform(0.01, 0.04))

                # ── Tentukan apakah hari ini anomali ──
                is_anomaly = bool(
                    scenario
                    and scenario.get("window", (999, 999))[0]
                    <= day
                    <= scenario.get("window", (999, 999))[1]
                )
                anomaly_type = scenario.get("type", "normal") if is_anomaly else "normal"

                records.append(
                    {
                        "date": date.strftime("%Y-%m-%d"),
                        "sku_id": sku_id,
                        "sku_name": product["sku_name"],
                        "category": product["category"],
                        "unit": product["unit"],
                        "stock_level": int(current_stock),
                        "daily_consumption": int(daily_consumption),
                        "reject_qty": reject_qty,
                        "hold_qty": hold_qty,
                        "unreleased_qty": unreleased_qty,
                        "available_stock": max(
                            0,
                            int(current_stock) - hold_qty - unreleased_qty - reject_qty,
                        ),
                        "reject_rate": round(reject_rate, 4),
                        "lead_time_days": lead_time,
                        "reorder_point": reorder_point,
                        "unit_cost": product["unit_cost"],
                        "is_anomaly": is_anomaly,
                        "anomaly_type": anomaly_type,
                        "cumulative_consumption": int(cumulative_consumption),
                    }
                )

        df = pd.DataFrame(records)
        df["date"] = pd.to_datetime(df["date"])
        return df

    def get_current_snapshot(self) -> List[Dict]:
        """
        Ambil snapshot inventaris terkini (hari ini).
        Digunakan untuk tampilan dashboard real-time.
        """
        df = self.generate_historical_data(days=90)
        latest = df.groupby("sku_id").last().reset_index()
        return latest.to_dict(orient="records")

    def get_product_catalog(self) -> List[Dict]:
        """Kembalikan katalog produk lengkap."""
        return self.products


# ─────────────────────────────────────────────
# Entry point untuk testing mandiri
# ─────────────────────────────────────────────
if __name__ == "__main__":
    gen = SyntheticDataGenerator()
    df = gen.generate_historical_data(days=90)
    print(f"✅ Data generated: {len(df)} records, {df['sku_id'].nunique()} SKUs")
    print(f"📊 Anomaly records: {df['is_anomaly'].sum()} ({df['is_anomaly'].mean()*100:.1f}%)")
    print(df.tail(10).to_string())
