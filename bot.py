"""Bot de Telegram 'Profeta de Reactivos'.

Capa conversacional sobre el backend FastAPI existente. El operario elige
condiciones de proceso con botones (no sliders) y recibe la dosis de colector
recomendada, el ahorro y la justificación.

Ejecutar localmente:
    python bot.py
"""
from __future__ import annotations

import logging
import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

import api_client
import config
from variables import PROFILES, PROFILES_BY_KEY, VARIABLES

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("profeta-bot")


# ---------------------------------------------------------------------------
# Control de acceso
# ---------------------------------------------------------------------------
def _autorizado(update: Update) -> bool:
    if not config.ALLOWED_CHAT_IDS:
        return True  # sin whitelist configurada => abierto (solo dev)
    chat = update.effective_chat
    return chat is not None and chat.id in config.ALLOWED_CHAT_IDS


async def _rechazar(update: Update) -> None:
    chat = update.effective_chat
    texto = (
        "🚫 No estás autorizado para usar este bot.\n"
        f"Tu chat_id es: `{chat.id if chat else '?'}`\n"
        "Compártelo con el administrador para que te habilite."
    )
    if update.callback_query:
        await update.callback_query.answer("No autorizado", show_alert=True)
        await update.callback_query.message.reply_text(texto, parse_mode=ParseMode.MARKDOWN)
    elif update.message:
        await update.message.reply_text(texto, parse_mode=ParseMode.MARKDOWN)


# ---------------------------------------------------------------------------
# Teclados
# ---------------------------------------------------------------------------
def _menu_principal() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🧪 Nueva recomendación", callback_data="menu:new")],
            [InlineKeyboardButton("📡 Estado del sistema", callback_data="menu:status")],
        ]
    )


def _menu_modo() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("⚡ Perfil rápido", callback_data="mode:profile")],
            [InlineKeyboardButton("🎛️ Ingresar variable por variable", callback_data="mode:manual")],
            [InlineKeyboardButton("⬅️ Menú", callback_data="menu:home")],
        ]
    )


def _teclado_perfiles() -> InlineKeyboardMarkup:
    filas = [[InlineKeyboardButton(p.label, callback_data=f"profile:{p.key}")] for p in PROFILES]
    filas.append([InlineKeyboardButton("⬅️ Atrás", callback_data="menu:new")])
    return InlineKeyboardMarkup(filas)


def _teclado_variable(var_index: int) -> InlineKeyboardMarkup:
    var = VARIABLES[var_index]
    filas = []
    # Opciones de rango, 2 por fila.
    fila_actual = []
    for opt_index, opt in enumerate(var.options):
        fila_actual.append(
            InlineKeyboardButton(opt.label, callback_data=f"var:{var_index}:{opt_index}")
        )
        if len(fila_actual) == 2:
            filas.append(fila_actual)
            fila_actual = []
    if fila_actual:
        filas.append(fila_actual)
    filas.append([InlineKeyboardButton("❌ Cancelar", callback_data="menu:home")])
    return InlineKeyboardMarkup(filas)


def _teclado_resultado() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("❓ ¿Por qué esta dosis?", callback_data="result:why")],
            [InlineKeyboardButton("📊 Ver los 9 escenarios", callback_data="result:scenarios")],
            [InlineKeyboardButton("🔁 Nueva consulta", callback_data="menu:new")],
        ]
    )


# ---------------------------------------------------------------------------
# Comandos
# ---------------------------------------------------------------------------
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _autorizado(update):
        await _rechazar(update)
        return
    context.user_data.clear()
    texto = (
        "*🔮 Profeta de Reactivos*\n\n"
        "Optimización IA de dosis de colector para flotación de cobre.\n"
        "Elige las condiciones actuales del proceso y te doy la dosis recomendada, "
        "el ahorro estimado y el porqué.\n\n"
        "¿Qué deseas hacer?"
    )
    await update.message.reply_text(
        texto, parse_mode=ParseMode.MARKDOWN, reply_markup=_menu_principal()
    )


