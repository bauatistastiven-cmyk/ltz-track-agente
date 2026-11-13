"""
agent/crm.py — CRM de LTZ Track: listas de clientes, campañas y envío gradual

Qué hace:
  - Importa listas de clientes desde CSV (numero, nombre, vehiculo, notas...)
  - Crea campañas: el agente le escribe primero a cada cliente con un mensaje
    personalizado, despacio y en horario, para cuidar el número.
  - Cuando el cliente responde, el agente conoce sus datos y sigue la venta.
  - Panel web en /crm protegido con usuario y contraseña (CRM_USUARIO / CRM_PASSWORD).
"""
import asyncio
import csv
import io
import logging
import os
import random
import re
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

logger = logging.getLogger("agentkit.crm")

# República Dominicana: UTC-4 todo el año (sin horario de verano)
TZ_RD = timezone(timedelta(hours=-4))

CRM_ACTIVO = os.getenv("CRM_ACTIVO", "true").lower() == "true"
LIMITE_DIARIO = int(os.getenv("CRM_LIMITE_DIARIO", "40"))
PAUSA_MIN_SEG = int(os.getenv("CRM_PAUSA_MIN_SEG", "90"))
PAUSA_MAX_SEG = int(os.getenv("CRM_PAUSA_MAX_SEG", "240"))
HORA_INICIO = int(os.getenv("CRM_HORA_INICIO", "9"))   # 9am RD
HORA_FIN = int(os.getenv("CRM_HORA_FIN", "19"))         # 7pm RD

ESTADOS_ENVIO = ["pendiente", "enviado", "respondio", "error", "omitido", "no_contactar"]

FRASES_BAJA = [
    "no me escriban", "no me escribas", "no me interesa", "no estoy interesado",
    "no estoy interesada", "borrame", "bórrame", "eliminame", "elimíname",
    "sacame de", "sácame de", "stop", "baja", "no gracias", "no, gracias",
]

COLUMNAS_NUMERO = {"numero", "número", "telefono", "teléfono", "celular", "whatsapp", "movil", "móvil", "phone"}
COLUMNAS_NOMBRE = {"nombre", "name", "cliente", "nombre completo"}
COLUMNAS_VEHICULO = {"vehiculo", "vehículo", "carro", "auto", "modelo", "vehicle"}
COLUMNAS_NOTAS = {"notas", "nota", "comentarios", "comentario", "info", "informacion", "información"}


def ahora_rd() -> datetime:
    return datetime.now(TZ_RD)


def normalizar_numero(valor: str) -> str | None:
    """Deja solo dígitos y agrega el 1 a números dominicanos de 10 dígitos."""
    digitos = re.sub(r"\D", "", valor or "")
    if len(digitos) == 10 and digitos[:3] in {"809", "829", "849"}:
        digitos = "1" + digitos
    if len(digitos) < 10 or len(digitos) > 15:
        return None
    return digitos


def es_pedido_de_baja(texto: str) -> bool:
    t = texto.lower().strip(" .!¡¿?")
    return t in {"no", "stop", "baja"} or any(f in t for f in FRASES_BAJA)


# ─────────────────────────────────────────────────────────────────────────────
# Base de datos
# ─────────────────────────────────────────────────────────────────────────────

