# Отчёт: преобразования клетки до классификации «пусто»

Документ описывает **все шаги и параметры** от сырого изображения клетки до решения «пустая клетка» (`recognize_bgr` → `None`). На основе отчёта можно решить, какие пороги усилить.

---

## Общая схема

```
img_bgr
    → _preprocess_to_clean_binary(img_bgr)  →  bw (0/255, без largest component)
    → _is_empty_robust(bw)
        → если True  →  return None (пусто)
        → если False →  sym = _keep_largest_component(bw)
                        → _is_noise_symbol(sym)?  → True: return None
                        → _is_minus(sym)?         → True: return "-"
                        → _to_mnist_28x28(sym)    → mn (28×28, float [0,1])
                        → clf.predict_digit(mn)   → цифра "0".."9"
```

Решение «пусто» принимается в `_is_empty_robust(bw)` или в `_is_noise_symbol(sym)`. После этого крупнейшая компонента `sym` переводится в формат MNIST функцией `_to_mnist_28x28(sym)` без дополнительных морфологических операций над цифрой.

---

## 1. `_preprocess_to_clean_binary(img_bgr)` → `bw`

Вход: BGR-изображение клетки. Выход: бинарное изображение 0/255 (255 = чернила), **без** выделения самой большой компоненты.

### 1.1. Приведение к серому

- **Действие:** `cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)` при 3 каналах, иначе копия.
- **Параметры:** нет.

### 1.2. CLAHE (контраст)

- **Действие:** `cv2.createCLAHE(...)` + `clahe.apply(g)`.
- **Параметры (HeuristicsConfig):**
  - `clahe_clip: float = 2.0`
  - `clahe_grid: int = 8` (tileGridSize = (8, 8))

### 1.3. Размытие

- **Действие:** `cv2.GaussianBlur(g, (3, 3), 0)`.
- **Параметры:** ядро 3×3, sigma=0.

### 1.4. Чистка границ клетки: `clean_cell_borders_v2(g, BorderCleanParamsV2())`

Вход: серое изображение. Выход не используется по серому; берётся только **второй** — `cleaned_ink` (uint8, 255 = чернила). Дальше везде работа идёт с этим бинарником.

Внутри `clean_cell_borders_v2`:

- **Серое → бинаризация чернил** (`_binarize_ink`):
  - Консервативная бинаризация под чёрную гелевую ручку: серый шум не попадает в чернила.
  - `cv2.GaussianBlur(g, (3, 3), 0)` → оценка фона по квантилям: `p50, p80, p90`, `bg = 0.5*p80 + 0.5*p90`.
  - **Абсолютный порог:** пиксель ≤ `abs_thr` (70) → чернила.
  - **Относительный порог:** пиксель ≤ `bg - delta` (delta=55) → чернила.
  - Итог: чернила, если выполняется хотя бы один критерий; затем удаляются только связные компоненты с площадью ≤ 2 (микроточки), без MORPH_OPEN.
  - Параметры: `abs_thr = 70`, `delta = 55` (можно тюнить 60–90 и 40–70 соответственно).

- **Прибрежная зона (edge band):**
  - `band = max(1, round(min(h,w) * edge_band_frac))`
  - **Параметры (BorderCleanParamsV2):**
    - `edge_band_frac: float = 0.16` (16% от меньшей стороны)

- **Ядро цифры из внутренней области:**
  - Внутри `inner`: обнуляются полосы шириной `band` по краям (верх/низ/лево/право).
  - Open по `inner`: ядро `k_core × k_core`, `k_core = 3` если `min(h,w) >= 24`, иначе `2`.
  - **Параметры:** только размер ядра, без доп. параметров.

- **Поддержка цифры (расширение ядра):**
  - `d = max(1, int(support_dilate))`, ядро `(2*d+1)×(2*d+1)`.
  - **Параметры (BorderCleanParamsV2):**
    - `support_dilate: int = 2` → ядро 5×5.

