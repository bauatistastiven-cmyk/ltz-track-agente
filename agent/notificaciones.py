"""
agent/notificaciones.py — Notificaciones WhatsApp al administrador
"""
import os
import logging
import httpx

logger = logging.getLogger("agentkit.notificaciones")

WHAPI_BASE_URL = "https://gate.whapi.cloud"
ADMIN_NUMERO = os.getenv("ADMIN_WHATSAPP", "")
WHAPI_TOKEN = os.getenv("WHAPI_TOKEN", "")


async def notificar_cambio_etapa(numero_cliente: str, etapa_anterior: str, etapa_nueva: str):
    """Envía un mensaje WhatsApp al administrador cuando un cliente cambia de etapa."""
    if not ADMIN_NUMERO or not WHAPI_TOKEN:
        logger.warning("ADMIN_WHATSAPP o WHAPI_TOKEN no configurado, omitiendo notificacion")
        return

    mensaje = (
        f"LTZ Track - Actualizacion de cliente\n\n"
        f"Numero: {numero_cliente}\n"
        f"Etapa anterior: {etapa_anterior}\n"
        f"Etapa nueva: {etapa_nueva}"
    )

    url = f"{WHAPI_BASE_URL}/messages/text"
    headers = {
        "Authorization": f"Bearer {WHAPI_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "to": f"{ADMIN_NUMERO}@s.whatsapp.net",
        "body": mensaje,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            logger.info(f"Notificacion enviada al admin: {numero_cliente} -> {etapa_nueva}")
    except Exception as e:
        logger.error(f"Error enviando notificacion al admin: {e}")
