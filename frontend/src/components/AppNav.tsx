import { Link } from "react-router-dom";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { clearToken } from "@/api/auth";

export function AppNav() {
  const { user, loading } = useCurrentUser();

  const handleLogout = () => {
    clearToken();
    window.location.href = "/auth";
  };

  return (
    <nav className="flex items-center gap-4 text-sm border-b bg-background px-4 py-2">
      <Link to="/" className="text-primary hover:underline">
        Загрузка
      </Link>
      <Link to="/list" className="text-primary hover:underline">
        Список бланков
      </Link>
      {!loading && user?.is_admin && (
        <Link to="/users" className="text-primary hover:underline">
          Пользователи
        </Link>
      )}
      <span className="ml-auto flex items-center gap-2">
        {!loading && user && (
          <span className="text-muted-foreground">{user.login}</span>
        )}
        <button
          type="button"
          onClick={handleLogout}
          className="text-primary hover:underline"
        >
          Выход
        </button>
      </span>
    </nav>
  );
}
