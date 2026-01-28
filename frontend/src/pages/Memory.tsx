import { MemoryView } from "@/components/memory/MemoryView";
import { ResolutionPanel } from "@/components/resolution/ResolutionPanel";
import { Header } from "@/components/layout/Header";
import { Sidebar } from "@/components/layout/Sidebar";
import { useNavigate } from "react-router-dom";

const Memory = () => {
  const navigate = useNavigate();

  return (
    <div className="h-screen flex overflow-hidden bg-background">
      <Sidebar  />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header />

        <main className="flex-1 overflow-auto p-6 flex flex-col gap-6">
          <MemoryView />
          <ResolutionPanel onViewExplanation={() => navigate("/explanation")} />
        </main>
      </div>
    </div>
  );
};

export default Memory;
