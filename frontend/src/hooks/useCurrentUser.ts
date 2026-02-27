import { useEffect, useState } from "react";
import { fetchMe, isAuthenticated, type UserMeResponse } from "@/api/auth";

export function useCurrentUser(): {
  user: UserMeResponse | null;
  loading: boolean;
} {
  const [user, setUser] = useState<UserMeResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isAuthenticated()) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    fetchMe()
      .then((data) => {
        if (!cancelled) setUser(data);
      })
      .catch(() => {
        if (!cancelled) setUser(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { user, loading };
}
