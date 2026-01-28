import { useState } from 'react';
import { ArrowLeft, Upload } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface ExplanationViewProps {
  onBack: () => void;
}

export function DocumentationView({ onBack }: ExplanationViewProps) {
  const [files, setFiles] = useState<File[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);

  // Handle file selection
  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = event.target.files;
    if (!selectedFiles) return;

    const newFiles = Array.from(selectedFiles).filter(file => file.type === 'application/pdf');
    if (newFiles.length === 0) return;

    setFiles(prev => [...prev, ...newFiles]);
  };

  // Remove a selected file
  const handleRemoveFile = (index: number) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
  };

  // Trigger model processing
  const handleRunModel = () => {
    if (files.length === 0) return;

    setIsProcessing(true);

    // Replace this with your actual model function
    setTimeout(() => {
      console.log('Model triggered on files:', files);
      alert(`Model triggered on ${files.length} PDF file(s)!`);
      setIsProcessing(false);
    }, 1000);
  };

  return (
    <div className="h-full flex flex-col gap-6 animate-fade-in">
      {/* Header */}
      <div className="glass-panel p-4 mb-4 flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={onBack} className="shrink-0">
          <ArrowLeft className="w-5 h-5" />
        </Button>
        <div>
          <h2 className="font-semibold text-lg">Upload PDF Documents</h2>
        </div>
      </div>

      {/* File Upload Section */}
      <div className="glass-panel p-4 flex flex-col gap-3">
        <h3 className="font-semibold text-base">Upload PDFs</h3>

        {/* Upload Button */}
        <label className="flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded cursor-pointer w-max transition-colors">
          <Upload className="w-4 h-4" />
          Select PDFs
          <input
            type="file"
            accept="application/pdf"
            multiple
            onChange={handleFileUpload}
            className="hidden"
          />
        </label>

        {/* Uploaded Files Info */}
        {files.length > 0 && (
          <p className="text-sm text-green-400 mt-1">
            You have uploaded {files.length} PDF file{files.length > 1 ? 's' : ''}.
          </p>
        )}

        {/* Run Model Button */}
        {files.length > 0 && (
          <Button
            onClick={handleRunModel}
            className="mt-2 w-max"
            disabled={isProcessing}
          >
            {isProcessing ? 'Processing...' : 'Run Model'}
          </Button>
        )}

        {/* File List */}
        {files.length > 0 && (
          <ul className="mt-3 flex flex-col gap-2">
            {files.map((file, idx) => (
              <li key={idx} className="flex items-center justify-between border p-2 rounded bg-slate-800 text-white">
                <span>{file.name}</span>
                <button
                  type="button"
                  onClick={() => handleRemoveFile(idx)}
                  className="bg-red-500 text-white rounded-full w-6 h-6 flex items-center justify-center text-xs hover:bg-red-600 transition-colors"
                >
                  &times;
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
