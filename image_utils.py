"""Бинаризация и обрезка изображений."""

import cv2
import numpy as np


def binarize_image(img_bgr: np.ndarray) -> np.ndarray:
    """
    Бинаризация изображения (в т.ч. со скан-оттенками серого).
    Возвращает BGR с одинаковыми каналами 0/255 для совместимости с остальным кодом.
    """
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, binary = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)


def preprocess_for_blocks(img_bgr: np.ndarray) -> np.ndarray:
    """
    Предобработка для закрытия непропечатанного текста и пунктирных контуров.
    Бинаризация, раздутие, закрытие; на выходе — чёрное на белом (0/255), как для пайплайна.
    """
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    # 1) Бинаризация (инвертируем — линии белые)
    bw = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_MEAN_C,
        cv2.THRESH_BINARY_INV,
        51, 10
    )

    # 2) Минимальное раздутие (только точечные разрывы)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    bw = cv2.dilate(bw, kernel, iterations=1)

    # 3) Закрытие очень мелких дыр
    bw = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))

    # 4) Инвертируем в конвенцию «чёрное на белом», как ожидает пайплайн (rows.py)
    bw = cv2.bitwise_not(bw)
    return bw


def crop_rel(img: np.ndarray, x1: float, y1: float, x2: float, y2: float) -> np.ndarray:
    """Обрезка по относительным координатам [0..1]."""
    h, w = img.shape[:2]
    X1 = int(round(x1 * w))
    Y1 = int(round(y1 * h))
    X2 = int(round(x2 * w))
    Y2 = int(round(y2 * h))
    X1, Y1 = max(0, X1), max(0, Y1)
    X2, Y2 = min(w, X2), min(h, Y2)
    return img[Y1:Y2, X1:X2].copy()
