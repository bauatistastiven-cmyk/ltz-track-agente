"""
agent/providers/greenapi.py — Adaptador para Green API (WhatsApp)
"""
import os
import logging
from typing import Optional
import httpx

from agent.providers.base import WhatsAppProvider

logger = logging.getLogger("agentkit.greenapi")


class GreenApiProvider(WhatsAppProvider):
    def __init__(self):
        self.instance_id = os.environ["GREENAPI_INSTANCE_ID"]
        self.api_token = os.environ["GREENAPI_API_TOKEN"]
        self.api_url = os.getenv("GREENAPI_API_URL", "https://api.green-api.com").rstrip("/")
        self._client = httpx.AsyncClient(timeout=15.0)
        logger.info(f"Green API provider inicializado — instancia: {self.instance_id}")

    def parsear_webhook(self, body: dict) -> Optional[dict]:
        """
        Green API webhook payload:
        {
          "typeWebhook": "incomingMessageReceived",
          "senderData": {
            "chatId": "521234567890@c.us",
            "sender": "521234567890@c.us"
          },
          "messageData": {
            "typeMessage": "textMessage",
            "textMessageData": {
              "textMessage": "Hola"
            }
          }
        }
        Mensajes salientes del propietario:
        {
          "typeWebhook": "outgoingMessageReceived",
          ...
        }
        """
        tipo = body.get("typeWebhook", "")

        # Mensaje saliente del propietario (escrito manualmente)
        if tipo == "outgoingMessageReceived":
            sender_data = body.get("senderData", {})
            chat_id = sender_data.get("chatId", "")
            numero = chat_id.split("@")[0]
            if numero:
                return {"numero": numero, "texto": "", "es_propietario": True}
            return None

        # Solo procesar mensajes entrantes de texto
        if tipo != "incomingMessageReceived":
            return None

        message_data = body.get("messageData", {})
        tipo_mensaje = message_data.get("typeMessage", "")

        # Solo mensajes de texto
        if tipo_mensaje != "textMessage":
            return None

        texto = message_data.get("textMessageData", {}).get("textMessage", "").strip()
        if not texto:
            return None

        sender_data = body.get("senderData", {})
        chat_id = sender_data.get("chatId", "")
        numero = chat_id.split("@")[0]

        return {"numero": numero, "texto": texto}

    async def enviar_mensaje(self, numero: str, texto: str) -> bool:
        url = f"{self.api_url}/waInstance{self.instance_id}/sendMessage/{self.api_token}"
        payload = {
            "chatId": f"{numero}@c.us",
            "message": texto,
        }
        try:
            resp = await self._client.post(url, json=payload)
            resp.raise_for_status()
            return True
        except httpx.HTTPStatusError as e:
            logger.error(f"Error HTTP Green API: {e.response.status_code} - {e.response.text}")
            return False
        except Exception as e:
            logger.error(f"Error enviando mensaje por Green API: {e}")
            return False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self._client.aclose()
