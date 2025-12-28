import { createContext, useContext, useState, useEffect, ReactNode } from 'react';

export interface CompareItem {
  id: string;
  name: string;
}

interface CompareContextType {
  items: CompareItem[];
  addItem: (item: CompareItem) => void;
  removeItem: (id: string) => void;
  clear: () => void;
  isInCompare: (id: string) => boolean;
}

const CompareContext = createContext<CompareContextType | undefined>(undefined);

export function CompareProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<CompareItem[]>(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('teadata_compare');
      return saved ? JSON.parse(saved) : [];
    }
    return [];
  });

  useEffect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('teadata_compare', JSON.stringify(items));
    }
  }, [items]);

  const addItem = (item: CompareItem) => {
    if (items.length >= 4) {
      alert("You can compare up to 4 campuses at a time.");
      return;
    }
    if (!items.find(i => i.id === item.id)) {
      setItems([...items, item]);
    }
  };

  const removeItem = (id: string) => {
    setItems(items.filter(i => i.id !== id));
  };

  const clear = () => setItems([]);

  const isInCompare = (id: string) => !!items.find(i => i.id === id);

  return (
    <CompareContext.Provider value={{ items, addItem, removeItem, clear, isInCompare }}>
      {children}
    </CompareContext.Provider>
  );
}

export function useCompare() {
  const context = useContext(CompareContext);
  if (!context) {
    throw new Error('useCompare must be used within a CompareProvider');
  }
  return context;
}
