"""
agent/main.py — Servidor web principal del agente de WhatsApp
Generado por AgentKit
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse

from agent.brain import Brain
from agent.memory import Memory
from agent.providers import get_provider
from agent import crm as crm_mod
from agent import crm_whatsapp as wa_mod
from agent.crm import CRM, es_pedido_de_baja
from agent.notificaciones import notificar_cambio_etapa, notificar_descuento, notificar_interes_compra, enviar_plantilla_pago, notificar_pase_a_humano

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("agentkit")

memory: Memory = None
brain: Brain = None
provider = None
crm: CRM = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global memory, brain, provider, crm
    logger.info("Iniciando AgentKit...")
    memory = Memory()
    await memory.init()
    brain = Brain()
    provider = get_provider()
    logger.info(f"Proveedor activo: {provider.__class__.__name__}")
    crm = CRM(memory, brain, provider)
    await crm.init()
    crm_mod.configurar(crm)
    wa_mod.configurar(crm)
    crm.iniciar_envios()
    yield
    logger.info("Apagando AgentKit...")
    await crm.detener_envios()
    await memory.close()


app = FastAPI(
    title="WhatsApp AgentKit",
    description="Agente de WhatsApp con IA - LTZ Track",
    version="1.0.0",
    lifespan=lifespan,
)
app.include_router(crm_mod.router)
app.include_router(wa_mod.router)


@app.get("/")
async def root():
    return {"status": "ok", "message": "AgentKit esta corriendo"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/webhook")
async def verify_webhook(request: Request):
    params = dict(request.query_params)
    result = provider.verify_webhook(params)
    if result is not None:
        return PlainTextResponse(str(result))
    return JSONResponse({"status": "ok"})


@app.post("/webhook")
async def receive_message(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Body invalido")

    mensaje = provider.parsear_webhook(body)
    if not mensaje:
        return JSONResponse({"status": "ignored"})

    numero = mensaje["numero"]
    texto = mensaje["texto"]

    # Si el mensaje es del propietario (enviado manualmente desde el WhatsApp)
    if mensaje.get("es_propietario"):
        if not memory.fue_envio_del_bot(numero):
            # Es el propietario escribiendo manualmente — pausar bot para este chat
            await memory.pausar_bot(numero)
            logger.info(f"Propietario escribio manualmente a {numero} — bot pausado")
        return JSONResponse({"status": "owner_message"})

    logger.info(f"Mensaje de {numero}: {texto[:80]}")

    # CRM: datos del cliente y respuesta a campañas
    contacto = await crm.obtener_contacto(numero)
    if contacto and contacto.get("no_contactar"):
        await memory.save_message(numero, "user", texto)
        logger.info(f"{numero} esta marcado como no contactar — mensaje guardado, sin respuesta")
        return JSONResponse({"status": "no_contactar"})
    if contacto and contacto.get("estado_envio") == "enviado":
        if es_pedido_de_baja(texto):
            await crm.marcar_no_contactar(numero)
            await memory.save_message(numero, "user", texto)
            despedida = "Entendido, no te volveremos a escribir. Disculpa la molestia y que tengas buen dia."
            memory.registrar_envio_bot(numero)
            await provider.enviar_mensaje(numero, despedida)
            await memory.save_message(numero, "assistant", despedida)
            return JSONResponse({"status": "opt_out"})
        await crm.marcar_respondio(numero)

    # Si el bot está pausado, solo reactivar si dice "hola"
    if await memory.bot_esta_pausado(numero):
        if "hola" in texto.lower():
            await memory.reactivar_bot(numero)
            logger.info(f"Bot reactivado para {numero} por nuevo saludo")
        else:
            logger.info(f"Bot pausado para {numero} — mensaje ignorado")
            return JSONResponse({"status": "paused"})

    # Obtener historial
    historial = await memory.get_history(numero)

    texto_lower = texto.lower()

    # Detectar intenciones del cliente
    pide_descuento = any(p in texto_lower for p in ["descuento", "rebaja", "mas barato", "oferta", "promocion", "negociar"])
    quiere_comprar = any(p in texto_lower for p in ["quiero comprar", "me interesa", "quiero adquirir", "como compro", "quiero el gps", "lo quiero", "me lo llevo", "como pago", "quiero pagar", "datos de pago", "numero de cuenta", "donde pago", "transferencia"])
    quiere_pagar = any(p in texto_lower for p in ["como pago", "quiero pagar", "datos de pago", "numero de cuenta", "donde pago", "transferencia", "cuenta bancaria", "deposito"])

    # Determinar modo según si el trato fue cerrado
    cerrado = await memory.trato_cerrado(numero)
    if cerrado:
        modo = "soporte"
    elif "hola" in texto_lower and not historial:
        modo = "ventas"
    elif "hola" in texto_lower and historial:
        modo = "retoma" if not cerrado else "soporte"
    else:
        modo = "ventas"

    # Generar respuesta
    respuesta = await brain.responder(texto, historial, modo=modo, contexto=crm.contexto_para_agente(contacto))

    # Notificar al admin si pidió descuento
    if pide_descuento:
        await notificar_descuento(numero)

    # Notificar al admin si el cliente quiere comprar
    if quiere_comprar:
        await notificar_interes_compra(numero)

    # Enviar plantilla de pago si el cliente pregunta cómo pagar
    if quiere_pagar:
        await enviar_plantilla_pago(numero)

    # Pausar bot si se menciona "representante" en el mensaje del cliente o en la respuesta del bot
    if "representante" in texto_lower or "representante" in respuesta.lower():
        await memory.pausar_bot(numero)
        await notificar_pase_a_humano(numero)

    # Clasificar etapa del cliente
    etapa_nueva = await brain.clasificar_etapa(historial, texto)
    etapa_anterior = await memory.get_etapa(numero)
    cambio = await memory.set_etapa(numero, etapa_nueva)

    # Notificar al admin si cambió de etapa
    if cambio:
        await notificar_cambio_etapa(numero, etapa_anterior, etapa_nueva)

    # Guardar en memoria
    await memory.save_message(numero, "user", texto)
    await memory.save_message(numero, "assistant", respuesta)

    # Registrar que el bot va a enviar mensaje (para distinguirlo del propietario)
    memory.registrar_envio_bot(numero)

    # Enviar respuesta por WhatsApp
    await provider.enviar_mensaje(numero, respuesta)
    logger.info(f"Respuesta enviada a {numero}: {respuesta[:80]}")

    return JSONResponse({"status": "ok"})
