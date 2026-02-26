# Основная логика очистки границ клетки
from __future__ import annotations

import cv2
import numpy as np

from .config import BorderCleanParamsV2
from .image_utils import _binarize_ink, _edge_band_mask, _to_gray_u8


def clean_cell_borders_v2(
    cell_img: np.ndarray,
    params: BorderCleanParamsV2 = BorderCleanParamsV2(),
) -> tuple[np.ndarray, np.ndarray]:
    """
    Усиленная очистка рамок клетки (верх/низ/лево/право), включая толстые и цельные линии.
    Возвращает:
      cleaned_gray: uint8 (фон белый, цифра чёрная)
      cleaned_ink:  uint8 {0,255} (255=чернила)
    """
    gray = _to_gray_u8(cell_img)
    h, w = gray.shape[:2]
    m = min(h, w)

    ink = _binarize_ink(gray)

    band = max(1, int(round(m * params.edge_band_frac)))
    edge_mask = _edge_band_mask(h, w, band)

    # ---------- 1) core цифры строим из ВНУТРЕННЕЙ области (чтобы рамка туда не попала)
    inner = ink.copy()
    inner[:band, :] = 0
    inner[-band:, :] = 0
    inner[:, :band] = 0
    inner[:, -band:] = 0

    k_core = 3 if m >= 24 else 2
    ker_core = cv2.getStructuringElement(cv2.MORPH_RECT, (k_core, k_core))
    core = cv2.morphologyEx(inner, cv2.MORPH_OPEN, ker_core, iterations=1)

    # Поддержка цифры (разрешаем касание с рамкой)
    d = max(1, int(params.support_dilate))
    ker_sup = cv2.getStructuringElement(cv2.MORPH_RECT, (2 * d + 1, 2 * d + 1))
    digit_support = cv2.dilate(core, ker_sup, iterations=1)

    # ---------- 2) извлекаем кандидаты рамки как "длинные линии" в прибрежной зоне
    edge_ink = cv2.bitwise_and(ink, edge_mask)

    k_h = max(7, int(round(w * params.long_line_frac)))
    k_v = max(7, int(round(h * params.long_line_frac)))
    ker_h = cv2.getStructuringElement(cv2.MORPH_RECT, (k_h, 1))
    ker_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, k_v))

    line_h = cv2.morphologyEx(edge_ink, cv2.MORPH_OPEN, ker_h, iterations=1)
    line_v = cv2.morphologyEx(edge_ink, cv2.MORPH_OPEN, ker_v, iterations=1)
    border_lines = cv2.bitwise_or(line_h, line_v)

    # ---------- 3) добиваем "полные полосы" (когда морфология не поймала из-за разрывов)
    border_rc = np.zeros((h, w), np.uint8)

    # строки в верх/низ band
    row_thresh = int(round(params.full_row_frac * w))
    for y in list(range(0, band)) + list(range(h - band, h)):
        if int((ink[y, :] > 0).sum()) >= row_thresh:
            border_rc[y, :] = 255

    # столбцы в лев/прав band
    col_thresh = int(round(params.full_col_frac * h))
    for x in list(range(0, band)) + list(range(w - band, w)):
        if int((ink[:, x] > 0).sum()) >= col_thresh:
            border_rc[:, x] = 255

    border_candidates = cv2.bitwise_or(border_lines, border_rc)

    # ---------- 4) удаляем рамку, но сохраняем всё, что относится к цифре
    # (если цифра касается рамки — её пиксели будут в digit_support)
    remove = cv2.bitwise_and(border_candidates, cv2.bitwise_not(digit_support))
    cleaned_ink = ink.copy()
    cleaned_ink[remove > 0] = 0

    # ---------- 5) дополнительная зачистка: тонкие компоненты у края, не поддержанные цифрой
    if params.cleanup_border_cc:
        num, labels, stats, _ = cv2.connectedComponentsWithStats((cleaned_ink > 0).astype(np.uint8), 8)
        cc_max_th = max(1, int(params.cc_max_thickness))
        cc_min_len = max(3, int(round(m * params.cc_min_len_frac)))
        ds = (digit_support > 0)

        def touches_border(x: int, y: int, ww: int, hh: int) -> bool:
            return x == 0 or y == 0 or (x + ww) >= w or (y + hh) >= h

        for lab in range(1, num):
            x, y, ww, hh, area = stats[lab]
            if area <= 0:
                continue
            if not touches_border(x, y, ww, hh):
                continue

            thick = min(ww, hh)
            leng = max(ww, hh)
            if not (thick <= cc_max_th and leng >= cc_min_len):
                continue

            comp = (labels == lab)
            if int((comp & ds).sum()) > 0:
                continue  # есть поддержка цифры — не трогаем
            cleaned_ink[comp] = 0

    cleaned_gray = np.full_like(gray, 255, dtype=np.uint8)
    cleaned_gray[cleaned_ink > 0] = 0
    return cleaned_gray, cleaned_ink
