import { useState } from "react";
import { Link } from "react-router-dom";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { clearToken } from "@/api/auth";
import { downloadBlanksTable, ApiError, NetworkError } from "@/api/blankCheck";
import { Button } from "@/components/ui/button";
import { FileUp, List, Users, LogOut, Download, Loader2 } from "lucide-react";

export function AppNav() {
  const { user, loading } = useCurrentUser();
  const [downloadingTable, setDownloadingTable] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  const handleLogout = () => {
    clearToken();
    window.location.href = "/auth";
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
    <nav className="sticky top-0 z-10 flex items-center gap-2 border-b bg-background/95 px-4 py-2.5 shadow-sm backdrop-blur supports-[backdrop-filter]:bg-background/80">
      <div className="flex items-center gap-1">
        <Button variant="ghost" size="sm" asChild>
          <Link to="/" className="gap-1.5">
            <FileUp className="h-4 w-4" />
            Загрузка
          </Link>
        </Button>
        <Button variant="ghost" size="sm" asChild>
          <Link to="/list" className="gap-1.5">
            <List className="h-4 w-4" />
            Список бланков
          </Link>
        </Button>
        {!loading && user?.is_admin && (
          <Button variant="ghost" size="sm" asChild>
            <Link to="/users" className="gap-1.5">
              <Users className="h-4 w-4" />
              Пользователи
            </Link>
          </Button>
        )}
      </div>
      <div className="flex items-center gap-2 border-l pl-3 ml-1">
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={handleDownloadTable}
          disabled={downloadingTable}
          className="gap-1.5"
        >
          {downloadingTable ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Download className="h-4 w-4" />
          )}
          Скачать таблицу
        </Button>
        {downloadError && (
          <span className="text-xs text-destructive max-w-[180px] truncate" title={downloadError}>
            {downloadError}
          </span>
        )}
      </div>
      <span className="ml-auto flex items-center gap-2">
        {!loading && user && (
          <span className="text-sm text-muted-foreground">{user.login}</span>
        )}
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={handleLogout}
          className="gap-1.5 text-muted-foreground hover:text-foreground"
        >
          <LogOut className="h-4 w-4" />
          Выход
        </Button>
      </span>
    </nav>
  );
}
