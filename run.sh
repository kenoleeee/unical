#!/usr/bin/env bash
set -e

echo ""
echo "  ◈ VideoUniq"
echo "  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check required system tools
for tool in ffmpeg ffprobe; do
    if ! command -v "$tool" &>/dev/null; then
        echo "  ✗ $tool не найден. Установите: brew install ffmpeg"
        exit 1
    fi
done

if ! command -v yt-dlp &>/dev/null; then
    echo "  ✗ yt-dlp не найден. Установите: pip install yt-dlp"
    exit 1
fi

# Install Python dependencies
if ! python3 -c "import streamlit" &>/dev/null; then
    echo "  → Устанавливаю зависимости..."
    pip install -q -r requirements.txt
fi

# Generate sticker if missing
if [ ! -f "assets/sticker.png" ]; then
    echo "  → Генерирую логотип..."
    python3 assets/generate_sticker.py
fi

mkdir -p /tmp/unical

MODE="${1:-ui}"

case "$MODE" in
    api)
        echo "  → FastAPI запущен: http://localhost:8000"
        echo "  → Документация:    http://localhost:8000/docs"
        echo ""
        uvicorn app.api:app --host 0.0.0.0 --port 8000 --reload
        ;;
    both)
        echo "  → FastAPI:    http://localhost:8000"
        echo "  → Streamlit:  http://localhost:8501"
        echo ""
        uvicorn app.api:app --host 0.0.0.0 --port 8000 &
        API_PID=$!
        trap "kill $API_PID 2>/dev/null" EXIT
        streamlit run streamlit_app.py --server.port 8501
        ;;
    *)
        echo "  → Streamlit: http://localhost:8501"
        echo ""
        streamlit run streamlit_app.py --server.port 8501 --server.headless true &
        SL_PID=$!
        sleep 2 && open http://localhost:8501
        wait $SL_PID
        ;;
esac
