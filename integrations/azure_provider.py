"""
integrations/azure_provider.py
================================
Wrapper untuk Azure OpenAI Service (GPT-4o) yang mengtenagai
AI Insight Assistant Inventra AI.

Fitur:
- Menjawab pertanyaan natural language tentang inventaris dalam Bahasa Indonesia
- Menghasilkan ringkasan harian otomatis
- Menjelaskan reasoning di balik setiap rekomendasi AI
- Graceful fallback ke rule-based response jika Azure tidak tersedia

Author  : Inventra AI Team
Version : 1.0.0
"""

import os
import json
import logging
import re
from typing import Optional, Dict, List, Any
from datetime import datetime
import httpx

logger = logging.getLogger("inventra.azure_provider")


# ─────────────────────────────────────────────────────────────
# Konfigurasi Azure OpenAI
# ─────────────────────────────────────────────────────────────

AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_KEY      = os.getenv("AZURE_OPENAI_KEY", "")
AZURE_DEPLOYMENT_NAME = os.getenv("AZURE_DEPLOYMENT_NAME", "gpt-4o")
AZURE_API_VERSION     = os.getenv("AZURE_API_VERSION", "2024-02-15-preview")

# Fallback ke Anthropic Claude API (untuk demo tanpa Azure)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
USE_ANTHROPIC_FALLBACK = bool(ANTHROPIC_API_KEY and not AZURE_OPENAI_KEY)


# ─────────────────────────────────────────────────────────────
# System Prompt — Kepribadian AI Insight Assistant
# ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Kamu adalah Inventra AI Assistant — asisten kecerdasan buatan untuk sistem manajemen inventaris manufaktur Inventra AI.

PERAN DAN KEPRIBADIAN:
- Kamu adalah expert inventaris dan supply chain yang berpengalaman di industri manufaktur Indonesia
- Kamu berbicara dalam Bahasa Indonesia yang profesional namun mudah dipahami operator pabrik
- Kamu selalu berbasis data — setiap jawaban harus merujuk pada data inventaris yang tersedia
- Kamu proaktif dalam mengidentifikasi risiko dan memberikan rekomendasi tindakan konkret

KONTEKS SISTEM:
Inventra AI memiliki 3 lapisan analisis:
1. PREDICT: Forecasting stok 7-30 hari ke depan menggunakan ML
2. DETECT: Deteksi anomali real-time (reject spike, hold anomaly, stok kritis)
3. DECIDE: Rekomendasi tindakan otomatis (Restocking, Hold, Redistribusi, Monitor)

PANDUAN MENJAWAB:
- Selalu gunakan data inventaris yang diberikan dalam konteks
- Berikan jawaban yang actionable — operator harus tahu apa yang harus dilakukan
- Sertakan angka spesifik dari data saat relevan
- Jika ada anomali kritis, tekankan urgensi dengan jelas
- Untuk pertanyaan di luar konteks inventaris manufaktur, arahkan kembali ke topik yang relevan
- Gunakan emoji secara minimal dan profesional: ✅ ⚠️ 🔴 📊 untuk highlight penting

