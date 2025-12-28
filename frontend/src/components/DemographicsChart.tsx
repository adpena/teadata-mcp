
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from 'recharts';
import { DemographicStats } from '../types';

interface DemographicsChartProps {
  stats: DemographicStats;
}

const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884d8', '#82ca9d'];

export function DemographicsChart({ stats }: DemographicsChartProps) {
  const data = Object.entries(stats.ethnicity_percent)
    .filter(([_, val]) => val !== null && val > 0)
    .map(([key, val]) => ({
      name: key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
      value: val
    }))
    .sort((a, b) => (b.value || 0) - (a.value || 0));

  if (data.length === 0) {
    return <div className="text-gray-400 text-sm text-center py-10">No demographic data available</div>;
  }

  return (
    <div className="h-[300px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={60}
            outerRadius={80}
            fill="#8884d8"
            paddingAngle={2}
            dataKey="value"
          >
            {data.map((_, index) => (
              <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip formatter={(value: any) => `${value?.toFixed(1)}%`} />
          <Legend layout="vertical" verticalAlign="middle" align="right" wrapperStyle={{ fontSize: '12px' }} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
