import { useCallback, useEffect, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { CorrectionForm } from "@/components/CorrectionForm";
import { AppNav } from "@/components/AppNav";
import { fetchBlankById, setBlankVerifiedApi, type BlankEditResponse, type CorrectionPayload, ApiError, NetworkError } from "@/api/blankCheck";
import { Loader2, ArrowLeft } from "lucide-react";
import { Label } from "@/components/ui/label";

export function EditPage() {
  const { id } = useParams<"id">();
  const navigate = useNavigate();
  const [payload, setPayload] = useState<CorrectionPayload | null>(null);
  const [recordId, setRecordId] = useState<number | null>(null);
  const [verified, setVerified] = useState(false);
  const [verifiedAt, setVerifiedAt] = useState<string | null>(null);
  const [verifiedBy, setVerifiedBy] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [togglingVerified, setTogglingVerified] = useState(false);

  const load = useCallback(async (blankId: number) => {
    setLoading(true);
    setError(null);
    setNotFound(false);
    try {
      const data = await fetchBlankById(blankId) as BlankEditResponse;
      setPayload({
        page: data.page,
        aligned_image_url: data.aligned_image_url,
        fields: data.fields,
      });
      setRecordId(data.record_id);
      setVerified(!!data.verified);
      setVerifiedAt(data.verified_at ?? null);
      setVerifiedBy(data.verified_by ?? null);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setNotFound(true);
      } else if (err instanceof ApiError) {
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
    const n = id ? parseInt(id, 10) : NaN;
    if (Number.isNaN(n) || n < 1) {
      setNotFound(true);
      setLoading(false);
      return;
    }
    load(n);
  }, [id, load]);

  const handleSuccess = () => {
    navigate("/list");
  };

  const handleToggleVerified = async () => {
    if (recordId == null || togglingVerified) return;
    setTogglingVerified(true);
    setError(null);
    try {
      await setBlankVerifiedApi(recordId, !verified);
      const data = await fetchBlankById(recordId) as BlankEditResponse;
      setVerified(!!data.verified);
      setVerifiedAt(data.verified_at ?? null);
      setVerifiedBy(data.verified_by ?? null);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.code + ": " + err.message);
      } else if (err instanceof NetworkError) {
        setError(err.message);
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError(String(err));
      }
    } finally {
      setTogglingVerified(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-muted/30 flex flex-col">
        <AppNav />
        <div className="py-8 px-4 flex-1 flex items-center justify-center">
          <Loader2 className="h-10 w-10 animate-spin text-muted-foreground" />
        </div>
      </div>
    );
  }

  if (notFound) {
    return (
      <div className="min-h-screen bg-muted/30">
        <AppNav />
        <div className="py-8 px-4">
          <div className="max-w-lg mx-auto space-y-4">
            <Alert variant="destructive">Бланк с указанным ID не найден.</Alert>
            <Button variant="outline" asChild>
              <Link to="/list">
                <ArrowLeft className="h-4 w-4 mr-2" />
                К списку бланков
              </Link>
            </Button>
          </div>
        </div>
      </div>
    );
  }

  if (error && !payload) {
    return (
      <div className="min-h-screen bg-muted/30">
        <AppNav />
        <div className="py-8 px-4">
          <div className="max-w-lg mx-auto space-y-4">
            <Alert variant="destructive">{error}</Alert>
            <Button variant="outline" asChild>
              <Link to="/list">
                <ArrowLeft className="h-4 w-4 mr-2" />
                К списку бланков
              </Link>
            </Button>
          </div>
        </div>
      </div>
    );
  }

  if (!payload || recordId == null) {
    return null;
  }

  return (
    <div className="h-screen flex flex-col bg-muted/30 overflow-hidden">
      <AppNav />
      <div className="flex-shrink-0 py-4 px-4 border-b bg-background/80">
        <div className="max-w-6xl mx-auto flex items-center gap-4 flex-wrap">
          <Button variant="ghost" size="sm" asChild>
            <Link to="/list">
              <ArrowLeft className="h-4 w-4 mr-1" />
              К списку
            </Link>
          </Button>
          <h1 className="text-2xl font-bold tracking-tight">Редактирование бланка #{recordId}</h1>
          <div className="flex items-center gap-3 ml-auto">
            <div className="flex items-center gap-2">
              <input
                id="edit-verified"
                type="checkbox"
                checked={verified}
                onChange={handleToggleVerified}
                disabled={togglingVerified}
                className="h-4 w-4 rounded border-input"
              />
              <Label htmlFor="edit-verified" className="cursor-pointer text-sm font-normal">
                Проверено
              </Label>
            </div>
            {verified && (verifiedBy || verifiedAt) && (
              <span className="text-xs text-muted-foreground">
                {verifiedBy && `Проверил: ${verifiedBy}`}
                {verifiedBy && verifiedAt && " · "}
                {verifiedAt && new Date(verifiedAt).toLocaleString(undefined, { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" })}
              </span>
            )}
          </div>
        </div>
        {error && <Alert variant="destructive" className="max-w-6xl mx-auto mt-2">{error}</Alert>}
      </div>
      <div className="flex-1 min-h-0 flex flex-col overflow-hidden max-w-6xl w-full mx-auto px-4 py-4">
        <CorrectionForm
          payload={payload}
          recordId={recordId}
          onSuccess={handleSuccess}
        />
      </div>
    </div>
  );
}
