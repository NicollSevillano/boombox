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

# ── Intents ──────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True


# ── Bot con soporte híbrido (! y /) ─────────────────────────────
class RadioBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=PREFIX, intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        print("Slash commands sincronizados.")

    async def on_ready(self):
        print(f"Bot listo como {self.user}")


client = RadioBot()

# Historial en memoria (últimas 3)
historial = deque(maxlen=3)

HELP_MESSAGE = """🎙️ **BoomBox — Tu radio en Discord**
Reproducí cualquier emisora de radio o stream de audio en vivo directamente en un canal de voz. Sin complicaciones.

**📻 Comandos:**
`/play <url>` o `!play <url>` — Reproduce el stream de la URL
`/stop` o `!stop` — Detiene la radio y desconecta el bot
`/recientes` o `!recientes` — Muestra las últimas 3 radios reproducidas
`/favoritos` o `!favoritos` — Ve y reproducí tus favoritas con un clic
`/eliminar_favorito <nombre>` — Elimina un favorito *(solo admins/mods)*
`/ayuda` o `!ayuda` — Muestra este mensaje

**⭐ ¿Cómo guardar una radio como favorita?**
1. Usá `/play <url>` para reproducir una radio
2. Tocá el botón ⭐ Guardar favorito que aparece en la respuesta
3. Escribí el nombre y listo — queda guardada para siempre

**🔍 ¿Dónde encontrar URLs de radios?**
Entrá a una página de radio online, dale play, abrí DevTools con F12 → Network → Media y copiá la URL del stream.

*Tip: myradioenvivo.ar tiene radios argentinas de todo tipo.*"""


