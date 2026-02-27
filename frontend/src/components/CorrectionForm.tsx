import React, { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Alert } from "@/components/ui/alert";
import {
  submitCorrections,
  type BlankCheckResult,
  type CorrectionPayload,
  type FieldReview,
  type RecognizedCell,
  type ValidationIssue,
  ApiError,
  NetworkError,
  isCorrectionPayload,
} from "@/api/blankCheck";
import { formatDate } from "@/utils/format";

export interface CorrectionFormProps {
  payload: CorrectionPayload;
  recordId?: number | null;
  onSuccess?: (result: BlankCheckResult) => void;
}

export function CorrectionForm({ payload, recordId, onSuccess }: CorrectionFormProps) {
  const [fieldStates, setFieldStates] = useState<Record<string, FieldReview>>({});
  const [activeFieldId, setActiveFieldId] = useState<string | null>(null);
  const [activeCellIndex, setActiveCellIndex] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const byId: Record<string, FieldReview> = {};
    for (const field of payload.fields) {
      byId[field.field_id] = field;
    }
    setFieldStates(byId);
    setActiveFieldId(null);
    setActiveCellIndex(null);
  }, [payload]);

  const hasInvalidFields = Object.values(fieldStates).some((f) => !f.is_valid);

  const updateField = useCallback(
    (fieldId: string, updater: (field: FieldReview) => FieldReview) => {
      setFieldStates((prev) => {
        const current = prev[fieldId];
        if (!current) return prev;
        const updated = updater(current);
        return { ...prev, [fieldId]: updated };
      });
    },
    [],
  );

  const recalcFieldValidation = useCallback((field: FieldReview): FieldReview => {
    const DATE_DIGIT_INDICES = [0, 1, 3, 4, 6, 7] as const;
    const isDate = field.field_id === "date";
    const digitSet = isDate ? new Set(DATE_DIGIT_INDICES) : null;
    const cellsForDigits =
      digitSet != null
        ? field.cells.filter((c) => digitSet.has(c.index as 0 | 1 | 3 | 4 | 6 | 7))
        : field.cells;
    const nonEmptyIndices = cellsForDigits
      .filter((c) => c.symbol !== null && c.symbol !== "")
      .map((c) => c.index);
    const issues: ValidationIssue[] = [];
    const requiredFields = ["variant", "date", "reg_number"];

    if (nonEmptyIndices.length === 0) {
      if (requiredFields.includes(field.field_id)) {
        issues.push({
          field_id: field.field_id,
          cell_indices: [],
          code: "REQUIRED_FIELD_EMPTY",
          message: "Поле обязательно для заполнения.",
        });
        return { ...field, issues, proposed_joined: "", parsed_integer: null, is_valid: false };
      }
      return { ...field, issues: [], proposed_joined: "", parsed_integer: null, is_valid: true };
    }

    const first = Math.min(...nonEmptyIndices);
    const last = Math.max(...nonEmptyIndices);
    const indicesForLeading =
      digitSet != null
        ? [...digitSet].filter((idx) => idx < first)
        : field.cells.map((c) => c.index).filter((idx) => idx < first);
    if (indicesForLeading.length > 0) {
      issues.push({
        field_id: field.field_id,
        cell_indices: indicesForLeading,
        code: "LEADING_EMPTY_CELL",
        message: "Число не может начинаться с пустых клеток.",
      });
    }

    const internalEmpty: number[] = [];
    for (let idx = first; idx <= last; idx += 1) {
      if (digitSet != null && !digitSet.has(idx as 0 | 1 | 3 | 4 | 6 | 7)) continue;
      const cell = field.cells.find((c) => c.index === idx);
      if (!cell) continue;
      if (cell.symbol === null || cell.symbol === "") internalEmpty.push(idx);
    }
    if (internalEmpty.length > 0) {
      issues.push({
        field_id: field.field_id,
        cell_indices: internalEmpty,
        code: "INTERNAL_EMPTY_CELL",
        message: "Внутри числа есть пустые клетки.",
      });
    }

    const minusIndices = cellsForDigits.filter((c) => c.symbol === "-").map((c) => c.index);
    if (minusIndices.length > 1) {
      issues.push({
        field_id: field.field_id,
        cell_indices: minusIndices,
        code: "MULTIPLE_MINUS",
        message: "Допускается не более одного знака минус.",
      });
    }
    if (minusIndices.length > 0 && minusIndices[0] !== first) {
      issues.push({
        field_id: field.field_id,
        cell_indices: [minusIndices[0]],
        code: "MINUS_NOT_LEADING",
        message: "Знак минус может быть только в первой непустой клетке.",
      });
    }

    const joinedParts: string[] = [];
    for (const c of cellsForDigits) {
      const sym = c.symbol ?? "";
      if (!sym || sym === "S") continue;
      joinedParts.push(sym);
    }
    const proposed_joined = joinedParts.join("");

    if (!proposed_joined) {
      issues.push({
        field_id: field.field_id,
        cell_indices: nonEmptyIndices,
        code: "EMPTY_AFTER_TRIM",
        message: "После удаления пустых клеток не осталось цифр.",
      });
      return { ...field, issues, proposed_joined, parsed_integer: null, is_valid: false };
    }

    if (!/^-?[0-9]+$/.test(proposed_joined)) {
      issues.push({
        field_id: field.field_id,
        cell_indices: nonEmptyIndices,
        code: "NOT_AN_INTEGER",
        message: "Значение не является корректным целым числом.",
      });
      return { ...field, issues, proposed_joined, parsed_integer: null, is_valid: false };
    }

    let parsed: number | null = null;
    try {
      parsed = Number.parseInt(proposed_joined, 10);
      if (Number.isNaN(parsed)) parsed = null;
    } catch {
      parsed = null;
    }

    return {
      ...field,
      issues,
      proposed_joined,
      parsed_integer: parsed,
      is_valid: issues.length === 0 && parsed !== null,
    };
  }, []);

  const handleCellClick = (fieldId: string, index: number) => {
    setActiveFieldId(fieldId);
    setActiveCellIndex(index);
  };

  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (!activeFieldId || activeCellIndex == null) return;
    const key = event.key;
    if (
      ![
        "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
        "-", "Backspace", "Delete", "ArrowLeft", "ArrowRight",
      ].includes(key)
    ) {
      return;
    }
    event.preventDefault();

    if (key === "ArrowLeft" || key === "ArrowRight") {
      setActiveCellIndex((prev) => {
        if (prev == null) return prev;
        const field = fieldStates[activeFieldId];
        if (!field) return prev;
        const maxIndex = field.cells.length - 1;
        return key === "ArrowLeft" ? Math.max(0, prev - 1) : Math.min(maxIndex, prev + 1);
      });
      return;
    }

    updateField(activeFieldId, (field) => {
      const cells: RecognizedCell[] = field.cells.map((c) => ({ ...c }));
      const target = cells.find((c) => c.index === activeCellIndex);
      if (!target) return field;
      if (key === "Backspace" || key === "Delete") target.symbol = "";
      else if (key === "-") target.symbol = "-";
      else if (key >= "0" && key <= "9") target.symbol = key;
      return recalcFieldValidation({ ...field, cells });
    });
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const submission = {
        page: payload.page,
        fields: Object.values(fieldStates).map((field) => ({
          field_id: field.field_id,
          joined_value: field.proposed_joined,
          cells: field.cells,
        })),
        aligned_image_url: payload.aligned_image_url ?? undefined,
        record_id: recordId ?? undefined,
      };
      const data = await submitCorrections(submission);
      onSuccess?.(data);
    } catch (err) {
      if (err instanceof ApiError) {
        if (
          err.status === 422 &&
          err.code === "REVIEW_REQUIRED" &&
          isCorrectionPayload(err.details)
        ) {
          const details = err.details;
          setFieldStates(() => {
            const byId: Record<string, FieldReview> = {};
            for (const field of details.fields) {
              byId[field.field_id] = field;
            }
            return byId;
          });
        } else {
          setError(err.message);
        }
      } else if (err instanceof NetworkError) {
        setError(err.message);
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError(String(err));
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card className="overflow-hidden w-full h-full flex flex-col min-h-0" onKeyDown={handleKeyDown} tabIndex={0}>
      <CardContent className="p-0 w-full flex-1 min-h-0 flex flex-col overflow-hidden">
        <div className="flex flex-col md:flex-row flex-1 min-h-0 overflow-hidden w-full">
          {/* Слева — оригинал страницы (всегда виден, без прокрутки) */}
          <aside className="w-full md:w-[380px] md:min-w-[340px] md:max-w-[45%] md:flex-shrink-0 flex flex-col p-4 md:p-5 bg-muted/25 border-b md:border-b-0 md:border-r overflow-hidden min-h-0">
            <p className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-3 shrink-0">Оригинал страницы</p>
            {payload.aligned_image_url ? (
              <div className="rounded-xl border border-border/80 bg-card/50 shadow-sm overflow-hidden flex-1 min-h-0 flex items-center justify-center">
                <img
                  src={payload.aligned_image_url}
                  alt="Страница бланка для сверки"
                  className="max-w-full max-h-full w-auto h-auto object-contain block"
                />
              </div>
            ) : (
              <Alert className="max-w-full shrink-0">Изображение страницы недоступно.</Alert>
            )}
          </aside>
          {/* Справа — поля ввода, прокрутка только здесь */}
          <main className="flex-1 min-w-0 min-h-0 flex flex-col overflow-hidden">
            <div className="p-4 md:p-5 border-b bg-muted/20 shrink-0">
              <p className="text-sm font-semibold text-muted-foreground">Поля для ввода — сверьте с оригиналом и исправьте при необходимости</p>
            </div>
            <div className="flex-1 min-h-0 overflow-y-auto overflow-x-hidden p-4 md:p-5 space-y-6 overscroll-contain">
              <CorrectionFields
                fieldStates={fieldStates}
                activeFieldId={activeFieldId}
                activeCellIndex={activeCellIndex}
                onCellClick={handleCellClick}
              />
            </div>
            <div className="p-4 md:p-5 border-t bg-muted/20 flex flex-wrap items-center justify-between gap-2 shrink-0">
              {error && <Alert variant="destructive" className="flex-1 min-w-0">{error}</Alert>}
              <Button
                type="button"
                onClick={handleSave}
                disabled={saving || hasInvalidFields}
              >
                {saving ? "Сохранение…" : "Сохранить исправления"}
              </Button>
            </div>
          </main>
        </div>
      </CardContent>
    </Card>
  );
}

