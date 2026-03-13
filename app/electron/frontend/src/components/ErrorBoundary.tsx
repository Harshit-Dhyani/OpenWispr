import { Component, type ReactNode, type ErrorInfo } from 'react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

/**
 * Error Boundary component to catch React rendering errors
 * and prevent the entire app from crashing.
 */
export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error('ErrorBoundary caught error:', error);
    console.error('Component stack:', errorInfo.componentStack);
    this.props.onError?.(error, errorInfo);
  }

  render(): ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="min-h-screen flex items-center justify-center bg-lawn-bg p-4">
          <div className="max-w-md w-full border-2 border-error bg-lawn-panel p-6 text-center">
            <h2 className="text-xl font-black text-error mb-4">Something went wrong</h2>
            <p className="text-sm text-lawn-border mb-4">
              An error occurred while rendering this component.
            </p>
            <details className="text-left text-xs bg-lawn-bg p-3 mb-4 overflow-auto max-h-40">
              <summary className="cursor-pointer font-bold">Error details</summary>
              <pre className="mt-2 whitespace-pre-wrap break-words text-error">
                {this.state.error?.message}
              </pre>
            </details>
            <button
              onClick={() => window.location.reload()}
              className="px-6 py-2 border-2 border-lawn-accent bg-lawn-accent text-lawn-bg font-bold hover:shadow-brutal-sm transition-all"
            >
              Reload Application
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
