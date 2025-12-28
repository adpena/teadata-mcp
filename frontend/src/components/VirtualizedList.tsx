import React from 'react';
import { FixedSizeList as List } from 'react-window';
import { useElementSize } from '../hooks/useElementSize';

interface VirtualizedListProps<T> {
  items: T[];
  itemHeight: number;
  maxHeight?: number;
  className?: string;
  itemKey?: (item: T, index: number) => string;
  renderItem: (item: T, index: number) => React.ReactNode;
}

export function VirtualizedList<T>({
  items,
  itemHeight,
  maxHeight = 520,
  className,
  itemKey,
  renderItem
}: VirtualizedListProps<T>) {
  // Always call the hook to satisfy Rules of Hooks, even if we might not use the result for small lists.
  const { ref, width } = useElementSize<HTMLDivElement>();

  if (!items.length) {
    return null;
  }

  // Optimization: For small lists, virtualization overhead exceeds benefits (especially in constrained envs).
  // Render a simple scrollable list instead.
  if (items.length < 100) {
    return (
        <div 
          className={`overflow-y-auto ${className || ''}`}
          style={{ maxHeight }}
        >
            {items.map((item, index) => (
                <div key={itemKey ? itemKey(item, index) : index} style={{ height: itemHeight }}>
                    {renderItem(item, index)}
                </div>
            ))}
        </div>
    );
  }

  const height = Math.min(maxHeight, items.length * itemHeight);

  return (
    <div ref={ref} className={className}>
      {width > 0 && (
        <List
          height={height}
          width={width}
          itemCount={items.length}
          itemSize={itemHeight}
          itemKey={(index) => (itemKey ? itemKey(items[index], index) : index)}
        >
          {({ index, style }) => (
            <div style={style} className="pr-2">
              {renderItem(items[index], index)}
            </div>
          )}
        </List>
      )}
    </div>
  );
}
