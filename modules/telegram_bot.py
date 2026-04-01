"""
Módulo de Telegram - Envío de alertas
"""
import os
import requests
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
        self.threshold = int(os.getenv("TELEGRAM_ALERT_THRESHOLD", "80"))
        self.sent_ids = set()
        self.enabled = bool(self.token and self.chat_id)
        
        if self.enabled:
            logger.info("Telegram bot inicializado")
        else:
            logger.warning("Telegram no configurado")
    
    def send_alert(self, row):
        if not self.enabled:
            return False
        
        uid = row.get("id", row.get("title", ""))[:64]
        if uid in self.sent_ids:
            return False
        
        nivel = row.get("risk", "Desconocido")
        emoji = {"Crítico": "🔴", "Alto": "🟠", "Medio": "🟡"}.get(nivel, "⚪")
        
        msg = (
            f"{emoji} *ALERTA CIBER — {nivel.upper()}*\n\n"
            f"📋 {row.get('title', 'Sin título')[:200]}\n\n"
            f"🏢 Fuente: `{row.get('origin', '?')}`\n"
            f"🌍 Región: `{row.get('region', '?')}`\n"
            f"🕐 {datetime.now().strftime('%d/%m %H:%M')}\n"
        )
        
        url = row.get("link", "")
        if url:
            msg += f"\n[Leer más]({url})"
        
        try:
            resp = requests.post(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                json={"chat_id": self.chat_id, "text": msg, "parse_mode": "Markdown"},
                timeout=5
            )
            if resp.status_code == 200:
                self.sent_ids.add(uid)
                logger.info(f"Alerta enviada: {nivel}")
                return True
        except Exception as e:
            logger.error(f"Error Telegram: {e}")
        return False
    
    def dispatch_alerts(self, df):
        if not self.enabled or "risk" not in df.columns:
            return 0
        
        sent = 0
        criticos = df[df["risk"] == "Crítico"].head(5)
        for _, row in criticos.iterrows():
            if self.send_alert(row.to_dict()):
                sent += 1
        return sent
