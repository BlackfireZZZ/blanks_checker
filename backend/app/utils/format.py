"""Shared formatting utilities."""

# Date uses 8 cells; positions 2 and 5 (0-based) are always dot separators.
DATE_DOT_INDICES = (2, 5)
DATE_DIGIT_INDICES = (0, 1, 3, 4, 6, 7)


def format_date_xx_xx_xx(cells: list[str]) -> str:
    """
    Format date from 8 cell symbols to XX.XX.XX.
    Indices 2 and 5 are always dots; indices 0,1,3,4,6,7 are digits.
    Empty/E/whitespace shown as empty.
    """
    if len(cells) < 8:
        return "".join(c or "" for c in cells)

    def digit(c: str | None) -> str:
        if not c or c.strip() in ("", "E"):
            return ""
        return c.strip()

    return (
        digit(cells[0]) + digit(cells[1]) + "."
        + digit(cells[3]) + digit(cells[4]) + "."
        + digit(cells[6]) + digit(cells[7])
    )