# ── Favoritos (persistentes en JSON) ────────────────────────────
def cargar_favoritos():
    if os.path.exists(FAVS_FILE):
        with open(FAVS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def guardar_favoritos(favs):
    with open(FAVS_FILE, "w", encoding="utf-8") as f:
        json.dump(favs, f, ensure_ascii=False, indent=2)


# ── Lógica de reproducción ───────────────────────────────────────
async def reconectar(voice_client, url):
    await asyncio.sleep(3)
    if voice_client.is_connected() and not voice_client.is_playing():
        print("Reconectando...")
        try:
            # Forzamos la búsqueda del ejecutable 'ffmpeg'
            source = await FFmpegOpusAudio.from_probe(
                url,
                executable="ffmpeg",
                before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
                options="-vn"
            )
            voice_client.play(source, after=lambda e: asyncio.run_coroutine_threadsafe(
                reconectar(voice_client, url), client.loop
            ))
        except Exception as e:
            print(f"Error al reconectar: {e}")


async def reproducir(interaction_or_ctx, url: str, es_interaction: bool = True):
    # Obtener autor y canal según el tipo
    if es_interaction:
        author = interaction_or_ctx.user
        guild  = interaction_or_ctx.guild
        send   = interaction_or_ctx.followup.send
        voice_client = guild.voice_client
    else:
        author = interaction_or_ctx.author
        guild  = interaction_or_ctx.guild
        send   = interaction_or_ctx.send
        voice_client = interaction_or_ctx.voice_client

    if not author.voice:
        await send("⚠️ Tenés que estar en un canal de voz para usar este comando.")
        return

    channel = author.voice.channel

    if voice_client:
        await voice_client.disconnect()

    try:
        vc = await channel.connect()
    except Exception as e:
        await send(f"❌ No pude conectarme al canal: {e}")
        return

    try:
        source = FFmpegOpusAudio(
            url,
            before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
        )
        vc.play(source, after=lambda e: asyncio.run_coroutine_threadsafe(
            reconectar(vc, url), client.loop
        ))

        # Actualizar historial
        if url in historial:
            historial.remove(url)
        historial.appendleft(url)

        # Botón para guardar favorito
        view = BotonFavorito(url)
        await send(
            f"📻 Reproduciendo en `{channel.name}`\n🔗 `{url}`",
            view=view
        )
    except Exception as e:
        await send(f"❌ No pude reproducir esa URL: {e}")


# ── Botón ⭐ Guardar favorito ────────────────────────────────────
class BotonFavorito(discord.ui.View):
    def __init__(self, url: str):
        super().__init__(timeout=60)
        self.url = url

    @discord.ui.button(label="⭐ Guardar favorito", style=discord.ButtonStyle.secondary)
    async def guardar(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Solo admins/mods (manage_channels)
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("❌ Solo admins/mods pueden guardar favoritos.", ephemeral=True)
            return

        await interaction.response.send_modal(ModalNombreFavorito(self.url))


class ModalNombreFavorito(discord.ui.Modal, title="Guardar favorito"):
    nombre = discord.ui.TextInput(
        label="Nombre de la radio",
        placeholder="Ej: Radio Disney",
        max_length=50
    )

    def __init__(self, url: str):
        super().__init__()
        self.url = url

    async def on_submit(self, interaction: discord.Interaction):
        favs = cargar_favoritos()
        favs[self.nombre.value] = self.url
        guardar_favoritos(favs)
        await interaction.response.send_message(
            f"⭐ **{self.nombre.value}** guardado en favoritos.",
            ephemeral=True
        )


# ── Botones de favoritos ─────────────────────────────────────────
class BotonesFavoritos(discord.ui.View):
    def __init__(self, favs: dict):
        super().__init__(timeout=120)
        for nombre, url in favs.items():
            self.add_item(BotonReproducirFavorito(nombre, url))


class BotonReproducirFavorito(discord.ui.Button):
    def __init__(self, nombre: str, stream_url: str):
        super().__init__(label=f"▶️ {nombre}", style=discord.ButtonStyle.primary, custom_id=f"fav_{nombre}")
        self.stream_url = stream_url

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await reproducir(interaction, self.stream_url, es_interaction=True)


# ── Comandos slash (/play, /stop, /recientes, /favoritos) ────────

@client.tree.command(name="play", description="Reproduce un stream de radio con una URL")
@app_commands.describe(url="URL directa del stream de audio")
async def slash_play(interaction: discord.Interaction, url: str):
    await interaction.response.defer()
    await reproducir(interaction, url, es_interaction=True)


@client.tree.command(name="stop", description="Detiene la radio y desconecta el bot")
async def slash_stop(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        interaction.guild.voice_client.stop()
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("⏹️ Radio detenida.")
    else:
        await interaction.response.send_message("No estoy reproduciendo nada.")


@client.tree.command(name="recientes", description="Muestra las últimas 3 radios reproducidas")
async def slash_recientes(interaction: discord.Interaction):
    if not historial:
        await interaction.response.send_message(f"📭 Todavía no se reprodujo ninguna radio.")
        return
    lineas = ["📻 **Últimas radios:**"]
    for i, url in enumerate(historial, 1):
        lineas.append(f"  `{i}` — {url}")
    await interaction.response.send_message("\n".join(lineas))


@client.tree.command(name="favoritos", description="Muestra los favoritos guardados")
async def slash_favoritos(interaction: discord.Interaction):
    favs = cargar_favoritos()
    if not favs:
        await interaction.response.send_message("📭 No hay favoritos guardados todavía.")
        return
    lineas = ["⭐ **Favoritos:**"]
    for nombre, url in favs.items():
        lineas.append(f"  — **{nombre}**: `{url}`")
    view = BotonesFavoritos(favs)
    await interaction.response.send_message("\n".join(lineas), view=view)


@client.tree.command(name="eliminar_favorito", description="Elimina un favorito (solo admins/mods)")
@app_commands.describe(nombre="Nombre exacto del favorito a eliminar")
async def slash_eliminar_fav(interaction: discord.Interaction, nombre: str):
    if not interaction.user.guild_permissions.manage_channels:
        await interaction.response.send_message("❌ Solo admins/mods pueden eliminar favoritos.", ephemeral=True)
        return
    favs = cargar_favoritos()
    if nombre not in favs:
        await interaction.response.send_message(f"❌ No existe un favorito llamado **{nombre}**.", ephemeral=True)
        return
    del favs[nombre]
    guardar_favoritos(favs)
    await interaction.response.send_message(f"🗑️ Favorito **{nombre}** eliminado.")


@client.tree.command(name="ayuda", description="Muestra los comandos disponibles")
async def slash_ayuda(interaction: discord.Interaction):
    await interaction.response.send_message(HELP_MESSAGE)


# ── Comandos con prefijo ! (misma funcionalidad) ─────────────────

@client.command(name="play", aliases=["p"])
async def prefix_play(ctx, url: str = None):
    if url is None:
        await ctx.send(f"⚠️ Pasá una URL. Ej: `{PREFIX}play http://url-del-stream.mp3`")
        return
    await reproducir(ctx, url, es_interaction=False)


@client.command(name="stop", aliases=["s", "detener"])
async def prefix_stop(ctx):
    if ctx.voice_client:
        ctx.voice_client.stop()
        await ctx.voice_client.disconnect()
        await ctx.send("⏹️ Radio detenida.")
    else:
        await ctx.send("No estoy reproduciendo nada.")


@client.command(name="recientes", aliases=["r"])
async def prefix_recientes(ctx):
    if not historial:
        await ctx.send("📭 Todavía no se reprodujo ninguna radio.")
        return
    lineas = ["📻 **Últimas radios:**"]
    for i, url in enumerate(historial, 1):
        lineas.append(f"  `{i}` — {url}")
    await ctx.send("\n".join(lineas))


@client.command(name="favoritos", aliases=["favs"])
async def prefix_favoritos(ctx):
    favs = cargar_favoritos()
    if not favs:
        await ctx.send("📭 No hay favoritos guardados todavía.")
        return
    lineas = ["⭐ **Favoritos:**"]
    for nombre, url in favs.items():
        lineas.append(f"  — **{nombre}**: `{url}`")
    view = BotonesFavoritos(favs)
    await ctx.send("\n".join(lineas), view=view)


@client.command(name="ayuda", aliases=["h", "commands"])
async def prefix_ayuda(ctx):
    await ctx.send(HELP_MESSAGE)


client.run(TOKEN)
