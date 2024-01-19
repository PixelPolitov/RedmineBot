# Устанавливаем базовый образ
FROM python:3.11-slim-bullseye

# Устанавливаем рабочую директорию
WORKDIR /bot
# Копируем зависимости
COPY requirements.txt .
# Обновляем pip
RUN pip install --upgrade pip
# Устанавливаем зависимости
RUN pip install -r requirements.txt
# Копируем все файлы
COPY . .
# Открываем порт 5000 для сервера вебхуков
EXPOSE 5000
