import React, { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { api } from './services/api';
import { DownloadButton } from './components/DownloadButton';

interface CompareViewProps {
  ids: string[];
}

export function CompareView({ ids }: CompareViewProps) {
  const [data, setData] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchData() {
      setLoading(true);
      setError(null);
      try {
        const result = await api.compareCampuses(ids);
        const payload = result.payload || result;
        setData(payload.comparison || []);
      } catch (e: any) {
        setError(e.message || "Failed to compare campuses.");
      } finally {
        setLoading(false);
      }
    }
    if (ids.length > 0) fetchData();
  }, [ids]);

  if (loading) {
      return (
          <div className="flex flex-col items-center justify-center py-20 text-gray-500">
              <Loader2 className="w-8 h-8 animate-spin mb-4" />
              <p>Comparing campuses...</p>
          </div>
      );
  }

  if (error) {
      return <div className="text-red-500 text-center py-10">{error}</div>;
  }

  if (data.length === 0) {
      return <div className="text-center py-10">No data found.</div>;
  }

  // Define metrics to show
  const metrics = [
      { label: 'Rating', key: 'rating' },
      { label: 'Enrollment', key: 'enrollment', format: (v: any) => v?.toLocaleString() },
      { label: 'Avg Teacher Salary', key: 'avg_teacher_salary', format: (v: any) => v ? `$${v.toLocaleString()}` : '-' },
      { label: 'Student/Teacher Ratio', key: 'student_teacher_ratio', format: (v: any) => v ? `${v.toFixed(1)}:1` : '-' },
      { label: '% Econ Disadvantaged', key: 'percent_econ_disadv', format: (v: any) => v ? `${v.toFixed(1)}%` : '-' },
      { label: '% Special Ed', key: 'percent_special_ed', format: (v: any) => v ? `${v.toFixed(1)}%` : '-' },
  ];

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
          <h1 className="text-2xl font-bold">Campus Comparison</h1>
          <DownloadButton data={data} filename="campus-comparison" />
      </div>
      
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr>
              <th className="p-3 border-b-2 border-gray-100 bg-gray-50 w-1/4 sticky left-0 z-10">Metric</th>
              {data.map(campus => (
                <th key={campus.campus_number} className="p-3 border-b-2 border-gray-100 font-bold min-w-[200px]">
                  {campus.name}
                  <div className="text-xs font-normal text-gray-500">{campus.campus_number}</div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {metrics.map(metric => (
              <tr key={metric.key} className="hover:bg-gray-50">
                <td className="p-3 border-b border-gray-100 font-medium text-gray-600 sticky left-0 bg-white z-10">
                  {metric.label}
                </td>
                {data.map(campus => (
                  <td key={campus.campus_number} className="p-3 border-b border-gray-100">
                    {metric.format ? metric.format(campus[metric.key]) : (campus[metric.key] || '-')}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
