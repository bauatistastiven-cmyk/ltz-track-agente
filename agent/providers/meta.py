"""
agent/providers/meta.py — Adaptador para Meta Cloud API (WhatsApp Business)
Generado por AgentKit
"""
import os
import logging
from typing import Optional

import httpx

from agent.providers.base import WhatsAppProvider

logger = logging.getLogger("agentkit.meta")

META_API_VERSION = "v19.0"
META_BASE_URL = f"https://graph.facebook.com/{META_API_VERSION}"


class MetaProvider(WhatsAppProvider):
    """
    Adaptador para Meta Cloud API (WhatsApp Business Platform).
    Requiere:
      - META_ACCESS_TOKEN
      - META_PHONE_NUMBER_ID
      - META_VERIFY_TOKEN (para verificación del webhook)
    """

    def __init__(self):
        self.access_token = os.environ["META_ACCESS_TOKEN"]
        self.phone_number_id = os.environ["META_PHONE_NUMBER_ID"]
        self.verify_token = os.getenv("META_VERIFY_TOKEN", "agentkit_verify")
        self._client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            },
            timeout=15.0,
        )
        logger.info("📱 Meta Cloud API provider inicializado")

    def verify_webhook(self, params: dict) -> Optional[str]:
        """Meta verifica el webhook con un GET que incluye hub.challenge."""
        mode = params.get("hub.mode")
        token = params.get("hub.verify_token")
        challenge = params.get("hub.challenge")
        if mode == "subscribe" and token == self.verify_token:
            logger.info("✅ Webhook de Meta verificado correctamente")
            return challenge
        logger.warning("⚠️ Intento de verificación fallido — token incorrecto")
        return None

    def parsear_webhook(self, body: dict) -> Optional[dict]:
        """
        Meta envía webhooks con esta estructura:
        {
          "entry": [{
            "changes": [{
              "value": {
                "messages": [{
                  "from": "521234567890",
                  "type": "text",
                  "text": {"body": "Hola"}
                }]
              }
            }]
          }]
        }
        """
        try:
            entry = body.get("entry", [])[0]
            change = entry.get("changes", [])[0]
            value = change.get("value", {})
            mensajes = value.get("messages", [])
            if not mensajes:
                return None
            msg = mensajes[0]
            if msg.get("type") != "text":
                return None
            numero = msg.get("from", "")
            texto = msg.get("text", {}).get("body", "").strip()
            if not texto:
                return None
            return {"numero": numero, "texto": texto}
        except (IndexError, KeyError, TypeError):
            return None

    async def enviar_plantilla(self, numero: str, nombre_plantilla: str, parametros: list[str]) -> bool:
        """
        Envía una plantilla aprobada por Meta (obligatorio para escribirle primero a un cliente).
        Los parametros reemplazan {{1}}, {{2}}... del cuerpo de la plantilla.
        Idioma configurable con META_TEMPLATE_LANG (por defecto 'es').
        """
        url = f"{META_BASE_URL}/{self.phone_number_id}/messages"
        template: dict = {
            "name": nombre_plantilla,
            "language": {"code": os.getenv("META_TEMPLATE_LANG", "es")},
        }
        n_params = int(os.getenv("META_TEMPLATE_PARAMS", str(len(parametros))))
        if n_params > 0:
            template["components"] = [{
                "type": "body",
                "parameters": [{"type": "text", "text": p or "-"} for p in parametros[:n_params]],
            }]
        payload = {"messaging_product": "whatsapp", "to": numero, "type": "template", "template": template}
        try:
            resp = await self._client.post(url, json=payload)
            resp.raise_for_status()
            return True
        except httpx.HTTPStatusError as e:
            logger.error(f"Error Meta plantilla: {e.response.status_code} — {e.response.text}")
            return False
        except Exception as e:
            logger.error(f"Error enviando plantilla por Meta: {e}")
            return False

    async def enviar_mensaje(self, numero: str, texto: str) -> bool:
        url = f"{META_BASE_URL}/{self.phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": numero,
            "type": "text",
            "text": {"body": texto},
        }
        try:
            resp = await self._client.post(url, json=payload)
            resp.raise_for_status()
            return True
        except httpx.HTTPStatusError as e:
            logger.error(f"Error Meta API: {e.response.status_code} — {e.response.text}")
            return False
        except Exception as e:
            logger.error(f"Error enviando por Meta: {e}")
            return False
