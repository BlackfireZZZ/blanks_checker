# Утилиты: градации серого, бинаризация, маски
from __future__ import annotations

import cv2
import numpy as np


def _to_gray_u8(img: np.ndarray) -> np.ndarray:
    if img.ndim == 2:
        g = img
    else:
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if g.dtype != np.uint8:
        g = cv2.normalize(g, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    return g


def _binarize_ink(gray: np.ndarray) -> np.ndarray:
    """
    255 = чернила (abs_thr + bg-delta). Без MORPH_OPEN 2×2 — он съедает тонкую '1'.
    Удаляем только компоненты площади <= 2 (микроточки).
    """
    g = gray.astype(np.uint8)
    g = cv2.GaussianBlur(g, (3, 3), 0)

    p80 = float(np.percentile(g, 80))
    p90 = float(np.percentile(g, 90))
    bg = 0.5 * p80 + 0.5 * p90

    abs_thr = 70
    delta = 55
    rel_thr = max(0.0, bg - delta)

    ink = ((g <= abs_thr) | (g <= rel_thr)).astype(np.uint8) * 255

    # НЕ делаем morphology open 2x2 — убивает '1'. Убираем только микроточки по площади
    cc = (ink > 0).astype(np.uint8)
    num, labels, stats, _ = cv2.connectedComponentsWithStats(cc, 8)
    out = ink.copy()
    for i in range(1, num):
        if stats[i, cv2.CC_STAT_AREA] <= 2:
            out[labels == i] = 0
    return out


def _edge_band_mask(h: int, w: int, band: int) -> np.ndarray:
    m = np.zeros((h, w), np.uint8)
    if band <= 0:
        return m
    m[:band, :] = 255
    m[-band:, :] = 255
    m[:, :band] = 255
    m[:, -band:] = 255
    return m
