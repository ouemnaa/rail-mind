import { ExplanationView } from "@/components/explanation/ExplanationView";
import { Header } from "@/components/layout/Header";
import { Sidebar } from "@/components/layout/Sidebar";
import { useNavigate } from "react-router-dom";

const Explanation = () => {
  const navigate = useNavigate();

  return (
    <div className="h-screen flex overflow-hidden bg-background">
      <Sidebar  />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header />

        <main className="flex-1 overflow-auto p-6 max-w-3xl mx-auto">
          <ExplanationView onBack={() => navigate("/memory")} />
        </main>
      </div>
    </div>
  );
};

export default Explanation;
