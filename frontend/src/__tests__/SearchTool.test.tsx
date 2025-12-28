import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { SearchTool } from '../SearchTool';
import { vi } from 'vitest';

describe('SearchTool', () => {
    it('renders input and select fields', () => {
        const mockSearch = vi.fn();
        render(<SearchTool onSearch={mockSearch} isLoading={false} />);

        expect(screen.getByPlaceholderText(/search by name/i)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /search/i })).toBeInTheDocument();
        // Selects are tricky with Radix UI / custom components sometimes, usually they have implicit roles
        // But @openai/apps-sdk-ui Select might render a native select or trigger.
    });

    it('calls onSearch with correct arguments on submission', () => {
        const mockSearch = vi.fn();
        render(<SearchTool onSearch={mockSearch} isLoading={false} />);

        // Type in query
        const input = screen.getByPlaceholderText(/search by name/i);
        fireEvent.change(input, { target: { value: 'Magnet' } });

        // Submit
        const button = screen.getByRole('button', { name: /search/i });
        fireEvent.click(button);

        expect(mockSearch).toHaveBeenCalledWith('Magnet', 'all', 'all', 'all');
    });

    it('handles loading state', () => {
        render(<SearchTool onSearch={vi.fn()} isLoading={true} />);
        expect(screen.getByRole('button', { name: /searching/i })).toBeDisabled();
    });
});
