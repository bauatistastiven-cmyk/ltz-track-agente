"""
agent/providers/waha.py — Adaptador para WAHA (WhatsApp HTTP API)
"""
import os
import logging
from typing import Optional
import httpx

from agent.providers.base import WhatsAppProvider

logger = logging.getLogger("agentkit.waha")


class WahaProvider(WhatsAppProvider):
    def __init__(self):
        self.api_url = os.environ["WAHA_API_URL"].rstrip("/")
        self.api_key = os.getenv("WAHA_API_KEY", "")
        self.session = os.getenv("WAHA_SESSION", "default")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-Api-Key"] = self.api_key
        self._client = httpx.AsyncClient(headers=headers, timeout=15.0)
        logger.info(f"WAHA provider inicializado — sesion: {self.session}")

    def parsear_webhook(self, body: dict) -> Optional[dict]:
        """
        WAHA webhook payload:
        {
          "event": "message",
          "session": "default",
          "payload": {
            "from": "521234567890@c.us",
            "fromMe": false,
            "body": "Hola",
            "hasMedia": false
          }
        }
        """
        event = body.get("event", "")
        if event not in ("message", "message.any"):
            return None

        payload = body.get("payload", {})

        if payload.get("fromMe"):
            numero_raw = payload.get("from", "")
            numero = numero_raw.split("@")[0]
            if numero:
                return {"numero": numero, "texto": "", "es_propietario": True}
            return None

        texto = payload.get("body", "").strip()
        if not texto or payload.get("hasMedia"):
            return None

        numero_raw = payload.get("from", "")
        numero = numero_raw.split("@")[0]

        return {"numero": numero, "texto": texto}

    async def enviar_mensaje(self, numero: str, texto: str) -> bool:
        url = f"{self.api_url}/api/sendText"
        payload = {
            "chatId": f"{numero}@c.us",
            "text": texto,
            "session": self.session,
        }
        try:
            resp = await self._client.post(url, json=payload)
            resp.raise_for_status()
            return True
        except httpx.HTTPStatusError as e:
            logger.error(f"Error HTTP WAHA: {e.response.status_code} - {e.response.text}")
            return False
        except Exception as e:
            logger.error(f"Error enviando mensaje por WAHA: {e}")
            return False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self._client.aclose()
