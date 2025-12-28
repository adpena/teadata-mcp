import React, { useEffect, useState } from 'react';
import { Card } from './Card';
import { api } from '../services/api';
import { Loader2 } from 'lucide-react';

interface NearbyCampusesProps {
  identifier: string;
}

export function NearbyCampuses({ identifier }: NearbyCampusesProps) {
  const [nearby, setNearby] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchNearby() {
      try {
        const result = await api.getNearbyCampuses(identifier);
        setNearby(result.results || []);
      } catch (e) {
        console.error("Failed to load nearby campuses", e);
      } finally {
        setLoading(false);
      }
    }
    fetchNearby();
  }, [identifier]);

  if (loading) {
    return <div className="flex justify-center p-4"><Loader2 className="animate-spin text-gray-400" /></div>;
  }

  if (nearby.length === 0) {
    return null;
  }

  return (
    <div className="space-y-3">
      <h3 className="font-bold text-lg">Nearby Schools</h3>
      <div className="flex overflow-x-auto space-x-4 pb-4">
        {nearby.slice(1).map((campus: any) => ( // Skip first one as it's likely the campus itself
          <Card key={campus.campus_number} className="min-w-[200px] w-[200px] p-3 flex-shrink-0 text-sm">
            <div className="font-semibold truncate" title={campus.name}>{campus.name}</div>
            <div className="text-gray-500 text-xs">{campus.district_name}</div>
            <div className="flex justify-between mt-2">
                <span className="font-medium">{campus.rating || 'NR'}</span>
                <span className="text-gray-400">{campus.distance_miles?.toFixed(1)} mi</span>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
