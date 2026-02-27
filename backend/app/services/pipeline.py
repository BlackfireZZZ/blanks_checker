"""
End-to-end blanks pipeline: PDF bytes -> structured recognition result in memory.
"""

from pathlib import Path
from typing import Any

from app.services.pdf_loader import pdf_bytes_to_bgr
from app.alignment.align import align_form_from_image
from app.rows.extract import extract_cells_to_result
from app.ocr.cell_ocr import recognize_cell

# Valid symbols from recognize_cell: E, -, 0-9. Anything else -> S (skip/comma/dot/unreadable).
VALID_SYMBOLS = frozenset("E-" + "0123456789")


def _cell_to_symbol(cell_img, weights_path=None, debug: bool = False) -> str:
    raw = recognize_cell(
        cell_img,
        weights_path=weights_path,
        debug=debug,
        debug_out_dir=None,
    )
    return raw if raw in VALID_SYMBOLS else "S"


def run_blanks_pipeline(
    pdf_bytes: bytes,
    page_index: int = 0,
    zoom: float = 2.0,
    out_size: tuple[int, int] = (1654, 2339),
    margin_px: int | None = None,
    debug: bool = False,
    weights_path: str | Path | None = None,
) -> dict[str, Any]:
    """
    Запускает пайплайн полностью в памяти: PDF bytes -> структурированный результат.

    Возвращает:
        variant: list[str] (4 символа)
        date: list[str] (8)
        reg_number: list[str] (8)
        answers: list[list[str]] (10 строк по 9 символов)
        repl: list[list[str]] (10 строк по 9 символов)

    Символы: E (пусто), - (минус), 0-9, S (запятая/точка/нечитаемое).
    """
    img_bgr = pdf_bytes_to_bgr(pdf_bytes, page_index=page_index, zoom=zoom)
    debug_dir = None  # in-memory: never write by default
    aligned = align_form_from_image(
        img_bgr,
        out_size=out_size,
        margin_px=margin_px,
        debug_dir=debug_dir,
    )
    result_cells = extract_cells_to_result(aligned, debug=debug)

    def run_ocr(cells_list, debug_ocr=False):
        return [
            _cell_to_symbol(c, weights_path=weights_path, debug=debug_ocr)
            for c in cells_list
        ]

    variant = run_ocr(result_cells["variant"], debug_ocr=debug)
    date = run_ocr(result_cells["date"], debug_ocr=debug)
    reg_number = run_ocr(result_cells["reg_number"], debug_ocr=debug)
    answers = [run_ocr(row, debug_ocr=debug) for row in result_cells["answers"]]
    repl = [run_ocr(row, debug_ocr=debug) for row in result_cells["repl"]]

    return {
        "variant": variant,
        "date": date,
        "reg_number": reg_number,
        "answers": answers,
        "repl": repl,
    }
