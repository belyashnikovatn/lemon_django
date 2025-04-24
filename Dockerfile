# Используем официальный Python образ
FROM python:3.9-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файл зависимостей
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код проекта
COPY . .

# Открываем порт, на котором будет работать сервер
EXPOSE 8000

# Команда для запуска Django
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
