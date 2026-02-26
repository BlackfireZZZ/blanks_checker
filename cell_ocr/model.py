# MNIST classifier (LeNet-ish)
from __future__ import annotations

from pathlib import Path
from typing import Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F


class _LeNetMNIST(nn.Module):
    """Моя (более мощная) версия: 32/64 канала, padding=2, fc=256."""
    def __init__(self) -> None:
        super().__init__()
        self.conv1 = nn.Conv2d(1, 32, 5, padding=2)
        self.conv2 = nn.Conv2d(32, 64, 5, padding=2)
        self.fc1 = nn.Linear(64 * 7 * 7, 256)
        self.fc2 = nn.Linear(256, 10)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = F.relu(self.conv1(x))
        x = F.max_pool2d(x, 2)  # 28->14
        x = F.relu(self.conv2(x))
        x = F.max_pool2d(x, 2)  # 14->7
        x = x.view(x.size(0), -1)
        x = F.relu(self.fc1(x))
        return self.fc2(x)


class _LeNetTiny(nn.Module):
    """Архитектура, совместимая с весами из твоей ошибки: 2/6 канала, без padding, fc=32."""
    def __init__(self) -> None:
        super().__init__()
        self.conv1 = nn.Conv2d(1, 2, 5, padding=0)
        self.conv2 = nn.Conv2d(2, 6, 5, padding=0)
        self.fc1 = nn.Linear(96, 32)  # 6*4*4
        self.fc2 = nn.Linear(32, 10)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = F.relu(self.conv1(x))     # 28->24
        x = F.max_pool2d(x, 2)        # 24->12
        x = F.relu(self.conv2(x))     # 12->8
        x = F.max_pool2d(x, 2)        # 8->4
        x = x.view(x.size(0), -1)     # 6*4*4=96
        x = F.relu(self.fc1(x))
        return self.fc2(x)


def _build_model_for_state_dict(state: dict) -> nn.Module:
    """
    Автоматически выбираем архитектуру по shape conv1.weight.
    """
    w = state.get("conv1.weight", None)
    if w is None:
        raise RuntimeError("В state_dict нет ключа conv1.weight — непонятный формат весов.")

    out_ch = int(w.shape[0])
    if out_ch == 2:
        return _LeNetTiny()
    if out_ch == 32:
        return _LeNetMNIST()

    raise RuntimeError(f"Неизвестная архитектура по conv1.out_channels={out_ch}.")


class MnistDigitClassifier:
    def __init__(self, weights_path: str | Path, device: str = "cpu") -> None:
        self.device = torch.device(device)
        weights_path = Path(weights_path)
        if not weights_path.exists():
            raise FileNotFoundError(f"Не найден файл весов: {weights_path}")

        state = torch.load(weights_path, map_location=self.device)

        # иногда сохраняют {'state_dict': ...}
        if isinstance(state, dict) and "state_dict" in state and isinstance(state["state_dict"], dict):
            state = state["state_dict"]

        self.model = _build_model_for_state_dict(state).to(self.device)
        self.model.load_state_dict(state, strict=True)
        self.model.eval()

    @torch.inference_mode()
    def predict_digit(self, mnist_28x28_float01: np.ndarray) -> Tuple[int, float]:
        x = torch.from_numpy(mnist_28x28_float01.astype(np.float32)).unsqueeze(0).unsqueeze(0).to(self.device)
        logits = self.model(x)
        probs = torch.softmax(logits, dim=1)[0]
        digit = int(torch.argmax(probs).item())
        conf = float(probs[digit].item())
        return digit, conf
