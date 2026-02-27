"""Нарезка области клеток на отдельные изображения."""

from pathlib import Path

import cv2
import numpy as np

from app.rows.debug_utils import _save_debug_img
from app.rows.morphology import _adaptive_inv, _extract_vertical_separators, _find_line_centers_1d


def _safe_trim_cell(cell: np.ndarray) -> np.ndarray:
    """Микротрим по краям клетки, чтобы убрать остатки линий сетки."""
    h, w = cell.shape[:2]
    m = min(h, w)
    t = int(round(0.06 * m))
    t = int(np.clip(t, 1, 3))
    if t <= 0:
        return cell
    return cell[t : h - t, t : w - t].copy() if (h - 2 * t) > 2 and (w - 2 * t) > 2 else cell


def _pick_boundaries_from_separators(
    sep_img: np.ndarray,
    n_cells: int,
    debug_dir: Path | None = None,
) -> list[int]:
    """
    Возвращает список границ по X длиной n_cells+1 (в пикселях sep_img).
    Робастно: пытается взять найденные линии возле ожидаемых позиций,
    иначе ставит границу по ожидаемой позиции.
    """
    h, w = sep_img.shape[:2]
    proj = sep_img.sum(axis=0) / 255.0  # "сила" вертикальной линии
    _save_debug_img(debug_dir, "cells_sep_v.png", sep_img)

    # кандидаты линий
    xs = _find_line_centers_1d(proj, thr_rel=0.35, max_gap=6)
    xs = sorted(xs)

    # ожидаемые позиции внутренних границ
    step = w / float(n_cells)
    bounds = [0]

    # чтобы не подхватывать шум: требуем линию в окне вокруг ожидаемой
    win = max(6, int(step * 0.35))

    for k in range(1, n_cells):
        exp = int(round(k * step))
        # найти кандидатов в окне [exp-win, exp+win]
        cand = [x for x in xs if (exp - win) <= x <= (exp + win)]
        if cand:
            # выбрать самый "сильный" по proj
            best = max(cand, key=lambda x: proj[x])
            bounds.append(int(best))
        else:
            bounds.append(exp)

    bounds.append(w)

    # монотонность + минимальная ширина
    bounds = sorted(bounds)
    min_w = max(2, int(step * 0.35))
    fixed = [bounds[0]]
    for b in bounds[1:]:
        if b - fixed[-1] < min_w:
            b = fixed[-1] + min_w
        fixed.append(min(b, w))
    fixed[-1] = w
    fixed[0] = 0
    return fixed


def split_cells(
    cells_region_bgr: np.ndarray,
    n_cells: int,
    debug_dir: Path | None = None,
) -> list[np.ndarray]:
    """
    Нарезает область "только клетки" на n_cells.
    Вход: BGR/Gray, где уже нет лишнего вокруг клеток (у тебя так и есть).
    Выход: список изображений клеток (BGR).
    """
    if cells_region_bgr.ndim == 2:
        gray = cells_region_bgr
        bgr = cv2.cvtColor(cells_region_bgr, cv2.COLOR_GRAY2BGR)
    else:
        bgr = cells_region_bgr
        gray = cv2.cvtColor(cells_region_bgr, cv2.COLOR_BGR2GRAY)

    bw = _adaptive_inv(gray)
    _save_debug_img(debug_dir, "cells_bw_inv.png", bw)

    sep = _extract_vertical_separators(bw, min_len_ratio=0.78)

    bounds = _pick_boundaries_from_separators(sep, n_cells=n_cells, debug_dir=debug_dir)

    # визуализация границ
    if debug_dir is not None:
        vis = bgr.copy()
        for x in bounds:
            cv2.line(vis, (x, 0), (x, vis.shape[0] - 1), (0, 0, 255), 1)
        _save_debug_img(debug_dir, "cells_bounds.png", vis)

    # режем
    out: list[np.ndarray] = []
    pad = 1
    for i in range(n_cells):
        x1 = max(0, bounds[i] + pad)
        x2 = min(bgr.shape[1], bounds[i + 1] - pad)
        if x2 <= x1:
            # fallback: равномерно по шагу
            step = bgr.shape[1] / float(n_cells)
            x1 = int(round(i * step))
            x2 = int(round((i + 1) * step))
        cell = bgr[:, x1:x2].copy()
        cell = _safe_trim_cell(cell)
        out.append(cell)

    return out


def save_crop(img: np.ndarray, bbox: tuple[int, int, int, int], out_path: Path | str) -> None:
    x, y, w, h = bbox
    crop = img[y : y + h, x : x + w].copy()
    cv2.imwrite(str(out_path), crop)


def _save_cells_list(cells: list[np.ndarray], out_dir: Path, prefix: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for i, cell in enumerate(cells, start=1):
        cv2.imwrite(str(out_dir / f"{prefix}_{i:02d}.png"), cell)
