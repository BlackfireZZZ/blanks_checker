import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/alert";
import { AppNav } from "@/components/AppNav";
import {
  fetchUsersList,
  createUserApi,
  deleteUserApi,
  type UserListItem,
} from "@/api/auth";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { Trash2 } from "lucide-react";

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

export function UsersPage() {
  const { user: currentUser } = useCurrentUser();
  const [list, setList] = useState<UserListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [forbidden, setForbidden] = useState(false);
  const [loginName, setLoginName] = useState("");
  const [password, setPassword] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  /** Пароли только что созданных пользователей (видны главному админу) */
  const [createdPasswords, setCreatedPasswords] = useState<Record<number, string>>({});
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    setForbidden(false);
    try {
      const data = await fetchUsersList();
      setList(data);
    } catch (err) {
      if (err instanceof Error) {
        if (err.message === "Доступ запрещён") setForbidden(true);
        else setError(err.message);
      } else {
        setError(String(err));
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!loginName.trim() || !password) {
      setCreateError("Введите логин и пароль");
      return;
    }
    setCreateError(null);
    setCreating(true);
    try {
      const created = await createUserApi(loginName.trim(), password);
      setCreatedPasswords((prev) => ({ ...prev, [created.id]: created.password }));
      setLoginName("");
      setPassword("");
      await load();
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : "Ошибка создания");
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (userId: number, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!window.confirm("Удалить этого пользователя?")) return;
    setDeletingId(userId);
    try {
      await deleteUserApi(userId);
      setCreatedPasswords((prev) => {
        const next = { ...prev };
        delete next[userId];
        return next;
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка удаления");
    } finally {
      setDeletingId(null);
    }
  };

  if (forbidden) {
    return (
      <>
        <AppNav />
        <div className="max-w-5xl mx-auto py-8 px-4">
          <Alert variant="destructive">Доступ запрещён. Только для администратора.</Alert>
          <p className="mt-4">
            <Link to="/" className="text-primary hover:underline">
              На главную
            </Link>
          </p>
        </div>
      </>
    );
  }

  return (
    <div className="min-h-screen bg-muted/30">
      <AppNav />
      <div className="max-w-5xl mx-auto py-8 px-4 space-y-6">
        <h1 className="text-2xl font-bold tracking-tight">Пользователи</h1>

        {error && <Alert variant="destructive">{error}</Alert>}

        <Card>
          <CardHeader>
            <CardTitle>Добавить пользователя</CardTitle>
            <CardDescription>
              Логин и пароль для нового пользователя
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleCreate} className="flex flex-wrap gap-4 items-end">
              <div className="space-y-2">
                <Label htmlFor="new-login">Логин</Label>
                <Input
                  id="new-login"
                  type="text"
                  autoComplete="username"
                  value={loginName}
                  onChange={(e) => setLoginName(e.target.value)}
                  disabled={creating}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="new-password">Пароль</Label>
                <Input
                  id="new-password"
                  type="password"
                  autoComplete="new-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  disabled={creating}
                />
              </div>
              <Button type="submit" disabled={creating}>
                {creating ? "Создание…" : "Добавить"}
              </Button>
            </form>
            {createError && (
              <p className="mt-2 text-sm text-destructive">{createError}</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Список пользователей</CardTitle>
            <CardDescription>
              Пользователи из базы (главный админ задаётся в настройках)
            </CardDescription>
          </CardHeader>
          <CardContent>
            {loading ? (
              <p className="text-muted-foreground">Загрузка…</p>
            ) : list.length === 0 ? (
              <p className="text-muted-foreground">Нет пользователей</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left">
                      <th className="p-2 font-medium">ID</th>
                      <th className="p-2 font-medium">Логин</th>
                      {currentUser?.is_admin && (
                        <th className="p-2 font-medium">Пароль</th>
                      )}
                      <th className="p-2 font-medium">Дата создания</th>
                      <th className="p-2 font-medium w-[80px]"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {list.map((item) => (
                      <tr key={item.id} className="border-b">
                        <td className="p-2 font-mono">{item.id}</td>
                        <td className="p-2">{item.login}</td>
                        {currentUser?.is_admin && (
                          <td className="p-2 font-mono text-muted-foreground">
                            {createdPasswords[item.id] ?? "—"}
                          </td>
                        )}
                        <td className="p-2 text-muted-foreground">
                          {formatCreatedAt(item.created_at)}
                        </td>
                        <td className="p-2">
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8 text-destructive hover:text-destructive"
                            onClick={(e) => handleDelete(item.id, e)}
                            disabled={deletingId !== null}
                            title="Удалить"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </td>
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
