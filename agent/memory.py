"""
agent/memory.py — Gestión del historial y etapas de clientes
Generado por AgentKit
"""
import os
import logging
from datetime import datetime
import aiosqlite

logger = logging.getLogger("agentkit.memory")

DB_PATH = os.getenv("DB_PATH", "agentkit.db")
MAX_HISTORY = int(os.getenv("MAX_HISTORY_MESSAGES", "20"))

ETAPAS = [
    "Nuevo contacto",
    "En cotización",
    "Pago pendiente",
    "Instalación agendada",
    "Cliente activo",
]


class Memory:
    def __init__(self):
        self._db: aiosqlite.Connection | None = None

    async def init(self):
        self._db = await aiosqlite.connect(DB_PATH)
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS mensajes (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                numero      TEXT NOT NULL,
                role        TEXT NOT NULL,
                content     TEXT NOT NULL,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_numero ON mensajes (numero, created_at)"
        )
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS clientes (
                numero      TEXT PRIMARY KEY,
                etapa       TEXT NOT NULL DEFAULT 'Nuevo contacto',
                nombre      TEXT,
                bot_pausado INTEGER NOT NULL DEFAULT 0,
                updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await self._db.commit()
        logger.info(f"Base de datos lista: {DB_PATH}")

    async def get_history(self, numero: str) -> list[dict]:
        async with self._db.execute(
            """
            SELECT role, content FROM mensajes
            WHERE numero = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (numero, MAX_HISTORY),
        ) as cursor:
            rows = await cursor.fetchall()
        return [{"role": r[0], "content": r[1]} for r in reversed(rows)]

    async def save_message(self, numero: str, role: str, content: str):
        await self._db.execute(
            "INSERT INTO mensajes (numero, role, content) VALUES (?, ?, ?)",
            (numero, role, content),
        )
        await self._db.commit()

    async def get_etapa(self, numero: str) -> str:
        async with self._db.execute(
            "SELECT etapa FROM clientes WHERE numero = ?", (numero,)
        ) as cursor:
            row = await cursor.fetchone()
        return row[0] if row else "Nuevo contacto"

    async def set_etapa(self, numero: str, etapa: str) -> bool:
        """Actualiza la etapa del cliente solo si avanza. Retorna True si cambió."""
        etapa_actual = await self.get_etapa(numero)
        if etapa_actual == etapa:
            return False

        # Solo avanzar, nunca retroceder
        indice_actual = ETAPAS.index(etapa_actual) if etapa_actual in ETAPAS else 0
        indice_nuevo = ETAPAS.index(etapa) if etapa in ETAPAS else 0
        if indice_nuevo <= indice_actual:
            return False

        await self._db.execute(
            """
            INSERT INTO clientes (numero, etapa, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(numero) DO UPDATE SET etapa=excluded.etapa, updated_at=excluded.updated_at
            """,
            (numero, etapa),
        )
        await self._db.commit()
        logger.info(f"Cliente {numero}: {etapa_actual} -> {etapa}")
        return True

    async def clear_history(self, numero: str):
        await self._db.execute("DELETE FROM mensajes WHERE numero = ?", (numero,))
        await self._db.commit()

    async def get_stats(self) -> dict:
        async with self._db.execute(
            "SELECT COUNT(DISTINCT numero), COUNT(*) FROM mensajes"
        ) as cursor:
            row = await cursor.fetchone()
        return {
            "total_usuarios": row[0],
            "total_mensajes": row[1],
        }

    async def bot_esta_pausado(self, numero: str) -> bool:
        """Verifica si el bot está pausado para este número."""
        async with self._db.execute(
            "SELECT bot_pausado FROM clientes WHERE numero = ?", (numero,)
        ) as cursor:
            row = await cursor.fetchone()
        return bool(row[0]) if row else False

    async def pausar_bot(self, numero: str):
        """Pausa el bot para este número — un humano tomará el control."""
        await self._db.execute(
            """
            INSERT INTO clientes (numero, etapa, bot_pausado, updated_at)
            VALUES (?, 'Instalación agendada', 1, CURRENT_TIMESTAMP)
            ON CONFLICT(numero) DO UPDATE SET bot_pausado=1, updated_at=CURRENT_TIMESTAMP
            """,
            (numero,),
        )
        await self._db.commit()
        logger.info(f"Bot pausado para {numero} — control pasado a humano")

    async def reactivar_bot(self, numero: str):
        """Reactiva el bot para este número."""
        await self._db.execute(
            "UPDATE clientes SET bot_pausado=0, updated_at=CURRENT_TIMESTAMP WHERE numero=?",
            (numero,),
        )
        await self._db.commit()
        logger.info(f"Bot reactivado para {numero}")

    async def close(self):
        if self._db:
            await self._db.close()
