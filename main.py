"""
Точка входа: выравнивание бланка по маркерам (с бинаризацией) и вырезка ячеек.
"""

from alignment import align_pdf_form
from rows import extract_cells


def main(
    pdf_path: str = r"examples/3993.pdf",
    aligned_path: str | None = None,
    rows_out_dir: str = "rows_out",
    page_index: int = 0,
    zoom: float = 2.0,
    out_size: tuple = (1654, 2339),
    margin_px: int | None = None,
    debug: bool = False,
) -> None:
    debug_dir: str | None = "debug" if debug else None
    # 1) Загрузка PDF → выравнивание; в файл пишем только для дебага или если нужен aligned_path
    aligned = align_pdf_form(
        pdf_path=pdf_path,
        out_path=aligned_path,
        page_index=page_index,
        zoom=zoom,
        out_size=out_size,
        margin_px=margin_px,
        debug_dir=debug_dir,
    )

    # 2) Вырезка ячеек из выравненного изображения (передаём в памяти)
    extract_cells(aligned_image=aligned, out_dir=rows_out_dir, debug=debug)


if __name__ == "__main__":
    main(
        pdf_path=r"examples/3993.pdf",
        aligned_path=None,  # None = не сохранять aligned; укажи путь для сохранения выравненного листа
        rows_out_dir="rows_out",
        page_index=0,
        zoom=2.0,
        out_size=(1654, 2339),
        margin_px=None,
        debug=False,
    )
