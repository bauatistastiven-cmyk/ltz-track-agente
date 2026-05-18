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


async def _enviar_al_admin(mensaje: str):
    if not ADMIN_NUMERO or not WHAPI_TOKEN:
        logger.warning("ADMIN_WHATSAPP o WHAPI_TOKEN no configurado, omitiendo notificacion")
        return
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
    except Exception as e:
        logger.error(f"Error enviando notificacion al admin: {e}")


async def notificar_cambio_etapa(numero_cliente: str, etapa_anterior: str, etapa_nueva: str):
    """Envía un mensaje WhatsApp al administrador cuando un cliente cambia de etapa."""
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

    await _enviar_al_admin(mensaje)
    logger.info(f"Notificacion enviada al admin: {numero_cliente} -> {etapa_nueva}")


async def notificar_descuento(numero_cliente: str):
    """Notifica al admin cuando un cliente pide descuento."""
    mensaje = (
        f"LTZ Track - Solicitud de descuento\n\n"
        f"El cliente {numero_cliente} esta pidiendo un descuento.\n"
        f"Contactalo para cerrar la venta."
    )
    await _enviar_al_admin(mensaje)
    logger.info(f"Notificacion de descuento enviada al admin para cliente {numero_cliente}")


async def notificar_interes_compra(numero_cliente: str):
    """Notifica al admin cuando un cliente muestra interes en comprar."""
    mensaje = (
        f"LTZ Track - Cliente listo para comprar\n\n"
        f"El cliente {numero_cliente} esta interesado en adquirir el GPS.\n"
        f"Este es el momento de cerrar la venta."
    )
    await _enviar_al_admin(mensaje)
    logger.info(f"Notificacion de interes de compra enviada al admin para cliente {numero_cliente}")


PLANTILLA_PAGO = """LTZ Track - Informacion de Pago

Para completar tu instalacion de GPS, realiza el pago de *RD$ 7,499* a cualquiera de estas cuentas:

*Titular:* Stevenson Bautista

Cuentas de Ahorro:
Banco Popular: 722575461
Mio: 4252854456
Banco BHD Leon: 16326440025
Qik: 1003944294

Cuenta Corriente:
Banreserva: 9607484706

Una vez realizado el pago, envianos el comprobante por este mismo chat y un asesor confirmara tu cita de instalacion.

Gracias por confiar en LTZ Track."""


async def notificar_pase_a_humano(numero_cliente: str):
    """Notifica al admin que debe tomar el control del chat."""
    mensaje = (
        f"LTZ Track - Cliente listo para cerrar\n\n"
        f"El cliente {numero_cliente} esta listo para hablar con un representante.\n"
        f"El bot ha sido pausado. Tu tomas el control de este chat."
    )
    await _enviar_al_admin(mensaje)
    logger.info(f"Notificacion de pase a humano enviada para cliente {numero_cliente}")


async def enviar_plantilla_pago(numero_cliente: str):
    """Envia la plantilla de pago directamente al cliente."""
    if not WHAPI_TOKEN:
        logger.warning("WHAPI_TOKEN no configurado")
        return
    url = f"{WHAPI_BASE_URL}/messages/text"
    headers = {
        "Authorization": f"Bearer {WHAPI_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "to": f"{numero_cliente}@s.whatsapp.net",
        "body": PLANTILLA_PAGO,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            logger.info(f"Plantilla de pago enviada al cliente {numero_cliente}")
    except Exception as e:
        logger.error(f"Error enviando plantilla de pago: {e}")
