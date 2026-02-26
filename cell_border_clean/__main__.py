# CLI: python -m cell_border_clean <image_path>
import sys

import cv2

from . import clean_cell_borders_v2


def main() -> None:
    p = sys.argv[1]
    img = cv2.imread(p, cv2.IMREAD_COLOR)
    out_gray, out_ink = clean_cell_borders_v2(img)
    cv2.imwrite("clean_gray.png", out_gray)
    cv2.imwrite("clean_ink.png", out_ink)


if __name__ == "__main__":
    main()
