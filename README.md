# AgentKit — WhatsApp AI Agent Builder

Construye tu propio agente de WhatsApp con inteligencia artificial en menos de 30 minutos.
No necesitas saber programar. Claude Code construye todo por ti.

---

## ¿Qué es AgentKit?

AgentKit usa **Claude Code** para generar un agente de WhatsApp completo y personalizado
para tu negocio. Tú solo respondes preguntas. Claude Code se encarga de todo lo demás.

---

## Inicio rápido (3 comandos)

```bash
# 1. Clona el repositorio
git clone https://github.com/Hainrixz/whatsapp-agentkit.git
cd whatsapp-agentkit

# 2. Verifica tu entorno
bash start.sh

# 3. Abre Claude Code y construye tu agente
claude
# Escribe: /build-agent
```

---

## Cómo funciona

```
Un cliente escribe "Hola" por WhatsApp
         │
         ▼
Tu proveedor (Whapi/Meta/Twilio) recibe el mensaje
         │
         ▼
agent/providers/ → Normaliza el mensaje
         │
         ▼
agent/memory.py → Busca historial del cliente
         │
         ▼
agent/brain.py → Envía a Claude AI con contexto completo
         │
         ▼
Claude AI genera una respuesta inteligente
         │
         ▼
agent/providers/ → Envía respuesta por WhatsApp
```

---

## Estructura del proyecto

```
whatsapp-agentkit/
├── agent/
│   ├── main.py           # Servidor FastAPI
│   ├── brain.py          # Conexión con Claude AI
│   ├── memory.py         # Historial SQLite
│   └── providers/
│       ├── base.py       # Interfaz común
│       ├── __init__.py   # Selector de proveedor
│       ├── whapi.py      # Adaptador Whapi.cloud
│       ├── meta.py       # Adaptador Meta Cloud API
│       └── twilio.py     # Adaptador Twilio
├── config/
│   ├── business.yaml     # Datos de tu negocio
│   └── prompts.yaml      # Personalidad del agente
├── knowledge/            # Tus archivos (menú, FAQ, precios...)
├── tests/
│   └── test_local.py     # Simulador de chat en terminal
├── .env.example          # Plantilla de variables de entorno
├── requirements.txt      # Dependencias Python
├── Dockerfile            # Para producción
├── docker-compose.yml    # Orquestación
├── start.sh              # Verificador de entorno
└── CLAUDE.md             # Instrucciones para Claude Code
```

---

## Proveedores de WhatsApp

| Proveedor | Dificultad | Mejor para |
|---|---|---|
| **Whapi.cloud** | ⭐ Fácil | Empezar rápido, pruebas |
| **Meta Cloud API** | ⭐⭐ Media | Producción seria |
| **Twilio** | ⭐⭐ Media | Alta confiabilidad |

**Si no estás seguro, empieza con Whapi.cloud.**

---

## Comandos útiles

```bash
# Probar el agente sin WhatsApp (chat en terminal)
python tests/test_local.py

# Arrancar el servidor localmente
uvicorn agent.main:app --reload --port 8000

# Build Docker para producción
docker compose up --build

# Ver logs del agente
docker compose logs -f agent
```

---

## Requisitos previos

- Python 3.11+
- Claude Code (`npm install -g @anthropic-ai/claude-code`)
- API Key de Anthropic ([platform.anthropic.com](https://platform.anthropic.com))
- Cuenta en Whapi.cloud / Meta / Twilio

---

## Stack técnico

| Componente | Tecnología |
|---|---|
| IA | Claude AI (claude-sonnet-4-20250514) |
| Servidor | FastAPI + Uvicorn |
| Base de datos | SQLite (local) / PostgreSQL (prod) |
| Deploy | Docker + Railway |

---

Creado por **Todo de IA** — [@soyenriquerocha](https://instagram.com/soyenriquerocha)

Licencia MIT — Úsalo como quieras.
