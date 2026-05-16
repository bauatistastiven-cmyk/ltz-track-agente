"""
agent/providers/base.py — Interfaz base para proveedores de WhatsApp
Generado por AgentKit
"""
from abc import ABC, abstractmethod
from typing import Optional


class WhatsAppProvider(ABC):
    """
    Interfaz común que todos los proveedores de WhatsApp deben implementar.
    Esto permite cambiar de proveedor (Whapi, Meta, Twilio) sin modificar
    el resto del código.
    """

    @abstractmethod
    def parsear_webhook(self, body: dict) -> Optional[dict]:
        """
        Parsea el payload del webhook y extrae el mensaje.

        Returns:
            dict con {'numero': str, 'texto': str} si es un mensaje de texto.
            None si el evento debe ignorarse (ej: estado de entrega, reacción).
        """
        ...

    @abstractmethod
    async def enviar_mensaje(self, numero: str, texto: str) -> bool:
        """
        Envía un mensaje de texto a un número de WhatsApp.

        Args:
            numero: Número en formato internacional (ej: "521234567890")
            texto: Mensaje a enviar

        Returns:
            True si se envió correctamente, False en caso de error.
        """
        ...

    def verify_webhook(self, params: dict) -> Optional[str]:
        """
        Verifica el webhook (solo necesario para Meta Cloud API).
        Retorna el hub.challenge si la verificación es correcta, None si no aplica.
        """
        return None
