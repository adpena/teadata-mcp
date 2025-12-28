import React from 'react';
import { useCompare } from '../context/CompareContext';
import { Button } from '@openai/apps-sdk-ui/components/Button';
import { GitCompare, Check } from 'lucide-react';

interface CompareButtonProps {
  id: string;
  name: string;
  variant?: 'ghost' | 'primary' | 'secondary' | 'outline' | 'destructive';
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export function CompareButton({ id, name, variant = 'outline', size = 'sm', className }: CompareButtonProps) {
  const { isInCompare, addItem, removeItem } = useCompare();
  const selected = isInCompare(id);

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent card clicks
    if (selected) {
      removeItem(id);
    } else {
      addItem({ id, name });
    }
  };

  return (
    <Button 
      variant={selected ? 'primary' : variant} 
      size={size} 
      onClick={handleClick}
      className={className}
    >
      {selected ? <Check className="w-4 h-4 mr-2" /> : <GitCompare className="w-4 h-4 mr-2" />}
      {selected ? 'Added' : 'Compare'}
    </Button>
  );
}
