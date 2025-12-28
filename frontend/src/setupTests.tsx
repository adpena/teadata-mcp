import '@testing-library/jest-dom';
import { vi } from 'vitest';
import React from 'react';

// Mock OpenAI Apps SDK UI components
vi.mock('@openai/apps-sdk-ui/components/Button', () => ({
  Button: ({ children, onClick, disabled, className, type, color }: any) => (
    <button onClick={onClick} disabled={disabled} className={className} type={type} data-color={color}>
      {children}
    </button>
  ),
}));

vi.mock('@openai/apps-sdk-ui/components/Input', () => ({
  Input: (props: any) => <input {...props} data-testid="openai-input" />,
}));

vi.mock('@openai/apps-sdk-ui/components/Select', () => ({
  Select: ({ value, onChange, options }: any) => (
    <select value={value} onChange={onChange} data-testid="openai-select">
      {options.map((opt: any) => (
        <option key={opt.value} value={opt.value}>
          {opt.label}
        </option>
      ))}
    </select>
  ),
}));