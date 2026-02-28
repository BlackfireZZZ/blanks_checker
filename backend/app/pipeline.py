"""
Точка входа: выравнивание бланка по маркерам и вырезка ячеек.
CLI использует in-memory пайплайн (по умолчанию ничего не пишет на диск).
"""

from pathlib import Path

from app.alignment.align import align_pdf_form
from app.rows.extract import extract_cells
from app.services.pipeline import run_blanks_pipeline


def main(
    pdf_path: str = r"examples/3993.pdf",
    aligned_path: str | None = None,
    rows_out_dir: str = "rows_out",
    page_index: int = 0,
    zoom: float = 2.0,
    out_size: tuple = (1654, 2339),
    margin_px: int | None = None,
    debug: bool = False,
    weights_path: str | None = None,
) -> dict | None:
    """
    Читает PDF с диска, запускает in-memory пайплайн, возвращает результат.
    При aligned_path или rows_out_dir дополнительно пишет файлы (для обратной совместимости).
    """
    path = Path(pdf_path)
    if not path.is_file():
        raise FileNotFoundError(f"PDF не найден: {pdf_path}")
    pdf_bytes = path.read_bytes()

    result = run_blanks_pipeline(
        pdf_bytes,
        page_index=page_index,
        zoom=zoom,
        out_size=out_size,
        margin_px=margin_px,
        debug=debug,
        weights_path=weights_path,
    )

    if aligned_path is not None or rows_out_dir is not None:
        debug_dir = "debug" if debug else None
        aligned = align_pdf_form(
            pdf_path=pdf_path,
            out_path=aligned_path,
            page_index=page_index,
            zoom=zoom,
            out_size=out_size,
            margin_px=margin_px,
            debug_dir=debug_dir,
        )
        extract_cells(aligned_image=aligned, out_dir=rows_out_dir, debug=debug)

    return result


if __name__ == "__main__":
    import json
    res = main(
        pdf_path=r"examples/1410.pdf",
        aligned_path=None,
        rows_out_dir="rows_out",
        page_index=0,
        zoom=2.0,
        out_size=(1654, 2339),
        margin_px=None,
        debug=False,
    )
    if res is not None:
        print(json.dumps(res, ensure_ascii=False, indent=2))
