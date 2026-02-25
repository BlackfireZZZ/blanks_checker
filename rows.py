"""Поиск строк ответов и вырезка ячеек с выравненного бланка."""

from pathlib import Path

import cv2
import numpy as np

from image_utils import crop_rel

# ROI заголовка в долях изображения (вариант, дата, рег. номер)
HEADER_ROIS = {
    "variant.png": (0.305, 0.122, 0.425, 0.159),
    "date.png": (0.447, 0.122, 0.710, 0.159),
    "reg_number.png": (0.735, 0.122, 0.965, 0.159),
}


def detect_answer_rows(img_bgr: np.ndarray):
    """
    Находит 20 длинных прямоугольников строк:
    - 10 слева: ответы 1..10
    - 10 справа: замена 1..10
    Возвращает два списка bbox: (x,y,w,h), отсортированные по номеру.
    """
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    bw = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 31, 10
    )
    bw = cv2.morphologyEx(bw, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8), iterations=1)

    contours, _ = cv2.findContours(bw, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    H, W = gray.shape[:2]
    rects = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        area = w * h
        if area < 4000:
            continue
        if not (28 <= h <= 95):
            continue
        aspect = w / float(h)
        if aspect < 5.0:
            continue
        if w > 0.95 * W or h > 0.95 * H:
            continue
        rects.append((x, y, w, h, aspect, area))

    rects.sort(key=lambda r: r[5], reverse=True)
    rects = rects[:35]

    hs = np.array([r[3] for r in rects], dtype=np.int32)
    if len(hs) == 0:
        raise RuntimeError("Не нашёл ни одной строки ответов (контуры).")
    h_med = int(np.median(hs))
    rects = [r for r in rects if abs(r[3] - h_med) <= 12]

    rects.sort(key=lambda r: r[5], reverse=True)
    rects = rects[:20]
    if len(rects) != 20:
        raise RuntimeError(
            f"Ожидал 20 строк (10+10), нашёл {len(rects)}. Подстрой фильтры."
        )

    rects.sort(key=lambda r: (r[1], r[0]))
    xs = [r[0] for r in rects]
    x_mid = np.median(xs)

    left = [r for r in rects if r[0] < x_mid]
    right = [r for r in rects if r[0] >= x_mid]

    left.sort(key=lambda r: (r[1], r[0]))
    right.sort(key=lambda r: (r[1], r[0]))

    if len(left) != 10 or len(right) != 10:
        left = [r for r in rects if (r[0] + r[2] / 2) < (W / 2)]
        right = [r for r in rects if (r[0] + r[2] / 2) >= (W / 2)]
        left.sort(key=lambda r: (r[1], r[0]))
        right.sort(key=lambda r: (r[1], r[0]))

    if len(left) != 10 or len(right) != 10:
        raise RuntimeError(
            f"Не удалось разделить на 10/10: left={len(left)}, right={len(right)}"
        )

    left.sort(key=lambda r: r[1])
    right.sort(key=lambda r: r[1])

    def tighten(r, pad=2):
        x, y, w, h = r[:4]
        return (x + pad, y + pad, max(1, w - 2 * pad), max(1, h - 2 * pad))

    left = [tighten(r) for r in left]
    right = [tighten(r) for r in right]
    return left, right


def save_crop(img: np.ndarray, bbox: tuple, out_path: Path | str) -> None:
    x, y, w, h = bbox
    crop = img[y : y + h, x : x + w].copy()
    cv2.imwrite(str(out_path), crop)


def extract_cells(
    aligned_path: str = "aligned.png",
    out_dir: str = "rows_out",
) -> None:
    """
    Читает выравненное (и уже бинаризованное) изображение,
    вырезает заголовочные ROI и 20 строк ответов/замен.
    """
    img = cv2.imread(aligned_path)
    if img is None:
        raise FileNotFoundError(f"Не могу прочитать {aligned_path}")

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    for name, (x1, y1, x2, y2) in HEADER_ROIS.items():
        crop = crop_rel(img, x1, y1, x2, y2)
        cv2.imwrite(str(out_dir / name), crop)

    left_rows, right_rows = detect_answer_rows(img)

    for i, bbox in enumerate(left_rows, start=1):
        save_crop(img, bbox, out_dir / f"answers_{i:02d}.png")

    for i, bbox in enumerate(right_rows, start=1):
        save_crop(img, bbox, out_dir / f"repl_{i:02d}.png")

    print(f"OK: ячейки сохранены в {out_dir.resolve()}")
