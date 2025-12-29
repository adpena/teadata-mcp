# Plan for Teadata ChatGPT App Improvements

This document tracks the implementation of features to enhance the `teadata-mcp` frontend using rich visualizations and the OpenAI Apps SDK.

## 1. Interactive Geospatial Explorer (Maps)
**Goal:** Visualize district boundaries and campus locations on an interactive map.
- [x] **Install Dependencies**: Add `leaflet`, `react-leaflet`, and `@types/leaflet`.
- [x] **Map Component**: Create a reusable `MapBox` component wrapping `react-leaflet`.
- [x] **District Map**:
    - [x] Update `DistrictView.tsx` to display a map.
    - [x] Render the district polygon using data from `get_entity_geometry`.
    - [x] Plot pins for campuses within the district.
- [x] **Campus Map**:
    - [x] Update `CampusView.tsx` to show the campus location pin.
    - [ ] (Optional) Show nearby schools if data allows.
- [x] **Styling**: Ensure map container handles resizing and fits `apps-sdk-ui` layout.

## 2. Visual Performance Dashboards (Charts)
**Goal:** Use charts to visualize demographics, staffing, and class size data.
- [x] **Install Dependencies**: Add `recharts`.
- [x] **Demographics Chart**:
    - [x] Create `DemographicsChart.tsx` (Pie/Donut) to visualize ethnicity breakdown.
    - [x] Add to `CampusView.tsx`.
- [x] **Class Size Chart**:
    - [x] Create `ClassSizeChart.tsx` (Bar) to visualize class sizes by grade.
    - [x] Add to `CampusView.tsx`.
- [x] **Staffing/Salary Chart**: Covered by Staffing KPI card update.

## 3. "Head-to-Head" Campus Comparator
**Goal:** Allow users to select multiple campuses and compare them side-by-side.
- [x] **State Management**: Add `CompareContext` to manage selected campuses.
- [x] **UI Actions**:
    - [x] Add "Compare" button to `CampusView` and `SearchTool` results.
    - [x] Create a floating `CompareTray` widget.
- [x] **Comparison View**:
    - [x] Create `CompareView.tsx`.
    - [x] Fetch data using `compare_campuses` tool.
    - [x] Render a side-by-side table/grid.

## 4. Deep Linking & Report View ("Canvas" Mode)
**Goal:** Create a polished, printer-friendly "Report" view for districts/campuses.
- [x] **Report Component**: Utilized `CampusView` with print-specific styles (`print:hidden`).
- [x] **Navigation**: Added "Print Report" button.
- [x] **Deep Linking**: Added `useEffect` in `App.tsx` to handle `?campus_id` and `?district_id`.

# Production Readiness Plan

## 1. Frontend Testing
**Goal:** Establish a testing baseline for the React application.
- [x] **Install Dependencies:** `vitest`, `jsdom`, `@testing-library/react`, `@testing-library/jest-dom`, `@testing-library/user-event`.
- [x] **Configure Vitest:** Update `vite.config.ts` to support testing.
- [x] **Create Test Setup:** Add `frontend/src/setupTests.tsx`.
- [x] **Write Tests:** Create `frontend/src/__tests__/App.test.tsx` to verify:
    - App renders without crashing.
    - Search interaction works (mocking the API).
    - Compare tray appears when items are added.

## 2. Backend Security & Hardening
**Goal:** Protect the API from abuse and malformed inputs.
- [x] **Rate Limiting:**
    - Install `slowapi`.
    - Integrate `Limiter` into `sse_server.py`.
    - Apply basic limits (e.g., 100/minute) to API endpoints.
- [x] **Input Validation:**
    - Update `router.py` to enforce length limits on search queries and identifiers (e.g., max 100 chars) to prevent potential DoS or buffer issues.

## 3. Verification
- [x] Run backend tests (`pytest`).
- [x] Run new frontend tests (`npm test`).