"""Сохранение отладочных изображений."""

from pathlib import Path

import cv2
import numpy as np


def _save_debug_img(debug_dir: Path | None, name: str, img: np.ndarray) -> None:
    """Безопасное сохранение отладочного изображения."""
    if debug_dir is None:
        return
    debug_dir.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(debug_dir / name), img)
