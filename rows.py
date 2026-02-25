"""Поиск строк ответов по линиям и вырезка ячеек с выравненного бланка."""

from pathlib import Path

import cv2
import numpy as np

from image_utils import crop_rel

# ROI заголовка в долях изображения (примерно). Дальше внутри обрезаем "только клетки".
HEADER_ROIS = {
    "variant.png": (0.270, 0.150, 0.415, 0.185),
    "date.png": (0.425, 0.145, 0.710, 0.185),
    "reg_number.png": (0.710, 0.145, 0.996, 0.190),
}

# ROI двух блоков строк (примерно). Подгоняется один раз по aligned.png в каноническом размере.
# y1/y2 увеличены, чтобы захватить строки сверху и снизу (раньше обрезало).
TABLE_ROIS = {
    "answers": (0.06, 0.44, 0.49, 0.95),  # левый блок "Ответы к заданиям"
    "repl": (0.52, 0.44, 0.95, 0.95),  # правый блок "Замена..."
}


def _save_debug_img(debug_dir: Path | None, name: str, img: np.ndarray) -> None:
    """Безопасное сохранение отладочного изображения."""
    if debug_dir is None:
        return
    debug_dir.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(debug_dir / name), img)


def _adaptive_inv(gray: np.ndarray) -> np.ndarray:
    """Адаптивная бинаризация: линии/текст -> белые (255) на чёрном фоне."""
    return cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_MEAN_C,
        cv2.THRESH_BINARY_INV,
        31,
        10,
    )


