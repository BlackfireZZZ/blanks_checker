# Параметры очистки границ клетки
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BorderCleanParamsV2:
    # Прибрежная зона (в долях от min(h,w)), где ожидаем рамку
    edge_band_frac: float = 0.16

    # Порог "почти целая строка/столбец" (доля ширины/высоты)
    full_row_frac: float = 0.80
    full_col_frac: float = 0.80

    # Длина структурного элемента для поиска длинных линий (доля от W/H)
    long_line_frac: float = 0.70

    # Поддержка цифры: насколько расширяем "ядро", чтобы не срезать касание с рамкой
    support_dilate: int = 2  # 1..3 обычно

    # После удаления рамки можно слегка почистить одиночный мусор у края
    cleanup_border_cc: bool = True
    # Максимальная "толщина" компоненты у края, которую можно удалять как рамку/мусор
    cc_max_thickness: int = 3
    # Мин. длина (в долях min(h,w)) для компонент-линий у края
    cc_min_len_frac: float = 0.30
