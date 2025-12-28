import { Suspense } from 'react';
import { render, screen } from '@testing-library/react';
import { CampusView } from '../CampusView';
import { CampusDetail } from '../types';
import { vi } from 'vitest';

// Mock charts since they are lazy loaded and we don't want to test them deeply here
vi.mock('../components/DemographicsChart', () => ({
    DemographicsChart: () => <div data-testid="demo-chart">Demo Chart</div>
}));
vi.mock('../components/ClassSizeChart', () => ({
    ClassSizeChart: () => <div data-testid="class-chart">Class Chart</div>
}));
vi.mock('../components/MapBox', () => ({
    MapBox: () => <div data-testid="mapbox">Map</div>
}));
vi.mock('../components/NearbyCampuses', () => ({
    NearbyCampuses: () => <div data-testid="nearby">Nearby</div>
}));

const mockCampus: CampusDetail = {
    campus_number: '101902001',
    name: 'Aldine High School',
    district_name: 'Aldine ISD',
    charter: false,
    charter_label: 'ISD',
    is_private: false,
    enrollment: 2500,
    rating: 'B',
    grade_range: '09-12',
    district_slug: '101902',
    staffing: {
        total_teachers_fte: 150.5,
        student_teacher_ratio: 16.6,
        avg_teacher_salary: 60000,
        avg_teacher_experience_years: 10.5,
        teacher_turnover_rate: 12.3
    },
    class_sizes: { elementary: {}, secondary: {} },
    demographics: {
        ethnicity_percent: { african_american: 0, hispanic: 0, white: 0, asian: 0, pacific_islander: 0, two_or_more: 0 },
        programs_percent: { special_ed: 0, econ_disadv: 0, emergent_bilingual: 0, immigrant: 0 }
    },
    location: { lat: 29.9, lon: -95.4 },
    transfers_out: []
};

describe('CampusView', () => {
    it('renders campus details', async () => {
        render(
            <Suspense fallback="loading">
                <CampusView campus={mockCampus} />
            </Suspense>
        );

        // Basic info
        expect(screen.getByText('Aldine High School')).toBeInTheDocument();
        expect(screen.getByText(/Aldine ISD/)).toBeInTheDocument();

        // Stats
        expect(screen.getByText('2,500')).toBeInTheDocument(); // Enrollment
        expect(screen.getByText('B')).toBeInTheDocument(); // Rating

        // Staffing
        expect(screen.getByText('150.5')).toBeInTheDocument();
        expect(screen.getByText('16.6:1')).toBeInTheDocument();
    });

    it('renders map when location is present', () => {
        render(
            <Suspense fallback="loading">
                <CampusView campus={mockCampus} />
            </Suspense>
        );
        expect(screen.getByTestId('mapbox')).toBeInTheDocument();
        expect(screen.getByTestId('nearby')).toBeInTheDocument();
    });

    it('renders charts', async () => {
        render(
            <Suspense fallback="loading">
                <CampusView campus={mockCampus} />
            </Suspense>
        );

        expect(await screen.findByTestId('demo-chart')).toBeInTheDocument();
        expect(await screen.findByTestId('class-chart')).toBeInTheDocument();
    });
});
