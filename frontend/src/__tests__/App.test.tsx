import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import App from '../App';
import { api } from '../services/api';
import { vi } from 'vitest';

// Mock the API service
vi.mock('../services/api', () => ({
  api: {
    searchCampuses: vi.fn(),
    getCampusDetail: vi.fn(),
    getDistrictDetail: vi.fn(),
    compareCampuses: vi.fn(),
    findCampusesInDistrict: vi.fn(),
  }
}));

describe('App', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the home screen with search tool', async () => {
    render(<App />);
    
    // Check for title (lazy loaded)
    expect(await screen.findByText(/Texas Education Data/i)).toBeInTheDocument();
    
    // Check for search input (placeholder text from SearchTool)
    const searchInput = await screen.findByPlaceholderText(/search by name/i);
    expect(searchInput).toBeInTheDocument();
  });

  it('performs a search when user types and submits', async () => {
    const mockResults = [
        { name: 'Test School', campus_number: '123', district_name: 'Test District' }
    ];
    (api.searchCampuses as any).mockResolvedValue({ results: mockResults });

    render(<App />);

    const searchInput = await screen.findByPlaceholderText(/search by name/i);
    fireEvent.change(searchInput, { target: { value: 'Test' } });
    
    const searchButton = screen.getByRole('button', { name: /search/i });
    fireEvent.click(searchButton);

    await waitFor(() => {
        expect(api.searchCampuses).toHaveBeenCalledWith('Test', 'all', 'all', 'all');
        expect(screen.getByText('Test School')).toBeInTheDocument();
    });
  });
});
