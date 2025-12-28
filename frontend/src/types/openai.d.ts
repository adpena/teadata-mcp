export interface OpenAIWindow {
  callTool: (name: string, args: Record<string, any>) => Promise<any>;
}

declare global {
  interface Window {
    openai?: OpenAIWindow;
  }
}
