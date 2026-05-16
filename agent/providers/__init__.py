"""
agent/providers/__init__.py — Selecciona el proveedor de WhatsApp automáticamente
Generado por AgentKit
"""
import os
from agent.providers.base import WhatsAppProvider


def get_provider() -> WhatsAppProvider:
    """
    Devuelve el proveedor configurado en WHATSAPP_PROVIDER.
    Valores válidos: 'whapi' | 'meta' | 'twilio'
    """
    proveedor = os.getenv("WHATSAPP_PROVIDER", "whapi").lower().strip()

    if proveedor == "whapi":
        from agent.providers.whapi import WhapiProvider
        return WhapiProvider()
    elif proveedor == "meta":
        from agent.providers.meta import MetaProvider
        return MetaProvider()
    elif proveedor == "twilio":
        from agent.providers.twilio import TwilioProvider
        return TwilioProvider()
    else:
        raise ValueError(
            f"Proveedor desconocido: '{proveedor}'. "
            f"Opciones válidas: 'whapi', 'meta', 'twilio'"
        )
