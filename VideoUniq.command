#!/bin/bash
# Double-click this file to launch VideoUniq

cd ~/unical

# Kill old instance if already running
OLD=$(lsof -ti tcp:8501 2>/dev/null)
[ -n "$OLD" ] && kill "$OLD" 2>/dev/null && sleep 1

# Generate sticker if missing
[ ! -f assets/sticker.png ] && python3 assets/generate_sticker.py

# Start and open browser
streamlit run streamlit_app.py \
    --server.port 8501 \
    --server.headless true \
    --browser.gatherUsageStats false \
    >/dev/null 2>&1 &

sleep 2
open http://localhost:8501

echo "VideoUniq запущен → http://localhost:8501"
echo "Закройте это окно — сервер продолжит работать."
echo "Чтобы остановить: lsof -ti tcp:8501 | xargs kill"