function CorrectionFields({
  fieldStates,
  activeFieldId,
  activeCellIndex,
  onCellClick,
}: {
  fieldStates: Record<string, FieldReview>;
  activeFieldId: string | null;
  activeCellIndex: number | null;
  onCellClick: (fieldId: string, index: number) => void;
}) {
  const variant = fieldStates["variant"];
  const date = fieldStates["date"];
  const reg_number = fieldStates["reg_number"];
  const answerFields = Object.keys(fieldStates)
    .filter((id) => id.startsWith("answer_r"))
    .sort()
    .map((id) => fieldStates[id]);
  const replFields = Object.keys(fieldStates)
    .filter((id) => id.startsWith("repl_r"))
    .sort()
    .map((id) => fieldStates[id]);

  return (
    <>
      {(variant || date || reg_number) && (
        <section>
          <h3 className="text-sm font-semibold text-muted-foreground mb-2">Шапка бланка</h3>
          <div className="space-y-3">
            {variant && <FieldEditor field={variant} activeFieldId="variant" activeFieldIdCurrent={activeFieldId} activeCellIndex={activeCellIndex} onCellClick={onCellClick} />}
            {date && <FieldEditor field={date} activeFieldId="date" activeFieldIdCurrent={activeFieldId} activeCellIndex={activeCellIndex} onCellClick={onCellClick} />}
            {reg_number && <FieldEditor field={reg_number} activeFieldId="reg_number" activeFieldIdCurrent={activeFieldId} activeCellIndex={activeCellIndex} onCellClick={onCellClick} />}
          </div>
        </section>
      )}
      {answerFields.length > 0 && (
        <section>
          <h3 className="text-sm font-semibold text-muted-foreground mb-2">Ответы (по строкам)</h3>
          <div className="space-y-3">
            {answerFields.map((field) => (
              <FieldEditor
                key={field.field_id}
                field={field}
                activeFieldId={field.field_id}
                activeFieldIdCurrent={activeFieldId}
                activeCellIndex={activeCellIndex}
                onCellClick={onCellClick}
              />
            ))}
          </div>
        </section>
      )}
      {replFields.length > 0 && (
        <section>
          <h3 className="text-sm font-semibold text-muted-foreground mb-2">Замена (по строкам)</h3>
          <div className="space-y-3">
            {replFields.map((field) => (
              <FieldEditor
                key={field.field_id}
                field={field}
                activeFieldId={field.field_id}
                activeFieldIdCurrent={activeFieldId}
                activeCellIndex={activeCellIndex}
                onCellClick={onCellClick}
              />
            ))}
          </div>
        </section>
      )}
    </>
  );
}

