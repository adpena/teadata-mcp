import { SearchTool } from './SearchTool';
import { Button } from '@openai/apps-sdk-ui/components/Button';
import { BarChart3, ArrowRightLeft, MapPin, Building2, ArrowLeftRight, HelpCircle } from 'lucide-react';
import { ResultSkeleton } from './components/Skeleton';

interface LandingPageProps {
  onSearch: (query: string, status: string, rating: string, grade_level: string) => void;
  isLoading: boolean;
  onNavigate: (viewType: 'staffing_dashboard' | 'transfer_insights') => void;
}

const EXAMPLE_QUERIES = [
  {
    category: "Districts & Campuses",
    icon: <Building2 className="w-4 h-4" />,
    queries: [
      "Show me information about Austin ISD.",
      "Tell me about the district Dallas ISD.",
      "Show details for Westlake High School.",
      "What are the demographics for Casis Elementary?"
    ]
  },
  {
    category: "Comparisons & Analysis",
    icon: <ArrowLeftRight className="w-4 h-4" />,
    queries: [
      "Compare Westlake High School and Lake Travis High School.",
      "Compare demographics of Austin High and McCallum High.",
      "Where do students from Kealing Middle School transfer to?",
      "Analyze transfer destinations in Austin ISD."
    ]
  },
  {
    category: "Geographic Search",
    icon: <MapPin className="w-4 h-4" />,
    queries: [
      "Find schools within 5 miles of Westlake High School.",
      "Show me all schools within 3 miles of Austin City Hall.",
      "Which charter schools are located within Austin ISD boundaries?",
      "Map Austin ISD campuses colored by economically disadvantaged percent."
    ]
  }
];

export function LandingPage({ onSearch, isLoading, onNavigate }: LandingPageProps) {
  return (
    <div className="max-w-4xl mx-auto mt-10 space-y-12">
      {/* Hero Section */}
      <div className="text-center space-y-6">
        <div className="space-y-2">
          <h1 className="text-4xl font-bold tracking-tight text-gray-900 sm:text-5xl">
            Texas Education Data
          </h1>
          <p className="text-lg text-gray-600">
            Powered by <a href="https://dataforpubliceducation.com" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">Data for Public Education</a>
          </p>
        </div>

        <div className="max-w-2xl mx-auto">
          <SearchTool onSearch={onSearch} isLoading={isLoading} />
        </div>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
          <Button variant="solid" color="primary" onClick={() => onNavigate('staffing_dashboard')}>
            <BarChart3 className="w-4 h-4 mr-2" />
            Staffing Analysis Dashboard
          </Button>
          <Button variant="ghost" color="primary" onClick={() => onNavigate('transfer_insights')}>
            <ArrowRightLeft className="w-4 h-4 mr-2" />
            Transfer Insights
          </Button>
        </div>
      </div>

      {isLoading && <ResultSkeleton />}

      {/* AI Assistant Section */}
      <div className="bg-gray-50 rounded-xl p-8 border border-gray-100">
        <div className="flex items-center gap-3 mb-6">
          <div className="p-2 bg-blue-100 rounded-lg text-blue-600">
            <HelpCircle className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-xl font-semibold text-gray-900">How to use with AI</h2>
            <p className="text-sm text-gray-500">Works with ChatGPT and Claude</p>
          </div>
        </div>
        
        <p className="text-gray-600 mb-8">
          This application is designed to be used with AI assistants. You can ask natural language questions about Texas education data, and the assistant will query the database to provide answers, visualizations, and insights.
        </p>

        <div className="grid md:grid-cols-3 gap-6">
          {EXAMPLE_QUERIES.map((section, idx) => (
            <div key={idx} className="space-y-4">
              <div className="flex items-center gap-2 text-gray-900 font-medium">
                {section.icon}
                <h3>{section.category}</h3>
              </div>
              <ul className="space-y-3">
                {section.queries.map((q, qIdx) => (
                  <li key={qIdx}>
                    <button 
                      className="text-left text-sm text-gray-600 hover:text-blue-600 hover:bg-blue-50 p-2 rounded-md transition-colors w-full"
                      onClick={() => navigator.clipboard.writeText(q)}
                      title="Click to copy"
                    >
                      "{q}"
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <p className="text-xs text-center text-gray-400 mt-8">
          Click any query to copy it to your clipboard
        </p>
      </div>
    </div>
  );
}
