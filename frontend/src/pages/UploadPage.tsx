import React, { useState } from "react";
import { Link } from "react-router-dom";
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
  downloadBlanksTable,
  type BlankCheckResult,
  type CorrectionPayload,
  ApiError,
  NetworkError,
  isCorrectionPayload,
} from "@/api/blankCheck";
import { CorrectionForm } from "@/components/CorrectionForm";
import { formatDate } from "@/utils/format";
import { FileUp, Loader2, Download, List } from "lucide-react";

export function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<BlankCheckResult | null>(null);
  const [lastRecordId, setLastRecordId] = useState<number | null>(null);
  const [correction, setCorrection] = useState<CorrectionPayload | null>(null);
  const [downloadingTable, setDownloadingTable] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setError("Выберите PDF-файл");
      return;
    }
    setError(null);
    setResult(null);
    setCorrection(null);
    setLastRecordId(null);
    setLoading(true);
    try {
      const data = await uploadPdfAndPredict(file, page);
      setResult(data);
      setLastRecordId(data.record_id);
    } catch (err) {
      if (err instanceof ApiError) {
        if (
          err.status === 422 &&
          err.code === "REVIEW_REQUIRED" &&
          isCorrectionPayload(err.details)
        ) {
          setCorrection(err.details);
          setError(null);
        } else {
          const base = `Ошибка (${err.code})`;
          const maybePage =
            err.details && typeof (err.details as any).page === "number"
              ? ` (страница ${(err.details as any).page})`
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
    setResult(null);
    setLastRecordId(null);
    setCorrection(null);
  };

  const handleDownloadTable = async () => {
    setDownloadError(null);
    setDownloadingTable(true);
    try {
      await downloadBlanksTable();
    } catch (err) {
      if (err instanceof ApiError) {
        setDownloadError(`${err.code}: ${err.message}`);
      } else if (err instanceof NetworkError) {
        setDownloadError(err.message);
      } else if (err instanceof Error) {
        setDownloadError(err.message);
      } else {
        setDownloadError(String(err));
      }
    } finally {
      setDownloadingTable(false);
    }
  };

  return (
    <div className="min-h-screen bg-muted/30 py-8 px-4">
      <AppNav />
      <div className="max-w-5xl mx-auto space-y-8">
        <div className="text-center flex flex-col items-center gap-3">
          <h1 className="text-2xl font-bold tracking-tight">Проверка бланков</h1>
          <p className="text-muted-foreground mt-1">
            Загрузите PDF-страницу бланка для распознавания
          </p>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={handleDownloadTable}
            disabled={downloadingTable}
          >
            {downloadingTable ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Download className="h-4 w-4" />
            )}
            <span className="ml-2">Скачать таблицу</span>
          </Button>
          <Button variant="outline" size="sm" asChild>
            <Link to="/list">
              <List className="h-4 w-4 mr-2" />
              К списку бланков
            </Link>
          </Button>
          {downloadError && (
            <Alert variant="destructive" className="max-w-md">
              {downloadError}
            </Alert>
          )}
        </div>

        <Card>
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
                  disabled={loading}
                />
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

        {lastRecordId !== null && (
          <Alert>
            ID сохранённой записи в БД: <strong>{lastRecordId}</strong>
          </Alert>
        )}

        {correction && (
          <CorrectionForm
            payload={correction}
            onSuccess={(data) => {
              setResult(data);
              setLastRecordId(data.record_id);
              setCorrection(null);
            }}
          />
        )}

        {result && (
          <Card>
            <CardHeader>
              <CardTitle>Результат распознавания</CardTitle>
              <CardDescription>
                Вариант, дата, регистрационный номер, ответы и замена
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {result.aligned_image_url && (
                <Alert>
                  <a
                    href={result.aligned_image_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="underline"
                  >
                    Скачать выровненное изображение страницы (PNG)
                  </a>
                </Alert>
              )}
              <ResultBlock title="Вариант" items={[result.variant.join("")]} />
              <ResultBlock title="Дата" items={[formatDate(result.date)]} />
              <ResultBlock title="Рег. номер" items={[result.reg_number.join("")]} />
              <ResultBlock
                title="Ответы"
                items={result.answers.map((row, i) => `Строка ${i + 1}: ${row.join("")}`)}
              />
              <ResultBlock
                title="Замена"
                items={result.repl.map((row, i) => `Строка ${i + 1}: ${row.join("")}`)}
              />
              {result.warnings.length > 0 && (
                <Alert>
                  <ul className="list-disc list-inside text-sm">
                    {result.warnings.map((w, i) => (
                      <li key={i}>{w}</li>
                    ))}
                  </ul>
                </Alert>
              )}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}

function ResultBlock({
  title,
  items,
}: {
  title: string;
  items: string[];
}) {
  return (
    <div>
      <h3 className="text-sm font-medium text-muted-foreground mb-1">{title}</h3>
      <pre className="bg-muted rounded-md p-3 text-sm font-mono overflow-x-auto">
        {items.join("\n")}
      </pre>
    </div>
  );
}
