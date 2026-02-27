"""
Recognize a single symbol from a scanned answer-sheet cell image.

Each cell contains exactly one of:
- empty cell         -> "E"
- a minus sign "-"   -> "-"
- a digit "0".."9"   -> digit string

This module is intentionally training-free: digits are classified using a pretrained
MNIST model (PyTorch). All quality depends on preprocessing that converts a cell
image into an MNIST-like 28×28 crop.

UPDATED PIPELINE (stability-focused, tested on your ZIP sample set):
- OPTIONAL tiny border shrink (adaptive two-pass: shrink=1 then fallback to shrink=0)
- light blur
- percentile-based threshold (no Otsu), with STRICT/RELAX deltas (two-pass)
- NO global close/dilate (prevents "slipping"/merging strokes)
- connected components cleanup:
    - remove tiny components (noise)
    - remove grid-like edge components using edge-band + geometry + mean-gray check
- robust empty detection:
    - uses both ink count AND dark-percentile (protects digit "1" and vertical strokes)
- minus detection (heuristic) on cleaned mask
- MNIST 28×28 canonicalization (+ center-of-mass alignment)
- digit classification

CLI:
    python -m cell_ocr path/to/cell.png --debug-out debug_dir
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

try:
    import timm
except Exception as e:  # pragma: no cover
    raise RuntimeError(
        "This ResNet version requires timm. Install it:\n"
        "  pip install timm\n"
        "If you want torchvision ResNet, switch back to that implementation."
    ) from e

MNIST_CANVAS = 28

# -----------------------------
# Hyperparameters (UPDATED)
# -----------------------------

# Adaptive border shrink:
# First pass tries shrink=1 (helps remove faint border), but if it looks "suspicious"
# we fallback to shrink=0 to avoid cutting digits near the edge.
BORDER_SHRINK_PX_PRIMARY = 1
BORDER_SHRINK_PX_FALLBACK = 0

BLUR_KSIZE = 3

# Robust percentile thresholding (two-pass):
BG_PERCENTILE = 90
DELTA_STRICT = 24  # conservative: avoids turning grid into ink + avoids merging strokes
DELTA_RELAX = 18   # fallback: if strict becomes too thin but image has real dark strokes
T_MIN = 170
T_MAX = 245

# Connected components cleanup
AREA_MIN = 6  # remove tiny specks

# Edge-grid suppression (very important for empty cells with faint borders)
EDGE_BAND = 2
EDGE_THICK_MAX = EDGE_BAND + 4  # "thin" along at least one axis
EDGE_AREA_MAX = 250
EDGE_GRAY_MARGIN = 10  # remove edge component if it's not much darker than threshold

# Empty detection (robust, protects "1" and thin vertical strokes)
EMPTY_MIN_INK_PX = 25
EMPTY_P1_GRAY_MIN = 200  # if even the darkest 1% pixels are still bright -> empty
DARK_P1_PERCENTILE = 1

# If shrink pass returned empty-ish ink but p1 is dark -> likely we cut a digit -> fallback
FALLBACK_P1_DARK = 180

# Minus detection (same as before, works well after cleanup)
MINUS_ASPECT_MIN = 2.8
MINUS_HEIGHT_MAX_FRAC = 0.35
MINUS_FILL_MIN = 0.20
MINUS_INK_MIN = 40

# MNIST canonicalization
BBOX_PAD_PX = 3  # slightly larger pad to avoid losing thin strokes after stricter threshold
MNIST_CANVAS = 28
MNIST_TARGET_MAX_SIDE = 20

# ResNet-specific: build MNIST-like grayscale (not binary) for classification
BG_NORM_SIGMA = 12  # illumination normalization blur sigma
CONTRAST_P_LOW = 5
CONTRAST_P_HIGH = 95
EPS = 1e-6

# -----------------------------
# Utilities
# -----------------------------


def _clamp_int(x: float, lo: int, hi: int) -> int:
    return int(max(lo, min(hi, int(round(x)))))


def _to_gray(img: np.ndarray) -> np.ndarray:
    """
    Convert BGR/RGB/GRAY to grayscale uint8 without relying on channel order.
    """
    if img.ndim == 2:
        if img.dtype == np.uint8:
            return img
        return np.clip(img, 0, 255).astype(np.uint8)
    if img.ndim != 3 or img.shape[2] < 3:
        raise ValueError(f"Expected HxW or HxWxC image, got shape {img.shape}")
    rgb_like = img[:, :, :3].astype(np.float32)
    gray = np.mean(rgb_like, axis=2)
    return np.clip(gray, 0, 255).astype(np.uint8)


def _safe_crop_border(gray: np.ndarray, shrink: int) -> np.ndarray:
    if shrink <= 0:
        return gray
    h, w = gray.shape[:2]
    if h <= 2 * shrink or w <= 2 * shrink:
        return gray
    return gray[shrink:-shrink, shrink:-shrink]


def _bbox_from_mask(mask: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
    ys, xs = np.where(mask > 0)
    if xs.size == 0:
        return None
    x1 = int(xs.min())
    x2 = int(xs.max())
    y1 = int(ys.min())
    y2 = int(ys.max())
    return x1, y1, x2, y2


def _pad_and_clip_bbox(
    bbox: Tuple[int, int, int, int],
    pad_px: int,
    h: int,
    w: int,
) -> Tuple[int, int, int, int]:
    x1, y1, x2, y2 = bbox
    x1 = max(0, x1 - pad_px)
    y1 = max(0, y1 - pad_px)
    x2 = min(w - 1, x2 + pad_px)
    y2 = min(h - 1, y2 + pad_px)
    return x1, y1, x2, y2


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _write_debug_png(out_dir: Path, name: str, img: np.ndarray) -> None:
    _ensure_dir(out_dir)
    out_path = out_dir / name
    cv2.imwrite(str(out_path), img)


def _percentile_u8(gray: np.ndarray, q: float) -> float:
    return float(np.percentile(gray.reshape(-1), q))

def _illumination_normalize(gray_u8: np.ndarray) -> np.ndarray:
    """
    Make background more uniform (helps ResNet a lot on scanned cells).
    Returns uint8 image.
    """
    g = gray_u8.astype(np.float32)
    bg = cv2.GaussianBlur(g, (0, 0), sigmaX=BG_NORM_SIGMA, sigmaY=BG_NORM_SIGMA)
    bg = np.clip(bg, 1.0, 255.0)
    norm = cv2.divide(g, bg, scale=255.0)
    norm = np.clip(norm, 0.0, 255.0).astype(np.uint8)
    # tiny blur for stability (keeps anti-alias, reduces salt noise)
    norm = cv2.GaussianBlur(norm, (BLUR_KSIZE, BLUR_KSIZE), 0)
    return norm


# -----------------------------
# Connected components cleanup
# -----------------------------


def _remove_small_components(mask: np.ndarray, area_min: int) -> np.ndarray:
    if area_min <= 1:
        return mask
    num, labels, stats, _ = cv2.connectedComponentsWithStats((mask > 0).astype(np.uint8), connectivity=8)
    if num <= 1:
        return mask
    out = mask.copy()
    for lab in range(1, num):
        area = int(stats[lab, cv2.CC_STAT_AREA])
        if area < area_min:
            out[labels == lab] = 0
    return out


def _remove_edge_grid_components(mask: np.ndarray, gray: np.ndarray, t: int) -> np.ndarray:
    """
    Remove components near the cell border that look like faint grid/border artifacts.

    Criteria (stable on your set):
    - component touches EDGE_BAND band near any border
    - component is thin along at least one axis
    - component area is not huge
    - component is not significantly darker than the threshold (i.e. likely grid, not digit)
    """
    H, W = mask.shape[:2]
    num, labels, stats, _ = cv2.connectedComponentsWithStats((mask > 0).astype(np.uint8), connectivity=8)
    if num <= 1:
        return mask

    out = mask.copy()

    for lab in range(1, num):
        x = int(stats[lab, cv2.CC_STAT_LEFT])
        y = int(stats[lab, cv2.CC_STAT_TOP])
        w = int(stats[lab, cv2.CC_STAT_WIDTH])
        h = int(stats[lab, cv2.CC_STAT_HEIGHT])
        area = int(stats[lab, cv2.CC_STAT_AREA])

        # near border?
        near_left = x <= EDGE_BAND
        near_top = y <= EDGE_BAND
        near_right = (x + w) >= (W - EDGE_BAND)
        near_bottom = (y + h) >= (H - EDGE_BAND)
        if not (near_left or near_top or near_right or near_bottom):
            continue

        # thin and limited area?
        if not (min(w, h) <= EDGE_THICK_MAX):
            continue
        if area > EDGE_AREA_MAX:
            continue

        comp_pixels = (labels == lab)
        if not np.any(comp_pixels):
            continue

        mean_g = float(np.mean(gray[comp_pixels]))
        # If it's close to threshold (i.e. light), it's likely grid/border.
        if mean_g >= float(t - EDGE_GRAY_MARGIN):
            out[comp_pixels] = 0

    return out


# -----------------------------
# Preprocessing (UPDATED pipeline)
# -----------------------------


def _threshold_percentile(gray_blur: np.ndarray, delta: int) -> Tuple[np.ndarray, int, float]:
    bg = _percentile_u8(gray_blur, BG_PERCENTILE)
    t = int(bg - float(delta))
    t = int(max(T_MIN, min(T_MAX, t)))
    mask = ((gray_blur < t).astype(np.uint8)) * 255
    return mask, t, bg


def preprocess_cell_to_binary(
    img: np.ndarray,
    *,
    shrink: int,
    delta: int,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Convert input image to a clean binary mask (ink=255, bg=0).
    Returns (mask_clean, debug_info).
    """
    debug: Dict[str, Any] = {}

    gray0 = _to_gray(img)
    gray = _safe_crop_border(gray0, shrink)

    # Keep a copy of original-gray (after shrink) for robust empty checks
    gray_orig = gray.copy()

    gray_blur = cv2.GaussianBlur(gray, (BLUR_KSIZE, BLUR_KSIZE), 0)
    # ResNet classification path uses illumination-normalized grayscale
    gray_norm = _illumination_normalize(gray_orig)

    mask_raw, t, bg = _threshold_percentile(gray_blur, delta=delta)

    # Cleanup without CLOSE/DILATE to avoid merging strokes
    mask = mask_raw
    mask = _remove_small_components(mask, area_min=AREA_MIN)
    mask = _remove_edge_grid_components(mask, gray=gray_blur, t=t)

    ink = int(np.count_nonzero(mask))

    debug["shrink"] = int(shrink)
    debug["delta"] = int(delta)
    debug["bg"] = float(bg)
    debug["T"] = int(t)
    debug["gray_orig"] = gray_orig
    debug["gray"] = gray_blur
    debug["gray_norm"] = gray_norm
    debug["mask_raw"] = mask_raw
    debug["mask_clean"] = mask
    debug["ink_pixels"] = ink
    debug["p1"] = float(_percentile_u8(gray_orig, DARK_P1_PERCENTILE))

    bbox = _bbox_from_mask(mask)
    debug["bbox"] = bbox  # (x1, y1, x2, y2) or None
    if bbox is not None:
        x1, y1, x2, y2 = bbox
        w = x2 - x1 + 1
        h = y2 - y1 + 1
        H, W = mask.shape[:2]
        aspect = float(w) / float(max(h, 1))
        fill = float(ink) / float(max(w * h, 1))
        debug["bbox_w"] = w
        debug["bbox_h"] = h
        debug["mask_H"] = H
        debug["mask_W"] = W
        debug["aspect"] = aspect
        debug["fill"] = fill

    return mask, debug


