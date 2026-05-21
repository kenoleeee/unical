import os
import uuid
import threading
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .downloader import download_video
from .processor import process_video

TMP_DIR = Path(os.getenv("UNICAL_TMP_DIR", "/tmp/unical"))
WATERMARK = Path(os.getenv("UNICAL_ASSETS_DIR", "assets")) / "sticker.png"

_tasks: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    yield
    for task in _tasks.values():
        path = task.get("output_path")
        if path and os.path.exists(path):
            os.unlink(path)


app = FastAPI(
    title="VideoUniq API",
    description="Автоматическая уникализация видео",
    version="1.0.0",
    lifespan=lifespan,
)


class ProcessURLRequest(BaseModel):
    url: str


@app.post("/api/process/url", summary="Обработать видео по ссылке")
async def process_from_url(request: ProcessURLRequest):
    task_id = uuid.uuid4().hex
    _tasks[task_id] = {"status": "pending"}
    threading.Thread(target=_run_url_task, args=(task_id, request.url), daemon=True).start()
    return {"task_id": task_id, "status": "pending"}


@app.post("/api/process/file", summary="Обработать загруженный файл")
async def process_from_file(file: UploadFile = File(...)):
    task_id = uuid.uuid4().hex
    input_path = str(TMP_DIR / f"upload_{task_id[:8]}.mp4")
    TMP_DIR.mkdir(parents=True, exist_ok=True)

    content = await file.read()
    with open(input_path, "wb") as f:
        f.write(content)

    _tasks[task_id] = {"status": "pending"}
    threading.Thread(target=_run_file_task, args=(task_id, input_path), daemon=True).start()
    return {"task_id": task_id, "status": "pending"}


@app.get("/api/status/{task_id}", summary="Статус задачи")
async def get_status(task_id: str):
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(404, detail="Задача не найдена")

    out = {"task_id": task_id, "status": task["status"]}
    if task["status"] == "error":
        out["error"] = task.get("error", "Неизвестная ошибка")
    if task["status"] == "done":
        out["file_size_mb"] = task.get("file_size_mb")
    return out


@app.get("/api/download/{task_id}", summary="Скачать обработанное видео")
async def download_result(task_id: str):
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(404, detail="Задача не найдена")
    if task["status"] != "done":
        raise HTTPException(400, detail=f"Статус задачи: {task['status']}")

    path = task["output_path"]
    if not os.path.exists(path):
        raise HTTPException(410, detail="Файл больше не доступен")

    return FileResponse(path, filename="uniq_video.mp4", media_type="video/mp4")


@app.delete("/api/task/{task_id}", summary="Удалить задачу и файл")
async def delete_task(task_id: str):
    task = _tasks.pop(task_id, None)
    if task:
        path = task.get("output_path")
        if path and os.path.exists(path):
            os.unlink(path)
    return {"deleted": task_id}


@app.get("/api/tasks", summary="Список активных задач")
async def list_tasks():
    return [
        {"task_id": tid, "status": t["status"]}
        for tid, t in _tasks.items()
    ]


def _wm_path() -> Optional[str]:
    return str(WATERMARK) if WATERMARK.exists() else None


def _run_url_task(task_id: str, url: str):
    try:
        _tasks[task_id]["status"] = "downloading"
        dl_path = download_video(url)

        _tasks[task_id]["status"] = "processing"
        out_path = process_video(dl_path, watermark_path=_wm_path())
        os.unlink(dl_path)

        size_mb = round(os.path.getsize(out_path) / (1024 * 1024), 2)
        _tasks[task_id].update({"status": "done", "output_path": out_path, "file_size_mb": size_mb})
    except Exception as e:
        _tasks[task_id].update({"status": "error", "error": str(e)})


def _run_file_task(task_id: str, input_path: str):
    try:
        _tasks[task_id]["status"] = "processing"
        out_path = process_video(input_path, watermark_path=_wm_path())
        os.unlink(input_path)

        size_mb = round(os.path.getsize(out_path) / (1024 * 1024), 2)
        _tasks[task_id].update({"status": "done", "output_path": out_path, "file_size_mb": size_mb})
    except Exception as e:
        if os.path.exists(input_path):
            os.unlink(input_path)
        _tasks[task_id].update({"status": "error", "error": str(e)})
