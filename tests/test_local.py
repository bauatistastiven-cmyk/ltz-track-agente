"""
tests/test_local.py — Simulador de chat en la terminal
Úsalo para probar tu agente SIN necesitar WhatsApp.

Uso:
    python tests/test_local.py

Comandos especiales:
    /reset   — Borra el historial de la conversación
    /stats   — Muestra estadísticas
    /quit    — Salir
"""
import asyncio
import os
import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Cargar variables de entorno
from dotenv import load_dotenv
load_dotenv()

from agent.brain import Brain
from agent.memory import Memory

NUMERO_TEST = "test_local_000"
BOLD = "\033[1m"
GREEN = "\033[92m"
BLUE = "\033[94m"
YELLOW = "\033[93m"
RESET = "\033[0m"
CYAN = "\033[96m"


async def main():
    sep = "-" * 55
    print(f"\n{BOLD}{sep}{RESET}")
    print(f"{BOLD}  AgentKit - Simulador de Chat Local{RESET}")
    print(f"{BOLD}{sep}{RESET}")
    print(f"  Comandos: {CYAN}/reset{RESET} | {CYAN}/stats{RESET} | {CYAN}/quit{RESET}")
    print(f"{sep}\n")

    memory = Memory()
    await memory.init()
    brain = Brain()

    print(f"{GREEN}Agente listo. Escribe tu primer mensaje...{RESET}\n")

    while True:
        try:
            user_input = input(f"{BOLD}{BLUE}Tú:{RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{YELLOW}Hasta luego!{RESET}\n")
            break

        if not user_input:
            continue

        # Comandos especiales
        if user_input.lower() == "/quit":
            print(f"\n{YELLOW}Hasta luego!{RESET}\n")
            break
        elif user_input.lower() == "/reset":
            await memory.clear_history(NUMERO_TEST)
            print(f"{YELLOW}Historial borrado.{RESET}\n")
            continue
        elif user_input.lower() == "/stats":
            stats = await memory.get_stats()
            print(f"{CYAN}Usuarios: {stats['total_usuarios']} | Mensajes: {stats['total_mensajes']}{RESET}\n")
            continue

        # Obtener historial y generar respuesta
        historial = await memory.get_history(NUMERO_TEST)
        print(f"{YELLOW}⏳ Pensando...{RESET}", end="\r")

        respuesta = await brain.responder(user_input, historial)

        # Guardar en memoria
        await memory.save_message(NUMERO_TEST, "user", user_input)
        await memory.save_message(NUMERO_TEST, "assistant", respuesta)

        print(f"         ", end="\r")  # Limpiar "Pensando..."
        print(f"{BOLD}Agente:{RESET} {GREEN}{respuesta}{RESET}\n")

    await memory.close()


if __name__ == "__main__":
    asyncio.run(main())
