"""Перспективное преобразование по маркерам."""

import cv2
import numpy as np

from app.alignment.markers import order_points


def warp_keep_full_page(
    img_bgr: np.ndarray,
    marker_centers4: np.ndarray,
    out_size=(1654, 2339),
    margin_px: int = 90,
) -> np.ndarray:
    """
    SRC: центры маркеров на изображении.
    DST: центры маркеров в шаблоне с отступом margin_px от края.
    """
    w, h = out_size
    src = order_points(marker_centers4)

    dst = np.array(
        [
            [margin_px, margin_px],
            [w - 1 - margin_px, margin_px],
            [w - 1 - margin_px, h - 1 - margin_px],
            [margin_px, h - 1 - margin_px],
        ],
        dtype=np.float32,
    )

    M = cv2.getPerspectiveTransform(src, dst)
    return cv2.warpPerspective(img_bgr, M, (w, h), flags=cv2.INTER_CUBIC)
