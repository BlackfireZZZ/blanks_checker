"""Выравнивание бланка по чёрным маркерам."""

from pathlib import Path

import cv2
import numpy as np

from pdf_loader import pdf_page_to_bgr


def order_points(pts: np.ndarray) -> np.ndarray:
    pts = np.asarray(pts, dtype=np.float32)
    s = pts.sum(axis=1)
    diff = np.diff(pts, axis=1).reshape(-1)
    tl = pts[np.argmin(s)]
    br = pts[np.argmax(s)]
    tr = pts[np.argmin(diff)]
    bl = pts[np.argmax(diff)]
    return np.array([tl, tr, br, bl], dtype=np.float32)


def _find_marker_in_roi(
    gray_roi: np.ndarray, corner_xy: tuple[int, int]
) -> tuple[tuple[float, float, float] | None, np.ndarray]:
    """
    Ищем «самый тёмный маленький квадрат возле угла» в ROI.
    corner_xy: (0,0) / (w-1,0) / (w-1,h-1) / (0,h-1) — какой угол ROI настоящий.
    Возвращает (cx, cy, side) в координатах ROI или None, и bw для дебага.
    """
    h, w = gray_roi.shape[:2]

    # Порог по «очень тёмному» — маркеры почти чёрные, линии/текст серее
    p = np.percentile(gray_roi, 8)
    thr = int(min(110, p + 20))
    bw = (gray_roi < thr).astype(np.uint8) * 255

    bw = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8), iterations=1)

    num, labels, stats, centroids = cv2.connectedComponentsWithStats(bw, connectivity=8)

    if num <= 1:
        return None, bw

    cx_corner, cy_corner = corner_xy

    max_w = int(w * 0.25)
    max_h = int(h * 0.25)
    min_area = int(w * h * 0.0005)
    max_area = int(w * h * 0.05)

    best = None
    best_score = -1e18

    for i in range(1, num):
        x, y, ww, hh, area = stats[i]
        if area < min_area or area > max_area:
            continue
        if ww <= 2 or hh <= 2:
            continue
        if ww > max_w or hh > max_h:
            continue

        aspect = max(ww, hh) / max(1, min(ww, hh))
        if aspect > 1.6:
            continue

        fill = area / float(ww * hh)
        if fill < 0.35:
            continue

        cx, cy = centroids[i]
        dist = np.hypot(cx - cx_corner, cy - cy_corner)
        score = (area * fill / aspect) - (dist * 200.0)

        if score > best_score:
            best_score = score
            best = (float(cx), float(cy), float((ww + hh) / 2.0))

    return best, bw


def detect_black_square_markers(
    img_bgr: np.ndarray,
    roi_frac: float = 0.28,
    debug_dir: str | Path | None = None,
):
    """
    Ищем маркеры в 4 угловых ROI (тёмный порог + размер + близость к углу).
    Если найдено 3 — восстанавливаем 4-й как параллелограмм.
    Возвращает centers4 (tl, tr, br, bl) и avg_side.
    """
    gray_full = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    H, W = gray_full.shape[:2]

    rw, rh = int(W * roi_frac), int(H * roi_frac)

    rois = {
        "tl": (0, 0, rw, rh, (0, 0)),
        "tr": (W - rw, 0, W, rh, (rw - 1, 0)),
        "br": (W - rw, H - rh, W, H, (rw - 1, rh - 1)),
        "bl": (0, H - rh, rw, H, (0, rh - 1)),
    }

    found: dict[str, np.ndarray] = {}
    sides: dict[str, float] = {}

    for key, (x0, y0, x1, y1, corner_xy) in rois.items():
        roi = gray_full[y0:y1, x0:x1]
        best, bw = _find_marker_in_roi(roi, corner_xy=corner_xy)

        if debug_dir is not None:
            Path(debug_dir).mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(Path(debug_dir) / f"debug_bw_{key}.png"), bw)

        if best is None:
            continue

        cx, cy, side = best
        found[key] = np.array([cx + x0, cy + y0], dtype=np.float32)
        sides[key] = side

    if len(found) < 3:
        raise RuntimeError(
            f"Не удалось найти хотя бы 3 маркера: найдено {len(found)} ({list(found.keys())})"
        )

    corners = ["tl", "tr", "br", "bl"]
    missing = [c for c in corners if c not in found]

    if len(missing) == 1:
        m = missing[0]
        if m == "tl":
            found["tl"] = found["tr"] + found["bl"] - found["br"]
        elif m == "tr":
            found["tr"] = found["tl"] + found["br"] - found["bl"]
        elif m == "br":
            found["br"] = found["tr"] + found["bl"] - found["tl"]
        elif m == "bl":
            found["bl"] = found["tl"] + found["br"] - found["tr"]

        mean_side = float(np.mean(list(sides.values())))
        sides[m] = mean_side

    elif len(missing) > 1:
        raise RuntimeError(
            f"Найдено слишком мало маркеров: {len(found)} ({list(found.keys())})"
        )

    centers4 = np.array(
        [found["tl"], found["tr"], found["br"], found["bl"]], dtype=np.float32
    )
    avg_side = float(np.mean([sides[k] for k in corners]))
    return centers4, avg_side


def warp_keep_full_page(
    img_bgr: np.ndarray,
    marker_centers4: np.ndarray,
    out_size=(1654, 2339),
    margin_px: int = 90,
) -> np.ndarray:
    """
    SRC: центры маркеров на изображении.
    DST: центры маркеров в шаблоне с отступом margin_px от края.
    """
    w, h = out_size
    src = order_points(marker_centers4)

    dst = np.array(
        [
            [margin_px, margin_px],
            [w - 1 - margin_px, margin_px],
            [w - 1 - margin_px, h - 1 - margin_px],
            [margin_px, h - 1 - margin_px],
        ],
        dtype=np.float32,
    )

    M = cv2.getPerspectiveTransform(src, dst)
    return cv2.warpPerspective(img_bgr, M, (w, h), flags=cv2.INTER_CUBIC)


def align_pdf_form(
    pdf_path: str,
    out_path: str = "aligned.png",
    page_index: int = 0,
    zoom: float = 2.0,
    out_size=(1654, 2339),
    margin_px: int | None = None,
    debug_dir: str | Path | None = None,
) -> None:
    """
    Загружает страницу PDF, выравнивает по маркерам, сохраняет.

    ВАЖНО: здесь НЕ делаем preprocess_for_blocks(), потому что он убивает линии сетки.
    Предобработку (бинаризацию/линии) делаем локально в rows.py.
    """
    img = pdf_page_to_bgr(pdf_path, page_index=page_index, zoom=zoom)
    centers4, avg_side = detect_black_square_markers(
        img, roi_frac=0.28, debug_dir=debug_dir
    )

    if margin_px is None:
        margin_px = max(40, int(avg_side * 2.0))

    aligned = warp_keep_full_page(img, centers4, out_size=out_size, margin_px=margin_px)

    if debug_dir is not None:
        Path(debug_dir).mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(Path(debug_dir) / "aligned_raw.png"), aligned)

    cv2.imwrite(out_path, aligned)
    print(f"OK: {out_path} (margin_px={margin_px})")
    if debug_dir is not None:
        print(f"Debug: {Path(debug_dir).resolve()}")
