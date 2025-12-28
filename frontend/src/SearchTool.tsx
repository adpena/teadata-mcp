import React, { useState } from 'react';
import { Input } from '@openai/apps-sdk-ui/components/Input';
import { Button } from '@openai/apps-sdk-ui/components/Button';
import { Select } from '@openai/apps-sdk-ui/components/Select';

interface SearchToolProps {
  onSearch: (query: string, status: string, rating: string, grade_level: string) => void;
  isLoading: boolean;
}

export function SearchTool({ onSearch, isLoading }: SearchToolProps) {
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('all');
  const [rating, setRating] = useState('all');
  const [gradeLevel, setGradeLevel] = useState('all');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSearch(query, status, rating, gradeLevel);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="flex gap-2">
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search by name, number, or district..."
          className="flex-1"
        />
        <Button type="submit" disabled={isLoading} color="primary">
          {isLoading ? 'Searching...' : 'Search'}
        </Button>
      </div>
      <div className="flex gap-4">
        <div className="w-48">
          <Select
            value={status}
            onChange={(e: any) => setStatus(e.target.value)}
            options={[
              { label: 'Status: Any', value: 'all' },
              { label: 'ISD Only', value: 'isd' },
              { label: 'Charter Only', value: 'charter' },
              { label: 'Private Only', value: 'private' },
            ]}
          />
        </div>
        <div className="w-48">
          <Select
            value={rating}
            onChange={(e: any) => setRating(e.target.value)}
            options={[
              { label: 'Rating: Any', value: 'all' },
              { label: 'A', value: 'A' },
              { label: 'B', value: 'B' },
              { label: 'C', value: 'C' },
              { label: 'D', value: 'D' },
              { label: 'F', value: 'F' },
              { label: 'Not Rated', value: 'NR' },
            ]}
          />
        </div>
        <div className="w-48">
          <Select
            value={gradeLevel}
            onChange={(e: any) => setGradeLevel(e.target.value)}
            options={[
              { label: 'Grade: Any', value: 'all' },
              { label: 'Elementary', value: 'ELEMENTARY' },
              { label: 'Middle School', value: 'MIDDLE' },
              { label: 'High School', value: 'HIGH' },
            ]}
          />
        </div>
      </div>
    </form>
  );
}
