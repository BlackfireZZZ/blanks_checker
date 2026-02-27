# rows/line_clean.py
from __future__ import annotations
from pathlib import Path
from typing import Literal
import cv2
import numpy as np


def remove_grid_lines(
    img: np.ndarray,
    min_len_ratio: float = 0.70,
    max_thickness: int = 3,
    close_gaps: int = 1,
    mode: Literal["h", "v", "hv"] = "hv",
    debug_dir: Path | None = None,
) -> np.ndarray:
    """
    Убирает длинные вертикальные/горизонтальные линии (границы клеток) на уровне ROI строки/таблицы.
    Возвращает изображение того же типа (BGR если вход BGR, иначе Gray).

    min_len_ratio: какую долю ширины/высоты должна занимать линия, чтобы считаться "сеткой"
    max_thickness: толщина линии (px), которую считаем сеткой (обычно 1-3)
    close_gaps: закрыть небольшие разрывы в линии (0/1/2)
    mode: какие линии удалять: "h" (только горизонтальные), "v" (только вертикальные), "hv" (оба)
    """
    is_bgr = (img.ndim == 3)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if is_bgr else img.copy()

    # бинаризация: 255 = линии/чернила
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    _, bw = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    h, w = bw.shape[:2]
    k_h = max(9, int(round(w * min_len_ratio)))
    k_v = max(9, int(round(h * min_len_ratio)))

    # можно слегка закрыть разрывы перед детектом линий
    if close_gaps > 0:
        ker_close = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        bw2 = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, ker_close, iterations=close_gaps)
    else:
        bw2 = bw

    # выделяем длинные линии
    ker_h = cv2.getStructuringElement(cv2.MORPH_RECT, (k_h, 1))
    ker_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, k_v))
    line_h = cv2.morphologyEx(bw2, cv2.MORPH_OPEN, ker_h, iterations=1)
    line_v = cv2.morphologyEx(bw2, cv2.MORPH_OPEN, ker_v, iterations=1)

    if mode == "h":
        lines = line_h
    elif mode == "v":
        lines = line_v
    else:
        lines = cv2.bitwise_or(line_h, line_v)

    # Ограничим линии по толщине (если вдруг схватили жирные элементы).
    # Важно: для mode="h" используем мягкий режим (только эрозия), чтобы маска не "расползалась" в цифры.
    t = max(1, int(max_thickness))
    ker_th = cv2.getStructuringElement(cv2.MORPH_RECT, (t, t))
    if mode == "h":
        lines = cv2.erode(lines, ker_th, iterations=1)
    else:
        lines = cv2.dilate(cv2.erode(lines, ker_th, 1), ker_th, 1)

    if debug_dir is not None:
        debug_dir.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(debug_dir / "bw.png"), bw)
        cv2.imwrite(str(debug_dir / "bw2.png"), bw2)
        cv2.imwrite(str(debug_dir / "line_h.png"), line_h)
        cv2.imwrite(str(debug_dir / "line_v.png"), line_v)
        cv2.imwrite(str(debug_dir / "lines_mask.png"), lines)

    # --- digit-safe gate: never inpaint dark ink pixels ---
    p10 = float(np.percentile(gray, 10))
    dark_thr = int(min(220, p10 + 10))
    safe = ((gray >= dark_thr).astype(np.uint8) * 255)
    lines_safe = cv2.bitwise_and(lines, safe)

    if debug_dir is not None:
        cv2.imwrite(str(debug_dir / "lines_safe.png"), lines_safe)
        overlay = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        overlay[lines > 0] = (0, 0, 255)  # red: detected lines mask
        overlay[lines_safe > 0] = (0, 255, 0)  # green: inpaint mask after gate
        cv2.imwrite(str(debug_dir / "overlay_lines.png"), overlay)

    # удаляем линии из исходного gray (инпейнт на малых ROI работает очень неплохо)
    # маска lines_safe: 255 где безопасно инпейнтить (не затрагивает тёмные штрихи цифр)
    cleaned = cv2.inpaint(gray, lines_safe, 1, cv2.INPAINT_TELEA)

    if is_bgr:
        return cv2.cvtColor(cleaned, cv2.COLOR_GRAY2BGR)
    return cleaned
