#!/bin/sh

# Авторизация
ngrok config add-authtoken "$NGROK_AUTHTOKEN"

# Запуск в фоне
ngrok http --host-header=rewrite django:8000 &

# Ждём запуск API ngrok
sleep 5

# Получаем URL
NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | grep -o 'https://[^"]*' | head -n 1)

echo "🌍 Public ngrok URL: $NGROK_URL"

# Чтобы контейнер не завершался
tail -f /dev/null