def is_empty(binary_mask: np.ndarray, *, p1: float) -> bool:
    # Empty only if (very little ink) AND (no truly dark pixels in the original gray)
    ink = int(np.count_nonzero(binary_mask))
    return (ink < EMPTY_MIN_INK_PX) and (p1 > float(EMPTY_P1_GRAY_MIN))


def is_minus(binary_mask: np.ndarray) -> Tuple[bool, Dict[str, float]]:
    ink = int(np.count_nonzero(binary_mask))
    bbox = _bbox_from_mask(binary_mask)
    if bbox is None:
        return False, {"ink": float(ink), "aspect": 0.0, "fill": 0.0, "h_frac": 0.0}
    x1, y1, x2, y2 = bbox
    w = x2 - x1 + 1
    h = y2 - y1 + 1
    H, _W = binary_mask.shape[:2]
    aspect = float(w) / float(max(h, 1))
    fill = float(ink) / float(max(w * h, 1))
    h_frac = float(h) / float(max(H, 1))

    ok = (
        (ink >= MINUS_INK_MIN)
        and (aspect >= MINUS_ASPECT_MIN)
        and (h <= (MINUS_HEIGHT_MAX_FRAC * H))
        and (fill >= MINUS_FILL_MIN)
    )
    return ok, {"ink": float(ink), "aspect": aspect, "fill": fill, "h_frac": h_frac}


