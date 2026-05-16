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
from agent.notificaciones import notificar_cambio_etapa, notificar_descuento, notificar_interes_compra, enviar_plantilla_pago, notificar_pase_a_humano

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("agentkit")

memory: Memory = None
brain: Brain = None
provider = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global memory, brain, provider
    logger.info("Iniciando AgentKit...")
    memory = Memory()
    await memory.init()
    brain = Brain()
    provider = get_provider()
    logger.info(f"Proveedor activo: {provider.__class__.__name__}")
    yield
    logger.info("Apagando AgentKit...")
    await memory.close()


app = FastAPI(
    title="WhatsApp AgentKit",
    description="Agente de WhatsApp con IA - LTZ Track",
    version="1.0.0",
    lifespan=lifespan,
)


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
    logger.info(f"Mensaje de {numero}: {texto[:80]}")

    # Si el bot está pausado para este cliente, no responder
    if await memory.bot_esta_pausado(numero):
        logger.info(f"Bot pausado para {numero} — mensaje ignorado")
        return JSONResponse({"status": "paused"})

    # Obtener historial
    historial = await memory.get_history(numero)

    texto_lower = texto.lower()

    # Detectar intenciones del cliente
    pide_descuento = any(p in texto_lower for p in ["descuento", "rebaja", "mas barato", "oferta", "promocion", "negociar"])
    quiere_comprar = any(p in texto_lower for p in ["quiero comprar", "me interesa", "quiero adquirir", "como compro", "quiero el gps", "lo quiero", "me lo llevo", "como pago", "quiero pagar", "datos de pago", "numero de cuenta", "donde pago", "transferencia"])
    quiere_pagar = any(p in texto_lower for p in ["como pago", "quiero pagar", "datos de pago", "numero de cuenta", "donde pago", "transferencia", "cuenta bancaria", "deposito"])

    # Generar respuesta
    respuesta = await brain.responder(texto, historial)

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

    # Enviar respuesta por WhatsApp
    await provider.enviar_mensaje(numero, respuesta)
    logger.info(f"Respuesta enviada a {numero}: {respuesta[:80]}")

    return JSONResponse({"status": "ok"})
