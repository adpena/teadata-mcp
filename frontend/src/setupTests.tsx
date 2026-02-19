import '@testing-library/jest-dom';
import { vi } from 'vitest';

// JSDOM + newer Node runtimes can expose a partial/experimental Web Storage API.
// For tests, we need a predictable localStorage implementation.
if (typeof window !== 'undefined') {
  const existing = (window as any).localStorage;
  if (!existing || typeof existing.getItem !== 'function') {
    let store: Record<string, string> = {};
    const localStorageMock = {
      getItem: (key: string) => (key in store ? store[key] : null),
      setItem: (key: string, value: string) => {
        store[key] = String(value);
      },
      removeItem: (key: string) => {
        delete store[key];
      },
      clear: () => {
        store = {};
      },
    };
    Object.defineProperty(window, 'localStorage', {
      value: localStorageMock,
      configurable: true,
    });
  }
}

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
