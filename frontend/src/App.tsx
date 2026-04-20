import { Route, Routes } from "react-router-dom";

import { MainLayout } from "@/components/layout/main-layout";
import { AnalyzePage } from "@/pages/analyze-page";
import { GovernancePage } from "@/pages/governance-page";
import { HomePage } from "@/pages/home-page";
import { LineagePage } from "@/pages/lineage-page";
import { NotFoundPage } from "@/pages/not-found-page";
import { PRDetailPage } from "@/pages/pr-detail-page";

function App() {
  return (
    <Routes>
      <Route element={<MainLayout />}>
        <Route index element={<HomePage />} />
        <Route path="pr/:id" element={<PRDetailPage />} />
        <Route path="lineage" element={<LineagePage />} />
        <Route path="governance" element={<GovernancePage />} />
        <Route path="analyze" element={<AnalyzePage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}

export default App;
