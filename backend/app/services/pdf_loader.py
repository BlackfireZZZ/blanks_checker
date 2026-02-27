"""Загрузка страниц PDF в изображения BGR."""

import cv2
import numpy as np
import fitz  # PyMuPDF


def pdf_bytes_to_bgr(
    pdf_bytes: bytes, page_index: int = 0, zoom: float = 2.0
) -> np.ndarray:
    """Рендер одной страницы PDF из bytes в BGR (numpy, uint8)."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc.load_page(page_index)
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
        pix.height, pix.width, 3
    )
    doc.close()
    return cv2.cvtColor(img, cv2.COLOR_RGB2BGR)


def pdf_page_to_bgr(
    pdf_path: str, page_index: int = 0, zoom: float = 2.0
) -> np.ndarray:
    """Рендер одной страницы PDF в BGR (numpy, uint8)."""
    doc = fitz.open(pdf_path)
    page = doc.load_page(page_index)
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
        pix.height, pix.width, 3
    )
    doc.close()
    return cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
