import { useEffect, useRef, useState } from "react";
import { checkBackendReady } from "@/api/backendHealth";

const POLL_INTERVAL_MS = 1500;

export function BackendLoadingOverlay() {
  const [ready, setReady] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    let cancelled = false;

    const poll = async () => {
      const ok = await checkBackendReady(3000);
      if (!cancelled) {
        setReady(ok);
        if (ok && intervalRef.current) {
          clearInterval(intervalRef.current);
          intervalRef.current = null;
        }
      }
    };

    poll();
    intervalRef.current = setInterval(poll, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  if (ready) return null;

  return (
    <div
      className="fixed inset-0 z-[9999] flex flex-col items-center justify-center bg-background text-foreground"
      aria-live="polite"
      aria-busy="true"
      role="status"
    >
      <div
        className="h-12 w-12 animate-spin rounded-full border-4 border-muted-foreground/30 border-t-primary"
        aria-hidden
      />
      <p className="mt-4 text-lg font-medium text-muted-foreground">
        Сервер запускается…
      </p>
      <p className="mt-1 text-sm text-muted-foreground/80">
        Подождите, пока бекенд будет готов.
      </p>
    </div>
  );
}
