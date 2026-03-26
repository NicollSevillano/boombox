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

# ── Intents ─────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True


# ── Bot ─────────────────────────────────────────────
class RadioBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=PREFIX, intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        print("Slash commands sincronizados.")

    async def on_ready(self):
        print(f"Bot listo como {self.user}")


client = RadioBot()

# Historial
historial = deque(maxlen=3)

# ── HELP ────────────────────────────────────────────
HELP_MESSAGE = """🎙️ **BoomBox — Tu radio en Discord**

Reproducí cualquier emisora de radio o stream en vivo.

━━━━━━━━━━━━━━━━━━━━━━━
📻 **Comandos**

`/play <url>` o `!play <url>` → Reproducir radio  
`/stop` o `!stop` → Detener  
`/recientes` o `!recientes` → Últimas radios  
`/favoritos` o `!favoritos` → Ver favoritos  
`/eliminar_favorito <nombre>` → Eliminar favorito  
`/ayuda` o `!ayuda` → Mostrar ayuda  

━━━━━━━━━━━━━━━━━━━━━━━
⭐ Guardar favoritos:
1. Usá /play  
2. Tocá ⭐  
3. Poné nombre  

━━━━━━━━━━━━━━━━━━━━━━━
⚠️ Algunas radios pueden cortarse, el bot reconecta automáticamente.
"""

