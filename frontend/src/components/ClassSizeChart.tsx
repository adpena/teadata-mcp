import React from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { ClassSizeStats } from '../types';

interface ClassSizeChartProps {
  stats: ClassSizeStats;
}

export function ClassSizeChart({ stats }: ClassSizeChartProps) {
  // Combine elementary and secondary data
  const rawData = { ...stats.elementary, ...stats.secondary };
  
  // Define a sort order for grades
  const gradeOrder = ['PK', 'KG', '01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12'];
  
  const data = Object.entries(rawData)
    .filter(([_, size]) => size !== null)
    .map(([grade, size]) => ({
      grade: grade.toUpperCase(),
      size: size
    }))
    .sort((a, b) => {
        const idxA = gradeOrder.indexOf(a.grade);
        const idxB = gradeOrder.indexOf(b.grade);
        if (idxA === -1 && idxB === -1) return a.grade.localeCompare(b.grade);
        if (idxA === -1) return 1;
        if (idxB === -1) return -1;
        return idxA - idxB;
    });

  if (data.length === 0) {
    return <div className="text-gray-400 text-sm text-center py-10">No class size data available</div>;
  }

  return (
    <div className="h-[300px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          margin={{ top: 5, right: 30, left: 0, bottom: 5 }}
        >
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="grade" tick={{ fontSize: 12 }} />
          <YAxis tick={{ fontSize: 12 }} />
          <Tooltip 
            formatter={(value: number) => [value.toFixed(1), 'Avg Students']}
            labelFormatter={(label) => `Grade ${label}`}
          />
          <Bar dataKey="size" fill="#3b82f6" radius={[4, 4, 0, 0]} name="Avg Class Size" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
