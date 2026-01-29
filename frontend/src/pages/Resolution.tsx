import { useParams, useNavigate } from "react-router-dom";
import { ResolutionPanel } from "@/components/resolution/ResolutionPanel";
import { Header } from "@/components/layout/Header";
import { Sidebar } from "@/components/layout/Sidebar";

const Resolution = () => {
  const navigate = useNavigate();
  const { conflictId } = useParams<{ conflictId: string }>();

  return (
    <div className="h-screen flex overflow-hidden bg-background">
      {/* Sidebar with current view and navigation */}
      <Sidebar
        
      />

      {/* Main content area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header />

        <main className="flex-1 overflow-auto p-6 max-w-[1600px] w-full mx-auto">
          {/* Pass conflictId to ResolutionPanel if available */}
          <ResolutionPanel
            onViewExplanation={(resolution) => navigate("/explanation", { state: { resolution } })}
          />
        </main>
      </div>
    </div>
  );
};

export default Resolution;
