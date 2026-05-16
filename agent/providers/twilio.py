"""
agent/providers/twilio.py — Adaptador para Twilio WhatsApp
Generado por AgentKit
"""
import os
import logging
from typing import Optional
from urllib.parse import parse_qs

import httpx

from agent.providers.base import WhatsAppProvider

logger = logging.getLogger("agentkit.twilio")


class TwilioProvider(WhatsAppProvider):
    """
    Adaptador para Twilio WhatsApp.
    Requiere:
      - TWILIO_ACCOUNT_SID
      - TWILIO_AUTH_TOKEN
      - TWILIO_PHONE_NUMBER (ej: "whatsapp:+14155238886")
    """

    def __init__(self):
        self.account_sid = os.environ["TWILIO_ACCOUNT_SID"]
        self.auth_token = os.environ["TWILIO_AUTH_TOKEN"]
        self.from_number = os.environ["TWILIO_PHONE_NUMBER"]
        self.base_url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json"
        self._client = httpx.AsyncClient(
            auth=(self.account_sid, self.auth_token),
            timeout=15.0,
        )
        logger.info("📱 Twilio WhatsApp provider inicializado")

    def parsear_webhook(self, body: dict) -> Optional[dict]:
        """
        Twilio envía el webhook como form data (no JSON).
        Este método espera que FastAPI ya lo haya convertido a dict.
        El número viene como "whatsapp:+521234567890".
        """
        numero_raw = body.get("From", "")
        texto = (body.get("Body") or "").strip()
        if not numero_raw or not texto:
            return None
        # Limpiar el prefijo "whatsapp:+"
        numero = numero_raw.replace("whatsapp:+", "").replace("whatsapp:", "")
        return {"numero": numero, "texto": texto}

    async def enviar_mensaje(self, numero: str, texto: str) -> bool:
        payload = {
            "From": self.from_number,
            "To": f"whatsapp:+{numero}",
            "Body": texto,
        }
        try:
            resp = await self._client.post(self.base_url, data=payload)
            resp.raise_for_status()
            return True
        except httpx.HTTPStatusError as e:
            logger.error(f"Error Twilio: {e.response.status_code} — {e.response.text}")
            return False
        except Exception as e:
            logger.error(f"Error enviando por Twilio: {e}")
            return False
