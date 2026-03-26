FROM python:3.13-slim

# Instalar ffmpeg
RUN apt-get update && apt-get install -y ffmpeg && apt-get clean

# Carpeta de trabajo
WORKDIR /app

# Copiar todo
COPY . .

# Instalar dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Ejecutar bot
CMD ["python", "radiobot.py"]