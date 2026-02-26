"""
cell_ocr — распознавание одного знака в клетке (PNG/JPG).
- эвристиками OpenCV аккуратно определяем: пусто ли, и является ли знак минусом
- если не пусто и не минус -> классифицируем цифру 0-9 моделью, обученной на MNIST (CPU)

Ограничения задачи (как ты описал):
- в клетке может быть пусто
- иначе там ТОЛЬКО 0-9 или '-' (других вариантов не рассматриваем)

Зависимости:
    pip install opencv-python numpy torch torchvision

Использование (импорт как модуль):
    from cell_ocr import CellRecognizer, MnistDigitClassifier
    clf = MnistDigitClassifier(weights_path="mnist_lenet.pt")
    rec = CellRecognizer(clf)
    label = rec.recognize_bgr(cv2.imread("cell.png"))  # -> None | "-" | "0".."9"
"""

from .config import HeuristicsConfig
from .model import MnistDigitClassifier
from .preprocess import CellRecognizer, save_mnist_input

__all__ = [
    "CellRecognizer",
    "HeuristicsConfig",
    "MnistDigitClassifier",
    "save_mnist_input",
]
