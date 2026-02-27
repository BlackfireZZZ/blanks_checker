"""Поиск строк таблицы по линиям сетки."""

import json
from pathlib import Path

import cv2
import numpy as np

from app.rows.debug_utils import _save_debug_img
from app.rows.morphology import _adaptive_inv, _extract_lines, _find_line_centers_1d

# Строки ниже этой высоты считаем ложными (отступ/граница блока), скипаем
MIN_ROW_HEIGHT_PX = 20


def _pair_row_lines(ys: list[int], want_rows: int = 10) -> list[tuple[int, int]]:
    """
    Тут НЕ таблица. Каждая строка — прямоугольник => две горизонтальные линии (верх/низ),
    между строками — зазор. Поэтому собираем пары (top, bottom).
    """
    ys = sorted(ys)
    if len(ys) < 2:
        return []

    diffs = np.diff(ys)
    if len(diffs) == 0:
        return []

    big_thr = float(np.percentile(diffs, 60))

    pairs: list[tuple[int, int]] = []
    i = 0
    while i + 1 < len(ys) and len(pairs) < want_rows:
        d = ys[i + 1] - ys[i]
        if d >= big_thr:
            pairs.append((ys[i], ys[i + 1]))
            i += 2
        else:
            i += 1

    if len(pairs) < want_rows:
        pairs = []
        for j in range(0, len(ys) - 1, 2):
            pairs.append((ys[j], ys[j + 1]))
            if len(pairs) >= want_rows:
                break

    return pairs[:want_rows]


def detect_rows_by_grid(
    img_bgr: np.ndarray,
    table_roi: tuple[float, float, float, float],
    debug_dir: Path | None = None,
) -> list[tuple[int, int, int, int]]:
    """
    Внутри ROI блока строк:
    - достаём горизонтальные/вертикальные линии,
    - превращаем горизонтальные линии в пары (верх/низ) строк,
    - возвращаем bbox только клеточной части строки.
    """
    H, W = img_bgr.shape[:2]
    x1, y1, x2, y2 = table_roi
    X1, Y1, X2, Y2 = int(x1 * W), int(y1 * H), int(x2 * W), int(y2 * H)
    roi = img_bgr[Y1:Y2, X1:X2]
    _save_debug_img(debug_dir, "table_roi_raw.png", roi)

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

    bw = _adaptive_inv(gray)
    h_lines = _extract_lines(bw, "h")
    v_lines = _extract_lines(bw, "v")

    proj_y = h_lines.sum(axis=1) / 255.0
    proj_x = v_lines.sum(axis=0) / 255.0

    ys = _find_line_centers_1d(proj_y, thr_rel=0.35, max_gap=6)
    xs = _find_line_centers_1d(proj_x, thr_rel=0.5, max_gap=6)
    xs = sorted(xs)

    if debug_dir is not None:
        debug_dir.mkdir(parents=True, exist_ok=True)
        _save_debug_img(debug_dir, "table_bw_inv.png", bw)
        _save_debug_img(debug_dir, "table_h_lines.png", h_lines)
        _save_debug_img(debug_dir, "table_v_lines.png", v_lines)

    if len(xs) < 4 or len(ys) < 8:
        raise RuntimeError(f"Не смог восстановить линии: ys={len(ys)} xs={len(xs)}")

    row_pairs = _pair_row_lines(ys, want_rows=10)
    if len(row_pairs) != 10:
        raise RuntimeError(f"Не смог собрать 10 строк: pairs={len(row_pairs)} (ys={len(ys)})")

    # Если первая пара — узкая полоска (< MIN), это ложная "строка" (отступ сверху).
    # Выкидываем первую линию и заново собираем пары — тогда первая строка станет (y1,y2).
    dropped_top_line = False
    if row_pairs and (row_pairs[0][1] - row_pairs[0][0]) < MIN_ROW_HEIGHT_PX:
        ys_shifted = sorted(ys)[1:]
        if len(ys_shifted) < 20:
            raise RuntimeError(f"После отбрасывания ложной верхней линии осталось {len(ys_shifted)} y, нужно ≥20")
        row_pairs = _pair_row_lines(ys_shifted, want_rows=10)
        if len(row_pairs) != 10:
            raise RuntimeError(f"После сдвига не смог собрать 10 строк: pairs={len(row_pairs)}")
        dropped_top_line = True

    # Берём полную ширину клеток (у тебя уже вырезано без "№", поэтому xs[0]..xs[-1] — ок)
    x_cells_l = xs[0]
    x_cells_r = xs[-1]

    rows: list[tuple[int, int, int, int]] = []
    pad = 2
    for (y_top, y_bot) in row_pairs:
        x = X1 + x_cells_l + pad
        y = Y1 + y_top + pad
        w = (x_cells_r - x_cells_l) - 2 * pad
        h = (y_bot - y_top) - 2 * pad
        rows.append((int(x), int(y), int(w), int(h)))

    if debug_dir is not None:
        debug_dir.mkdir(parents=True, exist_ok=True)
        lines_debug = {
            "roi_offset_px": {"X1": X1, "Y1": Y1, "X2": X2, "Y2": Y2},
            "roi_size": {"w": X2 - X1, "h": Y2 - Y1},
            "line_centers_y_roi": ys,
            "line_centers_x_roi": xs,
            "dropped_top_line": dropped_top_line,
            "row_pairs_roi": [[int(a), int(b)] for (a, b) in row_pairs],
            "x_cells_roi": [x_cells_l, x_cells_r],
        }
        (debug_dir / "table_lines_debug.json").write_text(json.dumps(lines_debug, indent=2), encoding="utf-8")
        vis = img_bgr.copy()
        for (x, y, w, h) in rows:
            cv2.rectangle(vis, (x, y), (x + w, y + h), (0, 0, 255), 1)
        _save_debug_img(debug_dir, "rows_bbox_full.png", vis)

    return rows
