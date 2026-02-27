/**
 * Format date from 8 cell symbols to XX.XX.XX.
 * Indices 2 and 5 (0-based) are always dots; indices 0,1,3,4,6,7 are digits.
 */
export function formatDate(dateCells: string[]): string {
  const pad: string[] = Array(8).fill("");
  dateCells.forEach((c, i) => {
    if (i < 8) pad[i] = (c ?? "").trim();
  });
  const digit = (i: number) => {
    const s = pad[i] ?? "";
    return s === "" || s === "E" ? "" : s;
  };
  return (
    digit(0) +
    digit(1) +
    "." +
    digit(3) +
    digit(4) +
    "." +
    digit(6) +
    digit(7)
  );
}
