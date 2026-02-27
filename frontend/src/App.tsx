import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { UploadPage } from "./pages/UploadPage";
import { AuthPage } from "./pages/AuthPage";
import { ListPage } from "./pages/ListPage";
import { EditPage } from "./pages/EditPage";
import { UsersPage } from "./pages/UsersPage";
import { ProtectedRoute, AuthOnlyRoute } from "./components/ProtectedRoute";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <UploadPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/list"
          element={
            <ProtectedRoute>
              <ListPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/edit/:id"
          element={
            <ProtectedRoute>
              <EditPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/users"
          element={
            <ProtectedRoute>
              <UsersPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/auth"
          element={
            <AuthOnlyRoute>
              <AuthPage />
            </AuthOnlyRoute>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
