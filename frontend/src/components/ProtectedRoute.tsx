import { Navigate, useLocation } from "react-router-dom";
import { isAuthenticated } from "@/api/auth";

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  if (!isAuthenticated()) {
    return <Navigate to="/auth" state={{ from: location }} replace />;
  }
  return <>{children}</>;
}

export function AuthOnlyRoute({ children }: { children: React.ReactNode }) {
  if (isAuthenticated()) {
    return <Navigate to="/" replace />;
  }
  return <>{children}</>;
}
