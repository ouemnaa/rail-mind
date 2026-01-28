import { DocumentationView } from "@/components/documentation/DocumentationView";
import { Header } from "@/components/layout/Header";
import { Sidebar } from "@/components/layout/Sidebar";
import { useNavigate } from "react-router-dom";

const Documentation = () => {
  const navigate = useNavigate();

  return (
    <div className="h-screen flex overflow-hidden bg-background">
      <Sidebar  />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-auto p-6">
          <DocumentationView onBack={() => navigate("/")} />
        </main>
      </div>
    </div>
  );
};

export default Documentation;
