import React from 'react';

export const Button = ({ children, onClick, disabled, className }: any) => (
  <button onClick={onClick} disabled={disabled} className={className} data-testid="openai-btn">
    {children}
  </button>
);

export const Badge = ({ children, className }: any) => (
  <span className={className} data-testid="openai-badge">{children}</span>
);

export const Input = (props: any) => (
  <input {...props} data-testid="openai-input" />
);

export const Select = (props: any) => (
  <select {...props} data-testid="openai-select">{props.children}</select>
);

export const AppsSDKUIProvider = ({ children }: any) => <>{children}</>;
