import React, { useState, useEffect, Suspense, lazy } from 'react';
import { CampusDetail, DistrictSummary } from './types';
import { Button } from '@openai/apps-sdk-ui/components/Button';
import { ArrowLeft, SearchX, Loader2, BarChart3 } from 'lucide-react';
import { ErrorBanner } from './components/ErrorBanner';
import { ResultSkeleton, DetailSkeleton } from './components/Skeleton';
import { CompareProvider, useCompare } from './context/CompareContext';
import { CompareTray } from './components/CompareTray';
import { CompareButton } from './components/CompareButton';
import { VirtualizedList } from './components/VirtualizedList';
import { useDebouncedCallback } from './hooks/useDebouncedCallback';
import { api } from './services/api';

const SearchTool = lazy(() => import('./SearchTool').then(module => ({ default: module.SearchTool })));
const CampusView = lazy(() => import('./CampusView').then(module => ({ default: module.CampusView })));
const DistrictView = lazy(() => import('./DistrictView').then(module => ({ default: module.DistrictView })));
const CompareView = lazy(() => import('./CompareView').then(module => ({ default: module.CompareView })));
const StaffingDashboard = lazy(() => import('./StaffingDashboard').then(module => ({ default: module.StaffingDashboard })));

type ViewState = 
  | { type: 'home' }
  | { type: 'search_results'; results: any[] }
  | { type: 'campus_detail'; data: CampusDetail }
  | { type: 'district_detail'; data: DistrictSummary }
  | { type: 'compare_view'; ids: string[] }
  | { type: 'staffing_dashboard' }
  | { type: 'loading_detail' };

