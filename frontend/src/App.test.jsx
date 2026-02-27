import { render, screen } from "@testing-library/react";
import { test, expect } from "vitest";
import App from "./App";

test("renders upload page with title and form", () => {
  render(<App />);
  expect(screen.getByText("Проверка бланков")).toBeInTheDocument();
  expect(screen.getByLabelText(/PDF-файл/i)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Загрузить и распознать/i })).toBeInTheDocument();
});
