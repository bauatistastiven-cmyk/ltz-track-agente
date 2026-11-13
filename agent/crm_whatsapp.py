"""
agent/crm_whatsapp.py — Funciones para administrar WhatsApp desde el CRM

Endpoints:
  GET /crm/api/whatsapp/estado — estado de la conexión
  POST /crm/api/whatsapp/enviar — enviar mensaje manual
  GET /crm/api/whatsapp/numeros — números configurados
"""
import os
import logging
from fastapi import APIRouter, Depends, Form, HTTPException

logger = logging.getLogger("agentkit.crm.whatsapp")

router = APIRouter(prefix="/crm/api/whatsapp")
_crm = None

def configurar(crm):
    global _crm
    _crm = crm

def _crm_listo():
    if _crm is None:
        raise HTTPException(503, "CRM no iniciado")
    return _crm

@router.get("/estado")
async def estado_whatsapp():
    """Estado de la conexión WhatsApp."""
    crm = _crm_listo()
    proveedor = crm.provider.__class__.__name__.replace("Provider", "")
    conectado = True
    numero = None
    
    if hasattr(crm.provider, 'phone_number_id'):
        numero = os.getenv("META_PHONE_NUMBER_ID", "").replace("_", " ")
    elif hasattr(crm.provider, 'instance_id'):
        numero = os.getenv("GREENAPI_INSTANCE_ID", "").replace("_", " ")
    elif hasattr(crm.provider, 'api_token'):
        numero = os.getenv("WHAPI_TOKEN", "")[:10] + "..."
    
    return {
        "proveedor": proveedor,
        "conectado": conectado,
        "numero": numero or "No configurado",
        "horario": f"{os.getenv('CRM_HORA_INICIO', '9')}:00 - {os.getenv('CRM_HORA_FIN', '19')}:00",
    }

@router.post("/enviar")
async def enviar_mensaje(numero: str = Form(...), texto: str = Form(...)):
    """Envía un mensaje manual desde el CRM (de un humano, no del bot)."""
    crm = _crm_listo()
    
    if not numero or not texto:
        raise HTTPException(400, "Número y texto requeridos")
    
    texto = texto.strip()
    if len(texto) > 4000:
        raise HTTPException(400, "Mensaje muy largo (máximo 4000 caracteres)")
    
    try:
        ok = await crm.provider.enviar_mensaje(numero, texto)
        if not ok:
            raise Exception("El proveedor no envió el mensaje")
        
        # Guardar como si fuera del propietario (para que el bot no intente responder)
        await crm.memory.save_message(numero, "propietario", texto)
        logger.info(f"Mensaje manual enviado a {numero}: {texto[:80]}")
        
        return {"ok": True, "mensaje": "Mensaje enviado"}
    except Exception as e:
        logger.error(f"Error enviando mensaje manual: {e}")
        raise HTTPException(500, f"Error: {str(e)}")

@router.get("/numeros-admin")
async def numeros_admin():
    """Números configurados como administrador."""
    return {
        "admin": os.getenv("ADMIN_WHATSAPP", ""),
        "test": "Para pruebas: envía 'hola' al número del agente",
    }
