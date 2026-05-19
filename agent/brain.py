"""
agent/brain.py — El cerebro del agente (Groq AI)
Generado por AgentKit
"""
import os
import yaml
import logging
from pathlib import Path
from groq import AsyncGroq

logger = logging.getLogger("agentkit.brain")

KNOWLEDGE_DIR = Path("knowledge")
CONFIG_DIR = Path("config")

ETAPAS = [
    "Nuevo contacto",
    "En cotización",
    "Pago pendiente",
    "Instalación agendada",
    "Cliente activo",
]


def _load_knowledge() -> str:
    textos = []
    if not KNOWLEDGE_DIR.exists():
        return ""
    for archivo in sorted(KNOWLEDGE_DIR.iterdir()):
        if archivo.suffix in {".txt", ".md", ".yaml", ".yml", ".csv"}:
            try:
                contenido = archivo.read_text(encoding="utf-8")
                textos.append(f"=== {archivo.name} ===\n{contenido}")
            except Exception as e:
                logger.warning(f"No se pudo leer {archivo.name}: {e}")
    return "\n\n".join(textos)


def _load_system_prompt() -> str:
    prompts_path = CONFIG_DIR / "prompts.yaml"
    business_path = CONFIG_DIR / "business.yaml"

    system = ""

    if business_path.exists():
        with open(business_path, encoding="utf-8") as f:
            negocio = yaml.safe_load(f) or {}
        system += f"""Eres {negocio.get('nombre_agente', 'un asistente')} de {negocio.get('nombre_negocio', 'este negocio')}.

SOBRE EL NEGOCIO:
{negocio.get('descripcion', '')}

PROPOSITO DEL AGENTE:
{negocio.get('proposito', 'Ayudar a los clientes con sus preguntas.')}

TONO DE COMUNICACION:
{negocio.get('tono', 'Amigable y profesional.')}

HORARIO DE ATENCION:
{negocio.get('horario', 'Lunes a Viernes 9am a 6pm.')}

"""

    if prompts_path.exists():
        with open(prompts_path, encoding="utf-8") as f:
            prompts = yaml.safe_load(f) or {}
        if prompts.get("instrucciones_extra"):
            system += f"INSTRUCCIONES ADICIONALES:\n{prompts['instrucciones_extra']}\n\n"

    knowledge = _load_knowledge()
    if knowledge:
        system += f"BASE DE CONOCIMIENTO (usa esta informacion para responder):\n\n{knowledge}\n\n"

    system += """REGLAS DE FORMATO — OBLIGATORIAS:
- MAXIMO 3 lineas por respuesta. Si puedes decirlo en 2, mejor.
- NUNCA escribas parrafos largos. WhatsApp no es un correo.
- SIEMPRE termina con una pregunta o accion concreta para el cliente.
- No uses listas con guiones a menos que sea precio o cuentas bancarias.
- No uses markdown (no uses **, ##, etc.). Solo texto plano.
- NUNCA repitas lo que el cliente ya sabe.
- NUNCA inventes informacion. Si no sabes algo di: "Dejame verificarlo y te confirmo."
- Responde en el idioma del cliente.
"""
    return system.strip()


class Brain:
    def __init__(self):
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY no encontrada en variables de entorno")
        self.client = AsyncGroq(api_key=api_key)
        self.model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        self.max_tokens = int(os.getenv("MAX_TOKENS", "220"))
        self.system_prompt = _load_system_prompt()
        logger.info(f"Brain inicializado con modelo {self.model}")

    def _prompt_soporte(self) -> str:
        """System prompt para clientes que ya compraron — modo soporte."""
        return self.system_prompt + """

MODO ACTUAL: SOPORTE AL CLIENTE
Este cliente ya adquirio el servicio GPS de LTZ Track. Su trato fue cerrado.
Tu rol ahora es brindarle soporte tecnico y atencion postventa.

COMPORTAMIENTO EN MODO SOPORTE:
- Saluda de forma calida reconociendo que ya es cliente.
- Ayudalo con cualquier duda sobre el uso del GPS, la plataforma o la app.
- Si tiene un problema tecnico, guialo paso a paso.
- Si necesita algo que no puedes resolver, ofrece conectarlo con un tecnico.
- No intentes venderle nada nuevo, ya es cliente activo.
"""

    def _prompt_ventas_retoma(self) -> str:
        """System prompt para clientes que no cerraron — modo persuasion."""
        return self.system_prompt + """

MODO ACTUAL: RETOMA DE VENTA
Este cliente tuvo una conversacion anterior pero no cerro el trato.
Tu objetivo es retomar la conversacion y persuadirlo para cerrar la venta ahora.

COMPORTAMIENTO EN MODO RETOMA:
- Saluda con energia y menciona que es un gusto volver a saber de el.
- Recuerda brevemente el valor del servicio sin repetir todo desde cero.
- Usa urgencia: "Tenemos pocos cupos disponibles esta semana."
- Ofrece agendar directamente: "Te aparto la instalacion ahora mismo."
- Si pide descuento, consulta con supervisor como siempre.
- Meta: cerrar en esta conversacion, no dejar para despues.
"""

    async def responder(self, mensaje: str, historial: list[dict], modo: str = "ventas") -> str:
        try:
            if modo == "soporte":
                system = self._prompt_soporte()
            elif modo == "retoma":
                system = self._prompt_ventas_retoma()
            else:
                system = self.system_prompt

            messages = [{"role": "system", "content": system}]
            for msg in historial:
                messages.append({"role": msg["role"], "content": msg["content"]})
            messages.append({"role": "user", "content": mensaje})

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
            )
            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"Error en Brain: {e}")
            return "Lo siento, tuve un problema tecnico. Intenta de nuevo en un momento."

    async def clasificar_etapa(self, historial: list[dict], mensaje_actual: str) -> str:
        """Analiza la conversación y determina en qué etapa está el cliente."""
        resumen = "\n".join(
            f"{m['role'].upper()}: {m['content']}" for m in historial[-6:]
        )
        resumen += f"\nUSER: {mensaje_actual}"

        prompt = f"""Analiza esta conversacion de WhatsApp sobre venta de GPS vehicular y determina la etapa MAS AVANZADA que ha alcanzado el cliente.

Conversacion:
{resumen}

REGLAS IMPORTANTES:
- Solo sube de etapa si hay evidencia CLARA Y DIRECTA en la conversacion
- Si el cliente solo pregunta precios o caracteristicas = "En cotizacion"
- Si el cliente dice explicitamente que quiere comprar o preguntar como pagar = "Pago pendiente"
- Si el cliente confirmo fecha de instalacion o ya pago = "Instalacion agendada"
- Si menciona que ya tiene el GPS instalado o pregunta como usarlo = "Cliente activo"
- Si hay duda, mantener la etapa mas conservadora

Elige UNA (responde SOLO el nombre exacto):
- Nuevo contacto
- En cotizacion
- Pago pendiente
- Instalacion agendada
- Cliente activo

Etapa:"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=20,
            )
            etapa = response.choices[0].message.content.strip()
            # Validar que sea una etapa válida
            for e in ETAPAS:
                if e.lower() in etapa.lower():
                    return e
            return "Nuevo contacto"
        except Exception as e:
            logger.error(f"Error clasificando etapa: {e}")
            return "Nuevo contacto"
