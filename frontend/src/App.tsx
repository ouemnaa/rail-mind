import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";

import Memory from "./pages/Memory";
import Resolution from "./pages/Resolution";
import Explanation from "./pages/Explanation";
import Maintenance from "./pages/Maintenance";
import Documentation from "./pages/Documentation";
import NotFound from "./pages/NotFound";
import Index from "./pages/Index";

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      {/* Toasters */}
      <Toaster />
      <Sonner />

      <BrowserRouter>
        <Routes>
          {/* Main Pages */}
          <Route path="/" element={<Index/>} />
          <Route path="/memory" element={<Memory />} />
          <Route path="/resolution" element={<Resolution />} />
          <Route path="/resolution/:conflictId" element={<Resolution />} />
          <Route path="/explanation" element={<Explanation />} />
          <Route path="/maintenance" element={<Maintenance />} />
          <Route path="/documentation" element={<Documentation />} />

          {/* Catch-all */}
          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