def _extract_lines(bw_inv: np.ndarray, axis: str) -> np.ndarray:
    """Достаём протяжённые линии (горизонтальные или вертикальные) морфологией."""
    h, w = bw_inv.shape[:2]
    if axis == "h":
        k = max(25, w // 18)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k, 1))
    elif axis == "v":
        k = max(25, h // 18)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, k))
    else:
        raise ValueError("axis must be 'h' or 'v'")

    out = cv2.erode(bw_inv, kernel, iterations=1)
    out = cv2.dilate(out, kernel, iterations=2)
    return out


def _group_peaks(idx: np.ndarray, max_gap: int = 4) -> list[int]:
    """Группируем соседние индексы в один пик, возвращаем центры групп."""
    if len(idx) == 0:
        return []
    groups: list[tuple[int, int]] = []
    start = int(idx[0])
    prev = int(idx[0])
    for v in idx[1:]:
        v = int(v)
        if v - prev > max_gap:
            groups.append((start, prev))
            start = v
        prev = v
    groups.append((start, prev))
    return [int((a + b) / 2) for a, b in groups]


def _find_line_centers_1d(proj: np.ndarray, thr_rel: float = 0.45, max_gap: int = 6) -> list[int]:
    """По 1D-проекции ищем центры линий (пики)."""
    m = float(proj.max())
    if m <= 0:
        return []
    thr = m * thr_rel
    idx = np.where(proj >= thr)[0]
    return _group_peaks(idx, max_gap=max_gap)


def _largest_rect_like_component(bw_inv: np.ndarray) -> tuple[int, int, int, int] | None:
    """
    Ищем самый подходящий "прямоугольник рамки" внутри ROI.
    Возвращает bbox (x,y,w,h) или None.
    bw_inv: белое=объекты (линии/текст), чёрное=фон.
    """
    h, w = bw_inv.shape[:2]

    # Усиливаем именно рамку: соединяем разрывы и делаем контуры связными
    k_close = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    blob = cv2.morphologyEx(bw_inv, cv2.MORPH_CLOSE, k_close, iterations=2)

    # Убираем мелочь (цифры, мусор)
    k_open = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    blob = cv2.morphologyEx(blob, cv2.MORPH_OPEN, k_open, iterations=1)

    contours, _ = cv2.findContours(blob, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    roi_area = float(h * w)
    best_bbox = None
    best_score = -1e18

    for c in contours:
        x, y, ww, hh = cv2.boundingRect(c)
        area = float(ww * hh)
        if area < roi_area * 0.20:   # слишком маленькое — не рамка
            continue
        if area > roi_area * 0.98:   # почти весь ROI — часто фон/ошибка
            continue

        aspect = ww / float(max(1, hh))

        # "прямоугольность": насколько контур заполняет свой bbox
        cnt_area = float(cv2.contourArea(c))
        fill = cnt_area / float(max(1.0, area))

        # рамка — длинный прямоугольник, fill не должен быть совсем маленьким
        if fill < 0.10:
            continue
        if aspect < 2.0:  # у полей вариант/дата/рег обычно вытянутые
            continue

        # штрафуем компоненты, которые сильно не касаются краёв ROI (рамка обычно близко к границам crop)
        margin = min(x, y, w - (x + ww), h - (y + hh))
        score = area + 2000.0 * fill - 500.0 * margin

        if score > best_score:
            best_score = score
            best_bbox = (x, y, ww, hh)

    return best_bbox


def crop_to_grid_only(
    img_bgr: np.ndarray,
    debug_dir: Path | None = None,
) -> np.ndarray:
    """
    Для заголовочных полей: из грубого ROI вырезаем ТОЛЬКО область клеток
    по внешней рамке прямоугольника.

    Главное: не используем проекции линий (они ломаются цифрами внутри клетки).
    """
    _save_debug_img(debug_dir, "roi_raw.png", img_bgr)

    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    bw = _adaptive_inv(gray)
    _save_debug_img(debug_dir, "roi_bw_inv.png", bw)

    # Сначала попытаемся найти рамку как "крупный прямоугольный компонент"
    bbox = _largest_rect_like_component(bw)
    if bbox is None:
        return img_bgr

    x, y, w, h = bbox

    # Визуализация найденной рамки
    dbg_vis = img_bgr.copy()
    cv2.rectangle(dbg_vis, (x, y), (x + w, y + h), (0, 0, 255), 1)
    _save_debug_img(debug_dir, "roi_grid_bbox.png", dbg_vis)

    pad = 2
    x1 = max(0, x + pad)
    y1 = max(0, y + pad)
    x2 = min(img_bgr.shape[1], x + w - pad)
    y2 = min(img_bgr.shape[0], y + h - pad)

    if x2 <= x1 or y2 <= y1:
        return img_bgr

    return img_bgr[y1:y2, x1:x2].copy()

def _pair_row_lines(ys: list[int], want_rows: int = 10) -> list[tuple[int, int]]:
    """
    ВАЖНО: тут НЕ таблица.
    Каждая "строка" — отдельный прямоугольник => две горизонтальные линии (верх/низ).
    Между строками — зазор.
    Поэтому превращаем список линий в пары (top, bottom) и берём 10 строк.
    """
    ys = sorted(ys)
    if len(ys) < 2:
        return []

    diffs = np.diff(ys)
    if len(diffs) == 0:
        return []

    # Высота строки — это "большие" диффы, зазор между прямоугольниками — "малые"
    big_thr = float(np.percentile(diffs, 60))  # устойчиво для чередования big/small

    pairs: list[tuple[int, int]] = []
    i = 0
    while i + 1 < len(ys) and len(pairs) < want_rows:
        d = ys[i + 1] - ys[i]
        if d >= big_thr:  # это похоже на (верх, низ) одной строки
            pairs.append((ys[i], ys[i + 1]))
            i += 2
        else:
            # это похоже на "зазор" или мусорная линия — сдвигаемся на 1
            i += 1

    # Если из-за шума не набрали 10, fallback: просто берём (0,1),(2,3)...
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
    - возвращаем bbox только клеточной части строки (без "№").
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

    # Для прямоугольников строки линии могут быть короче/прерывистее => threshold пониже
    ys = _find_line_centers_1d(proj_y, thr_rel=0.35, max_gap=6)
    xs = _find_line_centers_1d(proj_x, thr_rel=0.5, max_gap=6)
    xs = sorted(xs)

    if debug_dir is not None:
        debug_dir.mkdir(parents=True, exist_ok=True)
        _save_debug_img(debug_dir, "table_bw_inv.png", bw)
        _save_debug_img(debug_dir, "table_h_lines.png", h_lines)
        _save_debug_img(debug_dir, "table_v_lines.png", v_lines)

        # Простейшая визуализация проекций как изображений
        if proj_y.max() > 0:
            py = (proj_y / proj_y.max() * 255.0).astype(np.uint8)
            py_img = np.repeat(py[:, None], 64, axis=1)
            _save_debug_img(debug_dir, "table_proj_y.png", py_img)
        if proj_x.max() > 0:
            px = (proj_x / proj_x.max() * 255.0).astype(np.uint8)
            px_img = np.repeat(px[None, :], 64, axis=0)
            _save_debug_img(debug_dir, "table_proj_x.png", px_img)

    if len(xs) < 5 or len(ys) < 8:
        raise RuntimeError(f"Не смог восстановить линии: ys={len(ys)} xs={len(xs)}")

    row_pairs = _pair_row_lines(ys, want_rows=10)
    if len(row_pairs) != 10:
        raise RuntimeError(f"Не смог собрать 10 строк: pairs={len(row_pairs)} (ys={len(ys)})")

    # xs[0] — левый край сетки (включая первую клетку для цифры), xs[-1] — правый.
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

    # Визуализация всех найденных строк на полном изображении
    if debug_dir is not None:
        vis = img_bgr.copy()
        for (x, y, w, h) in rows:
            cv2.rectangle(vis, (x, y), (x + w, y + h), (0, 0, 255), 1)
        _save_debug_img(debug_dir, "rows_bbox_full.png", vis)

    return rows


def save_crop(img: np.ndarray, bbox: tuple[int, int, int, int], out_path: Path | str) -> None:
    x, y, w, h = bbox
    crop = img[y : y + h, x : x + w].copy()
    cv2.imwrite(str(out_path), crop)


def extract_cells(
    aligned_path: str = "aligned.png",
    out_dir: str = "rows_out",
) -> None:
    """
    Читает выравненное изображение,
    вырезает заголовочные ROI (потом "только клетки") и 20 строк ответов/замен.
    """
    img = cv2.imread(aligned_path)
    if img is None:
        raise FileNotFoundError(f"Не могу прочитать {aligned_path}")

    out_dir_p = Path(out_dir)
    out_dir_p.mkdir(parents=True, exist_ok=True)

    # Заголовки: вариант/дата/рег.номер -> только клетки
    for name, (x1, y1, x2, y2) in HEADER_ROIS.items():
        crop = crop_rel(img, x1, y1, x2, y2)

        # Отдельный подкаталог дебага для каждого заголовка
        header_debug_dir = out_dir_p / "_debug_header" / Path(name).stem
        crop = crop_to_grid_only(crop, debug_dir=header_debug_dir)

        cv2.imwrite(str(out_dir_p / name), crop)

    # Блоки строк: пары линий (верх/низ) каждой строки
    debug_base = out_dir_p / "_debug_grid"
    left_rows = detect_rows_by_grid(img, TABLE_ROIS["answers"], debug_dir=debug_base / "left")
    right_rows = detect_rows_by_grid(img, TABLE_ROIS["repl"], debug_dir=debug_base / "right")

    for i, bbox in enumerate(left_rows, start=1):
        save_crop(img, bbox, out_dir_p / f"answers_{i:02d}.png")

    for i, bbox in enumerate(right_rows, start=1):
        save_crop(img, bbox, out_dir_p / f"repl_{i:02d}.png")

    print(f"OK: ячейки сохранены в {out_dir_p.resolve()}")
