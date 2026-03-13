import { useState } from 'react';
import { useLiveQuery } from 'dexie-react-hooks';
import { db } from '../../db/database';
import { 
  Search, 
  Download, 
  Upload, 
  Table as TableIcon,
  Filter
} from 'lucide-react';
import { CsvImporter } from './CsvImporter';
import { exportTableToCsv } from '../../lib/csvImport';

const categories = [
  {
    name: 'LEADS & AGENTS',
    tables: [
      { id: 'travel_agents', name: 'Travel Agents', count: 330 },
      { id: 'wedding_event_planners', name: 'Wedding Event Planners', count: 22 },
      { id: 'maharashtra_tourism_govt', name: 'Maharashtra Tourism Govt', count: 17 },
    ]
  },
  {
    name: 'NASHIK ECOSYSTEM',
    tables: [
      { id: 'nashik_tourism_db', name: 'Nashik Tourism Database', count: 31 },
      { id: 'property_listings', name: 'Property Listings', count: 22 },
      { id: 'coworking_startups', name: 'Coworking Startups', count: 22 },
      { id: 'photo_video_drone', name: 'Photo Video Drone', count: 22 },
      { id: 'real_estate_developers', name: 'Real Estate Developers', count: 17 },
    ]
  },
  {
    name: 'INFLUENCERS & MEDIA',
    tables: [
      { id: 'travel_influencers', name: 'Travel Influencers', count: 22 },
      { id: 'nashik_content_creators', name: 'Nashik Content Creators', count: 22 },
      { id: 'family_mom_influencers', name: 'Family Mom Influencers', count: 22 },
      { id: 'travel_pr_journalists', name: 'Travel PR Journalists', count: 22 },
    ]
  }
];

export const TableBrowser = () => {
  const [selectedTable, setSelectedTable] = useState<string>('travel_agents');
  const [isImporterOpen, setIsImporterOpen] = useState(false);

  // Dynamic table data fetching
  const tableData = useLiveQuery(
    async () => {
      if (!selectedTable) return [];
      const table = (db as any)[selectedTable];
      if (!table) return [];
      return table.toArray();
    },
    [selectedTable]
  ) || [];

  const columns = tableData.length > 0 ? Object.keys(tableData[0]).filter(k => k !== 'id') : [];

  return (
    <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
      {/* Sidebar - Table Navigation */}
      <div className="lg:col-span-1 border-r border-white/5 space-y-6">
        {categories.map((cat) => (
          <div key={cat.name}>
            <h4 className="text-[10px] font-bold text-text-secondary uppercase tracking-widest mb-2 px-2">
              {cat.name}
            </h4>
            <div className="space-y-1">
              {cat.tables.map((table) => (
                <button
                  key={table.id}
                  onClick={() => setSelectedTable(table.id)}
                  className={`w-full flex items-center justify-between px-3 py-2 text-xs rounded-md transition-all ${
                    selectedTable === table.id 
                      ? 'bg-primary/10 text-primary border border-primary/20' 
                      : 'text-text-secondary hover:bg-white/5 hover:text-text-primary'
                  }`}
                >
                  <div className="flex items-center space-x-2">
                    <TableIcon size={14} />
                    <span>{table.name}</span>
                  </div>
                  <span className="text-[10px] opacity-50">({table.count})</span>
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Main Panel - Data Table */}
      <div className="lg:col-span-3 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-xl font-bold flex items-center space-x-2">
              <span className="text-primary capitalize">{selectedTable.replace(/_/g, ' ')}</span>
              <span className="text-sm font-normal text-text-secondary">({tableData.length} records)</span>
            </h3>
          </div>
          <div className="flex space-x-2">
            <button 
              onClick={() => exportTableToCsv(selectedTable)}
              className="flex items-center space-x-2 bg-white/5 border border-white/10 px-3 py-1.5 rounded text-xs hover:bg-white/10 transition-all font-medium"
            >
              <Download size={14} />
              <span>Export</span>
            </button>
            <button 
              onClick={() => setIsImporterOpen(true)}
              className="flex items-center space-x-2 bg-primary/20 text-primary border border-primary/30 px-3 py-1.5 rounded text-xs hover:bg-primary/30 transition-all font-medium"
            >
              <Upload size={14} />
              <span>Import Real CSV</span>
            </button>
          </div>
        </div>

        <div className="flex items-center space-x-3 bg-card border border-white/5 p-2 rounded-lg">
          <div className="flex-1 relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-secondary" />
            <input 
              type="text" 
              placeholder={`Filter ${selectedTable.replace(/_/g, ' ')}...`}
              className="w-full bg-background border border-white/5 rounded pl-9 pr-3 py-1.5 text-xs focus:outline-none focus:border-primary/50"
            />
          </div>
          <button className="p-2 bg-background border border-white/5 rounded hover:bg-white/5">
            <Filter size={14} className="text-text-secondary" />
          </button>
        </div>

        <div className="card p-0 overflow-hidden border border-white/5">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-white/5 text-text-secondary uppercase">
                <tr>
                  {columns.map(col => (
                    <th key={col} className="px-4 py-3 font-medium border-r border-white/5 last:border-0">{col.replace(/_/g, ' ')}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {tableData.length === 0 ? (
                  <tr>
                    <td colSpan={columns.length || 1} className="px-4 py-10 text-center text-text-secondary italic">
                      Empty table. Use the Import tool to seed data from the provided Excel sheets.
                    </td>
                  </tr>
                ) : (
                  tableData.map((row: any, i: number) => (
                    <tr key={i} className="hover:bg-white/[0.02]">
                      {columns.map(col => (
                        <td key={col} className="px-4 py-3 border-r border-white/5 last:border-0">{row[col]}</td>
                      ))}
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <CsvImporter 
        tableName={selectedTable} 
        isOpen={isImporterOpen} 
        onClose={() => setIsImporterOpen(false)}
        onSuccess={() => {
          // Re-triggering query is automatic in Dexie-react-hooks
          console.log('Real data updated');
        }}
      />
    </div>
  );
};
