import React, { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert } from "@/components/ui/alert";
import { AppNav } from "@/components/AppNav";
import {
  uploadPdfAndPredict,
  uploadPdfAndPredictMulti,
  type CorrectionPayload,
  type SavedRecordIdItem,
  ApiError,
  NetworkError,
  isCorrectionPayload,
  isMultiPageErrorDetails,
} from "@/api/blankCheck";
import { CorrectionForm } from "@/components/CorrectionForm";
import { FileUp, Loader2 } from "lucide-react";

export function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [page, setPage] = useState(0);
  const [processAllPages, setProcessAllPages] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastRecordId, setLastRecordId] = useState<number | null>(null);
  const [correction, setCorrection] = useState<CorrectionPayload | null>(null);
  const [correctionQueue, setCorrectionQueue] = useState<CorrectionPayload[]>([]);
  const [savedRecordIdsFromMulti, setSavedRecordIdsFromMulti] = useState<
    SavedRecordIdItem[]
  >([]);
  const [multiSuccessIds, setMultiSuccessIds] = useState<SavedRecordIdItem[] | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setError("Выберите PDF-файл");
      return;
    }
    setError(null);
    setCorrection(null);
    setCorrectionQueue([]);
    setSavedRecordIdsFromMulti([]);
    setMultiSuccessIds(null);
    setLastRecordId(null);
    setLoading(true);
    try {
      if (processAllPages) {
        const data = await uploadPdfAndPredictMulti(file);
        setMultiSuccessIds(data.saved_record_ids);
        setLastRecordId(null);
      } else {
        const data = await uploadPdfAndPredict(file, page);
        setLastRecordId(data.record_id);
      }
    } catch (err) {
      if (err instanceof ApiError) {
        if (
          err.status === 422 &&
          err.code === "REVIEW_REQUIRED" &&
          isMultiPageErrorDetails(err.details)
        ) {
          const details = err.details;
          setCorrectionQueue(details.pages_with_errors);
          setCorrection(details.pages_with_errors[0] ?? null);
          setSavedRecordIdsFromMulti(details.saved_record_ids);
          setError(null);
        } else if (
          err.status === 422 &&
          err.code === "REVIEW_REQUIRED" &&
          isCorrectionPayload(err.details)
        ) {
          setCorrection(err.details);
          setError(null);
        } else {
          const base = `Ошибка (${err.code})`;
          const maybePage =
            err.details && typeof (err.details as Record<string, unknown>).page === "number"
              ? ` (страница ${(err.details as Record<string, unknown>).page})`
              : "";
          setError(`${base}${maybePage}: ${err.message}`);
        }
      } else if (err instanceof NetworkError) {
        setError(err.message);
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError(String(err));
      }
    } finally {
      setLoading(false);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    setFile(f || null);
    setError(null);
    setLastRecordId(null);
    setCorrection(null);
    setCorrectionQueue([]);
    setSavedRecordIdsFromMulti([]);
    setMultiSuccessIds(null);
  };

  const totalCount =
    multiSuccessIds !== null && multiSuccessIds.length > 0
      ? multiSuccessIds.length
      : correctionQueue.length > 0
        ? savedRecordIdsFromMulti.length + correctionQueue.length
        : lastRecordId !== null
          ? 1
          : null;
  const remainingCount = correctionQueue.length > 0 ? correctionQueue.length : null;

  return (
    <div className="min-h-screen flex flex-col bg-muted/30 px-4 py-8">
      <AppNav />
      {correction ? (
        <>
          <div className="max-w-6xl mx-auto flex flex-col lg:flex-row lg:items-start gap-6 px-4 pt-8 pb-6">
            <div className="flex-1 min-w-0 flex flex-col min-h-[75vh] max-h-[88vh] overflow-hidden">
              <CorrectionForm
                payload={correction}
                onSuccess={(data) => {
                  setLastRecordId(data.record_id);
                  setCorrectionQueue((prev) => {
                    const next = prev.slice(1);
                    setCorrection(next[0] ?? null);
                    if (next.length === 0) {
                      setSavedRecordIdsFromMulti([]);
                    }
                    return next;
                  });
                }}
              />
            </div>
            {(totalCount !== null || remainingCount !== null) && (
              <aside className="w-full lg:w-52 shrink-0 rounded-lg border bg-card p-4 shadow-sm">
                <div className="space-y-3 text-sm">
                  {totalCount !== null && (
                    <div>
                      <span className="text-muted-foreground">Всего</span>
                      <p className="text-xl font-semibold tabular-nums">{totalCount}</p>
                    </div>
                  )}
                  {remainingCount !== null && (
                    <div>
                      <span className="text-muted-foreground">Осталось исправить</span>
                      <p className="text-xl font-semibold tabular-nums">{remainingCount}</p>
                    </div>
                  )}
                </div>
              </aside>
            )}
          </div>
        </>
      ) : (
        <div className="flex-1 flex justify-center items-center">
          <div className="max-w-5xl w-full flex flex-col lg:flex-row lg:items-center lg:justify-center lg:gap-6">
            <Card className="w-full max-w-xl">
              <CardHeader>
                <CardTitle>Загрузка PDF</CardTitle>
                <CardDescription>
                  Выберите файл и при необходимости укажите номер страницы (начиная с 0)
                </CardDescription>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleSubmit} className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="pdf-file">PDF-файл</Label>
                    <Input
                      id="pdf-file"
                      type="file"
                      accept=".pdf,application/pdf"
                      onChange={handleFileChange}
                      disabled={loading}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="page">Номер страницы</Label>
                    <Input
                      id="page"
                      type="number"
                      min={0}
                      value={page}
                      onChange={(e) => setPage(parseInt(e.target.value, 10) || 0)}
                      disabled={loading || processAllPages}
                    />
                  </div>
                  <div className="flex items-center gap-2">
                    <input
                      id="process-all-pages"
                      type="checkbox"
                      checked={processAllPages}
                      onChange={(e) => setProcessAllPages(e.target.checked)}
                      disabled={loading}
                      className="h-4 w-4 rounded border-input"
                    />
                    <Label htmlFor="process-all-pages" className="cursor-pointer">
                      Обработать все страницы PDF
                    </Label>
                  </div>
                  {error && <Alert variant="destructive">{error}</Alert>}
                  <Button type="submit" disabled={loading || !file}>
                    {loading ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Обработка…
                      </>
                    ) : (
                      <>
                        <FileUp className="h-4 w-4" />
                        Загрузить и распознать
                      </>
                    )}
                  </Button>
                </form>
              </CardContent>
            </Card>
            {(totalCount !== null || remainingCount !== null) && (
            <aside className="w-full lg:w-52 shrink-0 rounded-lg border bg-card p-4 shadow-sm">
              <div className="space-y-3 text-sm">
                {totalCount !== null && (
                  <div>
                    <span className="text-muted-foreground">Всего</span>
                    <p className="text-xl font-semibold tabular-nums">{totalCount}</p>
                  </div>
                )}
                {remainingCount !== null && (
                  <div>
                    <span className="text-muted-foreground">Осталось исправить</span>
                    <p className="text-xl font-semibold tabular-nums">{remainingCount}</p>
                  </div>
                )}
              </div>
            </aside>
          )}
          </div>
        </div>
      )}
    </div>
  );
}
