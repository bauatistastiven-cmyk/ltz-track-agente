"""
agent/providers/evolution.py — Adaptador para Evolution API
"""
import os
import logging
from typing import Optional
import httpx

from agent.providers.base import WhatsAppProvider

logger = logging.getLogger("agentkit.evolution")


class EvolutionProvider(WhatsAppProvider):
    def __init__(self):
        self.api_url = os.environ["EVOLUTION_API_URL"].rstrip("/")
        self.api_key = os.environ["EVOLUTION_API_KEY"]
        self.instance = os.environ["EVOLUTION_INSTANCE"]
        self._client = httpx.AsyncClient(
            headers={
                "apikey": self.api_key,
                "Content-Type": "application/json",
            },
            timeout=15.0,
        )
        logger.info(f"Evolution API provider inicializado — instancia: {self.instance}")

    def parsear_webhook(self, body: dict) -> Optional[dict]:
        """
        Evolution API webhook format:
        {
          "event": "messages.upsert",
          "data": {
            "key": {"remoteJid": "521234567890@s.whatsapp.net", "fromMe": false},
            "message": {"conversation": "Hola"},
            "messageType": "conversation"
          }
        }
        """
        event = body.get("event", "")
        if event != "messages.upsert":
            return None

        data = body.get("data", {})
        key = data.get("key", {})

        if key.get("fromMe"):
            return None

        message = data.get("message", {})
        # Texto puede venir en conversation o extendedTextMessage
        texto = (
            message.get("conversation")
            or message.get("extendedTextMessage", {}).get("text")
            or ""
        ).strip()

        if not texto:
            return None

        numero_raw = key.get("remoteJid", "")
        numero = numero_raw.split("@")[0]

        return {"numero": numero, "texto": texto}

    async def enviar_mensaje(self, numero: str, texto: str) -> bool:
        url = f"{self.api_url}/message/sendText/{self.instance}"
        payload = {
            "number": numero,
            "text": texto,
        }
        try:
            resp = await self._client.post(url, json=payload)
            resp.raise_for_status()
            return True
        except httpx.HTTPStatusError as e:
            logger.error(f"Error HTTP Evolution API: {e.response.status_code} - {e.response.text}")
            return False
        except Exception as e:
            logger.error(f"Error enviando mensaje por Evolution API: {e}")
            return False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self._client.aclose()