function FieldEditor({
  field,
  activeFieldId,
  activeFieldIdCurrent,
  activeCellIndex,
  onCellClick,
}: {
  field: FieldReview;
  activeFieldId: string;
  activeFieldIdCurrent: string | null;
  activeCellIndex: number | null;
  onCellClick: (fieldId: string, index: number) => void;
}) {
  const problematicIndices = new Set<number>();
  for (const issue of field.issues) {
    for (const idx of issue.cell_indices) problematicIndices.add(idx);
  }
  const isDate = field.field_id === "date";
  const dateDisplay =
    isDate && field.cells.length > 0
      ? formatDate(
          Array.from({ length: 8 }, (_, i) => {
            const c = field.cells.find((cell) => cell.index === i);
            return c?.symbol ?? "";
          }),
        )
      : null;
  const isActive = activeFieldIdCurrent === activeFieldId;

  return (
    <div className="border rounded-lg p-3 bg-card space-y-2">
      <div className="flex items-baseline justify-between gap-2 flex-wrap">
        <span className="font-medium text-sm">{field.label}</span>
        <span className="text-xs text-muted-foreground font-mono">
          {isDate && dateDisplay !== null
            ? dateDisplay ? `Число: ${dateDisplay}` : "— пусто —"
            : field.proposed_joined ? `Число: ${field.proposed_joined}` : "— пусто —"}
        </span>
      </div>
      <div className="flex flex-wrap gap-1">
        {field.cells.map((cell) => {
          const isProblem = problematicIndices.has(cell.index);
          const cellActive = isActive && activeCellIndex === cell.index;
          const display =
            isDate && (cell.index === 2 || cell.index === 5)
              ? "."
              : cell.symbol && cell.symbol !== ""
                ? cell.symbol
                : "\u00A0";
          return (
            <button
              key={cell.index}
              type="button"
              onClick={() => onCellClick(field.field_id, cell.index)}
              title="Клетка. Клик и ввод: 0–9, минус, Backspace"
              className={[
                "min-w-[2.25rem] h-11 border rounded-md flex items-center justify-center text-xl font-mono tabular-nums",
                "focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1",
                isProblem ? "border-red-500 bg-red-50 dark:bg-red-950/30 text-red-700 dark:text-red-400" : "bg-background border-input",
                cellActive ? "ring-2 ring-primary ring-offset-1" : "",
              ]
                .filter(Boolean)
                .join(" ")}
            >
              {display}
            </button>
          );
        })}
      </div>
      {field.issues.length > 0 && (
        <ul className="text-xs text-red-600 dark:text-red-400 list-disc list-inside">
          {field.issues.map((issue, idx) => (
            <li key={idx}>{issue.message}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
