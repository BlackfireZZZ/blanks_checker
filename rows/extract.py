"""Оркестрация: вырезка заголовков, строк и клеток с выравненного бланка."""

from pathlib import Path

import cv2
import numpy as np

from image_utils import crop_rel

from rows.config import FIELD_NCELLS, HEADER_ROIS, TABLE_ROIS
from rows.header import crop_to_grid_only
from rows.grid import detect_rows_by_grid
from rows.line_clean import remove_grid_lines
from rows.cells import split_cells, _save_cells_list
from rows.debug_utils import _save_debug_img


def extract_cells(
    aligned_image: np.ndarray | None = None,
    aligned_path: str | None = None,
    out_dir: str = "rows_out",
    debug: bool = False,
) -> None:
    """
    Вырезает заголовочные поля и строки из выравненного изображения, режет на клетки.

    Изображение передаётся либо в памяти (aligned_image), либо загружается по aligned_path.
    Файловая система — только для вывода в out_dir и для дебага.
    """
    if aligned_image is not None:
        img = aligned_image
    elif aligned_path is not None:
        img = cv2.imread(aligned_path)
        if img is None:
            raise FileNotFoundError(f"Не могу прочитать {aligned_path}")
    else:
        raise ValueError("Нужен aligned_image или aligned_path")

    out_dir_p = Path(out_dir)
    out_dir_p.mkdir(parents=True, exist_ok=True)

    cells_out = out_dir_p / "cells"
    cells_out.mkdir(parents=True, exist_ok=True)

    debug_base = (out_dir_p / "_debug_grid") if debug else None
    header_debug_base = (out_dir_p / "_debug_header") if debug else None

    # --- Заголовки: вариант/дата/рег.номер -> только клетки + нарезка ---
    header_imgs: dict[str, np.ndarray] = {}

    for name, (x1, y1, x2, y2) in HEADER_ROIS.items():
        crop = crop_rel(img, x1, y1, x2, y2)

        header_key = Path(name).stem  # variant/date/reg_number
        header_debug_dir = (header_debug_base / header_key) if header_debug_base else None
        crop_cells = crop_to_grid_only(crop, debug_dir=header_debug_dir)

        cv2.imwrite(str(out_dir_p / name), crop_cells)
        header_imgs[header_key] = crop_cells

        n = FIELD_NCELLS[header_key]
        dbg = (header_debug_dir / "cells") if header_debug_dir else None
        cells = split_cells(crop_cells, n_cells=n, debug_dir=dbg)
        _save_cells_list(cells, cells_out / header_key, prefix=header_key)

    # --- Строки ответов/замен: bbox -> crop -> нарезка 9 клеток ---
    left_rows = detect_rows_by_grid(img, TABLE_ROIS["answers"], debug_dir=debug_base / "left" if debug_base else None)
    right_rows = detect_rows_by_grid(img, TABLE_ROIS["repl"], debug_dir=debug_base / "right" if debug_base else None)

    n_row_cells = FIELD_NCELLS["answers"]

    for i, bbox in enumerate(left_rows, start=1):
        x, y, w, h = bbox
        row_img = img[y : y + h, x : x + w].copy()
        row_debug_dir = (debug_base / "left" / f"row_{i:02d}") if debug_base else None
        _save_debug_img(row_debug_dir, "row_raw.png", row_img)

        row_img = remove_grid_lines(row_img, min_len_ratio=0.75, max_thickness=3, close_gaps=1)
        _save_debug_img(row_debug_dir, "row_cleaned.png", row_img)

        cv2.imwrite(str(out_dir_p / f"answers_{i:02d}.png"), row_img)

        dbg = (debug_base / "left" / f"row_{i:02d}" / "cells") if debug_base else None
        cells = split_cells(row_img, n_cells=n_row_cells, debug_dir=dbg)
        _save_cells_list(cells, cells_out / "answers" / f"{i:02d}", prefix=f"answers_{i:02d}")

    for i, bbox in enumerate(right_rows, start=1):
        x, y, w, h = bbox
        row_img = img[y : y + h, x : x + w].copy()
        row_debug_dir = (debug_base / "right" / f"row_{i:02d}") if debug_base else None
        _save_debug_img(row_debug_dir, "row_raw.png", row_img)

        row_img = remove_grid_lines(row_img, min_len_ratio=0.75, max_thickness=3, close_gaps=1)
        _save_debug_img(row_debug_dir, "row_cleaned.png", row_img)

        cv2.imwrite(str(out_dir_p / f"repl_{i:02d}.png"), row_img)

        dbg = (debug_base / "right" / f"row_{i:02d}" / "cells") if debug_base else None
        cells = split_cells(row_img, n_cells=n_row_cells, debug_dir=dbg)
        _save_cells_list(cells, cells_out / "repl" / f"{i:02d}", prefix=f"repl_{i:02d}")

    print(f"OK: строки и клетки сохранены в {out_dir_p.resolve()}")