async def cmd_estado(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _autorizado(update):
        await _rechazar(update)
        return
    await _responder_estado(update.message.reply_text)


async def cmd_myid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    await update.message.reply_text(
        f"Tu chat_id es: `{chat.id}`", parse_mode=ParseMode.MARKDOWN
    )


# ---------------------------------------------------------------------------
# Callbacks (botones inline)
# ---------------------------------------------------------------------------
async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _autorizado(update):
        await _rechazar(update)
        return

    query = update.callback_query
    await query.answer()
    data = query.data or ""

    if data == "menu:home":
        context.user_data.clear()
        await query.edit_message_text(
            "*🔮 Profeta de Reactivos*\n\n¿Qué deseas hacer?",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_menu_principal(),
        )
        return

    if data == "menu:new":
        context.user_data.pop("inputs", None)
        context.user_data.pop("var_index", None)
        await query.edit_message_text(
            "¿Cómo quieres ingresar las condiciones del proceso?",
            reply_markup=_menu_modo(),
        )
        return

    if data == "menu:status":
        await _responder_estado(query.edit_message_text, con_menu=True)
        return

    if data == "mode:profile":
        await query.edit_message_text(
            "Elige un *perfil rápido* que se parezca a la condición actual:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_teclado_perfiles(),
        )
        return

    if data == "mode:manual":
        context.user_data["inputs"] = {}
        context.user_data["var_index"] = 0
        await _preguntar_variable(query, 0)
        return

    if data.startswith("profile:"):
        key = data.split(":", 1)[1]
        profile = PROFILES_BY_KEY.get(key)
        if not profile:
            await query.edit_message_text("Perfil no encontrado.", reply_markup=_menu_principal())
            return
        await _ejecutar_optimizacion(update, context, dict(profile.inputs))
        return

    if data.startswith("var:"):
        await _on_variable_elegida(update, context, data)
        return

    if data == "result:why":
        await _mostrar_justificacion(query, context)
        return

    if data == "result:scenarios":
        await _mostrar_escenarios(query, context)
        return


async def _on_variable_elegida(
    update: Update, context: ContextTypes.DEFAULT_TYPE, data: str
) -> None:
    query = update.callback_query
    _, var_index_str, opt_index_str = data.split(":")
    var_index = int(var_index_str)
    opt_index = int(opt_index_str)
    var = VARIABLES[var_index]
    value = var.options[opt_index].value

    inputs = context.user_data.setdefault("inputs", {})
    inputs[var.key] = value

    siguiente = var_index + 1
    if siguiente < len(VARIABLES):
        context.user_data["var_index"] = siguiente
        await _preguntar_variable(query, siguiente)
    else:
        await _ejecutar_optimizacion(update, context, dict(inputs))


async def _preguntar_variable(query, var_index: int) -> None:
    var = VARIABLES[var_index]
    texto = (
        f"*Paso {var_index + 1} de {len(VARIABLES)}*\n\n"
        f"{var.titulo}\n"
        f"Selecciona el rango ({var.unidad}):"
    )
    await query.edit_message_text(
        texto, parse_mode=ParseMode.MARKDOWN, reply_markup=_teclado_variable(var_index)
    )


# ---------------------------------------------------------------------------
# Optimización + presentación de resultados
# ---------------------------------------------------------------------------
async def _ejecutar_optimizacion(
    update: Update, context: ContextTypes.DEFAULT_TYPE, inputs: dict[str, float]
) -> None:
    query = update.callback_query

    # Anti-spam: respeta un intervalo mínimo entre consultas.
    ahora = time.monotonic()
    ultima = context.user_data.get("last_query_ts", 0.0)
    if ahora - ultima < config.MIN_SECONDS_BETWEEN_QUERIES:
        await query.answer("Espera un momento antes de consultar de nuevo.", show_alert=False)
        return
    context.user_data["last_query_ts"] = ahora

    await query.edit_message_text("⏳ Optimizando dosis de colector…")

    try:
        resultado = await api_client.optimizar(inputs)
    except api_client.ApiError as exc:
        await query.edit_message_text(
            f"⚠️ {exc}",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔁 Reintentar", callback_data="menu:new")]]
            ),
        )
        return
    except Exception as exc:  # noqa: BLE001
        logger.exception("Error inesperado optimizando")
        await query.edit_message_text(
            f"⚠️ Error inesperado: {exc}",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔁 Reintentar", callback_data="menu:new")]]
            ),
        )
        return

    context.user_data["last_result"] = resultado
    context.user_data["last_inputs"] = inputs
    await query.edit_message_text(
        _formato_resultado(resultado, inputs),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_teclado_resultado(),
    )


