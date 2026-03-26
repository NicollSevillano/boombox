import os
import json
import asyncio
from collections import deque
from dotenv import load_dotenv

import discord
from discord import app_commands, FFmpegOpusAudio
from discord.ext import commands

load_dotenv()

TOKEN   = os.getenv("DISCORD_TOKEN")
PREFIX  = os.getenv("PREFIX", "!")
FAVS_FILE = "favoritos.json"

intents = discord.Intents.default()
intents.message_content = True


class RadioBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=PREFIX, intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        print("Slash commands sincronizados.")

    async def on_ready(self):
        print(f"Bot listo como {self.user}")


client = RadioBot()
historial = deque(maxlen=3)

HELP_MESSAGE = """🎙️ BoomBox listo para usar."""


# ── Favoritos ─────────────────────────────────────────
def cargar_favoritos():
    if os.path.exists(FAVS_FILE):
        with open(FAVS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def guardar_favoritos(favs):
    with open(FAVS_FILE, "w", encoding="utf-8") as f:
        json.dump(favs, f, ensure_ascii=False, indent=2)


# ── RECONEXIÓN PRO ───────────────────────────────────
async def reconectar(vc, url):
    await asyncio.sleep(2)  # más rápido
    if vc.is_connected() and not vc.is_playing():
        print(f"🔄 Reconectando: {url}")
        try:
            source = await FFmpegOpusAudio.from_probe(
                url,
                executable="ffmpeg",
                before_options=(
                    "-reconnect 1 -reconnect_streamed 1 "
                    "-reconnect_delay_max 5 "
                    "-buffer_size 512k "
                    "-rw_timeout 15000000"
                ),
                options="-vn -loglevel quiet"
            )
            vc.play(source, after=lambda e: asyncio.run_coroutine_threadsafe(
                reconectar(vc, url), client.loop
            ))
        except Exception as e:
            print(f"❌ Error reconectando: {e}")


# ── REPRODUCCIÓN ─────────────────────────────────────
async def reproducir(interaction_or_ctx, url: str, es_interaction: bool = True):
    if es_interaction:
        author = interaction_or_ctx.user
        send   = interaction_or_ctx.followup.send
        voice_client = interaction_or_ctx.guild.voice_client
    else:
        author = interaction_or_ctx.author
        send   = interaction_or_ctx.send
        voice_client = interaction_or_ctx.voice_client

    if not author.voice:
        await send("⚠️ Tenés que estar en un canal de voz.")
        return

    channel = author.voice.channel

    if voice_client:
        if voice_client.channel.id != channel.id:
            await voice_client.move_to(channel)
        if voice_client.is_playing():
            voice_client.stop()

    try:
        vc = voice_client or await channel.connect()

        source = await FFmpegOpusAudio.from_probe(
            url,
            executable="ffmpeg",
            before_options=(
                "-reconnect 1 -reconnect_streamed 1 "
                "-reconnect_delay_max 5 "
                "-buffer_size 512k "
                "-rw_timeout 15000000"
            ),
            options="-vn -loglevel quiet"
        )

        def after_play(err):
            if err:
                print(f"⚠️ Error real: {err}")
            asyncio.run_coroutine_threadsafe(
                reconectar(vc, url), client.loop
            )

        vc.play(source, after=after_play)

        if url in historial:
            historial.remove(url)
        historial.appendleft(url)

        await send(f"📻 Reproduciendo en `{channel.name}`\n🔗 `{url}`")

    except Exception as e:
        await send(f"❌ Error: {e}")
        print(f"Detalle: {e}")


# ── COMANDOS ─────────────────────────────────────────

@client.tree.command(name="play")
async def slash_play(interaction: discord.Interaction, url: str):
    await interaction.response.defer()
    await reproducir(interaction, url, True)


@client.tree.command(name="stop")
async def slash_stop(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("⏹️ Stop.")
    else:
        await interaction.response.send_message("Nada sonando.")


@client.tree.command(name="recientes")
async def slash_recientes(interaction: discord.Interaction):
    if not historial:
        await interaction.response.send_message("📭 Vacío.")
        return
    await interaction.response.send_message("\n".join(historial))


@client.command(name="play")
async def prefix_play(ctx, url: str = None):
    if not url:
        await ctx.send("⚠️ Pasá una URL.")
        return
    await reproducir(ctx, url, False)


@client.command(name="stop")
async def prefix_stop(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("⏹️ Stop.")


client.run(TOKEN)
