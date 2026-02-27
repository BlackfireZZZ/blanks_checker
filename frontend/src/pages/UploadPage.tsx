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
import {
  uploadPdfAndPredict,
  type BlankCheckResult,
  ApiError,
  NetworkError,
} from "@/api/blankCheck";
import { FileUp, Loader2 } from "lucide-react";

export function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<BlankCheckResult | null>(null);
  const [lastRecordId, setLastRecordId] = useState<number | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setError("Выберите PDF-файл");
      return;
    }
    setError(null);
    setResult(null);
    setLastRecordId(null);
    setLoading(true);
    try {
      const data = await uploadPdfAndPredict(file, page);
      setResult(data);
      setLastRecordId(data.record_id);
    } catch (err) {
      if (err instanceof ApiError) {
        const base = `Ошибка (${err.code})`;
        const detailsPage =
          typeof err.details?.page === "number"
            ? ` (страница ${err.details.page})`
            : "";
        setError(`${base}${detailsPage}: ${err.message}`);
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
  };

  return (
    <div className="min-h-screen bg-muted/30 py-8 px-4">
      <div className="max-w-2xl mx-auto space-y-8">
        <div className="text-center">
          <h1 className="text-2xl font-bold tracking-tight">Проверка бланков</h1>
          <p className="text-muted-foreground mt-1">
            Загрузите PDF-страницу бланка для распознавания
          </p>
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

        {result && (
          <Card>
            <CardHeader>
              <CardTitle>Результат распознавания</CardTitle>
              <CardDescription>
                Вариант, дата, регистрационный номер, ответы и замена
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <ResultBlock title="Вариант" items={[result.variant.join("")]} />
              <ResultBlock title="Дата" items={[result.date.join("")]} />
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
