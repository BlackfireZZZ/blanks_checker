import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert } from "@/components/ui/alert";
import { AppNav } from "@/components/AppNav";
import { fetchBlanksList, type BlankListItem, ApiError, NetworkError } from "@/api/blankCheck";
import { formatDate } from "@/utils/format";
import { List, Loader2, Search } from "lucide-react";

function formatCreatedAt(iso: string): string {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function joinSymbols(cells: string[]): string {
  return cells
    .map((c) => (c && c.trim() && c !== "E" ? c.trim() : ""))
    .join("");
}

export function ListPage() {
  const [search, setSearch] = useState("");
  const [list, setList] = useState<BlankListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  const load = useCallback(async (searchTerm?: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchBlanksList(searchTerm);
      setList(data);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(`${err.code}: ${err.message}`);
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
  }, []);

  useEffect(() => {
    load(search);
  }, [load, search]);

  const handleRowClick = (id: number) => {
    navigate(`/edit/${id}`);
  };

  return (
    <div className="min-h-screen bg-muted/30 py-8 px-4">
      <AppNav />
      <div className="max-w-5xl mx-auto space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <h1 className="text-2xl font-bold tracking-tight">Список бланков</h1>
          <div className="relative flex-1 sm:max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              type="search"
              placeholder="Поиск по имени файла или URL…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9"
            />
          </div>
        </div>

        {error && (
          <Alert variant="destructive">{error}</Alert>
        )}

        <Card>
          <CardHeader>
            <CardTitle>Загруженные файлы</CardTitle>
            <CardDescription>
              Нажмите на строку, чтобы открыть редактирование бланка
            </CardDescription>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : list.length === 0 ? (
              <div className="py-12 text-center text-muted-foreground">
                <List className="h-12 w-12 mx-auto mb-2 opacity-50" />
                <p>Нет загруженных бланков</p>
              </div>
            ) : (
              <div className="overflow-x-auto -mx-2">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left">
                      <th className="p-2 font-medium">ID</th>
                      <th className="p-2 font-medium">Файл</th>
                      <th className="p-2 font-medium">Дата загрузки</th>
                      <th className="p-2 font-medium">Вариант</th>
                      <th className="p-2 font-medium">Дата бланка</th>
                      <th className="p-2 font-medium">Рег. номер</th>
                    </tr>
                  </thead>
                  <tbody>
                    {list.map((item) => (
                      <tr
                        key={item.id}
                        onClick={() => handleRowClick(item.id)}
                        className="border-b hover:bg-muted/50 cursor-pointer transition-colors"
                      >
                        <td className="p-2 font-mono">{item.id}</td>
                        <td className="p-2 max-w-[200px] truncate" title={item.source_filename ?? ""}>
                          {item.source_filename || "—"}
                        </td>
                        <td className="p-2 text-muted-foreground">
                          {formatCreatedAt(item.created_at)}
                        </td>
                        <td className="p-2 font-mono">{joinSymbols(item.variant) || "—"}</td>
                        <td className="p-2 font-mono">{formatDate(item.date) || "—"}</td>
                        <td className="p-2 font-mono">{joinSymbols(item.reg_number) || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
