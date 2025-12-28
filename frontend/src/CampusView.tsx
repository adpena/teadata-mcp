import React, { Suspense } from 'react';
import { Card } from './components/Card';
import { Badge } from '@openai/apps-sdk-ui/components/Badge';
import { CampusDetail } from './types';
import { MapBox } from './components/MapBox';
import { NearbyCampuses } from './components/NearbyCampuses';
import { DownloadButton } from './components/DownloadButton';

const DemographicsChart = React.lazy(() => import('./components/DemographicsChart').then(module => ({ default: module.DemographicsChart })));
const ClassSizeChart = React.lazy(() => import('./components/ClassSizeChart').then(module => ({ default: module.ClassSizeChart })));

interface CampusViewProps {
  campus: CampusDetail;
}

export function CampusView({ campus }: CampusViewProps) {
  const hasLocation = campus.location && campus.location.lat && campus.location.lon;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-2xl font-bold">{campus.name}</h1>
          <p className="text-gray-600">{campus.district_name} • {campus.campus_number}</p>
        </div>
        <div className="flex space-x-2">
            <DownloadButton data={campus} filename={`campus-${campus.campus_number}`} label="Export" />
            <Badge variant={campus.charter ? 'warning' : 'neutral'}>
            {campus.charter_label}
            </Badge>
        </div>
      </div>

      {hasLocation && (
        <MapBox 
          center={[campus.location.lat!, campus.location.lon!]} 
          zoom={15}
          markers={[{
            lat: campus.location.lat!,
            lon: campus.location.lon!,
            title: campus.name,
            description: `Rating: ${campus.rating || 'N/A'}`,
            rating: campus.rating || null
          }]}
          className="h-[250px] w-full rounded-lg shadow-sm border border-gray-200"
        />
      )}
      
      {hasLocation && <NearbyCampuses identifier={campus.campus_number} />}

      <div className="grid grid-cols-2 gap-4">
        <Card className="p-4">
          <h3 className="font-semibold text-gray-500 mb-1">Rating</h3>
          <p className="text-2xl font-bold">{campus.rating || 'N/A'}</p>
        </Card>
        <Card className="p-4">
          <h3 className="font-semibold text-gray-500 mb-1">Enrollment</h3>
          <p className="text-2xl font-bold">{campus.enrollment?.toLocaleString() || 'N/A'}</p>
        </Card>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card className="p-4 space-y-4">
          <h3 className="font-bold border-b pb-2">Staffing</h3>
          <dl className="space-y-3">
            <div className="flex justify-between">
              <dt className="text-gray-600">Total Teachers</dt>
              <dd className="font-medium">{campus.staffing.total_teachers_fte?.toFixed(1) || '-'}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-600">Student/Teacher Ratio</dt>
              <dd className="font-medium">{campus.staffing.student_teacher_ratio ? `${campus.staffing.student_teacher_ratio.toFixed(1)}:1` : '-'}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-600">Avg. Salary</dt>
              <dd className="font-medium">{campus.staffing.avg_teacher_salary ? `${campus.staffing.avg_teacher_salary.toLocaleString()}` : '-'}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-gray-600">Avg. Experience</dt>
              <dd className="font-medium">{campus.staffing.avg_teacher_experience_years?.toFixed(1) || '-'} years</dd>
            </div>
          </dl>
        </Card>

        <Card className="p-4 space-y-4 min-h-[350px]">
          <h3 className="font-bold border-b pb-2">Demographics</h3>
          <Suspense fallback={<div className="h-[300px] w-full bg-gray-50 animate-pulse rounded flex items-center justify-center text-gray-400">Loading chart...</div>}>
            <DemographicsChart stats={campus.demographics} />
          </Suspense>
        </Card>
      </div>
      
      <Card className="p-4 space-y-4">
          <h3 className="font-bold border-b pb-2">Class Sizes by Grade</h3>
          <Suspense fallback={<div className="h-[300px] w-full bg-gray-50 animate-pulse rounded flex items-center justify-center text-gray-400">Loading chart...</div>}>
            <ClassSizeChart stats={campus.class_sizes} />
          </Suspense>
      </Card>
    </div>
  );
}