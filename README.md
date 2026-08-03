# 🎙️ BoomBox — Bot de Radio para Discord

BoomBox es un bot de Discord que reproduce cualquier stream de radio o audio en vivo directamente en un canal de voz. Sin complicaciones, sin listas predefinidas — vos elegís qué escuchar.

---

## ✨ Funcionalidades

- 📻 Reproduce cualquier stream de radio online (MP3, AAC, OGG, etc.)
- ⭐ Guardá tus radios favoritas con nombre personalizado
- 🕐 Historial de las últimas 3 radios reproducidas
- 🔁 Reconexión automática si el stream se corta
- 🎛️ Compatible con comandos slash (`/`) y prefijo (`!`)

---

## 📋 Comandos

| Comando | Descripción |
|---|---|
| `/play <url>` | Reproduce el stream de la URL indicada |
| `/stop` | Detiene la radio y desconecta el bot |
| `/recientes` | Muestra las últimas 3 radios reproducidas |
| `/favoritos` | Muestra los favoritos guardados con botones para reproducir |
| `/eliminar_favorito <nombre>` | Elimina un favorito (solo admins/mods) |
| `/ayuda` | Muestra la ayuda del bot |

> Todos los comandos también funcionan con `!` como prefijo. Ej: `!play <url>`

---

## ⭐ ¿Cómo guardar una radio como favorita?

1. Reproducí una radio con `/play <url>`
2. Tocá el botón **⭐ Guardar favorito** que aparece en la respuesta
3. Escribí el nombre que querés darle
4. Listo — queda guardada permanentemente en `favoritos.json`

---

## 🔍 ¿Dónde encontrar URLs de streams?

1. Entrá a una página de radio online (ej: [myradioenvivo.ar](https://myradioenvivo.ar))
2. Dale play a la radio
3. Abrí DevTools con `F12` o Inspeccionar
4. Andá a la pestaña **Network** y filtrá por **Media**
5. Copiá la URL del stream que aparece

---

## 🛠️ Instalación

### Requisitos
- Python 3.8+
- ffmpeg instalado en el sistema

### Pasos

**1. Clonar el repositorio**
```bash
git clone https://github.com/tu-usuario/boombox-bot.git
cd boombox-bot
```

**2. Instalar dependencias**
```bash
pip install -r requirements.txt
pip install "discord.py[voice]"
```

**3. Instalar ffmpeg**

- Windows: `winget install ffmpeg`
- Linux: `sudo apt install ffmpeg`
- Mac: `brew install ffmpeg`

**4. Configurar el `.env`**
```
DISCORD_TOKEN=tu_token_acá
PREFIX=!
```

**5. Correr el bot**
```bash
python radiobot.py
```

---

## 📁 Estructura del proyecto

```
boombox-bot/
├── radiobot.py       ← código principal
├── favoritos.json    ← favoritos guardados (se crea automáticamente)
├── requirements.txt  ← dependencias
├── .env              ← token y configuración (no subir a GitHub)
└── .gitignore
```

---

## 📄 Licencia

MIT License

---

## 👨‍💻 Author

```
Developed by: **Nicoll Sevillano**  
Year: 2025
```
