# /build-agent — Constructor de agente de WhatsApp

Ejecuta el flujo completo de AgentKit:

1. Verificar el entorno (Python, dependencias)
2. Entrevistar al usuario sobre su negocio (10 preguntas, una por una)
3. Generar config/business.yaml y config/prompts.yaml con sus respuestas
4. Crear el archivo .env con sus API keys
5. Probar el agente con `python tests/test_local.py`
6. (Opcional) Guiar el deploy en Railway

Lee CLAUDE.md para el flujo detallado completo.

Empieza siempre con este mensaje:

"Soy tu asistente de configuración de AgentKit. Voy a ayudarte a construir
tu agente de WhatsApp con IA personalizado para tu negocio. El proceso toma
entre 15 y 30 minutos.

Antes de empezar, déjame verificar que tu entorno esté listo..."

Luego ejecuta la verificación del entorno (Fase 0).