# ── Favoritos ───────────────────────────────────────
def cargar_favoritos():
    if os.path.exists(FAVS_FILE):
        with open(FAVS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def guardar_favoritos(favs):
    with open(FAVS_FILE, "w", encoding="utf-8") as f:
        json.dump(favs, f, ensure_ascii=False, indent=2)


# ── RECONEXIÓN OPTIMIZADA ──────────────────────────────────
async def reconectar(vc, url):
    """
    Intenta restablecer la conexión si el stream se corta, 
    esperando un breve momento para limpiar el buffer.
    """
    await asyncio.sleep(2) 
    
    if vc and vc.is_connected() and not vc.is_playing():
        print(f"🔄 Re-estabilizando señal: {url}")
        try:
            source = await FFmpegOpusAudio.from_probe(
                url,
                executable="ffmpeg",
                before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
                options="-vn -af aresample=async=1"
            )

            vc.play(source, after=lambda e: asyncio.run_coroutine_threadsafe(
                reconectar(vc, url), client.loop
            ))
        except Exception as e:
            print(f"⚠️ Error en reconexión: {e}")

# ── REPRODUCIR CORREGIDO ──────────────────────────────────────
async def reproducir(interaction_or_ctx, url: str, es_interaction: bool = True):
    """
    Función principal de ejecución de audio compatible con Slash y Prefijo.
    """
    if es_interaction:
        author = interaction_or_ctx.user
        send   = interaction_or_ctx.followup.send
        guild  = interaction_or_ctx.guild
    else:
        author = interaction_or_ctx.author
        send   = interaction_or_ctx.send
        guild  = interaction_or_ctx.guild

    if not author.voice:
        await send("⚠️ Tenés que estar en un canal de voz para que me una.")
        return

    channel = author.voice.channel
    voice_client = guild.voice_client

    try:
        if voice_client:
            if voice_client.channel.id != channel.id:
                await voice_client.move_to(channel)
            if voice_client.is_playing():
                voice_client.stop()
            vc = voice_client
        else:
            vc = await channel.connect()

        source = await FFmpegOpusAudio.from_probe(
            url,
            executable="ffmpeg",
            before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            options="-vn -af aresample=async=1"
        )

        def after_play(err):
            if err:
                print(f"❌ Error detectado en el stream: {err}")
            asyncio.run_coroutine_threadsafe(reconectar(vc, url), client.loop)

        vc.play(source, after=after_play)

        if url in historial:
            historial.remove(url)
        historial.appendleft(url)

        view = BotonFavorito(url)
        await send(f"📻 Reproduciendo en `{channel.name}`\n🔗 `{url}`", view=view)

    except Exception as e:
        await send(f"❌ No pude reproducir la radio: {e}")
        print(f"Detalle técnico del error: {e}")

# ── BOTÓN FAVORITO ──────────────────────────────────
class BotonFavorito(discord.ui.View):
    def __init__(self, url: str):
        super().__init__(timeout=60)
        self.url = url

    @discord.ui.button(label="⭐ Guardar favorito", style=discord.ButtonStyle.secondary)
    async def guardar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("❌ Solo admins/mods.", ephemeral=True)
            return

        await interaction.response.send_modal(ModalNombreFavorito(self.url))


class ModalNombreFavorito(discord.ui.Modal, title="Guardar favorito"):
    nombre = discord.ui.TextInput(label="Nombre de la radio", max_length=50)

    def __init__(self, url: str):
        super().__init__()
        self.url = url

    async def on_submit(self, interaction: discord.Interaction):
        favs = cargar_favoritos()
        favs[self.nombre.value] = self.url
        guardar_favoritos(favs)

        await interaction.response.send_message(
            f"⭐ {self.nombre.value} guardado.",
            ephemeral=True
        )


# ── BOTONES FAVORITOS ───────────────────────────────
class BotonesFavoritos(discord.ui.View):
    def __init__(self, favs: dict):
        super().__init__(timeout=120)
        for nombre, url in favs.items():
            self.add_item(BotonReproducirFavorito(nombre, url))


class BotonReproducirFavorito(discord.ui.Button):
    def __init__(self, nombre: str, url: str):
        super().__init__(label=f"▶️ {nombre}", style=discord.ButtonStyle.primary)
        self.url = url

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await reproducir(interaction, self.url, True)


# ── SLASH COMMANDS ──────────────────────────────────
@client.tree.command(name="play", description="Reproduce una radio desde una URL")
async def slash_play(interaction: discord.Interaction, url: str):
    await interaction.response.defer()
    await reproducir(interaction, url, True)


@client.tree.command(name="stop", description="Detiene la radio y desconecta al bot")
async def slash_stop(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("⏹️ Stop.")
    else:
        await interaction.response.send_message("Nada sonando.")


@client.tree.command(name="recientes", description="Muestra las ultimas 3 estaciones")
async def slash_recientes(interaction: discord.Interaction):
    if not historial:
        await interaction.response.send_message("📭 Vacío.")
        return
    await interaction.response.send_message("\n".join(historial))


@client.tree.command(name="favoritos", description="Muestra tu lista de radios guardadas")
async def slash_favoritos(interaction: discord.Interaction):
    favs = cargar_favoritos()
    if not favs:
        await interaction.response.send_message("📭 No hay favoritos.")
        return

    texto = "\n".join([f"⭐ {n}" for n in favs])
    await interaction.response.send_message(texto, view=BotonesFavoritos(favs))


@client.tree.command(name="eliminar_favorito", description="Borra una radio de tu lista de favoritos")
async def slash_eliminar(interaction: discord.Interaction, nombre: str):
    if not interaction.user.guild_permissions.manage_channels:
        await interaction.response.send_message("❌ Solo admins.", ephemeral=True)
        return

    favs = cargar_favoritos()
    if nombre in favs:
        del favs[nombre]
        guardar_favoritos(favs)
        await interaction.response.send_message("🗑️ Eliminado.")
    else:
        await interaction.response.send_message("No existe.")


@client.tree.command(name="ayuda", description="Muestra la lista de comandos y cómo usar el bot")
async def slash_ayuda(interaction: discord.Interaction):
    await interaction.response.send_message(HELP_MESSAGE)


# ── PREFIX COMMANDS ────────────────────────────────
@client.command(name="play")
async def prefix_play(ctx, url: str = None):
    if not url:
        await ctx.send("⚠️ Pasá URL.")
        return
    await reproducir(ctx, url, False)


@client.command(name="stop")
async def prefix_stop(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("⏹️ Stop.")


@client.command(name="ayuda")
async def prefix_ayuda(ctx):
    await ctx.send(HELP_MESSAGE)


client.run(TOKEN)
