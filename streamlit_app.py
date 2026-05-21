import os
import sys
import uuid
import subprocess
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

from app.downloader import download_video
from app.processor import process_video, random_preset

TMP_DIR = Path(os.getenv("UNICAL_TMP_DIR", "/tmp/unical"))
ASSETS_DIR = Path(__file__).parent / "assets"
WATERMARK = ASSETS_DIR / "sticker.png"

# ─── Page config ────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="VideoUniq",
    page_icon="◈",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
    #MainMenu, footer, header {visibility: hidden;}

    .block-container {
        padding-top: 2.5rem;
        padding-bottom: 3rem;
        max-width: 680px;
    }

    .vu-title {
        font-size: 2.4rem;
        font-weight: 700;
        letter-spacing: -0.05em;
        color: #FFFFFF;
        line-height: 1;
        margin-bottom: 0;
    }
    .vu-sub {
        font-size: 0.75rem;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        color: #444;
        margin-top: 6px;
        margin-bottom: 2rem;
    }

    div[data-testid="stTabs"] button {
        font-size: 0.8rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }

    .metric-box {
        background: #141414;
        border-radius: 8px;
        padding: 1rem;
        text-align: center;
    }
    .metric-label { font-size: 0.7rem; color: #555; text-transform: uppercase; letter-spacing: 0.1em; }
    .metric-value { font-size: 1.4rem; font-weight: 600; color: #fff; margin-top: 2px; }
    .metric-delta { font-size: 0.75rem; color: #4CAF50; margin-top: 2px; }
</style>
""", unsafe_allow_html=True)

# ─── Session state ───────────────────────────────────────────────────────────

_defaults = {
    "result_bytes": None,
    "size_before_mb": None,
    "size_after_mb": None,
}
for k, v in _defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─── Header ──────────────────────────────────────────────────────────────────

st.markdown('<p class="vu-title">◈ VideoUniq</p>', unsafe_allow_html=True)
st.markdown('<p class="vu-sub">Автоматическая уникализация видео</p>', unsafe_allow_html=True)

# ─── Dependency check ────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def _check_deps() -> dict[str, bool]:
    tools = ["ffmpeg", "ffprobe", "yt-dlp"]
    return {t: subprocess.run(["which", t], capture_output=True).returncode == 0 for t in tools}

_deps = _check_deps()

if not _deps["ffmpeg"] or not _deps["ffprobe"]:
    st.error("**ffmpeg не найден.** Установите: `brew install ffmpeg`")
    st.stop()

_ytdlp_ok = _deps["yt-dlp"]

# ─── Preset controls ─────────────────────────────────────────────────────────

with st.expander("Параметры обработки", expanded=False):
    use_random = st.toggle("Случайный пресет", value=True)

    if not use_random:
        col1, col2 = st.columns(2)
        with col1:
            brightness = st.slider("Яркость", -0.10, 0.10, 0.0, 0.01, format="%.2f")
            contrast = st.slider("Контраст", 0.90, 1.15, 1.02, 0.01, format="%.2f")
            saturation = st.slider("Насыщенность", 0.90, 1.15, 1.02, 0.01, format="%.2f")
        with col2:
            zoom = st.slider("Масштаб", 1.00, 1.06, 1.03, 0.005, format="%.3f")
            fps = st.selectbox("FPS", ["29.97", "25", "23.976", "30"], index=0)
            audio_rate = st.selectbox("Частота аудио (Гц)", [44100, 48000], index=0)

st.markdown("---")


def _make_preset() -> dict:
    if use_random:
        return random_preset()
    return {
        "brightness": brightness,
        "contrast": contrast,
        "saturation": saturation,
        "zoom": zoom,
        "fps": fps,
        "audio_rate": audio_rate,
        "audio_bitrate": "128k",
        "text_x_ratio": 0.10,
        "text_y_ratio": 0.85,
        "text_opacity": 0.15,
    }


def _run(input_path: str, cleanup_input: bool, prog_label: str) -> bool:
    """Core processing logic shared by both tabs."""
    prog = st.progress(0, prog_label)
    try:
        st.session_state.size_before_mb = os.path.getsize(input_path) / (1024 * 1024)
        prog.progress(30, "Обрабатываю видео...")

        wm = str(WATERMARK) if WATERMARK.exists() else None
        out_path = process_video(input_path, watermark_path=wm, preset=_make_preset())

        if cleanup_input:
            os.unlink(input_path)

        prog.progress(85, "Финализирую...")
        st.session_state.size_after_mb = os.path.getsize(out_path) / (1024 * 1024)

        with open(out_path, "rb") as f:
            st.session_state.result_bytes = f.read()
        os.unlink(out_path)

        prog.progress(100, "Готово!")
        return True
    except Exception as exc:
        prog.empty()
        st.error(f"Ошибка: {exc}")
        if cleanup_input and os.path.exists(input_path):
            os.unlink(input_path)
        return False


# ─── Input tabs ──────────────────────────────────────────────────────────────

tab_url, tab_file = st.tabs(["По ссылке", "Загрузить файл"])

with tab_url:
    if not _ytdlp_ok:
        st.warning("yt-dlp не установлен. Установите: `pip3 install yt-dlp`", icon="⚠️")
    url = st.text_input(
        "URL",
        placeholder="https://www.tiktok.com/@user/video/...",
        label_visibility="collapsed",
        disabled=not _ytdlp_ok,
    )
    if st.button("◈ Уникализировать", key="btn_url", use_container_width=True, disabled=not _ytdlp_ok):
        if not url.strip():
            st.warning("Введите ссылку на видео.")
        else:
            st.session_state.result_bytes = None
            TMP_DIR.mkdir(parents=True, exist_ok=True)
            prog = st.progress(0, "Скачиваю видео...")
            try:
                dl_path = download_video(url.strip())
                prog.progress(35, "Видео скачано. Обрабатываю...")
                prog.empty()
                _run(dl_path, cleanup_input=True, prog_label="Обрабатываю...")
            except Exception as exc:
                prog.empty()
                st.error(f"Ошибка загрузки: {exc}")

with tab_file:
    uploaded = st.file_uploader(
        "Видео",
        type=["mp4", "mov", "avi", "mkv", "webm"],
        label_visibility="collapsed",
    )
    if st.button("◈ Уникализировать", key="btn_file", use_container_width=True):
        if not uploaded:
            st.warning("Загрузите видеофайл.")
        else:
            st.session_state.result_bytes = None
            TMP_DIR.mkdir(parents=True, exist_ok=True)
            tmp_input = str(TMP_DIR / f"upload_{uuid.uuid4().hex[:8]}.mp4")
            with open(tmp_input, "wb") as f:
                f.write(uploaded.read())
            _run(tmp_input, cleanup_input=True, prog_label="Обрабатываю...")

# ─── Result ──────────────────────────────────────────────────────────────────

if st.session_state.result_bytes:
    st.markdown("---")

    b = st.session_state.size_before_mb
    a = st.session_state.size_after_mb
    if b and a:
        delta_pct = (a - b) / b * 100 if b else 0
        c1, c2, c3 = st.columns(3)
        c1.markdown(
            f'<div class="metric-box"><div class="metric-label">До</div>'
            f'<div class="metric-value">{b:.1f} МБ</div></div>',
            unsafe_allow_html=True,
        )
        c2.markdown(
            f'<div class="metric-box"><div class="metric-label">После</div>'
            f'<div class="metric-value">{a:.1f} МБ</div></div>',
            unsafe_allow_html=True,
        )
        c3.markdown(
            f'<div class="metric-box"><div class="metric-label">Изменение</div>'
            f'<div class="metric-value">{delta_pct:+.0f}%</div></div>',
            unsafe_allow_html=True,
        )
        st.markdown("<br>", unsafe_allow_html=True)

    st.download_button(
        "⬇ Скачать уникализированное видео",
        data=st.session_state.result_bytes,
        file_name="uniq_video.mp4",
        mime="video/mp4",
        use_container_width=True,
    )

    if st.button("✕ Очистить", use_container_width=True):
        st.session_state.result_bytes = None
        st.session_state.size_before_mb = None
        st.session_state.size_after_mb = None
        st.rerun()