function AppContent() {
  const [view, setView] = useState<ViewState>({ type: 'home' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { items } = useCompare();

  // Deep linking support
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const campusId = params.get('campus_id');
    const districtId = params.get('district_id');

    if (campusId) {
        loadCampus(campusId);
    } else if (districtId) {
        loadDistrict(districtId);
    }
  }, []);

  const handleSearchImmediate = async (
    query: string,
    status: string,
    rating: string,
    grade_level: string
  ) => {
    setLoading(true);
    setError(null);
    try {
      const result = await api.searchCampuses(query, status, rating, grade_level);
      setView({ type: 'search_results', results: result.results });
    } catch (e: any) {
      console.error(e);
      setError(e.message || "An error occurred while searching.");
    } finally {
      setLoading(false);
    }
  };

  const { debounced: handleSearch } = useDebouncedCallback(handleSearchImmediate, 300);

  const loadCampus = async (id: string) => {
    setLoading(true);
    setView({ type: 'loading_detail' }); // Clear previous state to free memory
    setError(null);
    try {
      const data = await api.getCampusDetail(id);
      setView({ type: 'campus_detail', data });
    } catch (e: any) {
      console.error(e);
      setError(e.message || "Failed to load campus details.");
      setView({ type: 'home' }); // Fallback
    } finally {
      setLoading(false);
    }
  };

  const loadDistrict = async (id: string) => {
    setLoading(true);
    setView({ type: 'loading_detail' }); // Clear previous state to free memory
    setError(null);
    try {
      const data = await api.getDistrictDetail(id);
      setView({ type: 'district_detail', data });
    } catch (e: any) {
      console.error(e);
      setError(e.message || "Failed to load district details.");
      setView({ type: 'home' }); // Fallback
    } finally {
      setLoading(false);
    }
  };
  
  const handleCompare = () => {
      if (items.length < 2) return;
      setView({ type: 'compare_view', ids: items.map(i => i.id) });
  };

  const renderContent = () => {
    if (loading || view.type === 'loading_detail') {
       if (view.type === 'home' || view.type === 'search_results') {
         return <ResultSkeleton />;
       }
       return <DetailSkeleton />;
    }

    if (view.type === 'home') {
         return (
         <Suspense fallback={<ResultSkeleton />}>
             <div className="max-w-2xl mx-auto mt-10">
               <h1 className="text-3xl font-bold text-center mb-8">Texas Education Data</h1>
               <SearchTool onSearch={handleSearch} isLoading={loading} />
               <div className="mt-6 flex justify-center">
                 <Button variant="primary" onClick={() => setView({ type: 'staffing_dashboard' })}>
                   <BarChart3 className="w-4 h-4 mr-2" />
                   Staffing Analysis Dashboard
                 </Button>
               </div>
               <div className="mt-8">
                  {loading && <ResultSkeleton />}
               </div>
             </div>
         </Suspense>
       );
    }

    if (view.type === 'compare_view') {
        return (
            <Suspense fallback={<div className="flex justify-center p-10"><Loader2 className="animate-spin" /></div>}>
                <CompareView ids={view.ids} />
            </Suspense>
        );
    }

    if (view.type === 'staffing_dashboard') {
        return (
            <Suspense fallback={<div className="flex justify-center p-10"><Loader2 className="animate-spin" /></div>}>
                <StaffingDashboard />
            </Suspense>
        );
    }

    if (view.type === 'search_results') {
      if (view.results.length === 0) {
        return (
          <div className="text-center py-12 bg-gray-50 rounded-lg border border-dashed border-gray-300">
            <SearchX className="mx-auto h-12 w-12 text-gray-400" />
            <h3 className="mt-2 text-sm font-semibold text-gray-900">No results found</h3>
            <p className="mt-1 text-sm text-gray-500">Try adjusting your search terms or filters.</p>
          </div>
        );
      }
      return (
        <div className="space-y-4">
          <h2 className="text-xl font-bold">Results ({view.results.length})</h2>
          <VirtualizedList
            items={view.results}
            itemHeight={84}
            maxHeight={560}
            className="w-full"
            itemKey={(item: any) => item.campus_number || item.district_number || item.name}
            renderItem={(item: any) => (
              <div
                onClick={() =>
                  item.campus_number
                    ? loadCampus(item.campus_number)
                    : loadDistrict(item.district_number)
                }
                className="p-4 border rounded cursor-pointer hover:bg-gray-50 transition-colors flex justify-between items-center group"
              >
                <div>
                  <div className="font-bold">{item.name}</div>
                  <div className="text-sm text-gray-600">
                    {item.district_name || 'District'}
                  </div>
                </div>
                {item.campus_number && (
                  <div className="ml-2">
                    <CompareButton id={item.campus_number} name={item.name} />
                  </div>
                )}
              </div>
            )}
          />
        </div>
      );
    }

    if (view.type === 'campus_detail') {
      return (
        <div className="relative">
            <div className="absolute top-0 right-0 flex space-x-2">
                <Button 
                    variant="ghost" 
                    size="sm" 
                    onClick={() => window.print()}
                    className="hidden md:flex print:hidden"
                >
                    Print Report
                </Button>
                <CompareButton id={view.data.campus_number} name={view.data.name} />
            </div>
            <div className="print:p-0">
                <Suspense fallback={<DetailSkeleton />}>
                    <CampusView campus={view.data} />
                </Suspense>
            </div>
        </div>
      );
    }

    if (view.type === 'district_detail') {
      return (
          <Suspense fallback={<DetailSkeleton />}>
              <DistrictView district={view.data} onCampusClick={loadCampus} />
          </Suspense>
      );
    }
  };

  return (
    <div className="min-h-screen bg-white text-gray-900 p-4 pb-24">
      {view.type !== 'home' && (
        <div className="mb-4 print:hidden">
          <Button variant="ghost" onClick={() => setView({ type: 'home' })}>
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Search
          </Button>
        </div>
      )}

      <ErrorBanner message={error} onDismiss={() => setError(null)} />

      {view.type === 'home' ? (
        renderContent()
      ) : (
        renderContent()
      )}
      
      <div className="print:hidden">
        <CompareTray onCompare={handleCompare} />
      </div>
    </div>
  );
}

function App() {
    return (
        <CompareProvider>
            <AppContent />
        </CompareProvider>
    )
}

export default App;
