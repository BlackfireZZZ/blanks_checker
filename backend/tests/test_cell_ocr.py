"""
Скрипт для тестирования cell_ocr: выбирает случайную клетку из rows_out/cells
и выводит путь к файлу и предсказание содержимого.
"""

import random
import sys
from pathlib import Path

import cv2

from app.ocr.cell_ocr import recognize_cell


def find_all_cells(cells_dir: Path) -> list[Path]:
    """Собирает все PNG/JPG файлы клеток рекурсивно."""
    if not cells_dir.is_dir():
        return []
    return sorted([*cells_dir.rglob("*.png"), *cells_dir.rglob("*.jpg"), *cells_dir.rglob("*.jpeg")])


def main(
    cells_dir: str = "rows_out/cells",
    show_image: bool = False,
) -> None:
    base = Path(cells_dir)
    cells = find_all_cells(base)

    if not cells:
        print(f"Клетки не найдены в {base.resolve()}. Сначала запустите main() для вырезки ячеек.")
        sys.exit(1)

    cell_path = random.choice(cells)
    img = cv2.imread(str(cell_path))
    if img is None:
        print(f"Не удалось загрузить изображение: {cell_path}")
        sys.exit(1)

    pred = recognize_cell(img, weights_path=None)

    try:
        rel = cell_path.relative_to(base)
    except ValueError:
        rel = cell_path
    print(f"Клетка: {rel}")
    print(f"Предсказание: {repr(pred)}")
    if pred == "E":
        print("(пустая клетка)")

    if show_image:
        title = f"Клетка: {cell_path.name} -> {pred}"
        cv2.imshow(title, img)
        print("Нажмите любую клавишу в окне изображения для выхода.")
        cv2.waitKey(0)
        cv2.destroyAllWindows()


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Тест OCR на случайной клетке из rows_out/cells")
    p.add_argument("--cells-dir", default="rows_out/cells", help="Каталог с подкаталогами клеток (PNG/JPG)")
    p.add_argument("--seed", type=int, default=None, help="Seed для random (для воспроизводимости)")
    p.add_argument("--show", action="store_true", help="Показать изображение клетки в окне")
    args = p.parse_args()
    if args.seed is not None:
        random.seed(args.seed)
    main(cells_dir=args.cells_dir, show_image=args.show)
