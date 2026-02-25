"""
Точка входа: выравнивание бланка по маркерам (с бинаризацией) и вырезка ячеек.
"""

from alignment import align_pdf_form
from rows import extract_cells


def main(
    pdf_path: str = r"examples/3993.pdf",
    aligned_path: str = "aligned.png",
    rows_out_dir: str = "rows_out",
    page_index: int = 0,
    zoom: float = 2.0,
    out_size: tuple = (1654, 2339),
    margin_px: int | None = None,
    debug_dir: str | None = "debug",
) -> None:
    # 1) Загрузка PDF → бинаризация → выравнивание → сохранение
    align_pdf_form(
        pdf_path=pdf_path,
        out_path=aligned_path,
        page_index=page_index,
        zoom=zoom,
        out_size=out_size,
        margin_px=margin_px,
        debug_dir=debug_dir,
    )

    # 2) Вырезка ячеек из выравненного (уже бинаризованного) изображения
    extract_cells(aligned_path=aligned_path, out_dir=rows_out_dir)


if __name__ == "__main__":
    main(
        pdf_path=r"examples/3993.pdf",
        aligned_path="aligned.png",
        rows_out_dir="rows_out",
        page_index=0,
        zoom=2.0,
        out_size=(1654, 2339),
        margin_px=None,
        debug_dir="debug",
    )
