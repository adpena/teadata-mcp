
import { Button } from '@openai/apps-sdk-ui/components/Button';
import { Download } from 'lucide-react';

interface DownloadButtonProps {
  data: any;
  filename: string;
  label?: string;
  size?: 'sm' | 'md';
}

export function DownloadButton({ data, filename, label = "Download JSON", size = 'sm' }: DownloadButtonProps) {
  const handleDownload = () => {
    const jsonString = JSON.stringify(data, null, 2);
    const blob = new Blob([jsonString], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename.endsWith('.json') ? filename : `${filename}.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  return (
    <Button variant="ghost" size={size} onClick={handleDownload} className="print:hidden" color="primary">
      <Download className="w-4 h-4 mr-2" />
      {label}
    </Button>
  );
}
