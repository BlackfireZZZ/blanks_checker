"""
Оценка качества cell_ocr по разметке.
- S = не участвует в оценке (skip)
- E = клетка должна быть пустой (empty)
- Цифра или '-' = ожидаемое значение

Метрики: с пустыми клетками и без; отдельно — ошибки в пустых клетках.
"""

from collections import defaultdict
from pathlib import Path

import cv2

from cell_ocr import CellRecognizer, MnistDigitClassifier


def _norm_pred(pred: str | None) -> str:
    """Приводим предсказание к одному символу: пусто -> 'E', иначе строка."""
    if pred is None:
        return "E"
    return str(pred)


def build_ground_truth() -> list[tuple[str, str]]:
    """Возвращает список (относительный_путь_клетки, ожидаемая_метка)."""
    # Вариант: 4 клетки
    variant = [("variant/variant_01.png", "0"), ("variant/variant_02.png", "0"),
               ("variant/variant_03.png", "0"), ("variant/variant_04.png", "2")]
    # Дата: 8 клеток (S = skip)
    date = [
        ("date/date_01.png", "2"), ("date/date_02.png", "9"), ("date/date_03.png", "S"),
        ("date/date_04.png", "0"), ("date/date_05.png", "3"), ("date/date_06.png", "S"),
        ("date/date_07.png", "2"), ("date/date_08.png", "5"),
    ]
    # Регистрационный номер: 8 клеток
    reg = [
        ("reg_number/reg_number_01.png", "3"), ("reg_number/reg_number_02.png", "9"),
        ("reg_number/reg_number_03.png", "9"), ("reg_number/reg_number_04.png", "3"),
        ("reg_number/reg_number_05.png", "E"), ("reg_number/reg_number_06.png", "E"),
        ("reg_number/reg_number_07.png", "E"), ("reg_number/reg_number_08.png", "E"),
    ]
    # Ответы к заданиям: строки 1..10, по 9 клеток
    answers_labels = [
        "4 S 6 E E E E E".split(),
        "3 E E E E E E E".split(),
        "4 S 2 E E E E E".split(),
        "8 5 E E E E E E".split(),
        "2 S 3 E E E E E".split(),
        "2 1 E E E E E E".split(),
        "2 S 2 5 E E E E".split(),
        "8 E E E E E E E".split(),
        "3 1 E E E E E E".split(),
        "4 6 E E E E E E".split(),
    ]
    answers = []
    for row in range(1, 11):
        row_str = f"{row:02d}"
        for col, label in enumerate(answers_labels[row - 1], start=1):
            answers.append((f"answers/{row_str}/answers_{row_str}_{col:02d}.png", label))
    # Замена ошибочных ответов: строки 1..10, по 9 клеток
    repl_labels = [
        "1 E E E E E E E".split(),
        "5 S 2 E E E E E".split(),
        "3 S 2 E E E E E".split(),
        "0 S 8 E E E E E".split(),
        "1 0 E E E E E E".split(),
        "9 0 E E E E E E".split(),
        "1 1 S 5 5 E E E".split(),
        "3 E E E E E E E".split(),
        "1 4 E E E E E E".split(),
        "4 3 E E E E E E".split(),
    ]
    repl = []
    for row in range(1, 11):
        row_str = f"{row:02d}"
        for col, label in enumerate(repl_labels[row - 1], start=1):
            repl.append((f"repl/{row_str}/repl_{row_str}_{col:02d}.png", label))

    return variant + date + reg + answers + repl