def _formato_resultado(resultado: dict, inputs: dict[str, float]) -> str:
    optimo = resultado["optimo"]
    colector_actual = resultado["colector_actual"]
    delta_colector = resultado["delta_colector"]
    delta_rec = resultado["delta_recuperacion_pct"]
    ahorro_diario = resultado["ahorro_diario"]
    ahorro_anual = resultado["ahorro_anual"]
    agua_dia = resultado.get("agua_ahorrada_m3dia", 0.0)

    signo = "+" if delta_colector >= 0 else ""
    signo_rec = "+" if delta_rec >= 0 else ""

    return (
        "*✅ Recomendación de dosis*\n\n"
        f"🧪 *Colector: {optimo['colector_L_h']:.1f} L/h*\n"
        f"   (actual: {colector_actual:.1f} L/h · {signo}{delta_colector:.1f} L/h)\n\n"
        f"⚙️ Recuperación de cobre: *{optimo['recuperacion_pct']:.2f}%*"
        f" ({signo_rec}{delta_rec:.2f} pts)\n"
        f"💰 Ahorro diario: *${ahorro_diario:,.0f} USD/día*\n"
        f"📈 Ahorro anual: *${ahorro_anual:,.0f} USD/año*\n"
        f"💧 Agua ahorrada: {agua_dia:,.0f} m³/día\n"
        f"🎯 Score: {optimo['score_combinado']:.1f}/100\n\n"
        "_Usa los botones para ver el porqué o los 9 escenarios._"
    )


async def _mostrar_justificacion(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    resultado = context.user_data.get("last_result")
    if not resultado:
        await query.answer("No hay una consulta reciente.", show_alert=True)
        return
    recomendacion = resultado.get("recomendacion", "Sin justificación disponible.")
    disclaimer = resultado.get("disclaimer", "")
    texto = f"*❓ ¿Por qué esta dosis?*\n\n{recomendacion}"
    if disclaimer:
        texto += f"\n\n_{disclaimer}_"
    await query.edit_message_text(
        texto,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("📊 Ver los 9 escenarios", callback_data="result:scenarios")],
                [InlineKeyboardButton("🔁 Nueva consulta", callback_data="menu:new")],
            ]
        ),
    )


async def _mostrar_escenarios(query, context: ContextTypes.DEFAULT_TYPE) -> None:
    resultado = context.user_data.get("last_result")
    if not resultado:
        await query.answer("No hay una consulta reciente.", show_alert=True)
        return

    escenarios = resultado.get("escenarios", [])
    lineas = ["Colector  Recup%   Costo$/h  Ahorro$/d"]
    lineas.append("-" * 40)
    for e in escenarios:
        marca = "►" if e.get("es_optimo") else " "
        lineas.append(
            f"{marca}{e['colector_L_h']:>6.1f}  "
            f"{e['recuperacion_pct']:>6.2f}  "
            f"{e['costo_usd_h']:>8.0f}  "
            f"{e['ahorro_vs_actual']:>8.0f}"
        )
    tabla = "\n".join(lineas)
    texto = f"*📊 Los 9 escenarios evaluados*\n\n```\n{tabla}\n```\n► = óptimo"
    await query.edit_message_text(
        texto,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("❓ ¿Por qué esta dosis?", callback_data="result:why")],
                [InlineKeyboardButton("🔁 Nueva consulta", callback_data="menu:new")],
            ]
        ),
    )


# ---------------------------------------------------------------------------
# Estado del sistema
# ---------------------------------------------------------------------------
async def _responder_estado(reply_fn, con_menu: bool = False) -> None:
    try:
        estado = await api_client.modelos_status()
    except api_client.ApiError as exc:
        await reply_fn(f"⚠️ {exc}")
        return

    fallback = estado.get("fallback_analitico", False)
    modelos = estado.get("modelos", {})
    activos = sum(1 for v in modelos.values() if v)
    total = len(modelos) if modelos else 3

    if fallback or activos < total:
        cabecera = f"⚠️ Usando modelo analítico de respaldo ({activos}/{total} modelos IA)."
    else:
        cabecera = f"✅ {activos} modelos IA activos y operativos."

    detalle = "\n".join(
        f"   {'✅' if ok else '❌'} {nombre}" for nombre, ok in modelos.items()
    )
    mensaje = estado.get("mensaje", "")
    texto = f"*📡 Estado del sistema*\n\n{cabecera}\n"
    if detalle:
        texto += f"\n{detalle}\n"
    if mensaje:
        texto += f"\n_{mensaje}_"

    kwargs = {"parse_mode": ParseMode.MARKDOWN}
    if con_menu:
        kwargs["reply_markup"] = _menu_principal()
    await reply_fn(texto, **kwargs)


# ---------------------------------------------------------------------------
# Arranque
# ---------------------------------------------------------------------------
def main() -> None:
    config.validate()
    logger.info("Backend API: %s", config.API_URL)
    if config.ALLOWED_CHAT_IDS:
        logger.info("Whitelist activa: %s", config.ALLOWED_CHAT_IDS)
    else:
        logger.warning("Sin whitelist: el bot está abierto a cualquier usuario.")

    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("estado", cmd_estado))
    app.add_handler(CommandHandler("myid", cmd_myid))
    app.add_handler(CallbackQueryHandler(on_callback))

    logger.info("Bot iniciado (polling). Ctrl+C para detener.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
