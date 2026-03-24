FROM python:3.11-slim

WORKDIR /app

# Установка системных зависимостей для корректной работы библиотек
RUN apt-get update && apt-get install -y \
    build-essential \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Создание папки для загрузок, если её нет
RUN mkdir -p downloads

CMD ["python", "main.py"]
