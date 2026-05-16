"""
agent/providers/whapi.py — Adaptador para Whapi.cloud
Generado por AgentKit
"""
import os
import logging
from typing import Optional

import httpx

from agent.providers.base import WhatsAppProvider

logger = logging.getLogger("agentkit.whapi")

WHAPI_BASE_URL = "https://gate.whapi.cloud"


class WhapiProvider(WhatsAppProvider):
    """
    Adaptador para Whapi.cloud.
    Requiere: WHAPI_TOKEN en variables de entorno.
    """

    def __init__(self):
        self.token = os.environ["WHAPI_TOKEN"]
        self.channel_id = os.getenv("WHAPI_CHANNEL_ID", "")
        self.base_url = WHAPI_BASE_URL
        self._client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
            timeout=15.0,
        )
        logger.info("📱 Whapi.cloud provider inicializado")

    def parsear_webhook(self, body: dict) -> Optional[dict]:
        """
        Whapi envía webhooks con esta estructura:
        {
          "messages": [
            {
              "id": "...",
              "type": "text",
              "from": "521234567890@s.whatsapp.net",
              "text": {"body": "Hola"},
              "from_me": false
            }
          ]
        }
        """
        mensajes = body.get("messages", [])
        if not mensajes:
            return None

        msg = mensajes[0]

        # Ignorar mensajes enviados por el propio bot
        if msg.get("from_me"):
            return None

        # Solo procesar mensajes de texto
        if msg.get("type") != "text":
            logger.debug(f"Tipo de mensaje ignorado: {msg.get('type')}")
            return None

        texto = msg.get("text", {}).get("body", "").strip()
        if not texto:
            return None

        # El número viene como "521234567890@s.whatsapp.net"
        numero_raw = msg.get("from", "")
        numero = numero_raw.split("@")[0]

        return {"numero": numero, "texto": texto}

    async def enviar_mensaje(self, numero: str, texto: str) -> bool:
        """
        Envía un mensaje de texto vía Whapi.cloud.
        El número debe estar en formato internacional sin "+": "521234567890"
        """
        # Whapi acepta el número como "521234567890@s.whatsapp.net" o solo el número
        url = f"{self.base_url}/messages/text"
        payload = {
            "to": f"{numero}@s.whatsapp.net",
            "body": texto,
        }
        if self.channel_id:
            payload["channel_id"] = self.channel_id

        try:
            resp = await self._client.post(url, json=payload)
            resp.raise_for_status()
            logger.debug(f"Whapi respuesta: {resp.status_code}")
            return True
        except httpx.HTTPStatusError as e:
            logger.error(f"Error HTTP al enviar mensaje: {e.response.status_code} — {e.response.text}")
            return False
        except Exception as e:
            logger.error(f"Error enviando mensaje por Whapi: {e}")
            return False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self._client.aclose()
