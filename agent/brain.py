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

    system += """REGLAS IMPORTANTES:
- NUNCA inventes informacion. Solo responde con datos que tengas.
- Si no sabes algo, di: "No tengo esa informacion, dejame conectarte con alguien del equipo."
- Responde siempre en el idioma en que el cliente te escriba.
- Se conciso. Los mensajes de WhatsApp deben ser cortos y directos.
- No uses markdown (no uses **, ##, etc.). Solo texto plano.
- Maximo 3 parrafos cortos por respuesta.
"""
    return system.strip()


class Brain:
    def __init__(self):
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY no encontrada en variables de entorno")
        self.client = AsyncGroq(api_key=api_key)
        self.model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        self.max_tokens = int(os.getenv("MAX_TOKENS", "1024"))
        self.system_prompt = _load_system_prompt()
        logger.info(f"Brain inicializado con modelo {self.model}")

    async def responder(self, mensaje: str, historial: list[dict]) -> str:
        try:
            messages = [{"role": "system", "content": self.system_prompt}]
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