def run_evaluation(
    cells_dir: str | Path = "rows_out/cells",
    weights_path: str | Path = "mnist-classifier.pt",
    debug_mnist_dir: str | Path | None = None,
) -> None:
    cells_dir = Path(cells_dir)
    if not cells_dir.is_dir():
        print(f"Каталог не найден: {cells_dir.resolve()}. Сначала запустите main() для вырезки ячеек.")
        return

    gt = build_ground_truth()
    clf = MnistDigitClassifier(weights_path=str(weights_path), device="cpu")
    rec = CellRecognizer(clf, debug_mnist_dir=debug_mnist_dir)

    results: list[tuple[str, str, str, bool]] = []  # path, expected, pred, correct
    missing: list[str] = []

    for rel_path, expected in gt:
        if expected == "S":
            continue
        full = cells_dir / rel_path
        if not full.exists():
            missing.append(rel_path)
            continue
        img = cv2.imread(str(full))
        if img is None:
            missing.append(rel_path)
            continue
        pred = rec.recognize_bgr(img, debug_source_name=rel_path)
        pred_norm = _norm_pred(pred)
        correct = pred_norm == expected
        results.append((rel_path, expected, pred_norm, correct))

    if missing:
        print("Не найдены или не загружены клетки:")
        for p in missing[:20]:
            print(f"  {p}")
        if len(missing) > 20:
            print(f"  ... и ещё {len(missing) - 20}")
        print()

    # Разбивка: все (кроме skip), без пустых, только пустые
    all_eval = results
    non_empty = [(p, exp, pred, ok) for p, exp, pred, ok in all_eval if exp != "E"]
    empty_only = [(p, exp, pred, ok) for p, exp, pred, ok in all_eval if exp == "E"]

    def accuracy(pairs: list) -> tuple[int, int, float]:
        n = len(pairs)
        c = sum(1 for _ in (x for x in pairs if x[3]))
        return c, n, (c / n * 100.0) if n else 0.0

    # Метрики без пустых клеток (только цифры/минус)
    c_n, n_n, acc_n = accuracy(non_empty)
    # Метрики с пустыми клетками (все учитываемые)
    c_a, n_a, acc_a = accuracy(all_eval)
    # Ошибки в пустых клетках
    empty_errors = [(p, pred) for p, exp, pred, ok in empty_only if not ok]

    print("=== Метрики (без учёта S) ===\n")
    print(f"Без пустых клеток (только цифры/минус): {c_n}/{n_n} = {acc_n:.2f}%")
    print(f"С пустыми клетками (все):               {c_a}/{n_a} = {acc_a:.2f}%\n")

    if empty_only:
        c_e, n_e, acc_e = accuracy(empty_only)
        print(f"Только пустые клетки (ожидание E):     {c_e}/{n_e} = {acc_e:.2f}%")
    if empty_errors:
        print("\n--- Ошибки в пустых клетках (ожидалось E, получено иное) ---")
        for path, pred in empty_errors:
            print(f"  {path}  ->  предсказано: {pred!r}")
    else:
        print("\nОшибок в пустых клетках нет.")

    # Таблица по каждой метке: в каком файле ошиблись, доля ошибок на этой метке
    by_label: dict[str, list[tuple[str, str, str, bool]]] = defaultdict(list)
    for item in results:
        by_label[item[1]].append(item)

    print("\n--- Ошибки по метке (файл, доля ошибок на этой метке) ---")
    labels_sorted = sorted(by_label.keys(), key=lambda x: (x == "E", x))
    for label in labels_sorted:
        items = by_label[label]
        total = len(items)
        errors = [(p, pred) for p, exp, pred, ok in items if not ok]
        n_err = len(errors)
        rate = (n_err / total * 100.0) if total else 0.0
        print(f"\n  Метка {label!r}: всего {total}, ошибок {n_err}, доля ошибок {rate:.1f}%")
        for path, pred in errors:
            print(f"    {path}  ->  предсказано: {pred!r}")

    print("\nГотово.")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Оценка качества cell_ocr по разметке")
    p.add_argument("--cells-dir", default="rows_out/cells", help="Каталог с клетками")
    p.add_argument("--weights", default="mnist-classifier.pt", help="Путь к весам MNIST")
    p.add_argument("--debug-mnist-dir", default=None, help="Каталог для сохранения входов MNIST (отладка)")
    args = p.parse_args()
    run_evaluation(
        cells_dir=args.cells_dir,
        weights_path=args.weights,
        debug_mnist_dir=args.debug_mnist_dir,
    )