FORMAT JAWABAN:
- Singkat dan padat untuk pertanyaan sederhana (2-4 kalimat)
- Terstruktur untuk pertanyaan analitik kompleks (gunakan poin-poin)
- Selalu akhiri dengan rekomendasi tindakan jika relevan"""


# ─────────────────────────────────────────────────────────────
# Kelas Utama: AzureOpenAIProvider
# ─────────────────────────────────────────────────────────────

class AzureOpenAIProvider:
    """
    Wrapper untuk Azure OpenAI Service.
    Mengelola koneksi, konteks inventaris, dan response generation
    untuk AI Insight Assistant Inventra AI.
    """

    def __init__(self):
        self._client = httpx.AsyncClient(timeout=30.0)
        self._conversation_histories: Dict[str, List[Dict]] = {}
        logger.info(
            f"AzureOpenAIProvider diinisialisasi. "
            f"Mode: {'Azure OpenAI' if AZURE_OPENAI_KEY else 'Anthropic Fallback' if USE_ANTHROPIC_FALLBACK else 'Rule-based Fallback'}"
        )

    def _build_inventory_context(self, inventory_context: Optional[Dict]) -> str:
        """
        Ubah data inventaris menjadi teks konteks yang informatif untuk LLM.
        """
        if not inventory_context:
            return "Data inventaris saat ini tidak tersedia."

        lines = ["=== DATA INVENTARIS TERKINI ===\n"]

        # Dashboard summary
        summary = inventory_context.get("dashboard_summary", {})
        if summary:
            lines.append(f"📊 RINGKASAN SISTEM:")
            lines.append(f"  • Total SKU terpantau: {summary.get('total_skus', 0)}")
            lines.append(f"  • Anomali aktif: {summary.get('anomaly_active', 0)}")
            lines.append(f"  • Health Score sistem: {summary.get('health_score', 0)}%")
            action_dist = summary.get("action_distribution", {})
            lines.append(f"  • Distribusi rekomendasi: Restocking={action_dist.get('RESTOCKING',0)}, "
                        f"Hold={action_dist.get('HOLD',0)}, "
                        f"Redistribusi={action_dist.get('REDISTRIBUSI',0)}, "
                        f"Monitor={action_dist.get('MONITOR',0)}")
            lines.append("")

        # SKU kritis
        critical = summary.get("critical_skus", [])
        if critical:
            lines.append("🔴 SKU PRIORITAS TINGGI:")
            for sku in critical[:5]:
                lines.append(
                    f"  • {sku['sku_name']} ({sku['sku_id']}): "
                    f"{sku['action']} — {sku['priority']} "
                    f"[Risk: {sku['risk']}, Confidence: {sku['confidence']}%]"
                )
            lines.append("")

        # Data per SKU
        sku_decisions = inventory_context.get("sku_decisions", [])
        if sku_decisions:
            lines.append("📋 DETAIL PER SKU:")
            for d in sku_decisions[:8]:  # batasi 8 SKU untuk efisiensi token
                lines.append(
                    f"\n  [{d.get('sku_id')}] {d.get('sku_name')} ({d.get('category')})"
                )
                lines.append(f"    Stok: {d.get('current_stock', 'N/A')} unit | "
                            f"Reject: {d.get('reject_rate', 0)*100:.1f}% | "
                            f"Hold: {d.get('hold_ratio', 0)*100:.1f}%")
                lines.append(f"    Anomali: {d.get('severity', 'Normal')} | "
                            f"Rekomendasi: {d.get('action')} ({d.get('priority')})")
                if d.get("days_until_critical"):
                    lines.append(f"    ⚠️ Kritis dalam {d['days_until_critical']} hari")

        lines.append("\n=== AKHIR DATA INVENTARIS ===")
        return "\n".join(lines)

    def _get_or_create_history(self, session_id: str) -> List[Dict]:
        """Ambil atau buat riwayat percakapan baru untuk session."""
        if session_id not in self._conversation_histories:
            self._conversation_histories[session_id] = []
        return self._conversation_histories[session_id]

    def clear_history(self, session_id: str):
        """Hapus riwayat percakapan untuk session tertentu."""
        self._conversation_histories.pop(session_id, None)

    async def chat(
        self,
        user_message: str,
        session_id: str = "default",
        inventory_context: Optional[Dict] = None,
        max_history_turns: int = 6,
    ) -> Dict[str, Any]:
        """
        Kirim pesan ke AI Insight Assistant dan terima respons.

        Args:
            user_message      : Pertanyaan dari pengguna (Bahasa Indonesia)
            session_id        : ID sesi untuk menjaga riwayat percakapan
            inventory_context : Data inventaris terkini sebagai konteks
            max_history_turns : Batas riwayat percakapan (untuk menghindari overflow token)

        Returns:
            Dict berisi:
              - message   : Respons asisten
              - session_id: ID sesi
              - timestamp : Waktu respons
              - source    : Model yang digunakan
        """
        history = self._get_or_create_history(session_id)

        # Buat konteks inventaris yang siap masuk ke prompt
        context_text = self._build_inventory_context(inventory_context)

        # Bangun user message yang diperkaya dengan konteks terbaru
        enriched_message = f"{user_message}\n\n[KONTEKS DATA TERKINI]\n{context_text}"

        # Tambah ke history
        history.append({"role": "user", "content": enriched_message})

        # Batasi history agar tidak melebihi context window
        if len(history) > max_history_turns * 2:
            history = history[-(max_history_turns * 2):]
            self._conversation_histories[session_id] = history

        try:
            if AZURE_OPENAI_KEY:
                response_text = await self._call_azure_openai(history)
                source = "Azure OpenAI (GPT-4o)"
            elif USE_ANTHROPIC_FALLBACK:
                response_text = await self._call_anthropic(history, user_message, context_text)
                source = "Claude (Fallback)"
            else:
                response_text = self._rule_based_response(user_message, inventory_context)
                source = "Rule-based Engine"

        except Exception as e:
            logger.error(f"Error memanggil LLM API: {e}")
            response_text = self._rule_based_response(user_message, inventory_context)
            source = "Rule-based Fallback"

        # Simpan respons ke history
        history.append({"role": "assistant", "content": response_text})

        return {
            "message": response_text,
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "source": source,
        }

    async def _call_azure_openai(self, history: List[Dict]) -> str:
        """Panggil Azure OpenAI REST API."""
        url = (
            f"{AZURE_OPENAI_ENDPOINT}/openai/deployments/{AZURE_DEPLOYMENT_NAME}"
            f"/chat/completions?api-version={AZURE_API_VERSION}"
        )
        payload = {
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + history,
            "max_tokens": 800,
            "temperature": 0.3,
            "top_p": 0.9,
        }
        headers = {
            "Content-Type": "application/json",
            "api-key": AZURE_OPENAI_KEY,
        }
        resp = await self._client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()

    async def _call_anthropic(
        self, history: List[Dict], user_message: str, context_text: str
    ) -> str:
        """
        Fallback: Panggil Anthropic Claude API jika Azure tidak tersedia.
        Untuk demo kompetisi tanpa konfigurasi Azure.
        """
        url = "https://api.anthropic.com/v1/messages"
        # Format history untuk Anthropic (tanpa system role di messages)
        messages = []
        for msg in history:
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })

        payload = {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 800,
            "system": SYSTEM_PROMPT,
            "messages": messages,
        }
        headers = {
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
        }
        resp = await self._client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return data["content"][0]["text"].strip()

    def _rule_based_response(
        self, message: str, inventory_context: Optional[Dict]
    ) -> str:
        """
        Rule-based response engine sebagai fallback terakhir.
        Menghasilkan respons informatif berdasarkan keyword matching
        dan data inventaris yang tersedia.
        """
        msg_lower = message.lower()
        summary = (inventory_context or {}).get("dashboard_summary", {})
        critical_skus = summary.get("critical_skus", [])
        action_dist = summary.get("action_distribution", {})

        # ── Pattern: Barang paling berisiko ──
        if any(k in msg_lower for k in ["risiko", "berisiko", "berbahaya", "kritis", "prioritas"]):
            if critical_skus:
                sku = critical_skus[0]
                return (
                    f"⚠️ Berdasarkan analisis terkini, **{sku['sku_name']}** ({sku['sku_id']}) "
                    f"adalah SKU dengan risiko tertinggi minggu ini.\n\n"
                    f"**Status:** {sku['action']} — {sku['priority']}\n"
                    f"**Risk Level:** {sku['risk']}\n"
                    f"**Confidence AI:** {sku['confidence']}%\n\n"
                    f"Disarankan untuk segera menangani SKU ini sebelum berdampak ke lini produksi."
                )
            return "Saat ini tidak ada SKU dengan risiko kritis yang terdeteksi. Sistem berjalan normal. ✅"

        # ── Pattern: Ringkasan / summary ──
        elif any(k in msg_lower for k in ["ringkasan", "summary", "laporan", "status", "kondisi"]):
            anomaly_count = summary.get("anomaly_active", 0)
            health_score = summary.get("health_score", 100)
            total = summary.get("total_skus", 0)
            return (
                f"📊 **Ringkasan Inventaris Saat Ini:**\n\n"
                f"• Total SKU terpantau: **{total} SKU**\n"
                f"• Anomali aktif: **{anomaly_count} SKU** memerlukan perhatian\n"
                f"• Health Score sistem: **{health_score}%**\n"
                f"• Butuh Restocking: **{action_dist.get('RESTOCKING', 0)} SKU**\n"
                f"• Status Hold: **{action_dist.get('HOLD', 0)} SKU**\n"
                f"• Perlu Redistribusi: **{action_dist.get('REDISTRIBUSI', 0)} SKU**\n\n"
                f"{'⚠️ Ada anomali yang memerlukan tindakan segera.' if anomaly_count > 0 else '✅ Semua kondisi dalam batas normal.'}"
            )

        # ── Pattern: Restocking ──
        elif any(k in msg_lower for k in ["restock", "pesan", "order", "beli", "procurement"]):
            restock_count = action_dist.get("RESTOCKING", 0)
            restock_skus = [s for s in critical_skus if s["action"] == "RESTOCKING"]
            if restock_skus:
                sku_list = "\n".join([f"  • {s['sku_name']}: {s['priority']}" for s in restock_skus[:3]])
                return (
                    f"📦 **{restock_count} SKU** memerlukan restocking saat ini:\n\n"
                    f"{sku_list}\n\n"
                    f"Prioritaskan pemesanan SKU dengan status 'Segera' terlebih dahulu. "
                    f"Pastikan purchase order dikirim sebelum melewati lead time supplier."
                )
            return f"Saat ini **{restock_count} SKU** memerlukan restocking. Cek panel rekomendasi untuk detail lengkap."

        # ── Pattern: Anomali / reject ──
        elif any(k in msg_lower for k in ["anomali", "reject", "hold", "masalah", "problem", "gagal"]):
            anomaly_count = summary.get("anomaly_active", 0)
            severity_dist = summary.get("severity_distribution", {})
            return (
                f"🔍 **Status Anomali Inventaris:**\n\n"
                f"• Total anomali aktif: **{anomaly_count}**\n"
                f"• Critical: **{severity_dist.get('Critical', 0)}** SKU\n"
                f"• High: **{severity_dist.get('High', 0)}** SKU\n"
                f"• Medium: **{severity_dist.get('Medium', 0)}** SKU\n"
                f"• Low: **{severity_dist.get('Low', 0)}** SKU\n\n"
                f"Kunjungi panel 'Active Anomalies' untuk melihat detail dan reasoning trail tiap anomali."
            )

        # ── Pattern: Saran / rekomendasi ──
        elif any(k in msg_lower for k in ["saran", "rekomendasi", "apa yang harus", "tindakan"]):
            return (
                f"🧠 **Rekomendasi Tindakan Prioritas:**\n\n"
                f"1. **SEGERA** — Tangani {action_dist.get('RESTOCKING', 0) + action_dist.get('HOLD', 0)} "
                f"SKU dengan status Restocking/Hold\n"
                f"2. **DALAM 3 HARI** — Review {action_dist.get('REDISTRIBUSI', 0)} SKU "
                f"yang butuh redistribusi\n"
                f"3. **MONITORING** — Pantau {action_dist.get('MONITOR', 0)} SKU secara rutin\n\n"
                f"Cek panel 'AI Decision Recommendation' untuk reasoning trail lengkap dari setiap keputusan AI."
            )

        # ── Default response ──
        else:
            return (
                f"Halo! Saya Inventra AI Assistant. Saya dapat membantu Anda dengan:\n\n"
                f"• 📊 **Ringkasan status inventaris** — cukup tanya 'bagaimana kondisi inventaris hari ini?'\n"
                f"• ⚠️ **Identifikasi risiko** — tanya 'barang apa yang paling berisiko minggu ini?'\n"
                f"• 📦 **Informasi restocking** — tanya 'SKU apa yang perlu dipesan segera?'\n"
                f"• 🔍 **Analisis anomali** — tanya 'anomali apa yang sedang aktif?'\n"
                f"• 💡 **Rekomendasi tindakan** — tanya 'apa yang harus saya lakukan sekarang?'\n\n"
                f"Silakan ajukan pertanyaan Anda!"
            )

    async def generate_daily_briefing(self, inventory_context: Dict) -> str:
        """
        Generate ringkasan harian otomatis untuk operator di awal shift.
        """
        summary = inventory_context.get("dashboard_summary", {})
        critical_skus = summary.get("critical_skus", [])
        action_dist = summary.get("action_distribution", {})
        health_score = summary.get("health_score", 100)

        prompt = (
            f"Buat briefing harian untuk operator shift pagi pabrik. "
            f"Data: {json.dumps(summary, ensure_ascii=False)}. "
            f"Gunakan format ringkas, profesional, dan actionable. "
            f"Highlight SKU yang paling kritis dan tindakan yang harus diambil hari ini."
        )

        result = await self.chat(
            user_message=prompt,
            session_id="daily_briefing",
            inventory_context=inventory_context,
        )
        return result["message"]

    async def explain_decision(self, decision_data: Dict) -> str:
        """
        Jelaskan reasoning di balik keputusan AI dalam bahasa yang mudah dipahami operator.
        """
        prompt = (
            f"Jelaskan keputusan AI berikut kepada operator pabrik non-teknis "
            f"dalam 3-4 kalimat singkat yang mudah dipahami:\n"
            f"SKU: {decision_data.get('sku_name')}\n"
            f"Tindakan: {decision_data.get('recommended_action')}\n"
            f"Confidence: {decision_data.get('confidence_score')}%\n"
            f"Reasoning: {'; '.join(decision_data.get('reasoning_path', []))}"
        )
        result = await self.chat(
            user_message=prompt,
            session_id="explain_decision",
        )
        return result["message"]


# ─────────────────────────────────────────────────────────────
# Singleton global provider
# ─────────────────────────────────────────────────────────────

_provider_instance: Optional[AzureOpenAIProvider] = None


def get_ai_provider() -> AzureOpenAIProvider:
    """Kembalikan singleton AzureOpenAIProvider."""
    global _provider_instance
    if _provider_instance is None:
        _provider_instance = AzureOpenAIProvider()
    return _provider_instance
