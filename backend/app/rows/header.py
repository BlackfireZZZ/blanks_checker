"""Вырезка области клеток из заголовочных полей (вариант, дата, рег.номер)."""

from pathlib import Path

import cv2
import numpy as np

from app.rows.debug_utils import _save_debug_img
from app.rows.line_clean import remove_grid_lines
from app.rows.morphology import _adaptive_inv, _largest_rect_like_component


def crop_to_grid_only(
    img_bgr: np.ndarray,
    debug_dir: Path | None = None,
) -> np.ndarray:
    """
    Для заголовочных полей: из грубого ROI вырезаем ТОЛЬКО область клеток
    по внешней рамке прямоугольника.
    """
    _save_debug_img(debug_dir, "roi_raw.png", img_bgr)

    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    bw = _adaptive_inv(gray)
    _save_debug_img(debug_dir, "roi_bw_inv.png", bw)

    bbox = _largest_rect_like_component(bw)
    if bbox is None:
        return img_bgr

    x, y, w, h = bbox

    dbg_vis = img_bgr.copy()
    cv2.rectangle(dbg_vis, (x, y), (x + w, y + h), (0, 0, 255), 1)
    _save_debug_img(debug_dir, "roi_grid_bbox.png", dbg_vis)

    pad = 2
    x1 = max(0, x + pad)
    y1 = max(0, y + pad)
    x2 = min(img_bgr.shape[1], x + w - pad)
    y2 = min(img_bgr.shape[0], y + h - pad)

    if x2 <= x1 or y2 <= y1:
        return img_bgr

    crop = img_bgr[y1:y2, x1:x2].copy()

    _save_debug_img(debug_dir, "roi_grid_only_raw.png", crop)

    # прибиваем вертикальные/горизонтальные линии сетки на уровне всего поля
    crop = remove_grid_lines(crop, min_len_ratio=0.65, max_thickness=3, close_gaps=1)

    _save_debug_img(debug_dir, "roi_grid_only_cleaned.png", crop)

    return crop