class CRM:
    def __init__(self, memory, brain, provider):
        self.memory = memory
        self.brain = brain
        self.provider = provider
        self._tarea: asyncio.Task | None = None

    @property
    def db(self):
        return self.memory._db

    async def init(self):
        # Columnas nuevas en la tabla clientes (se agregan si no existen)
        async with self.db.execute("PRAGMA table_info(clientes)") as cur:
            existentes = {row[1] for row in await cur.fetchall()}
        nuevas = {
            "vehiculo": "TEXT",
            "notas": "TEXT",
            "campana_id": "INTEGER",
            "estado_envio": "TEXT",
            "enviado_at": "TEXT",
            "no_contactar": "INTEGER NOT NULL DEFAULT 0",
            "creado_at": "TEXT",
        }
        for col, tipo in nuevas.items():
            if col not in existentes:
                await self.db.execute(f"ALTER TABLE clientes ADD COLUMN {col} {tipo}")

        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS campanas (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre        TEXT NOT NULL,
                instrucciones TEXT,
                plantilla     TEXT,
                estado        TEXT NOT NULL DEFAULT 'pausada',
                creada_at     TEXT
            )
        """)
        await self.db.commit()
        logger.info("CRM listo")

    # ── Contactos ────────────────────────────────────────────────────────────

    async def obtener_contacto(self, numero: str) -> dict | None:
        async with self.db.execute(
            """SELECT numero, nombre, vehiculo, notas, etapa, campana_id, estado_envio,
                      no_contactar, bot_pausado, enviado_at
               FROM clientes WHERE numero = ?""",
            (numero,),
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return None
        claves = ["numero", "nombre", "vehiculo", "notas", "etapa", "campana_id",
                  "estado_envio", "no_contactar", "bot_pausado", "enviado_at"]
        return dict(zip(claves, row))

    def contexto_para_agente(self, contacto: dict | None) -> str:
        """Texto con los datos del cliente para que el agente lo use al responder."""
        if not contacto:
            return ""
        partes = []
        if contacto.get("nombre"):
            partes.append(f"Nombre: {contacto['nombre']}")
        if contacto.get("vehiculo"):
            partes.append(f"Vehiculo: {contacto['vehiculo']}")
        if contacto.get("notas"):
            partes.append(f"Notas internas: {contacto['notas']}")
        if not partes:
            return ""
        texto = "DATOS DEL CLIENTE (de nuestra lista; usalos con naturalidad, no los recites):\n"
        texto += "\n".join(partes)
        if contacto.get("campana_id"):
            texto += ("\nNosotros le escribimos primero a este cliente. No asumas que el pidio "
                      "informacion; se amable, despierta su interes y no presiones de mas.")
        return texto

    async def marcar_respondio(self, numero: str):
        await self.db.execute(
            "UPDATE clientes SET estado_envio='respondio' WHERE numero=? AND estado_envio='enviado'",
            (numero,),
        )
        await self.db.commit()

    async def marcar_no_contactar(self, numero: str):
        await self.db.execute(
            """INSERT INTO clientes (numero, etapa, no_contactar, bot_pausado, estado_envio, updated_at)
               VALUES (?, 'Nuevo contacto', 1, 1, 'no_contactar', CURRENT_TIMESTAMP)
               ON CONFLICT(numero) DO UPDATE SET no_contactar=1, bot_pausado=1,
                   estado_envio='no_contactar', updated_at=CURRENT_TIMESTAMP""",
            (numero,),
        )
        await self.db.commit()
        logger.info(f"{numero} pidió no ser contactado")

    async def importar_csv(self, contenido: bytes, campana_id: int) -> dict:
        texto = None
        for codificacion in ("utf-8-sig", "latin-1"):
            try:
                texto = contenido.decode(codificacion)
                break
            except UnicodeDecodeError:
                continue
        if texto is None:
            raise ValueError("No se pudo leer el archivo")

        try:
            dialecto = csv.Sniffer().sniff(texto[:4096], delimiters=",;\t")
        except csv.Error:
            dialecto = csv.excel
        lector = csv.DictReader(io.StringIO(texto), dialect=dialecto)
        if not lector.fieldnames:
            raise ValueError("El archivo está vacío")

        def buscar(columnas: set[str]) -> str | None:
            for f in lector.fieldnames:
                if f and f.strip().lower() in columnas:
                    return f
            return None

        col_num = buscar(COLUMNAS_NUMERO)
        if not col_num:
            raise ValueError("No encontré la columna del número. Llámala 'numero' o 'telefono'.")
        col_nom = buscar(COLUMNAS_NOMBRE)
        col_veh = buscar(COLUMNAS_VEHICULO)
        col_not = buscar(COLUMNAS_NOTAS)
        usadas = {c for c in (col_num, col_nom, col_veh, col_not) if c}

        res = {"agregados": 0, "invalidos": 0, "duplicados": 0, "bloqueados": 0}
        vistos = set()
        ahora = ahora_rd().isoformat()

        for fila in lector:
            numero = normalizar_numero(fila.get(col_num, ""))
            if not numero:
                res["invalidos"] += 1
                continue
            if numero in vistos:
                res["duplicados"] += 1
                continue
            vistos.add(numero)

            nombre = (fila.get(col_nom) or "").strip() if col_nom else ""
            vehiculo = (fila.get(col_veh) or "").strip() if col_veh else ""
            notas = [(fila.get(col_not) or "").strip()] if col_not else []
            for k, v in fila.items():
                if k and k not in usadas and v and str(v).strip():
                    notas.append(f"{k.strip()}: {str(v).strip()}")
            notas_txt = " | ".join(n for n in notas if n)

            existente = await self.obtener_contacto(numero)
            if existente:
                if existente["no_contactar"]:
                    res["bloqueados"] += 1
                    continue
                if existente["estado_envio"]:
                    res["duplicados"] += 1
                    continue
                await self.db.execute(
                    """UPDATE clientes SET
                         nombre=COALESCE(NULLIF(nombre,''), ?),
                         vehiculo=COALESCE(NULLIF(vehiculo,''), ?),
                         notas=COALESCE(NULLIF(notas,''), ?),
                         campana_id=?, estado_envio='pendiente', updated_at=CURRENT_TIMESTAMP
                       WHERE numero=?""",
                    (nombre or None, vehiculo or None, notas_txt or None, campana_id, numero),
                )
            else:
                await self.db.execute(
                    """INSERT INTO clientes (numero, etapa, nombre, vehiculo, notas, campana_id,
                                             estado_envio, creado_at, updated_at)
                       VALUES (?, 'Nuevo contacto', ?, ?, ?, ?, 'pendiente', ?, CURRENT_TIMESTAMP)""",
                    (numero, nombre or None, vehiculo or None, notas_txt or None, campana_id, ahora),
                )
            res["agregados"] += 1

        await self.db.commit()
        return res

    # ── Campañas ─────────────────────────────────────────────────────────────

    async def crear_campana(self, nombre: str, instrucciones: str, plantilla: str) -> int:
        cur = await self.db.execute(
            "INSERT INTO campanas (nombre, instrucciones, plantilla, estado, creada_at) VALUES (?, ?, ?, 'pausada', ?)",
            (nombre, instrucciones or None, plantilla or None, ahora_rd().isoformat()),
        )
        await self.db.commit()
        return cur.lastrowid

    async def obtener_campana(self, campana_id: int) -> dict | None:
        async with self.db.execute(
            "SELECT id, nombre, instrucciones, plantilla, estado FROM campanas WHERE id=?", (campana_id,)
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return None
        return dict(zip(["id", "nombre", "instrucciones", "plantilla", "estado"], row))

    async def cambiar_estado_campana(self, campana_id: int, estado: str):
        await self.db.execute("UPDATE campanas SET estado=? WHERE id=?", (estado, campana_id))
        await self.db.commit()

    async def enviados_hoy(self) -> int:
        hoy = ahora_rd().date().isoformat()
        async with self.db.execute(
            "SELECT COUNT(*) FROM clientes WHERE enviado_at LIKE ?", (f"{hoy}%",)
        ) as cur:
            return (await cur.fetchone())[0]

    async def generar_mensaje(self, contacto: dict, campana: dict) -> str:
        return await self.brain.mensaje_inicial(contacto, campana.get("instrucciones") or "")

    # ── Envío gradual ────────────────────────────────────────────────────────

    def iniciar_envios(self):
        if CRM_ACTIVO and self._tarea is None:
            self._tarea = asyncio.create_task(self._bucle())
            logger.info(
                f"Envíos de campañas activos: máx {LIMITE_DIARIO}/día, "
                f"{HORA_INICIO}:00-{HORA_FIN}:00 RD, pausa {PAUSA_MIN_SEG}-{PAUSA_MAX_SEG}s"
            )

    async def detener_envios(self):
        if self._tarea:
            self._tarea.cancel()
            try:
                await self._tarea
            except asyncio.CancelledError:
                pass
            self._tarea = None

    async def _bucle(self):
        while True:
            try:
                espera = await self._procesar_siguiente()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.exception(f"Error en envío de campaña: {e}")
                espera = 120
            await asyncio.sleep(espera)

    async def _procesar_siguiente(self) -> float:
        hora = ahora_rd().hour
        if not (HORA_INICIO <= hora < HORA_FIN):
            return 300
        if await self.enviados_hoy() >= LIMITE_DIARIO:
            return 600

        async with self.db.execute(
            """SELECT c.numero FROM clientes c JOIN campanas k ON c.campana_id = k.id
               WHERE k.estado='activa' AND c.estado_envio='pendiente' AND c.no_contactar=0
               ORDER BY c.rowid LIMIT 1"""
        ) as cur:
            row = await cur.fetchone()

        if not row:
            # Cerrar campañas activas que ya no tienen pendientes
            await self.db.execute(
                """UPDATE campanas SET estado='terminada' WHERE estado='activa' AND NOT EXISTS (
                       SELECT 1 FROM clientes WHERE campana_id=campanas.id AND estado_envio='pendiente')"""
            )
            await self.db.commit()
            return 60

        numero = row[0]
        contacto = await self.obtener_contacto(numero)
        campana = await self.obtener_campana(contacto["campana_id"])

        # Si ya tiene conversación con nosotros, no le mandamos el mensaje de campaña
        if await self.memory.get_history(numero):
            await self.db.execute("UPDATE clientes SET estado_envio='omitido' WHERE numero=?", (numero,))
            await self.db.commit()
            return 2

        plantilla = (campana.get("plantilla") or "").strip()
        if plantilla and hasattr(self.provider, "enviar_plantilla"):
            parametros = [contacto.get("nombre") or "", contacto.get("vehiculo") or "tu vehículo"]
            ok = await self.provider.enviar_plantilla(numero, plantilla, parametros)
            texto = f"[Plantilla {plantilla}] Hola {parametros[0]}, mensaje sobre GPS para {parametros[1]}"
        else:
            texto = await self.generar_mensaje(contacto, campana)
            self.memory.registrar_envio_bot(numero)
            ok = await self.provider.enviar_mensaje(numero, texto)

        if ok:
            await self.memory.save_message(numero, "assistant", texto)
            await self.db.execute(
                "UPDATE clientes SET estado_envio='enviado', enviado_at=? WHERE numero=?",
                (ahora_rd().isoformat(), numero),
            )
            logger.info(f"Campaña '{campana['nombre']}': enviado a {numero}")
        else:
            await self.db.execute("UPDATE clientes SET estado_envio='error' WHERE numero=?", (numero,))
            logger.warning(f"Campaña '{campana['nombre']}': falló el envío a {numero}")
        await self.db.commit()
        return random.uniform(PAUSA_MIN_SEG, PAUSA_MAX_SEG)


# ─────────────────────────────────────────────────────────────────────────────
# Panel web y API
# ─────────────────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/crm")
_seguridad = HTTPBasic()
_crm: CRM | None = None
PANEL_HTML = Path(__file__).parent / "gestor_panel.html"


def configurar(crm: CRM):
    global _crm
    _crm = crm


def _autenticar(cred: HTTPBasicCredentials = Depends(_seguridad)):
    clave = os.getenv("CRM_PASSWORD", "")
    usuario = os.getenv("CRM_USUARIO", "admin")
    if not clave:
        raise HTTPException(503, "Panel desactivado: configura CRM_PASSWORD en las variables de entorno")
    ok_user = secrets.compare_digest(cred.username.encode(), usuario.encode())
    ok_pass = secrets.compare_digest(cred.password.encode(), clave.encode())
    if not (ok_user and ok_pass):
        raise HTTPException(401, "Usuario o contraseña incorrectos", headers={"WWW-Authenticate": "Basic"})


def _crm_listo() -> CRM:
    if _crm is None:
        raise HTTPException(503, "CRM no iniciado")
    return _crm


@router.get("", response_class=HTMLResponse, dependencies=[Depends(_autenticar)])
async def panel():
    return HTMLResponse(PANEL_HTML.read_text(encoding="utf-8"))


@router.get("/api/resumen", dependencies=[Depends(_autenticar)])
async def resumen():
    crm = _crm_listo()
    async with crm.db.execute("SELECT etapa, COUNT(*) FROM clientes GROUP BY etapa") as cur:
        etapas = {r[0]: r[1] for r in await cur.fetchall()}
    async with crm.db.execute(
        "SELECT COALESCE(estado_envio,'sin_campana'), COUNT(*) FROM clientes GROUP BY 1"
    ) as cur:
        envios = {r[0]: r[1] for r in await cur.fetchall()}
    async with crm.db.execute(
        """SELECT k.id, k.nombre, k.estado, k.instrucciones, k.plantilla, k.creada_at,
                  COUNT(c.numero),
                  SUM(c.estado_envio='pendiente'), SUM(c.estado_envio='enviado'),
                  SUM(c.estado_envio='respondio'), SUM(c.estado_envio IN ('error','omitido')),
                  SUM(c.estado_envio='no_contactar')
           FROM campanas k LEFT JOIN clientes c ON c.campana_id = k.id
           GROUP BY k.id ORDER BY k.id DESC"""
    ) as cur:
        campanas = [
            {
                "id": r[0], "nombre": r[1], "estado": r[2], "instrucciones": r[3], "plantilla": r[4],
                "creada_at": r[5], "total": r[6], "pendientes": r[7] or 0, "enviados": r[8] or 0,
                "respondieron": r[9] or 0, "fallidos": r[10] or 0, "bajas": r[11] or 0,
            }
            for r in await cur.fetchall()
        ]
    return {
        "etapas": etapas,
        "envios": envios,
        "campanas": campanas,
        "enviados_hoy": await crm.enviados_hoy(),
        "limite_diario": LIMITE_DIARIO,
        "horario": f"{HORA_INICIO}:00 - {HORA_FIN}:00",
        "envios_activos": CRM_ACTIVO,
        "proveedor": crm.provider.__class__.__name__.replace("Provider", ""),
    }


@router.get("/api/contactos", dependencies=[Depends(_autenticar)])
async def contactos(q: str = "", etapa: str = "", estado: str = "", campana: int | None = None):
    crm = _crm_listo()
    sql = """SELECT c.numero, c.nombre, c.vehiculo, c.notas, c.etapa, c.estado_envio, c.bot_pausado,
                    c.no_contactar, c.campana_id, c.enviado_at, c.updated_at,
                    (SELECT content FROM mensajes m WHERE m.numero=c.numero ORDER BY m.id DESC LIMIT 1),
                    (SELECT created_at FROM mensajes m WHERE m.numero=c.numero ORDER BY m.id DESC LIMIT 1)
             FROM clientes c WHERE 1=1"""
    params: list = []
    if q:
        sql += " AND (c.numero LIKE ? OR c.nombre LIKE ? OR c.vehiculo LIKE ? OR c.notas LIKE ?)"
        params += [f"%{q}%"] * 4
    if etapa:
        sql += " AND c.etapa = ?"
        params.append(etapa)
    if estado:
        sql += " AND c.estado_envio = ?"
        params.append(estado)
    if campana:
        sql += " AND c.campana_id = ?"
        params.append(campana)
    sql += " ORDER BY COALESCE((SELECT MAX(id) FROM mensajes m WHERE m.numero=c.numero), 0) DESC, c.rowid DESC LIMIT 500"
    async with crm.db.execute(sql, params) as cur:
        filas = await cur.fetchall()
    claves = ["numero", "nombre", "vehiculo", "notas", "etapa", "estado_envio", "bot_pausado",
              "no_contactar", "campana_id", "enviado_at", "updated_at", "ultimo_mensaje", "ultimo_mensaje_at"]
    return [dict(zip(claves, f)) for f in filas]


@router.get("/api/conversacion/{numero}", dependencies=[Depends(_autenticar)])
async def conversacion(numero: str):
    crm = _crm_listo()
    async with crm.db.execute(
        "SELECT role, content, created_at FROM mensajes WHERE numero=? ORDER BY id", (numero,)
    ) as cur:
        mensajes = [{"role": r[0], "content": r[1], "at": r[2]} for r in await cur.fetchall()]
    return {"contacto": await crm.obtener_contacto(numero), "mensajes": mensajes}


@router.post("/api/importar", dependencies=[Depends(_autenticar)])
async def importar(
    archivo: UploadFile = File(...),
    nombre_campana: str = Form(...),
    instrucciones: str = Form(""),
    plantilla: str = Form(""),
):
    crm = _crm_listo()
    contenido = await archivo.read()
    if len(contenido) > 5_000_000:
        raise HTTPException(400, "El archivo es muy grande (máximo 5 MB)")
    campana_id = await crm.crear_campana(nombre_campana.strip() or "Campaña", instrucciones.strip(), plantilla.strip())
    try:
        res = await crm.importar_csv(contenido, campana_id)
    except ValueError as e:
        await crm.db.execute("DELETE FROM campanas WHERE id=?", (campana_id,))
        await crm.db.commit()
        raise HTTPException(400, str(e))
    return {"campana_id": campana_id, **res}


@router.post("/api/campanas/{campana_id}/estado", dependencies=[Depends(_autenticar)])
async def estado_campana(campana_id: int, estado: str = Form(...)):
    crm = _crm_listo()
    if estado not in ("activa", "pausada"):
        raise HTTPException(400, "Estado inválido")
    if not await crm.obtener_campana(campana_id):
        raise HTTPException(404, "Campaña no encontrada")
    await crm.cambiar_estado_campana(campana_id, estado)
    return {"ok": True}


@router.post("/api/campanas/{campana_id}/vista_previa", dependencies=[Depends(_autenticar)])
async def vista_previa(campana_id: int):
    """Genera (sin enviar) el mensaje que recibiría el próximo cliente pendiente."""
    crm = _crm_listo()
    campana = await crm.obtener_campana(campana_id)
    if not campana:
        raise HTTPException(404, "Campaña no encontrada")
    async with crm.db.execute(
        "SELECT numero FROM clientes WHERE campana_id=? ORDER BY estado_envio!='pendiente', rowid LIMIT 1",
        (campana_id,),
    ) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(400, "La campaña no tiene clientes")
    contacto = await crm.obtener_contacto(row[0])
    if campana.get("plantilla"):
        return {"numero": contacto["numero"], "nombre": contacto.get("nombre"),
                "mensaje": f"(Se enviará la plantilla de Meta '{campana['plantilla']}')"}
    return {"numero": contacto["numero"], "nombre": contacto.get("nombre"),
            "mensaje": await crm.generar_mensaje(contacto, campana)}


@router.post("/api/contactos/{numero}/accion", dependencies=[Depends(_autenticar)])
async def accion_contacto(numero: str, accion: str = Form(...)):
    crm = _crm_listo()
    if accion == "pausar":
        await crm.memory.pausar_bot(numero)
    elif accion == "reactivar":
        await crm.memory.reactivar_bot(numero)
    elif accion == "no_contactar":
        await crm.marcar_no_contactar(numero)
    else:
        raise HTTPException(400, "Acción inválida")
    return {"ok": True}


@router.get("/api/ejemplo.csv", dependencies=[Depends(_autenticar)])
async def ejemplo_csv():
    texto = (
        "numero,nombre,vehiculo,notas\n"
        "8095551234,Juan Pérez,Toyota Hilux 2020,Cliente de la feria de autos\n"
        "8295557890,María Gómez,Honda CR-V,Preguntó por GPS en Instagram\n"
    )
    return PlainTextResponse(
        texto, media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=ejemplo_clientes.csv"},
    )
