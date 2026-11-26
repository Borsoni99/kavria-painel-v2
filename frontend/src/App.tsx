import { Navigate, Route, Routes } from "react-router-dom";
import AdminLayout from "./admin/Layout";
import Metas from "./admin/Metas";
import Status from "./admin/Status";
import TvPage from "./tv/TvPage";

export default function App() {
  return (
    <Routes>
      <Route path="/admin" element={<AdminLayout />}>
        <Route index element={<Status />} />
        <Route path="metas" element={<Metas />} />
      </Route>
      <Route path="/tv" element={<TvPage />} />
      <Route path="*" element={<Navigate to="/admin" replace />} />
    </Routes>
  );
}
