# Предобработка изображения клетки и эвристики (пусто/минус/цифра)
from __future__ import annotations

from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from cell_border_clean import BorderCleanParamsV2, clean_cell_borders_v2

from .config import HeuristicsConfig
from .model import MnistDigitClassifier


def save_mnist_input(mnist_28x28_float01: np.ndarray, path: str) -> None:
    """Сохраняет вход для MNIST (28x28, float 0–1) в PNG для отладки."""
    img = (mnist_28x28_float01 * 255).clip(0, 255).astype("uint8")  # white digit on black
    cv2.imwrite(path, img)


class CellRecognizer:
    def __init__(
        self,
        digit_classifier: MnistDigitClassifier,
        cfg: HeuristicsConfig = HeuristicsConfig(),
        debug_mnist_dir: str | Path | None = None,
    ) -> None:
        self.clf = digit_classifier
        self.cfg = cfg
        self.debug_mnist_dir = Path(debug_mnist_dir) if debug_mnist_dir else None
        self._debug_mnist_counter = 0

    def recognize_bgr(
        self,
        img_bgr: np.ndarray,
        *,
        debug_source_name: str | Path | None = None,
    ) -> Optional[str]:
        """
        returns:
          None  -> пустая клетка
          "-"   -> минус
          "0".."9" -> цифра
        """
        if img_bgr is None or img_bgr.size == 0:
            raise ValueError("Пустое изображение.")

        bw, g = self._preprocess_to_clean_binary(img_bgr)  # 0/255, без largest component + серое после CLAHE+blur

        force_not_empty = self._has_strong_black_in_center(g)

        # 1) пусто? (inner-only, до keep_largest)
        if (not force_not_empty) and self._is_empty_robust(bw):
            return None

        # дальше работаем только с символом
        sym = self._keep_largest_component(bw)

        # veto: мусор/артефакт не отправляем в MNIST
        if (not force_not_empty) and self._is_noise_symbol(sym):
            return None

        # 2) минус?
        if self._is_minus(sym):
            return "-"

        # 3) иначе -> MNIST (сюда попадаем только если клетка не пустая и не минус)
        mn = self._to_mnist_28x28(sym)
        if self.debug_mnist_dir is not None:
            # В debug сохраняем только входы для непустых клеток (цифры); пустые уже отфильтрованы выше
            self.debug_mnist_dir.mkdir(parents=True, exist_ok=True)
            if debug_source_name is not None:
                # Имя как у исходника: путь с заменой / на _ (безопасно для файловой системы)
                base = str(debug_source_name).replace("/", "_").replace("\\", "_")
                if not base.lower().endswith(".png"):
                    base = f"{base}.png"
                path = self.debug_mnist_dir / base
            else:
                path = self.debug_mnist_dir / f"{self._debug_mnist_counter:05d}.png"
                self._debug_mnist_counter += 1
            save_mnist_input(mn, str(path))
        digit, conf = self.clf.predict_digit(mn)

        # При желании можно добавить "отказ" при очень низкой уверенности,
        # но ты сказал, что других классов нет — поэтому возвращаем цифру всегда.
        return str(digit)

    # -------- preprocessing --------
    def _preprocess_to_clean_binary(self, img_bgr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Возвращает (bw, g), где:
        - bw: бинарник 0/255, где 255 = штрихи (без рамки), БЕЗ выделения largest component
        - g: серое изображение uint8 после CLAHE и GaussianBlur, до clean_cell_borders_v2
        """
        g = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY) if img_bgr.ndim == 3 else img_bgr.copy()

        # Контраст для бледной ручки
        clahe = cv2.createCLAHE(
            clipLimit=self.cfg.clahe_clip,
            tileGridSize=(self.cfg.clahe_grid, self.cfg.clahe_grid),
        )
        g = clahe.apply(g)

        g = cv2.GaussianBlur(g, (3, 3), 0)
        g_for_guard = g.copy()

        # Чистка границ клетки перед бинаризацией/дальнейшей обработкой
        _, cleaned_ink = clean_cell_borders_v2(g, BorderCleanParamsV2())
        bw = cleaned_ink

        # Open 2×2 не делаем — режет тонкие штрихи и рвёт «3»

        # Выкидываем "рамочные" компоненты, которые касаются границы
        bw = self._remove_border_lines_by_cc(bw)

        # Гарантированно убиваем край (остатки рамки 1–3 px)
        bw = self._safe_trim_edges(bw)

        return bw, g_for_guard

    def _remove_border_lines_by_cc(self, bw: np.ndarray) -> np.ndarray:
        h, w = bw.shape[:2]
        band = int(round(min(h, w) * self.cfg.border_band_frac))
        band = int(np.clip(band, self.cfg.border_band_min, self.cfg.border_band_max))

        # Маска пограничной зоны (где ожидаем рамку)
        border_mask = np.zeros((h, w), np.uint8)
        border_mask[:band, :] = 1
        border_mask[-band:, :] = 1
        border_mask[:, :band] = 1
        border_mask[:, -band:] = 1

        cc = (bw > 0).astype(np.uint8)
        num, labels, stats, _ = cv2.connectedComponentsWithStats(cc, connectivity=8)

        out = bw.copy()

        for i in range(1, num):
            x, y, ww, hh, area = stats[i]
            if area < 8:
                continue

            comp_mask = labels == i

            # Компонент считается "пограничным", если касается border band
            touches_border = bool(np.any(border_mask[comp_mask] == 1))
            if not touches_border:
                continue

            aspect = max(ww / max(1.0, hh), hh / max(1.0, ww))
            fill = area / float(ww * hh)
            thickness_ok = (min(ww, hh) / float(min(h, w))) <= self.cfg.line_thickness_max_frac

            # Рамка/линия: очень вытянутая + не слишком плотная + тонкая
            if aspect >= self.cfg.line_aspect_min and fill <= self.cfg.line_fill_max and thickness_ok:
                out[comp_mask] = 0

        return out

    def _inner_roi(self, bw: np.ndarray, frac: float = 0.14) -> np.ndarray:
        """Внутренняя область (игнорируем края) для empty-check."""
        h, w = bw.shape[:2]
        m = min(h, w)
        pad = int(round(frac * m))
        pad = int(np.clip(pad, 2, 6))
        if (h - 2 * pad) < 5 or (w - 2 * pad) < 5:
            return bw
        return bw[pad : h - pad, pad : w - pad]

    def _has_strong_black_in_center(self, g: np.ndarray) -> bool:
        """
        g: grayscale uint8, уже после CLAHE и GaussianBlur.
        True -> в центре есть пиксели почти чёрные => это точно не пусто.
        """
        if g is None or g.size == 0:
            return False

        h, w = g.shape[:2]
        m = min(h, w)

        # центральное окно ~45% от размера
        pad = int(round(0.275 * m))
        pad = int(np.clip(pad, 4, 10))
        y1, y2 = pad, h - pad
        x1, x2 = pad, w - pad
        if y2 <= y1 or x2 <= x1:
            return False

        center = g[y1:y2, x1:x2]

        # "почти чёрные" пиксели (гелевый чёрный), абсолютный порог
        thr_black = int(self.cfg.center_black_thr)
        black = center <= thr_black

        # требуем не одиночные пиксели: минимум N пикселей или маленькая компонента
        cnt = int(black.sum())
        if cnt >= int(self.cfg.center_black_count_min):
            return True

        cc = black.astype(np.uint8)
        num, _, stats, _ = cv2.connectedComponentsWithStats(cc, 8)
        if num <= 1:
            return False
        largest = int(stats[1:, cv2.CC_STAT_AREA].max())
        return largest >= 4

    def _safe_trim_edges(self, bw: np.ndarray) -> np.ndarray:
        """
        Убираем узкую рамку по периметру только если край реально «грязный».
        Не триммим агрессивно, если в краевой зоне есть чернила цифры (есть опора из внутренней части).
        """
        h, w = bw.shape[:2]
        m = min(h, w)
        t = int(round(0.06 * m))
        t = int(np.clip(t, 1, 4))

        if t <= 0:
            return bw

        # если на краях почти нет чернил — трим не нужен
        edge = np.zeros((h, w), np.uint8)
        edge[:t, :] = 1
        edge[-t:, :] = 1
        edge[:, :t] = 1
        edge[:, -t:] = 1
        edge_ink = int(np.sum((bw > 0) & (edge == 1)))
        if edge_ink < 3:
            return bw

        # если это чернила цифры (есть опора из внутренней части), не триммим агрессивно
        inner = bw.copy()
        inner[:t, :] = 0
        inner[-t:, :] = 0
        inner[:, :t] = 0
        inner[:, -t:] = 0
        if cv2.countNonZero(inner) > 12:
            t2 = 1
            out = bw.copy()
            out[:t2, :] = 0
            out[-t2:, :] = 0
            out[:, :t2] = 0
            out[:, -t2:] = 0
            return out

        out = bw.copy()
        out[:t, :] = 0
        out[-t:, :] = 0
        out[:, :t] = 0
        out[:, -t:] = 0
        return out

    def _keep_largest_component(self, bw: np.ndarray) -> np.ndarray:
        cc = (bw > 0).astype(np.uint8)
        num, labels, stats, _ = cv2.connectedComponentsWithStats(cc, connectivity=8)
        if num <= 1:
            return bw * 0

        areas = stats[1:, cv2.CC_STAT_AREA]
        idx = int(np.argmax(areas)) + 1
        return (labels == idx).astype(np.uint8) * 255

    # -------- empty / minus --------
    def _is_empty_robust(self, bw: np.ndarray) -> bool:
        """
        Пустота только по внутренней области (inner ROI), чтобы края/остатки рамки не влияли.
        """
        inner = self._inner_roi(bw, frac=0.14)

        h, w = inner.shape[:2]
        area = float(h * w)
        ink = int(cv2.countNonZero(inner))
        ink_ratio = ink / area

        if ink_ratio > self.cfg.empty_ink_ratio_max:
            return False

        cc = (inner > 0).astype(np.uint8)
        num, labels, stats, _ = cv2.connectedComponentsWithStats(cc, connectivity=8)
        if num <= 1:
            return True

        largest = int(np.max(stats[1:, cv2.CC_STAT_AREA]))
        largest_ratio = largest / area
        if largest_ratio <= self.cfg.empty_largest_cc_ratio_max:
            return True

        # Доп: если largest выглядит как тонкая линия/полоска — это не цифра
        idx = int(np.argmax(stats[1:, cv2.CC_STAT_AREA])) + 1
        x, y, ww, hh, _ = stats[idx]
        aspect = max(ww / max(1.0, hh), hh / max(1.0, ww))
        thick = min(ww, hh) / float(min(h, w))

        if aspect >= self.cfg.empty_line_aspect_min and thick <= self.cfg.empty_line_thick_max:
            return True

        return False

    def _is_noise_symbol(self, sym: np.ndarray) -> bool:
        """
        sym: 0/255, уже largest component.
        Возвращает True если это вероятный мусор/артефакт (пустая клетка).
        """
        h, w = sym.shape[:2]
        area = float(h * w)
        ink = int(cv2.countNonZero(sym))
        if ink == 0:
            return True

        ys, xs = np.where(sym > 0)
        x1, x2 = xs.min(), xs.max()
        y1, y2 = ys.min(), ys.max()
        bw = (x2 - x1 + 1)
        bh = (y2 - y1 + 1)
        box_area = float(bw * bh)
        fill = ink / max(1.0, box_area)
        aspect = max(bw / max(1.0, bh), bh / max(1.0, bw))
        aspect_w_h = bh / max(1.0, bw)

        # подозрительная "ложная единица": очень тонкая, очень мало ink, близко к краю
        edge_margin = int(round(0.10 * min(h, w)))
        touches_edge_zone = (
            x1 <= edge_margin
            or x2 >= w - 1 - edge_margin
            or y1 <= edge_margin
            or y2 >= h - 1 - edge_margin
        )
        if touches_edge_zone and aspect_w_h > 4.5 and (ink / area) < 0.0014:
            return True

        if (ink / area) < self.cfg.noise_min_ink_ratio:
            return True

        if box_area / area < self.cfg.noise_box_area_ratio_max and fill > self.cfg.noise_fill_min:
            return True

        # исключение для '1': высокая узкая компонента в центре
        cx = 0.5 * (x1 + x2)
        cy = 0.5 * (y1 + y2)
        center_ok = (abs(cx - w / 2.0) < 0.22 * w) and (abs(cy - h / 2.0) < 0.30 * h)
        if center_ok and aspect_w_h > 4.5 and (bh / h) > 0.40:
            # скорее всего единица (или часть цифры), не считаем мусором
            return False

        thick = min(bw, bh) / float(min(h, w))
        if aspect >= self.cfg.noise_line_aspect_min and thick <= self.cfg.noise_line_thick_max:
            return True

        return False

    def _is_minus(self, bw: np.ndarray) -> bool:
        """
        Минус должен быть:
        - тонкий горизонтальный штрих примерно по центру
        - bbox широкий и невысокий
        - доминирующая "полоса" в горизонтальной проекции
        - без сильных вертикальных пиков (чтобы не спутать с '1' или '7')
        - угол линии около 0 градусов
        """
        # Найдём крупнейшую компоненту (если цифра, она обычно крупнейшая)
        comp = self._largest_component_mask(bw)
        if comp is None:
            return False

        ys, xs = np.where(comp > 0)
        if len(xs) < 10:
            return False

        x1, x2 = xs.min(), xs.max()
        y1, y2 = ys.min(), ys.max()
        bbox_w = (x2 - x1 + 1)
        bbox_h = (y2 - y1 + 1)

        h, w = bw.shape[:2]
        aspect = bbox_w / max(1.0, float(bbox_h))

        if aspect < self.cfg.minus_aspect_min:
            return False
        if bbox_h / h > self.cfg.minus_height_ratio_max:
            return False
        if bbox_w / w < self.cfg.minus_width_ratio_min:
            return False

        cy = (y1 + y2) / 2.0
        if abs(cy - (h / 2.0)) / h > self.cfg.minus_center_band:
            return False

        # Проекции
        ink = max(1, int(cv2.countNonZero(comp)))
        row_sum = np.sum(comp > 0, axis=1).astype(np.float32)
        col_sum = np.sum(comp > 0, axis=0).astype(np.float32)

        row_peak_ratio = float(row_sum.max() / ink)
        col_peak_ratio = float(col_sum.max() / ink)

        if row_peak_ratio < self.cfg.minus_row_peak_ratio_min:
            return False
        if col_peak_ratio > self.cfg.minus_col_peak_ratio_max:
            return False

        # Угол: через fitLine (устойчивее к шуму, чем Хафф на маленьких ROI)
        pts = np.column_stack([xs.astype(np.float32), ys.astype(np.float32)])
        if len(pts) < 20:
            return False

        vx, vy, _, _ = cv2.fitLine(pts, cv2.DIST_L2, 0, 0.01, 0.01)
        angle = float(np.degrees(np.arctan2(vy, vx)))
        # приводим к [-90, 90]
        while angle <= -90:
            angle += 180
        while angle > 90:
            angle -= 180

        if abs(angle) > self.cfg.minus_angle_max_deg:
            return False

        return True

    def _largest_component_mask(self, bw: np.ndarray) -> Optional[np.ndarray]:
        num, labels, stats, _ = cv2.connectedComponentsWithStats((bw > 0).astype(np.uint8), connectivity=8)
        if num <= 1:
            return None
        areas = stats[1:, cv2.CC_STAT_AREA]
        idx = int(np.argmax(areas)) + 1
        mask = (labels == idx).astype(np.uint8) * 255
        return mask

    # -------- MNIST formatting --------
    def _to_mnist_28x28(self, bw: np.ndarray) -> np.ndarray:
        """
        Делает MNIST-подобную нормализацию:
        - берём крупнейшую компоненту (основной символ)
        - обрезаем bbox + небольшой отступ
        - ресайзим так, чтобы символ влез в 20x20
        - центрируем по центру масс на 28x28
        - выдаём float32 [0,1], white stroke on black background
        """
        comp = self._largest_component_mask(bw)
        if comp is None:
            # если вдруг пусто, но эвристика не поймала
            return np.zeros((28, 28), np.float32)

        ys, xs = np.where(comp > 0)
        x1, x2 = xs.min(), xs.max()
        y1, y2 = ys.min(), ys.max()

        # небольшой padding
        pad = int(round(0.12 * max(x2 - x1 + 1, y2 - y1 + 1)))
        x1 = max(0, x1 - pad)
        y1 = max(0, y1 - pad)
        x2 = min(comp.shape[1] - 1, x2 + pad)
        y2 = min(comp.shape[0] - 1, y2 + pad)

        crop = comp[y1 : y2 + 1, x1 : x2 + 1]

        # resize into 20x20 box preserving aspect
        ch, cw = crop.shape[:2]
        if ch == 0 or cw == 0:
            return np.zeros((28, 28), np.float32)

        scale = 20.0 / max(ch, cw)
        nh = max(1, int(round(ch * scale)))
        nw = max(1, int(round(cw * scale)))
        resized = cv2.resize(crop, (nw, nh), interpolation=cv2.INTER_NEAREST)

        canvas = np.zeros((28, 28), np.uint8)

        # центр масс (на resized), чтобы центрировать как MNIST
        m = cv2.moments((resized > 0).astype(np.uint8))
        if abs(m["m00"]) < 1e-6:
            cy, cx = nh / 2.0, nw / 2.0
        else:
            cx = m["m10"] / m["m00"]
            cy = m["m01"] / m["m00"]

        # хотим, чтобы (cx,cy) попал в центр 28x28
        target_cx, target_cy = 14.0, 14.0
        # координаты top-left для вставки
        x0 = int(round(target_cx - cx))
        y0 = int(round(target_cy - cy))

        # но в MNIST обычно ещё есть "рамка" — поэтому сначала кладём в пределах 28x28 аккуратно
        for y in range(nh):
            yy = y0 + y
            if 0 <= yy < 28:
                row = resized[y]
                for x in range(nw):
                    xx = x0 + x
                    if 0 <= xx < 28:
                        canvas[yy, xx] = max(canvas[yy, xx], row[x])

        # нормализация в float [0,1]
        out = (canvas.astype(np.float32) / 255.0)
        return out