- **Длинные линии у края (кандидаты рамки):**
  - Ядра: горизонтальное `(k_h, 1)`, вертикальное `(1, k_v)`:
    - `k_h = max(7, round(w * long_line_frac))`
    - `k_v = max(7, round(h * long_line_frac))`
  - **Параметры (BorderCleanParamsV2):**
    - `long_line_frac: float = 0.70` (70% от ширины/высоты).

- **Полные строки/столбцы в band:**
  - Строка в верхнем/нижнем band: чернила в строке `>= full_row_frac * w`.
  - Столбец в левом/правом band: чернила в столбце `>= full_col_frac * h`.
  - **Параметры (BorderCleanParamsV2):**
    - `full_row_frac: float = 0.80`
    - `full_col_frac: float = 0.80`

- **Удаление рамки:** удаляется пересечение кандидатов рамки с дополнением «поддержки цифры». Результат — `cleaned_ink`.

- **Доп. зачистка прижатых к краю CC** (если `cleanup_border_cc`):
  - Компонента считается «у края», если bbox касается границы кадра.
  - Удаляются компоненты у края с:
    - `thick = min(ww, hh) <= cc_max_thickness`
    - `leng = max(ww, hh) >= cc_min_len`
    - и без пересечения с `digit_support`.
  - **Параметры (BorderCleanParamsV2):**
    - `cleanup_border_cc: bool = True`
    - `cc_max_thickness: int = 3`
    - `cc_min_len_frac: float = 0.30` → `cc_min_len = max(3, round(min(h,w)*0.30))`

После `clean_cell_borders_v2` в preprocess используется только **cleaned_ink** как `bw`.

### 1.5. Морфологическое открытие (мелкий мусор)

- **Действие:** не выполняется (в коде закомментировано: «Open 2×2 не делаем — режет тонкие штрихи и рвёт «3»»).

### 1.6. Удаление «рамочных» компонент по CC: `_remove_border_lines_by_cc(bw)`

- **Пограничная полоса:**
  - `band = round(min(h,w) * border_band_frac)`, затем `clip(band, border_band_min, border_band_max)`.
- **Параметры (HeuristicsConfig):**
  - `border_band_frac: float = 0.10` (10% от min(h,w))
  - `border_band_min: int = 2`
  - `border_band_max: int = 10`

- Для каждой компоненты (area ≥ 8), **касающейся** этой полосы, проверяется:
  - `aspect = max(ww/hh, hh/ww)`
  - `fill = area / (ww*hh)`
  - `thickness_ok = (min(ww,hh) / min(h,w)) <= line_thickness_max_frac`
  - Компонента обнуляется, если **одновременно:**
    - `aspect >= line_aspect_min`
    - `fill <= line_fill_max`
    - `thickness_ok == True`
- **Параметры (HeuristicsConfig):**
  - `line_aspect_min: float = 6.0`
  - `line_fill_max: float = 0.35`
  - `line_thickness_max_frac: float = 0.18`

### 1.7. Жёсткая обрезка краёв: `_safe_trim_edges(bw)`

- **Действие:** обнуление полосы по периметру шириной `t` пикселей (верх/низ/лево/право).
- **Расчёт:** `t = round(0.06 * min(h,w))`, затем `clip(t, 1, 4)` → итог от 1 до 4 px.
- **Параметры:** 0.06 и (1, 4) зашиты в коде, в конфиг не вынесены.

Итог шага 1: **`bw`** — бинарник после всей очистки и trim, без выделения largest component. Именно он подаётся в `_is_empty_robust`.

---

## 2. Решение «пусто»: `_is_empty_robust(bw)`

Вход: бинарное изображение `bw` (0/255) после пункта 1. Возвращает `True` → клетка считается пустой.

**Важно:** все проверки выполняются **по внутренней области (inner ROI)**, а не по всему кадру: `inner = _inner_roi(bw, frac=0.14)` (отступ от краёв ~14% от min(h,w), clip 2–6 px), чтобы края и остатки рамки не влияли на решение.

Порядок проверок (сразу выход при срабатывании):

### 2.1. Доля чернил во внутренней области

- `inner = _inner_roi(bw, frac=0.14)`; `area = h * w` (размер inner).
- `ink = cv2.countNonZero(inner)`
- `ink_ratio = ink / area`
- **Если** `ink_ratio > empty_ink_ratio_max` → **return False** (не пусто, дальше не проверяем).

