# 1. Usar una imagen base oficial de Python. 'slim' es más ligera.
FROM python:3.10-slim-bullseye

# 2. Establecer el directorio de trabajo dentro del contenedor
WORKDIR /app

# 3. Instalar dependencias del sistema si fueran necesarias (DeepFace a veces las necesita)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsm6 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

# 4. Copiar solo el archivo de requerimientos para aprovechar el caché de Docker
COPY requirements.txt .

# 5. Instalar las librerías de Python
# --no-cache-dir hace la imagen un poco más pequeña
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copiar el resto del código de la aplicación al directorio de trabajo
COPY . .

# 7. Exponer el puerto en el que correrá la aplicación dentro del contenedor
EXPOSE 5001

# 8. El comando para iniciar la aplicación en producción usando Gunicorn
# Se usa '0.0.0.0' para que sea accesible desde fuera del contenedor.
CMD ["gunicorn", "--worker-class", "gevent", "--workers", "1", "--threads", "8", "--timeout", "120", "--bind", "0.0.0.0:5001", "app:app"]