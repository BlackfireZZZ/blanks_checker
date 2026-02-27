"""Морфология и поиск линий на бинаризованных изображениях."""

import cv2
import numpy as np


def _adaptive_inv(gray: np.ndarray) -> np.ndarray:
    """Адаптивная бинаризация: линии/текст -> белые (255) на чёрном фоне."""
    return cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_MEAN_C,
        cv2.THRESH_BINARY_INV,
        31,
        10,
    )


def _extract_lines(bw_inv: np.ndarray, axis: str) -> np.ndarray:
    """Достаём протяжённые линии (горизонтальные или вертикальные) морфологией."""
    h, w = bw_inv.shape[:2]
    if axis == "h":
        k = max(25, w // 18)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k, 1))
    elif axis == "v":
        k = max(25, h // 18)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, k))
    else:
        raise ValueError("axis must be 'h' or 'v'")

    out = cv2.erode(bw_inv, kernel, iterations=1)
    out = cv2.dilate(out, kernel, iterations=2)
    return out


def _group_peaks(idx: np.ndarray, max_gap: int = 4) -> list[int]:
    """Группируем соседние индексы в один пик, возвращаем центры групп."""
    if len(idx) == 0:
        return []
    groups: list[tuple[int, int]] = []
    start = int(idx[0])
    prev = int(idx[0])
    for v in idx[1:]:
        v = int(v)
        if v - prev > max_gap:
            groups.append((start, prev))
            start = v
        prev = v
    groups.append((start, prev))
    return [int((a + b) / 2) for a, b in groups]


def _find_line_centers_1d(proj: np.ndarray, thr_rel: float = 0.45, max_gap: int = 6) -> list[int]:
    """По 1D-проекции ищем центры линий (пики)."""
    m = float(proj.max())
    if m <= 0:
        return []
    thr = m * thr_rel
    idx = np.where(proj >= thr)[0]
    return _group_peaks(idx, max_gap=max_gap)


def _largest_rect_like_component(bw_inv: np.ndarray) -> tuple[int, int, int, int] | None:
    """
    Ищем самый подходящий "прямоугольник рамки" внутри ROI.
    Возвращает bbox (x,y,w,h) или None.
    bw_inv: белое=объекты (линии/текст), чёрное=фон.
    """
    h, w = bw_inv.shape[:2]

    # Усиливаем именно рамку: соединяем разрывы и делаем контуры связными
    k_close = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    blob = cv2.morphologyEx(bw_inv, cv2.MORPH_CLOSE, k_close, iterations=2)

    # Убираем мелочь (цифры, мусор)
    k_open = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    blob = cv2.morphologyEx(blob, cv2.MORPH_OPEN, k_open, iterations=1)

    contours, _ = cv2.findContours(blob, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    roi_area = float(h * w)
    best_bbox = None
    best_score = -1e18

    for c in contours:
        x, y, ww, hh = cv2.boundingRect(c)
        area = float(ww * hh)
        if area < roi_area * 0.20:   # слишком маленькое — не рамка
            continue
        if area > roi_area * 0.98:   # почти весь ROI — часто фон/ошибка
            continue

        aspect = ww / float(max(1, hh))

        # "прямоугольность": насколько контур заполняет свой bbox
        cnt_area = float(cv2.contourArea(c))
        fill = cnt_area / float(max(1.0, area))

        # рамка — длинный прямоугольник, fill не должен быть совсем маленьким
        if fill < 0.10:
            continue
        if aspect < 1.3:  # чуть мягче, чтобы "variant" тоже уверенно ловился
            continue

        # штрафуем компоненты, которые сильно не касаются краёв ROI (рамка обычно близко к границам crop)
        margin = min(x, y, w - (x + ww), h - (y + hh))
        score = area + 2500.0 * fill - 600.0 * margin

        if score > best_score:
            best_score = score
            best_bbox = (x, y, ww, hh)

    return best_bbox


def _extract_vertical_separators(bw_inv: np.ndarray, min_len_ratio: float = 0.78) -> np.ndarray:
    """
    Вытаскиваем ТОЛЬКО вертикальные разделители, которые проходят большую часть высоты.
    Это фильтрует цифры (например '1'), потому что они не тянутся на ~80% высоты строки.
    """
    h, _ = bw_inv.shape[:2]
    k = max(9, int(h * min_len_ratio))
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, k))
    out = cv2.erode(bw_inv, kernel, iterations=1)
    out = cv2.dilate(out, kernel, iterations=2)
    return out
