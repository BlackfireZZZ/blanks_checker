"""
Одна команда: обработка всех PDF из конфига и подсчёт метрик по каждому файлу и в среднем.

Конфиг: eval_batch_config.py (BATCH = список с ключами pdf, variant, date, reg_number, answers, repl).

Использование:
  python run_batch_eval.py                    # извлечь клетки из PDF + оценить
  python run_batch_eval.py --no-extract       # только оценить (клетки уже в rows_out/<stem>/cells)
  python run_batch_eval.py --config my_config.py
"""

import sys
from pathlib import Path

# корень проекта для импортов и путей
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from main import main as run_main
from evaluate_cell_ocr import run_evaluation, ground_truth_from_config


def run(
    batch: list[dict],
    weights_path: str | Path = "mnist-classifier.pt",
    rows_out_base: str = "rows_out",
    no_extract: bool = False,
) -> None:
    """Для каждого PDF из списка извлекает клетки (если нужно), считает метрики, выводит сводку."""
    if not batch:
        print("BATCH пуст. Добавьте записи в eval_batch_config.py")
        sys.exit(1)

    rows_base = Path(rows_out_base)
    results: list[tuple[str, Path, dict]] = []  # (pdf_path, cells_dir, metrics)

    for i, entry in enumerate(batch):
        pdf_path = entry.get("pdf")
        if not pdf_path:
            print(f"[{i+1}] Пропуск: нет ключа 'pdf'")
            continue
        pdf_path = Path(pdf_path)
        if not pdf_path.is_absolute():
            pdf_path = PROJECT_ROOT / pdf_path
        stem = pdf_path.stem
        rows_out_dir = str(rows_base / stem)
        cells_dir = rows_base / stem / "cells"

        if not no_extract:
            print(f"[{i+1}/{len(batch)}] Обработка: {pdf_path.name} -> {rows_out_dir}")
            try:
                run_main(
                    pdf_path=str(pdf_path),
                    rows_out_dir=rows_out_dir,
                    debug=False,
                )
            except Exception as e:
                print(f"  Ошибка: {e}")
                results.append((str(pdf_path), cells_dir, {"error": str(e), "acc_no_empty": 0.0, "acc_all": 0.0}))
                continue
        else:
            if not cells_dir.is_dir():
                print(f"[{i+1}] Пропуск {pdf_path.name}: нет каталога {cells_dir}")
                continue

        gt = ground_truth_from_config(entry)
        w = Path(weights_path)
        if not w.is_absolute():
            w = PROJECT_ROOT / w
        metrics = run_evaluation(
            cells_dir=cells_dir,
            weights_path=w,
            ground_truth=gt,
            verbose=False,
        )
        results.append((str(pdf_path), cells_dir, metrics))

    # Сводная таблица
    print("\n" + "=" * 80)
    print("Сводка по файлам")
    print("=" * 80)
    print(f"{'Файл':<40} {'Без пустых':>12} {'С пустыми':>12} {'Пропущено':>10}")
    print("-" * 80)

    total_c_n, total_n_n = 0, 0
    total_c_a, total_n_a = 0, 0
    for pdf_path, _cells_dir, m in results:
        name = Path(pdf_path).name
        if "error" in m:
            print(f"{name:<40} {'—':>12} {'—':>12} {'—':>10}")
            continue
        acc_n = m.get("acc_no_empty", 0)
        acc_a = m.get("acc_all", 0)
        miss = m.get("n_missing", 0)
        cn, nn = m.get("correct_no_empty", 0), m.get("total_no_empty", 0)
        ca, na = m.get("correct_all", 0), m.get("total_all", 0)
        total_c_n += cn
        total_n_n += nn
        total_c_a += ca
        total_n_a += na
        print(f"{name:<40} {acc_n:>10.1f}% {acc_a:>10.1f}% {miss:>10}")

    print("-" * 80)
    if total_n_n > 0:
        agg_n = total_c_n / total_n_n * 100.0
        print(f"{'Среднее / итог (без пустых)':<40} {agg_n:>10.1f}% ({total_c_n}/{total_n_n})")
    if total_n_a > 0:
        agg_a = total_c_a / total_n_a * 100.0
        print(f"{'Среднее / итог (с пустыми)':<40} {agg_a:>10.1f}% ({total_c_a}/{total_n_a})")
    print()


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Пакетная оценка по конфигу (PDF + правильные ответы)")
    p.add_argument("--config", default="eval_batch_config", help="Модуль с BATCH (без .py)")
    p.add_argument("--weights", default="mnist-classifier.pt", help="Путь к весам MNIST")
    p.add_argument("--rows-out", default="rows_out", help="Базовый каталог для вырезки (rows_out/<stem>)")
    p.add_argument("--no-extract", action="store_true", help="Не извлекать клетки из PDF, только оценить")
    args = p.parse_args()

    config_path = PROJECT_ROOT / f"{args.config}.py"
    if not config_path.exists():
        print(f"Конфиг не найден: {config_path}")
        sys.exit(1)
    import importlib.util
    spec = importlib.util.spec_from_file_location("batch_config", config_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    batch = getattr(mod, "BATCH", None)
    if batch is None:
        print(f"В {args.config}.py не найден BATCH.")
        sys.exit(1)

    run(
        batch=batch,
        weights_path=args.weights,
        rows_out_base=args.rows_out,
        no_extract=args.no_extract,
    )
