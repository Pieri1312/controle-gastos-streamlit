import os
import logging
import whisper
import pandas as pd
from dotenv import load_dotenv, find_dotenv
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, MessageHandler, ContextTypes,
    filters, CommandHandler
)
import subprocess
import asyncio
import nest_asyncio

# Configurações
nest_asyncio.apply()
load_dotenv(find_dotenv())
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

model = None
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ARQUIVO_GASTOS = "gastos.csv"
ARQUIVO_CATEGORIAS = "categorias_usuario.csv"
CATEGORIAS_FIXAS = [
    "Alimentação", "Transporte", "Lazer", "Moradia", "Saúde",
    "Educação", "Contas", "Outros", "Viagem", "Compras"
]

# Cria arquivos
if not os.path.exists(ARQUIVO_GASTOS):
    pd.DataFrame(columns=["Data", "Categoria", "Valor", "Descrição"]).to_csv(ARQUIVO_GASTOS, index=False)

if not os.path.exists(ARQUIVO_CATEGORIAS):
    pd.DataFrame(columns=["Palavra", "Categoria"]).to_csv(ARQUIVO_CATEGORIAS, index=False)

# Extrair dados
def extrair_dados(texto):
    import re
    texto = texto.strip()
    padrao = r"(?P<valor>\d+[,.]?\d*)\s*(?P<descricao>.*)"
    match = re.search(padrao, texto, re.IGNORECASE)
    if not match:
        return None, None, None
    valor = float(match.group("valor").replace(",", "."))
    descricao = match.group("descricao").strip()
    categoria = None

    categorias_df = pd.read_csv(ARQUIVO_CATEGORIAS)
    palavras_desc = descricao.lower().split()

    for palavra in palavras_desc:
        resultado = categorias_df[categorias_df["Palavra"] == palavra]
        if not resultado.empty:
            categoria = resultado["Categoria"].values[0]
            break

    return categoria, valor, descricao

def converter_audio_ogg_para_wav(entrada, saida):
    subprocess.run(["ffmpeg", "-y", "-i", entrada, saida],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# Resposta de texto para categoria
async def receber_categoria(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "valor" not in context.user_data or "descricao" not in context.user_data:
        await update.message.reply_text("❌ Nenhum gasto pendente para classificar.")
        return

    categoria = update.message.text.strip().capitalize()
    if categoria not in CATEGORIAS_FIXAS:
        categoria = "Outros"

    # Aprender palavras
    categorias_df = pd.read_csv(ARQUIVO_CATEGORIAS)
    novas = []
    for palavra in context.user_data["descricao"].lower().split():
        if categorias_df[categorias_df["Palavra"] == palavra].empty:
            novas.append({"Palavra": palavra, "Categoria": categoria})
    if novas:
        categorias_df = pd.concat([categorias_df, pd.DataFrame(novas)], ignore_index=True)
        categorias_df.to_csv(ARQUIVO_CATEGORIAS, index=False)

    # Salvar gasto
    data = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    novo = pd.DataFrame([[data, categoria, context.user_data["valor"], context.user_data["descricao"]]],
                        columns=["Data", "Categoria", "Valor", "Descrição"])
    df = pd.read_csv(ARQUIVO_GASTOS)
    df = pd.concat([df, novo], ignore_index=True)
    df.to_csv(ARQUIVO_GASTOS, index=False)
    total = df["Valor"].sum()

    await update.message.reply_text(
        f"✅ *Gasto salvo!*\n\n"
        f"🗓 *Data:* {data}\n"
        f"📂 *Categoria:* {categoria}\n"
        f"💰 *Valor:* R$ {context.user_data['valor']:.2f}\n"
        f"📝 *Descrição:* {context.user_data['descricao']}\n\n"
        f"📊 *Total acumulado:* R$ {total:.2f}",
        parse_mode="Markdown"
    )
    context.user_data.clear()

# Handler de áudio
async def tratar_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global model

    if model is None:
        model = whisper.load_model("medium")
        logger.info("Modelo Whisper carregado.")

    file = await update.message.voice.get_file()
    caminho_ogg = f"audio_{update.message.message_id}.ogg"
    caminho_wav = f"audio_{update.message.message_id}.wav"
    await file.download_to_drive(caminho_ogg)
    converter_audio_ogg_para_wav(caminho_ogg, caminho_wav)
    texto = model.transcribe(caminho_wav)["text"]
    os.remove(caminho_ogg)
    os.remove(caminho_wav)

    categoria, valor, descricao = extrair_dados(texto)

    if not valor:
        await update.message.reply_text(f"🗣 Transcrição: {texto}\n\n❌ Não entendi. Tente: `90 almoço no shopping`")
        return

    if not categoria:
        context.user_data["valor"] = valor
        context.user_data["descricao"] = descricao

        keyboard = [[c] for c in CATEGORIAS_FIXAS]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

        await update.message.reply_text(
            f"🤔 *Descrição:* {descricao}\n💰 *Valor:* R$ {valor:.2f}\n\n"
            "Escolha a categoria:",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
        return

    # Se já tiver categoria, salva direto
    data = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    novo = pd.DataFrame([[data, categoria, valor, descricao]], columns=["Data", "Categoria", "Valor", "Descrição"])
    df = pd.read_csv(ARQUIVO_GASTOS)
    df = pd.concat([df, novo], ignore_index=True)
    df.to_csv(ARQUIVO_GASTOS, index=False)
    total = df["Valor"].sum()

    await update.message.reply_text(
        f"✅ *Gasto salvo!*\n\n"
        f"🗓 *Data:* {data}\n"
        f"📂 *Categoria:* {categoria}\n"
        f"💰 *Valor:* R$ {valor:.2f}\n"
        f"📝 *Descrição:* {descricao}\n\n"
        f"📊 *Total acumulado:* R$ {total:.2f}",
        parse_mode="Markdown"
    )

# Main
if __name__ == "__main__":
    if os.name == "nt":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.VOICE, tratar_audio))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receber_categoria))
    logger.info("Bot rodando...")
    app.run_polling()
