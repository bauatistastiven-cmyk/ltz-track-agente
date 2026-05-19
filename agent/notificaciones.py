"""
agent/notificaciones.py — Notificaciones WhatsApp al administrador via Green API
"""
import os
import logging
import httpx

logger = logging.getLogger("agentkit.notificaciones")

GREENAPI_INSTANCE_ID = os.getenv("GREENAPI_INSTANCE_ID", "")
GREENAPI_API_TOKEN = os.getenv("GREENAPI_API_TOKEN", "")
GREENAPI_API_URL = os.getenv("GREENAPI_API_URL", "https://api.green-api.com").rstrip("/")
ADMIN_NUMERO = os.getenv("ADMIN_WHATSAPP", "")


async def _enviar_al_admin(mensaje: str):
    if not ADMIN_NUMERO or not GREENAPI_INSTANCE_ID or not GREENAPI_API_TOKEN:
        logger.warning("ADMIN_WHATSAPP, GREENAPI_INSTANCE_ID o GREENAPI_API_TOKEN no configurado")
        return
    url = f"{GREENAPI_API_URL}/waInstance{GREENAPI_INSTANCE_ID}/sendMessage/{GREENAPI_API_TOKEN}"
    payload = {
        "chatId": f"{ADMIN_NUMERO}@c.us",
        "message": mensaje,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
    except Exception as e:
        logger.error(f"Error enviando notificacion al admin: {e}")


async def notificar_cambio_etapa(numero_cliente: str, etapa_anterior: str, etapa_nueva: str):
    mensaje = (
        f"LTZ Track - Actualizacion de cliente\n\n"
        f"Numero: {numero_cliente}\n"
        f"Etapa anterior: {etapa_anterior}\n"
        f"Etapa nueva: {etapa_nueva}"
    )
    await _enviar_al_admin(mensaje)
    logger.info(f"Notificacion enviada al admin: {numero_cliente} -> {etapa_nueva}")


async def notificar_descuento(numero_cliente: str):
    mensaje = (
        f"LTZ Track - Solicitud de descuento\n\n"
        f"El cliente {numero_cliente} esta pidiendo un descuento.\n"
        f"Contactalo para cerrar la venta."
    )
    await _enviar_al_admin(mensaje)
    logger.info(f"Notificacion de descuento enviada al admin para cliente {numero_cliente}")


async def notificar_interes_compra(numero_cliente: str):
    mensaje = (
        f"LTZ Track - Cliente listo para comprar\n\n"
        f"El cliente {numero_cliente} esta interesado en adquirir el GPS.\n"
        f"Este es el momento de cerrar la venta."
    )
    await _enviar_al_admin(mensaje)
    logger.info(f"Notificacion de interes de compra enviada al admin para cliente {numero_cliente}")


async def notificar_pase_a_humano(numero_cliente: str):
    mensaje = (
        f"LTZ Track - Cliente listo para cerrar\n\n"
        f"El cliente {numero_cliente} esta listo para hablar con un representante.\n"
        f"El bot ha sido pausado. Tu tomas el control de este chat."
    )
    await _enviar_al_admin(mensaje)
    logger.info(f"Notificacion de pase a humano enviada para cliente {numero_cliente}")


PLANTILLA_PAGO = """LTZ Track - Informacion de Pago

Para completar tu instalacion de GPS, realiza el pago de *RD$ 7,490* a cualquiera de estas cuentas:

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


async def enviar_plantilla_pago(numero_cliente: str):
    if not GREENAPI_INSTANCE_ID or not GREENAPI_API_TOKEN:
        logger.warning("GREENAPI_INSTANCE_ID o GREENAPI_API_TOKEN no configurado")
        return
    url = f"{GREENAPI_API_URL}/waInstance{GREENAPI_INSTANCE_ID}/sendMessage/{GREENAPI_API_TOKEN}"
    payload = {
        "chatId": f"{numero_cliente}@c.us",
        "message": PLANTILLA_PAGO,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            logger.info(f"Plantilla de pago enviada al cliente {numero_cliente}")
    except Exception as e:
        logger.error(f"Error enviando plantilla de pago: {e}")
