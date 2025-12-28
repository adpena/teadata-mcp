# Production Readiness Plan

## 1. Frontend Testing
**Goal:** Establish a testing baseline for the React application.
- [ ] **Install Dependencies:** `vitest`, `jsdom`, `@testing-library/react`, `@testing-library/jest-dom`, `@testing-library/user-event`.
- [ ] **Configure Vitest:** Update `vite.config.ts` to support testing.
- [ ] **Create Test Setup:** Add `frontend/src/setupTests.ts`.
- [ ] **Write Tests:** Create `frontend/src/__tests__/App.test.tsx` to verify:
    - App renders without crashing.
    - Search interaction works (mocking the API).
    - Compare tray appears when items are added.

## 2. Backend Security & Hardening
**Goal:** Protect the API from abuse and malformed inputs.
- [ ] **Rate Limiting:**
    - Install `slowapi`.
    - Integrate `Limiter` into `sse_server.py`.
    - Apply basic limits (e.g., 100/minute) to API endpoints.
- [ ] **Input Validation:**
    - Update `router.py` to enforce length limits on search queries and identifiers (e.g., max 100 chars) to prevent potential DoS or buffer issues.

## 3. Verification
- [ ] Run backend tests (`pytest`).
- [ ] Run new frontend tests (`npm test`).
