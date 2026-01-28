import { useState } from 'react';
import { ArrowLeft, Upload } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface ExplanationViewProps {
  onBack: () => void;
}

export function MaintenanceView({ onBack }: ExplanationViewProps) {
  const [images, setImages] = useState<File[]>([]);
  const [previews, setPreviews] = useState<string[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);

  // Handle file selection
  const handleImageUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files) return;

    const newFiles = Array.from(files);
    setImages(prev => [...prev, ...newFiles]);

    const newPreviews = newFiles.map(file => URL.createObjectURL(file));
    setPreviews(prev => [...prev, ...newPreviews]);
  };

  // Remove a selected image
  const handleRemoveImage = (index: number) => {
    setImages(prev => prev.filter((_, i) => i !== index));
    setPreviews(prev => prev.filter((_, i) => i !== index));
  };

  // Trigger model processing
  const handleRunModel = () => {
    if (images.length === 0) return;

    setIsProcessing(true);

    // Example: Replace this with your actual model function
    setTimeout(() => {
      console.log('Model triggered on images:', images);
      alert(`Model triggered on ${images.length} image(s)!`);
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
          <h2 className="font-semibold text-lg">Maintenance</h2>
        </div>
      </div>

      {/* Image Upload Section */}
      <div className="glass-panel p-4 flex flex-col gap-3">
        <h3 className="font-semibold text-base">Upload Images</h3>

        {/* Upload Button */}
        <label className="flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded cursor-pointer w-max transition-colors">
          <Upload className="w-4 h-4" />
          Select Images
          <input
            type="file"
            accept="image/*"
            multiple
            onChange={handleImageUpload}
            className="hidden"
          />
        </label>

        {/* Uploaded Images Info */}
        {images.length > 0 && (
          <p className="text-sm text-green-400 mt-1">
            You have uploaded {images.length} image{images.length > 1 ? 's' : ''}.
          </p>
        )}

        {/* Run Model Button */}
        {images.length > 0 && (
          <Button
            onClick={handleRunModel}
            className="mt-2 w-max"
            disabled={isProcessing}
          >
            {isProcessing ? 'Processing...' : 'Run Model'}
          </Button>
        )}

        {/* Preview grid */}
        {previews.length > 0 && (
          <div className="grid grid-cols-3 gap-4 mt-3">
            {previews.map((src, idx) => (
              <div key={idx} className="relative border rounded overflow-hidden">
                <img src={src} alt={`upload-${idx}`} className="w-full h-32 object-cover" />
                <button
                  type="button"
                  onClick={() => handleRemoveImage(idx)}
                  className="absolute top-1 right-1 bg-red-500 text-white rounded-full w-6 h-6 flex items-center justify-center text-xs hover:bg-red-600 transition-colors"
                >
                  &times;
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
