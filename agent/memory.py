"""
agent/memory.py — Gestión del historial de conversaciones
Generado por AgentKit
"""
import os
import logging
from datetime import datetime
import aiosqlite

logger = logging.getLogger("agentkit.memory")

DB_PATH = os.getenv("DB_PATH", "agentkit.db")
MAX_HISTORY = int(os.getenv("MAX_HISTORY_MESSAGES", "20"))


class Memory:
    def __init__(self):
        self._db: aiosqlite.Connection | None = None

    async def init(self):
        """Inicializa la base de datos y crea tablas si no existen."""
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
        await self._db.commit()
        logger.info(f"💾 Base de datos lista: {DB_PATH}")

    async def get_history(self, numero: str) -> list[dict]:
        """Devuelve el historial reciente de un número (últimos MAX_HISTORY mensajes)."""
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

        # Invertir para orden cronológico
        return [{"role": r[0], "content": r[1]} for r in reversed(rows)]

    async def save_message(self, numero: str, role: str, content: str):
        """Guarda un mensaje en el historial."""
        await self._db.execute(
            "INSERT INTO mensajes (numero, role, content) VALUES (?, ?, ?)",
            (numero, role, content),
        )
        await self._db.commit()

    async def clear_history(self, numero: str):
        """Borra el historial de un número (útil para tests)."""
        await self._db.execute("DELETE FROM mensajes WHERE numero = ?", (numero,))
        await self._db.commit()

    async def get_stats(self) -> dict:
        """Estadísticas básicas de uso."""
        async with self._db.execute(
            "SELECT COUNT(DISTINCT numero), COUNT(*) FROM mensajes"
        ) as cursor:
            row = await cursor.fetchone()
        return {
            "total_usuarios": row[0],
            "total_mensajes": row[1],
        }

    async def close(self):
        if self._db:
            await self._db.close()
