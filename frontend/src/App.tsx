import type { ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { getToken } from "./api";
import Editor from "./pages/Editor";
import Login from "./pages/Login";
import Workbench from "./pages/Workbench";

function Guard({ children }: { children: ReactNode }) {
  if (!getToken()) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/"
        element={
          <Guard>
            <Workbench />
          </Guard>
        }
      />
      <Route
        path="/jobs/:id"
        element={
          <Guard>
            <Editor />
          </Guard>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
