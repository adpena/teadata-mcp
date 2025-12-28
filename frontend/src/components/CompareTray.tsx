import React from 'react';
import { useCompare } from '../context/CompareContext';
import { Button } from '@openai/apps-sdk-ui/components/Button';
import { X, GitCompare } from 'lucide-react';

interface CompareTrayProps {
  onCompare: () => void;
}

export function CompareTray({ onCompare }: CompareTrayProps) {
  const { items, removeItem, clear } = useCompare();

  if (items.length === 0) return null;

  return (
    <div className="fixed bottom-4 left-4 right-4 bg-white shadow-xl border border-gray-200 rounded-lg p-4 flex items-center justify-between z-50 animate-in slide-in-from-bottom-5">
      <div className="flex items-center space-x-4 overflow-x-auto pb-1">
        <span className="text-sm font-semibold text-gray-500 whitespace-nowrap">
          Compare ({items.length}):
        </span>
        <div className="flex space-x-2">
            {items.map(item => (
            <div key={item.id} className="flex items-center bg-gray-100 rounded-full px-3 py-1 text-sm">
                <span className="truncate max-w-[150px]">{item.name}</span>
                <button 
                onClick={() => removeItem(item.id)}
                className="ml-2 text-gray-400 hover:text-red-500"
                >
                <X className="w-3 h-3" />
                </button>
            </div>
            ))}
        </div>
      </div>
      
      <div className="flex space-x-2 ml-4">
        <Button variant="ghost" size="sm" onClick={clear}>Clear</Button>
        <Button 
            variant="primary" 
            size="sm" 
            onClick={onCompare}
            disabled={items.length < 2}
        >
          <GitCompare className="w-4 h-4 mr-2" />
          Compare
        </Button>
      </div>
    </div>
  );
}
