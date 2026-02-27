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

from app.ocr.cell_ocr import recognize_cell


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
        "1 1 E E E E E E".split(),
        "5 S 2 E E E E E".split(),
        "3 S 2 E E E E E".split(),
        "0 S 8 E E E E E".split(),
        "1 0 E E E E E E".split(),
        "9 0 E E E E E E".split(),
        "1 1 S 5 E E E E".split(),
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


def ground_truth_from_config(config: dict) -> list[tuple[str, str]]:
    """
    Собирает список (относительный_путь_клетки, ожидаемая_метка) из конфига.
    config: variant (4 метки), date (8), reg_number (8), answers (10 списков по 9), repl (10 списков по 9).
    """
    out: list[tuple[str, str]] = []
    for i, label in enumerate(config.get("variant", []), start=1):
        out.append((f"variant/variant_{i:02d}.png", label))
    for i, label in enumerate(config.get("date", []), start=1):
        out.append((f"date/date_{i:02d}.png", label))
    for i, label in enumerate(config.get("reg_number", []), start=1):
        out.append((f"reg_number/reg_number_{i:02d}.png", label))
    for row in range(1, 11):
        row_str = f"{row:02d}"
        labels = config.get("answers", [[]])[row - 1] if row <= len(config.get("answers", [])) else []
        for col, label in enumerate(labels, start=1):
            out.append((f"answers/{row_str}/answers_{row_str}_{col:02d}.png", label))
    for row in range(1, 11):
        row_str = f"{row:02d}"
        labels = config.get("repl", [[]])[row - 1] if row <= len(config.get("repl", [])) else []
        for col, label in enumerate(labels, start=1):
            out.append((f"repl/{row_str}/repl_{row_str}_{col:02d}.png", label))
    return out


def run_evaluation(
    cells_dir: str | Path = "rows_out/cells",
    weights_path: str | Path | None = None,
    ground_truth: list[tuple[str, str]] | None = None,
    debug_mnist_dir: str | Path | None = None,
    debug_predictions: bool = False,
    verbose: bool = True,
) -> dict:
    """
    Возвращает словарь метрик: acc_no_empty, acc_all, acc_empty_only, n_missing, total_no_empty, total_all, ...
    """
    cells_dir = Path(cells_dir)
    if not cells_dir.is_dir():
        if verbose:
            print(f"Каталог не найден: {cells_dir.resolve()}. Сначала запустите main() для вырезки ячеек.")
        return {"error": "cells_dir not found", "acc_no_empty": 0.0, "acc_all": 0.0}

    gt = ground_truth if ground_truth is not None else build_ground_truth()
    debug_dir = Path(debug_mnist_dir) if debug_mnist_dir is not None else None
    if debug_dir is not None:
        debug_dir.mkdir(parents=True, exist_ok=True)

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
        # recognize_cell returns "E" | "-" | "0".."9"
        out_dir = None
        if debug_dir is not None:
            safe_name = rel_path.replace("\\", "__").replace("/", "__")
            out_dir = debug_dir / safe_name
        pred_norm = recognize_cell(
            img,
            weights_path=str(weights_path) if weights_path is not None else None,
            debug=out_dir is not None,
            debug_out_dir=out_dir,
        )
        correct = pred_norm == expected
        results.append((rel_path, expected, pred_norm, correct))

    if verbose and debug_predictions and results:
        # Одна строка вывода на логическую строку (вариант, дата, ответы/01, repl/01 и т.д.)
        current_row: str | None = None
        preds: list[str] = []
        for rel_path, _exp, pred_norm, _ok in results:
            row = str(Path(rel_path).parent).replace("\\", "/")
            if row != current_row:
                if current_row is not None:
                    print(f"{current_row}: {' '.join(preds)}")
                current_row = row
                preds = []
            preds.append(pred_norm)
        if current_row is not None:
            print(f"{current_row}: {' '.join(preds)}")
        print()

    if verbose and missing:
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
    c_e, n_e, acc_e = (accuracy(empty_only) if empty_only else (0, 0, 0.0))

    metrics = {
        "correct_no_empty": c_n,
        "total_no_empty": n_n,
        "acc_no_empty": acc_n,
        "correct_all": c_a,
        "total_all": n_a,
        "acc_all": acc_a,
        "correct_empty": c_e,
        "total_empty": n_e,
        "acc_empty_only": acc_e,
        "n_missing": len(missing),
        "empty_errors": empty_errors,
    }

    if verbose:
        print("=== Метрики (без учёта S) ===\n")
        print(f"Без пустых клеток (только цифры/минус): {c_n}/{n_n} = {acc_n:.2f}%")
        print(f"С пустыми клетками (все):               {c_a}/{n_a} = {acc_a:.2f}%\n")
        if empty_only:
            print(f"Только пустые клетки (ожидание E):     {c_e}/{n_e} = {acc_e:.2f}%")
        if empty_errors:
            print("\n--- Ошибки в пустых клетках (ожидалось E, получено иное) ---")
            for path, pred in empty_errors:
                print(f"  {path}  ->  предсказано: {pred!r}")
        else:
            print("\nОшибок в пустых клетках нет.")
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

    return metrics


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Оценка качества cell_ocr по разметке")
    p.add_argument("--cells-dir", default="rows_out/cells", help="Каталог с клетками")
    p.add_argument("--debug-mnist-dir", default=None, help="Каталог для сохранения входов MNIST (отладка)")
    p.add_argument("--debug", action="store_true", help="Выводить предикты по строкам (вариант, дата, ответы, замена)")
    args = p.parse_args()
    run_evaluation(
        cells_dir=args.cells_dir,
        debug_mnist_dir=args.debug_mnist_dir,
        debug_predictions=args.debug,
    )