**Параметр (HeuristicsConfig):**  
`empty_ink_ratio_max: float = 0.0016` (0.16% площади inner).

### 2.2. Нет связных компонент (только фон)

- `cv2.connectedComponentsWithStats(inner, connectivity=8)`.
- **Если** `num <= 1` (нет ни одной компоненты чернил) → **return True** (пусто).

**Параметры:** нет (connectivity=8 зашито).

### 2.3. Крупнейшая компонента слишком маленькая

- `largest = max(area всех компонент, кроме фона)` по inner.
- `largest_ratio = largest / area`
- **Если** `largest_ratio <= empty_largest_cc_ratio_max` → **return True** (пусто).

**Параметр (HeuristicsConfig):**  
`empty_largest_cc_ratio_max: float = 0.0008` (0.08% площади inner).

### 2.4. Крупнейшая компонента — «тонкая длинная линия» (остаток рамки/шум)

- Берётся компонента с максимальной площадью по inner: её bbox `(x, y, ww, hh)`.
- `aspect = max(ww/hh, hh/ww)`
- `thick = min(ww, hh) / min(h, w)` (h,w — размер inner).
- **Если** `aspect >= empty_line_aspect_min` **и** `thick <= empty_line_thick_max` → **return True** (пусто).

**Параметры (HeuristicsConfig):**  
`empty_line_aspect_min: float = 5.0`, `empty_line_thick_max: float = 0.16`.

### 2.5. Иначе

- **return False** (не пусто) → дальше `_keep_largest_component(bw)` → символ `sym`, затем veto по шуму, проверка минуса, подготовка к MNIST (см. раздел 3).

---

## 3. Обработка цифры перед подачей в модель

После того как клетка признана непустой, дальнейшая цепочка: одна крупнейшая компонента → фильтр «мусор» → проверка «минус» → нормализация в формат MNIST → предсказание модели.

### 3.1. Выделение символа: `_keep_largest_component(bw)`

- **Вход:** бинарник `bw` (0/255) после пункта 1.
- **Действие:** `cv2.connectedComponentsWithStats(bw, 8)`; выбирается компонента с максимальной площадью; остальное обнуляется.
- **Выход:** `sym` — бинарное изображение 0/255 с одной связной компонентой (основной символ).

### 3.2. Veto «мусор/артефакт»: `_is_noise_symbol(sym)`

Если возвращает **True**, символ не отправляется в MNIST, результат распознавания — **None** (как пустая клетка).

- **Условия (хотя бы одно → мусор):**
  1. Нет чернил: `ink == 0` → True.
  2. Слишком мало чернил: `ink / area < noise_min_ink_ratio` → True.
  3. Маленький bbox и плотная заливка: `box_area/area < noise_box_area_ratio_max` и `fill > noise_fill_min` → True (компактный артефакт).
  4. Длинная тонкая линия: `aspect >= noise_line_aspect_min` и `thick <= noise_line_thick_max` → True.

**Параметры (HeuristicsConfig):**  
`noise_min_ink_ratio = 0.0020`, `noise_box_area_ratio_max = 0.05`, `noise_fill_min = 0.70`,  
`noise_line_aspect_min = 6.0`, `noise_line_thick_max = 0.14`.

### 3.3. Проверка «минус»: `_is_minus(sym)`

Если возвращает **True**, результат — `"-"`; в модель не подаётся.

- Проверяются: соотношение сторон bbox, положение по вертикали (центр по y), доминирование горизонтальной проекции, ограничение вертикальных пиков, угол линии (fitLine) в пределах ±12°.
- **Параметры (HeuristicsConfig):** `minus_aspect_min`, `minus_height_ratio_max`, `minus_width_ratio_min`, `minus_center_band`, `minus_row_peak_ratio_min`, `minus_col_peak_ratio_max`, `minus_angle_max_deg` (см. `cell_ocr/config.py`).

### 3.4. Нормализация в формат MNIST: `_to_mnist_28x28(sym)`

