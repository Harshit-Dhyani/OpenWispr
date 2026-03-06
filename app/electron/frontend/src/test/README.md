# Frontend Testing Suite

Comprehensive testing suite for the Transcripta Electron frontend application.

## Test Structure

```
src/
├── test/
│   ├── setup.ts          # Test environment setup
│   ├── utils.ts          # Test utilities and helpers
│   ├── factories.ts      # Test data factories
│   ├── index.ts          # Test exports
│   └── integration/      # Integration tests
│       ├── flows.test.tsx
│       └── websocket.test.tsx
├── components/
│   └── __tests__/        # Component tests
├── hooks/
│   └── __tests__/        # Hook tests
└── lib/
    └── *.test.ts         # Utility tests
```

## Running Tests

### Basic Commands

```bash
# Run all tests
npm test

# Run tests in watch mode
npm run test:watch

# Run tests with coverage
npm run test:coverage

# Run only unit tests
npm run test:unit

# Run only integration tests
npm run test:integration

# Run tests with UI
npm run test:ui

# Debug tests
npm run test:debug
```

## Test Categories

### Unit Tests

Test individual components, hooks, and utilities in isolation.

- **Components**: Render tests, interaction tests, state tests
- **Hooks**: Behavior tests, lifecycle tests, callback tests
- **Utils**: Function tests, edge case tests

### Integration Tests

Test multiple components and systems working together.

- **Settings Flow**: Change → Save → Verify
- **Transcription Flow**: Start → Record → Stop → Verify
- **WebSocket Flow**: Connect → Message → Reconnect → Disconnect

## Coverage Targets

| Category | Target |
|----------|--------|
| Branches | 80% |
| Functions | 80% |
| Lines | 80% |
| Statements | 80% |

Configured in `vitest.config.ts`. Run `npm run test:coverage` to generate reports.

## Test Utilities

### Factories

Use factories to create consistent test data:

```typescript
import { createMockSettings, createMockSegment, createMockDevice } from '@/test';

const settings = createMockSettings({
  general: { theme: 'dark' }
});

const segment = createMockSegment({
  text: 'Test transcription',
  confidence: 0.95
});
```

### Mock APIs

Mock Electron and browser APIs:

```typescript
import { createMockElectronAPI, createMockMediaDevices, createMockFloatingAPI } from '@/test';

// Mock Electron API
window.transcriptaDesktop = createMockElectronAPI();

// Mock floating window API
window.floatingAPI = createMockFloatingAPI();

// Mock media devices
navigator.mediaDevices = createMockMediaDevices();
```

### Async Helpers

```typescript
import { waitFor, waitForCondition, flushPromises, actAndFlush, waitForPromises } from '@/test';

// Wait for expectation (from @testing-library/react)
await waitFor(() => expect(element).toBeInTheDocument());

// Wait for custom condition (polls until callback returns true)
await waitForCondition(() => element.isConnected);

// Flush promises
await flushPromises();

// Act and flush
await actAndFlush(() => fireEvent.click(button));

// Wait for multiple promise cycles
await waitForPromises(3);
```

## Writing Tests

### Component Test Example

```typescript
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MyComponent } from './MyComponent';

describe('MyComponent', () => {
  it('renders correctly', () => {
    render(<MyComponent />);
    expect(screen.getByText('Expected Text')).toBeInTheDocument();
  });

  it('handles user interaction', () => {
    const onClick = vi.fn();
    render(<MyComponent onClick={onClick} />);
    
    fireEvent.click(screen.getByRole('button'));
    expect(onClick).toHaveBeenCalled();
  });
});
```

### Hook Test Example

```typescript
import { describe, it, expect } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useMyHook } from './useMyHook';

describe('useMyHook', () => {
  it('returns initial state', () => {
    const { result } = renderHook(() => useMyHook());
    expect(result.current.value).toBe('initial');
  });

  it('updates state on action', () => {
    const { result } = renderHook(() => useMyHook());
    
    act(() => {
      result.current.setValue('new');
    });
    
    expect(result.current.value).toBe('new');
  });
});
```

## CI/CD Integration

Tests run automatically via:
- Local pre-commit hooks
- Manual quality gate with `npm run test`

### GitHub Actions

No automated frontend test workflow currently configured. Run tests locally before committing.

### Coverage Reporting

Coverage reports are:
- Uploaded to Codecov
- Posted as PR comments
- Tracked over time

## Flaky Test Detection

Tests run multiple times in CI to detect flaky tests:

```bash
# Run tests 5 times
for i in {1..5}; do
  npm test || exit 1
done
```

## Best Practices

1. **Use factories** for test data
2. **Mock external APIs** consistently
3. **Clean up** after each test
4. **Test behavior**, not implementation
5. **Use accessible queries** (getByRole, getByLabelText)
6. **Avoid snapshot tests** for dynamic content

## Troubleshooting

### Tests Failing in CI but Passing Locally

- Check for race conditions with `waitFor`
- Ensure proper cleanup in `afterEach`
- Use `act()` for state updates

### Coverage Not Meeting Targets

- Check uncovered lines in `coverage/html/index.html`
- Add tests for edge cases
- Exclude non-testable code with `/* istanbul ignore next */`

### Memory Issues

- Use `isolate: true` in vitest config
- Clean up large objects after tests
- Limit concurrent test runs
