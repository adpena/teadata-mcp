import { render, screen, waitFor } from '@testing-library/react';
import App from '../App';
import { describe, it, expect, vi } from 'vitest';

// Mock the API service
vi.mock('../services/api', () => ({
  api: {
    callTool: vi.fn(),
    isPerfEnabled: vi.fn().mockReturnValue(false),
  },
}));

// Mock map components which might fail in jsdom
vi.mock('../components/MapBox', () => ({
  default: () => <div data-testid="map-mock">Map</div>,
}));

vi.mock('../components/MapLibreView', () => ({
  default: () => <div data-testid="maplibre-mock">MapLibre</div>,
}));

// Mock LandingPage to avoid lazy loading issues and verify routing to home
vi.mock('../LandingPage', () => ({
  LandingPage: () => <div data-testid="landing-page">Landing Page Mock</div>,
}));

describe('App', () => {
  it('renders landing page by default', async () => {
    render(<App />);
    
    // Use waitFor because of Suspense/Lazy loading
    await waitFor(() => {
      expect(screen.getByTestId('landing-page')).toBeInTheDocument();
    });
  });
});
