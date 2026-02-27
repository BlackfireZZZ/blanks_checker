"""Выравнивание бланка по чёрным маркерам."""

from pathlib import Path

import cv2
import numpy as np

from app.services.pdf_loader import pdf_page_to_bgr
from app.alignment.markers import detect_black_square_markers
from app.alignment.warp import warp_keep_full_page


def align_form_from_image(
    img_bgr: np.ndarray,
    out_size: tuple[int, int] = (1654, 2339),
    margin_px: int | None = None,
    debug_dir: str | Path | None = None,
) -> np.ndarray:
    """
    Выравнивает уже загруженное изображение страницы по маркерам.
    Запись на диск только если передан debug_dir.
    """
    centers4, avg_side = detect_black_square_markers(
        img_bgr, roi_frac=0.28, debug_dir=debug_dir
    )
    if margin_px is None:
        margin_px = max(40, int(avg_side * 2.0))
    aligned = warp_keep_full_page(
        img_bgr, centers4, out_size=out_size, margin_px=margin_px
    )
    if debug_dir is not None:
        Path(debug_dir).mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(Path(debug_dir) / "aligned_raw.png"), aligned)
    return aligned


def align_pdf_form(
    pdf_path: str,
    out_path: str | None = None,
    page_index: int = 0,
    zoom: float = 2.0,
    out_size=(1654, 2339),
    margin_px: int | None = None,
    debug_dir: str | Path | None = None,
) -> np.ndarray:
    """
    Загружает страницу PDF, выравнивает по маркерам, возвращает изображение.

    Файл пишется только если передан out_path (дебаг или конечный вывод).
    ВАЖНО: здесь НЕ делаем preprocess_for_blocks(), потому что он убивает линии сетки.
    Предобработку (бинаризацию/линии) делаем локально в rows.py.
    """
    img = pdf_page_to_bgr(pdf_path, page_index=page_index, zoom=zoom)
    aligned = align_form_from_image(
        img,
        out_size=out_size,
        margin_px=margin_px,
        debug_dir=debug_dir,
    )
    if out_path is not None:
        cv2.imwrite(out_path, aligned)
        print(f"OK: {out_path} (margin_px={margin_px})")
    if debug_dir is not None:
        print(f"Debug: {Path(debug_dir).resolve()}")
    return aligned
