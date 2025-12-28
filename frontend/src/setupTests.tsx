import '@testing-library/jest-dom';

// Mock window.openai for tests
Object.defineProperty(window, 'openai', {
  value: {
    callTool: vi.fn(),
  },
  writable: true,
});

// Mock matchMedia for Recharts/Charts
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation(query => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(), // deprecated
    removeListener: vi.fn(), // deprecated
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

// Mock ResizeObserver
global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};

// Mock @openai/apps-sdk-ui components
const MockComponent = ({ children, className, ...props }: any) => (
  <div className={className} {...props} data-testid="mock-component">{children}</div>
);

vi.mock('@openai/apps-sdk-ui/components/Button', () => ({
  Button: ({ children, onClick, disabled, className }: any) => (
    <button onClick={onClick} disabled={disabled} className={className}>{children}</button>
  ),
}));

vi.mock('@openai/apps-sdk-ui/components/Badge', () => ({
  Badge: ({ children, className }: any) => <span className={className}>{children}</span>,
}));

vi.mock('@openai/apps-sdk-ui/components/Input', () => ({
  Input: (props: any) => <input {...props} data-testid="mock-input" />,
}));

vi.mock('@openai/apps-sdk-ui/components/Select', () => ({
  Select: (props: any) => <select {...props} data-testid="mock-select">{props.children}</select>,
}));

vi.mock('@openai/apps-sdk-ui/components/AppsSDKUIProvider', () => ({
  AppsSDKUIProvider: ({ children }: any) => <>{children}</>,
}));
