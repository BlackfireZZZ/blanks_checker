# Конфиг эвристик распознавания клетки
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HeuristicsConfig:
    # Бинаризация
    clahe_clip: float = 2.0
    clahe_grid: int = 8

    # Граница: сколько пикселей считаем "пограничной зоной"
    border_band_frac: float = 0.10  # 10% от min(h,w)
    border_band_min: int = 2
    border_band_max: int = 10

    # Фильтр "линейных" компонент (рамка)
    line_aspect_min: float = 6.0        # сильно вытянутая
    line_fill_max: float = 0.35         # "плотность" в bbox, линия обычно разрежена
    line_thickness_max_frac: float = 0.18  # линия не должна быть слишком толстой

    # Пустая клетка: лимиты по "чернилам" (строже, чтобы не пропускать артефакты)
    empty_ink_ratio_max: float = 0.0016
    empty_largest_cc_ratio_max: float = 0.0008
    # линия-артефакт в empty-check
    empty_line_aspect_min: float = 5.0
    empty_line_thick_max: float = 0.16

    # Noise veto для sym перед MNIST (отсечь мусор/артефакты)
    noise_min_ink_ratio: float = 0.0010          # если меньше 0.1% — мусор (не режем тонкую '1')
    noise_box_area_ratio_max: float = 0.035     # bbox занимает меньше 3.5% клетки
    noise_fill_min: float = 0.80                 # внутри bbox сильно заполнено (не ловить '1' как плотный артефакт)
    noise_line_aspect_min: float = 8.0            # строже: тонкую '1' не считать линией так легко
    noise_line_thick_max: float = 0.12           # строже к реальным линиям

    # Минус: условия
    minus_aspect_min: float = 4.5           # width/height у bbox минуса
    minus_height_ratio_max: float = 0.22    # bbox_h / roi_h
    minus_width_ratio_min: float = 0.42     # bbox_w / roi_w
    minus_center_band: float = 0.22         # минус должен быть около центра по y
    minus_row_peak_ratio_min: float = 0.42  # max(row_sum)/total_ink
    minus_col_peak_ratio_max: float = 0.22  # max(col_sum)/total_ink
    minus_angle_max_deg: float = 12.0       # линия почти горизонтальная

    # Guard по чёрному в центре (гелевые ручки)
    center_black_thr: int = 55
    center_black_count_min: int = 6
