import { useLiveQuery } from 'dexie-react-hooks';
import { db } from '../db/database';
import { Swords, ExternalLink, DollarSign } from 'lucide-react';

export default function Competitors() {
  const competitors = useLiveQuery(() => db.competitors.toArray()) || [];

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-text-primary">Competitor Intelligence</h2>
          <p className="text-sm text-text-secondary">Market positioning and live price monitoring against key rivals.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {competitors.slice(0, 3).map((comp, i) => (
          <div key={i} className="card space-y-4">
            <div className="flex items-start justify-between">
              <div>
                <h3 className="text-lg font-bold">{comp.company_name}</h3>
                <a href={comp.website} className="text-[10px] text-primary hover:underline flex items-center mt-1">
                  {comp.website} <ExternalLink size={10} className="ml-1" />
                </a>
              </div>
              <div className="p-2 bg-white/5 rounded-lg">
                <Swords size={20} className="text-text-secondary" />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4 border-t border-white/5 pt-4">
              <div>
                <div className="text-[10px] text-text-secondary uppercase">Properties</div>
                <div className="text-xl font-bold">{comp.properties_count || '120'}</div>
              </div>
              <div>
                <div className="text-[10px] text-text-secondary uppercase">Price Range</div>
                <div className="text-xl font-bold">{comp.price_range || '₹8k - 25k'}</div>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="card">
        <h3 className="font-semibold mb-6 flex items-center">
          <DollarSign size={18} className="text-primary mr-2" />
          Live Price Monitor
        </h3>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-white/5 text-text-secondary uppercase text-xs">
              <tr>
                <th className="px-6 py-3 font-medium">Platform</th>
                <th className="px-6 py-3 font-medium">Property Name</th>
                <th className="px-6 py-3 font-medium">Price/Night</th>
                <th className="px-6 py-3 font-medium">Availability</th>
                <th className="px-6 py-3 font-medium">Review Score</th>
                <th className="px-6 py-3 font-medium">Diff</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {[
                { platform: 'Booking.com', property: 'StayVista Nashik', price: '₹12,500', availability: '2 rooms', score: '4.5', diff: '+12%' },
                { platform: 'Airbnb', property: 'Zostel Homes', price: '₹6,200', availability: 'Sold Out', score: '4.8', diff: '-5%' },
                { platform: 'VayaVia (Direct)', property: 'Nashik Heritage', price: '₹10,500', availability: 'Available', score: '4.9', diff: '—' },
              ].map((row, i) => (
                <tr key={i} className="hover:bg-white/[0.02] transition-colors">
                  <td className="px-6 py-4">{row.platform}</td>
                  <td className="px-6 py-4 font-bold">{row.property}</td>
                  <td className="px-6 py-4 font-mono">{row.price}</td>
                  <td className="px-6 py-4">
                    <span className={row.availability === 'Sold Out' ? 'text-danger' : 'text-success'}>
                      {row.availability}
                    </span>
                  </td>
                  <td className="px-6 py-4">{row.score}</td>
                  <td className="px-6 py-4 font-bold">
                    <span className={row.diff.startsWith('+') ? 'text-primary' : row.diff.startsWith('-') ? 'text-success' : ''}>
                      {row.diff}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card">
        <h3 className="font-semibold mb-6">Market Share vs. SaffronStays</h3>
        <div className="flex items-center space-x-8">
          <div className="flex-1 space-y-2">
            <div className="flex justify-between text-xs font-bold uppercase">
              <span>VayaVia</span>
              <span>42%</span>
            </div>
            <div className="h-4 bg-white/5 rounded-full overflow-hidden">
              <div className="h-full bg-primary" style={{ width: '42%' }} />
            </div>
          </div>
          <div className="flex-1 space-y-2">
            <div className="flex justify-between text-xs font-bold uppercase text-text-secondary">
              <span>SaffronStays</span>
              <span>35%</span>
            </div>
            <div className="h-4 bg-white/5 rounded-full overflow-hidden">
              <div className="h-full bg-white/20" style={{ width: '35%' }} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