Вход: бинарный символ `sym` (0/255, одна компонента). Выход: массив 28×28, `float32` в диапазоне [0, 1], **белый штрих на чёрном фоне** (как в датасете MNIST).

Шаги:

1. **Bbox и отступ:** по маске чернил находятся `x1, y1, x2, y2`; добавляется отступ `pad = round(0.12 * max(bbox_w, bbox_h))`; по этим границам вырезается `crop`.
2. **Ресайз в бокс 20×20:** масштаб `scale = 20.0 / max(ch, cw)` с сохранением пропорций; ресайз `cv2.resize(..., INTER_NEAREST)`.
3. **Центрирование на 28×28:** центр масс (moments) по `resized`; сдвиг так, чтобы центр масс совпал с (14, 14); результат рисуется на чёрном холсте 28×28 (обрезание по границам).
4. **Нормализация:** `canvas.astype(np.float32) / 255.0` → значения 0.0 (фон) и 1.0 (штрих).

**Параметры:** коэффициент отступа 0.12 и размер целевого бокса 20×20 зашиты в коде. Морфологических операций над цифрой на этом этапе нет.

### 3.5. Предсказание модели

- **Вход:** `mn` — массив 28×28, float [0, 1], white-on-black.
- **Действие:** `clf.predict_digit(mn)` (модель обучена на MNIST-подобных данных).
- **Выход:** цифра 0–9, возвращается как строка `"0"` … `"9"`.

При включённом `debug_mnist_dir` массив `mn` перед вызовом модели сохраняется в PNG (имя — по `debug_source_name` или счётчик).

---

## Сводная таблица параметров, влияющих на «пусто»

| Где | Параметр | Текущее значение | Назначение |
|-----|----------|------------------|------------|
| **HeuristicsConfig** | `empty_ink_ratio_max` | 0.0016 | Порог доли чернил во inner: выше → не пусто |
| **HeuristicsConfig** | `empty_largest_cc_ratio_max` | 0.0008 | Порог доли площади крупнейшей CC: ниже → пусто |
| **HeuristicsConfig** | `empty_line_aspect_min` | 5.0 | Выше → легче признать остаток линии пустым |
| **HeuristicsConfig** | `empty_line_thick_max` | 0.16 | Ниже → легче признать тонкую линию пустым |
| **preprocess (код)** | inner ROI frac | 0.14 | Доля min(h,w) для отступа inner; clip(pad, 2, 6) px |
| **preprocess (код)** | trim: доля размера | 0.06 | Доля min(h,w) для ширины обрезки |
| **preprocess (код)** | trim: min/max px | (1, 4) | Ширина обрезки в пикселях |
| **image_utils** | `_binarize_ink` abs_thr | 70 | Абсолютный порог «почти чёрное»; серый шум не в чернилах |
| **image_utils** | `_binarize_ink` delta | 55 | Относительный порог (темнее фона на delta) |

Остальные параметры (CLAHE, border_band_*, line_* в `_remove_border_lines_by_cc`, все `BorderCleanParamsV2`) влияют на то, **какой** `bw` попадает в `_is_empty_robust`, но не на сами числовые пороги пустоты.

---

## Что можно усилить (идеи)

1. **Сделать пустоту строже:** уменьшить `empty_ink_ratio_max` и/или `empty_largest_cc_ratio_max`, чтобы меньше «мусорных» клеток проходили как непустые.
2. **Жёстче отсекать линии:** изменить `empty_line_aspect_min` / `empty_line_thick_max` в HeuristicsConfig, чтобы чаще считать тонкие остатки рамки пустотой.
3. **Сильнее обрезать край:** увеличить коэффициент trim (сейчас 0.06) или верхнюю границу (сейчас 4 px) в `_safe_trim_edges`.
4. **Бинаризация:** консервативная бинаризация в `_binarize_ink` (abs_thr=70, delta=55) уже отсекает серый шум; при необходимости можно тюнить эти пороги (60–90 и 40–70) или добавить авто-адаптацию по статистике клетки.

После изменений имеет смысл прогнать тесты/ручную проверку на типичных пустых клетках, которые сейчас ошибочно классифицируются.