def to_mnist_28x28(binary_mask: np.ndarray) -> np.ndarray:
    """
    Convert a cleaned binary mask (ink=255) into MNIST-like 28×28 uint8 image (ink=255).
    """
    bbox = _bbox_from_mask(binary_mask)
    if bbox is None:
        return np.zeros((MNIST_CANVAS, MNIST_CANVAS), dtype=np.uint8)

    H, W = binary_mask.shape[:2]
    x1, y1, x2, y2 = _pad_and_clip_bbox(bbox, BBOX_PAD_PX, H, W)
    crop = binary_mask[y1 : y2 + 1, x1 : x2 + 1]

    ch, cw = crop.shape[:2]
    if ch <= 0 or cw <= 0:
        return np.zeros((MNIST_CANVAS, MNIST_CANVAS), dtype=np.uint8)

    max_side = max(ch, cw)
    if max_side == 0:
        return np.zeros((MNIST_CANVAS, MNIST_CANVAS), dtype=np.uint8)

    scale = float(MNIST_TARGET_MAX_SIDE) / float(max_side)
    new_w = max(1, int(round(cw * scale)))
    new_h = max(1, int(round(ch * scale)))
    interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
    resized = cv2.resize(crop, (new_w, new_h), interpolation=interp)

    canvas = np.zeros((MNIST_CANVAS, MNIST_CANVAS), dtype=np.uint8)
    off_x = (MNIST_CANVAS - new_w) // 2
    off_y = (MNIST_CANVAS - new_h) // 2
    x_end = min(MNIST_CANVAS, off_x + new_w)
    y_end = min(MNIST_CANVAS, off_y + new_h)
    canvas[off_y:y_end, off_x:x_end] = resized[: (y_end - off_y), : (x_end - off_x)]

    # Center-of-mass alignment
    ys, xs = np.where(canvas > 0)
    if xs.size > 0:
        com_x = float(xs.mean())
        com_y = float(ys.mean())
        target = float(MNIST_CANVAS // 2)  # 14
        dx = target - com_x
        dy = target - com_y
        M = np.array([[1.0, 0.0, dx], [0.0, 1.0, dy]], dtype=np.float32)
        canvas = cv2.warpAffine(
            canvas,
            M,
            (MNIST_CANVAS, MNIST_CANVAS),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0,
        )

    return canvas


def to_mnist_28x28_gray(gray_norm_u8: np.ndarray, binary_mask: np.ndarray) -> np.ndarray:
    """
    Build an MNIST-like 28x28 *grayscale* image for ResNet classification.

    Key points:
    - bbox is taken from the cleaned binary mask
    - pixels come from illumination-normalized grayscale (NOT binary)
    - we invert to MNIST convention: digit is bright on dark background
    - per-crop contrast normalization (percentiles) to match MNIST-like dynamic range
    - center-of-mass alignment using intensity weights (better than binary COM)

    Returns float32 array in range [0..1], shape (28,28).
    """
    bbox = _bbox_from_mask(binary_mask)
    if bbox is None:
        return np.zeros((MNIST_CANVAS, MNIST_CANVAS), dtype=np.float32)

    H, W = gray_norm_u8.shape[:2]
    x1, y1, x2, y2 = _pad_and_clip_bbox(bbox, BBOX_PAD_PX, H, W)
    crop = gray_norm_u8[y1 : y2 + 1, x1 : x2 + 1]
    if crop.size == 0:
        return np.zeros((MNIST_CANVAS, MNIST_CANVAS), dtype=np.float32)

    # MNIST convention: digit bright on dark
    inv = (255 - crop).astype(np.float32)

    # Robust local contrast normalize (prevents washed-out strokes or too-thick fills)
    lo = float(np.percentile(inv, CONTRAST_P_LOW))
    hi = float(np.percentile(inv, CONTRAST_P_HIGH))
    inv = (inv - lo) / max(hi - lo, EPS)
    inv = np.clip(inv, 0.0, 1.0)

    ch, cw = inv.shape[:2]
    max_side = max(ch, cw)
    scale = float(MNIST_TARGET_MAX_SIDE) / float(max_side)
    new_w = max(1, int(round(cw * scale)))
    new_h = max(1, int(round(ch * scale)))
    interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
    resized = cv2.resize(inv, (new_w, new_h), interpolation=interp)

    canvas = np.zeros((MNIST_CANVAS, MNIST_CANVAS), dtype=np.float32)
    off_x = (MNIST_CANVAS - new_w) // 2
    off_y = (MNIST_CANVAS - new_h) // 2
    x_end = min(MNIST_CANVAS, off_x + new_w)
    y_end = min(MNIST_CANVAS, off_y + new_h)
    canvas[off_y:y_end, off_x:x_end] = resized[: (y_end - off_y), : (x_end - off_x)]

    # Weighted center-of-mass (intensity) alignment
    wsum = float(canvas.sum())
    if wsum > 1e-6:
        ys, xs = np.indices(canvas.shape)
        com_x = float((canvas * xs).sum() / wsum)
        com_y = float((canvas * ys).sum() / wsum)
        target = float(MNIST_CANVAS // 2)  # 14
        dx = target - com_x
        dy = target - com_y
        M = np.array([[1.0, 0.0, dx], [0.0, 1.0, dy]], dtype=np.float32)
        canvas = cv2.warpAffine(
            canvas,
            M,
            (MNIST_CANVAS, MNIST_CANVAS),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0.0,
        )

    return np.clip(canvas, 0.0, 1.0)


# -----------------------------
# MNIST model (unchanged; easily swappable)
# -----------------------------


# -----------------------------
# MNIST digit classifier (ResNet18; drop-in replacement)
# Keeps the same public API: MnistDigitClassifier + predict_digit(...)
# -----------------------------


def _build_resnet18_mnist() -> nn.Module:
    """
    Build ResNet18 exactly like the HuggingFace snippet you posted (timm).
    This is the safest way to match those weights.
    """
    net = timm.create_model("resnet18", pretrained=False, num_classes=10)
    net.conv1 = torch.nn.Conv2d(1, 64, kernel_size=7, stride=2, padding=3, bias=False)
    return net


def _build_model_for_state_dict(state: dict) -> nn.Module:
    """
    ResNet-only builder (timm).
    """
    if "conv1.weight" not in state:
        raise RuntimeError("Weights do not contain conv1.weight; not a ResNet18 MNIST checkpoint?")
    return _build_resnet18_mnist()


@dataclass(frozen=True)
class MnistPrediction:
    digit: int
    confidence: float


class MnistDigitClassifier:
    """
    Loads a pretrained MNIST digit classifier from a .pt/.pth file and runs CPU inference.

    Expected input: 28×28 float array in range 0..1 where digit/ink is high (white on black).
    """

    def __init__(self, weights_path: str | Path, device: str = "cpu") -> None:
        self.device = torch.device(device)
        weights_path = Path(weights_path)
        if not weights_path.exists():
            raise FileNotFoundError(f"Weights file not found: {weights_path}")

        state = torch.load(weights_path, map_location=self.device)

        # Common wrappers: {"state_dict": {...}} or {"model": {...}}
        if isinstance(state, dict):
            if "state_dict" in state and isinstance(state["state_dict"], dict):
                state = state["state_dict"]
            elif "model" in state and isinstance(state["model"], dict):
                state = state["model"]

        if not isinstance(state, dict):
            raise RuntimeError("Expected a state_dict (dict of tensors) in the weights file.")

        # Sometimes keys are prefixed (e.g., 'module.' from DataParallel)
        if any(k.startswith("module.") for k in state.keys()):
            state = {k[len("module."):]: v for k, v in state.items()}

        self.model = _build_model_for_state_dict(state).to(self.device)
        self.model.load_state_dict(state, strict=True)
        self.model.eval()

    @torch.inference_mode()
    def predict_digit(self, mnist_28x28_float01: np.ndarray) -> MnistPrediction:
        # Match HF MNIST preprocessing: Normalize((0.1307,), (0.3081,))
        x = mnist_28x28_float01.astype(np.float32)
        x = np.clip(x, 0.0, 1.0)
        x = (x - 0.1307) / 0.3081
        x = torch.from_numpy(x).unsqueeze(0).unsqueeze(0).to(self.device)
        logits = self.model(x)
        probs = torch.softmax(logits, dim=1)[0]
        digit = int(torch.argmax(probs).item())
        conf = float(probs[digit].item())
        return MnistPrediction(digit=digit, confidence=conf)


_GLOBAL_CLF: Optional[MnistDigitClassifier] = None
_GLOBAL_CLF_WEIGHTS: Optional[str] = None


def _get_default_weights_path() -> str:
    """
    Resolve default path to ResNet MNIST weights.

    Priority:
    1) app/ocr/models/resnet18_mnist.pth
    2) app/ocr/resnet18_mnist.pth
    3) <project_root>/resnet18_mnist.pth
    """
    default_name = "resnet18_mnist.pth"
    here = Path(__file__).resolve().parent
    candidates = [
        here / "models" / default_name,
        here / default_name,
        here.parent.parent / default_name,
    ]
    for p in candidates:
        if p.is_file():
            return str(p)
    # Fallback: current working directory / plain name
    return default_name


def _get_classifier(weights_path: Optional[str | Path] = None) -> MnistDigitClassifier:
    global _GLOBAL_CLF, _GLOBAL_CLF_WEIGHTS
    w = str(weights_path) if weights_path is not None else _get_default_weights_path()
    if _GLOBAL_CLF is None or _GLOBAL_CLF_WEIGHTS != w:
        _GLOBAL_CLF = MnistDigitClassifier(weights_path=w, device="cpu")
        _GLOBAL_CLF_WEIGHTS = w
    return _GLOBAL_CLF


def predict_digit(mnist_28x28: np.ndarray, *, weights_path: Optional[str | Path] = None) -> int:
    """
    Predict a digit from an MNIST-like 28×28 image.
    Accepts uint8 0..255 or float 0..1 (ink high).
    Returns 0..9.
    """
    if mnist_28x28.shape != (MNIST_CANVAS, MNIST_CANVAS):
        raise ValueError(f"Expected 28x28, got {mnist_28x28.shape}")
    # Accept uint8 0..255 or float 0..1. Classifier will apply MNIST Normalize.
    if mnist_28x28.dtype == np.uint8:
        x = mnist_28x28.astype(np.float32) / 255.0
    else:
        x = mnist_28x28.astype(np.float32)
        x = np.clip(x, 0.0, 1.0)

    clf = _get_classifier(weights_path=weights_path)
    pred = clf.predict_digit(x)
    return int(pred.digit)

# -----------------------------
# Public API
# -----------------------------


def _run_preprocess_two_pass(img: np.ndarray) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Two-pass preprocessing for stability:

    Pass 1:
      shrink=BORDER_SHRINK_PX_PRIMARY, delta=DELTA_STRICT
    If result looks suspicious (empty-ish ink but has dark pixels -> likely digit cut/thinned),
      fallback to shrink=BORDER_SHRINK_PX_FALLBACK.
    Also if strict delta yields too little ink but dark pixels exist, try RELAX delta.
    """
    # Pass 1: strict
    mask1, dbg1 = preprocess_cell_to_binary(
        img,
        shrink=BORDER_SHRINK_PX_PRIMARY,
        delta=DELTA_STRICT,
    )

    ink1 = int(dbg1["ink_pixels"])
    p1 = float(dbg1["p1"])

    # If strict is "too empty" but p1 is dark -> there is real ink, so try relax delta
    if ink1 < EMPTY_MIN_INK_PX and p1 < float(EMPTY_P1_GRAY_MIN):
        mask_relax, dbg_relax = preprocess_cell_to_binary(
            img,
            shrink=BORDER_SHRINK_PX_PRIMARY,
            delta=DELTA_RELAX,
        )
        # choose relax if it yields more meaningful ink
        if int(dbg_relax["ink_pixels"]) > ink1:
            mask1, dbg1 = mask_relax, dbg_relax
            ink1 = int(dbg1["ink_pixels"])
            p1 = float(dbg1["p1"])

    # Fallback shrink to avoid cutting digits near edges:
    # If pass1 yields empty-ish ink but p1 suggests dark strokes, fallback to shrink=0.
    if ink1 < EMPTY_MIN_INK_PX and p1 < float(FALLBACK_P1_DARK):
        mask2, dbg2 = preprocess_cell_to_binary(
            img,
            shrink=BORDER_SHRINK_PX_FALLBACK,
            delta=DELTA_STRICT,
        )

        # Try relax in fallback if still too thin but dark strokes exist
        ink2 = int(dbg2["ink_pixels"])
        p2 = float(dbg2["p1"])
        if ink2 < EMPTY_MIN_INK_PX and p2 < float(EMPTY_P1_GRAY_MIN):
            mask2r, dbg2r = preprocess_cell_to_binary(
                img,
                shrink=BORDER_SHRINK_PX_FALLBACK,
                delta=DELTA_RELAX,
            )
            if int(dbg2r["ink_pixels"]) > ink2:
                mask2, dbg2 = mask2r, dbg2r

        # Choose fallback if it preserves more ink (typical when digit touches border)
        if int(dbg2["ink_pixels"]) > ink1:
            return mask2, dbg2

    return mask1, dbg1


def recognize_cell(
    bgr_or_rgb_img: np.ndarray,
    *,
    weights_path: Optional[str | Path] = None,
    debug: bool = False,
    debug_out_dir: Optional[str | Path] = None,
) -> str:
    """
    Recognize a single cell.

    Returns:
        "E" for empty
        "-" for minus
        "0".."9" for digits
    """
    mask, dbg = _run_preprocess_two_pass(bgr_or_rgb_img)

    if debug:
        dbg_out = Path(debug_out_dir) if debug_out_dir is not None else None
        if dbg_out is not None:
            _write_debug_png(dbg_out, "00_gray_orig.png", dbg["gray_orig"])
            _write_debug_png(dbg_out, "01_gray_blur.png", dbg["gray"])
            _write_debug_png(dbg_out, "02_mask_raw.png", dbg["mask_raw"])
            _write_debug_png(dbg_out, "03_mask_clean.png", dbg["mask_clean"])

            # Save a small text dump with key stats
            stats_txt = (
                f"shrink={dbg['shrink']}\n"
                f"delta={dbg['delta']}\n"
                f"bg={dbg['bg']:.2f}\n"
                f"T={dbg['T']}\n"
                f"ink_pixels={dbg['ink_pixels']}\n"
                f"p1={dbg['p1']:.2f}\n"
                f"bbox={dbg.get('bbox')}\n"
                f"aspect={dbg.get('aspect')}\n"
                f"fill={dbg.get('fill')}\n"
            )
            _ensure_dir(dbg_out)
            (dbg_out / "stats.txt").write_text(stats_txt, encoding="utf-8")

    if is_empty(mask, p1=float(dbg["p1"])):
        return "E"

    minus_ok, minus_metrics = is_minus(mask)
    if debug and debug_out_dir is not None:
        dbg_out = Path(debug_out_dir)
        _ensure_dir(dbg_out)
        (dbg_out / "minus_metrics.txt").write_text(
            f"minus={minus_ok}\n{minus_metrics}\n",
            encoding="utf-8",
        )

    if minus_ok:
        return "-"

    # For ResNet: build MNIST-like grayscale (not binary) from illumination-normalized gray.
    mnist_f01 = to_mnist_28x28_gray(dbg["gray_norm"], mask)
    if debug and debug_out_dir is not None:
        mnist_vis = (np.clip(mnist_f01, 0.0, 1.0) * 255.0).astype(np.uint8)
        _write_debug_png(Path(debug_out_dir), "04_mnist_28_gray.png", mnist_vis)

    d = predict_digit(mnist_f01, weights_path=weights_path)
    return str(d)


# -----------------------------
# CLI
# -----------------------------


def _cli() -> int:
    p = argparse.ArgumentParser(description="Recognize a single answer-sheet cell symbol.")
    p.add_argument("image", help="Path to a cell image (png/jpg).")
    p.add_argument(
        "--debug-out",
        default=None,
        help="Directory to dump debug PNGs (weights are loaded from the built-in location).",
    )
    args = p.parse_args()

    img = cv2.imread(str(args.image), cv2.IMREAD_COLOR)
    if img is None:
        raise SystemExit(f"Failed to read image: {args.image}")

    debug_out = args.debug_out
    pred = recognize_cell(
        img,
        weights_path=None,
        debug=debug_out is not None,
        debug_out_dir=debug_out,
    )
    print(pred)
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())