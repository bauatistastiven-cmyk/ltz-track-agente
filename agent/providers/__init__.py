"""
agent/providers/__init__.py — Selecciona el proveedor de WhatsApp automáticamente
Generado por AgentKit
"""
import os
from agent.providers.base import WhatsAppProvider


def get_provider() -> WhatsAppProvider:
    """
    Devuelve el proveedor configurado en WHATSAPP_PROVIDER.
    Valores válidos: 'whapi' | 'waha' | 'greenapi' | 'evolution' | 'meta' | 'twilio'
    """
    proveedor = os.getenv("WHATSAPP_PROVIDER", "greenapi").lower().strip()

    if proveedor == "whapi":
        from agent.providers.whapi import WhapiProvider
        return WhapiProvider()
    elif proveedor == "waha":
        from agent.providers.waha import WahaProvider
        return WahaProvider()
    elif proveedor == "greenapi":
        from agent.providers.greenapi import GreenApiProvider
        return GreenApiProvider()
    elif proveedor == "evolution":
        from agent.providers.evolution import EvolutionProvider
        return EvolutionProvider()
    elif proveedor == "meta":
        from agent.providers.meta import MetaProvider
        return MetaProvider()
    elif proveedor == "twilio":
        from agent.providers.twilio import TwilioProvider
        return TwilioProvider()
    else:
        raise ValueError(
            f"Proveedor desconocido: '{proveedor}'. "
            f"Opciones válidas: 'whapi', 'waha', 'greenapi', 'evolution', 'meta', 'twilio'"
        )
