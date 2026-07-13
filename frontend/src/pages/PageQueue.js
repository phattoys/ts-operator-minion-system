import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { 
  Search, Filter, Plus, ArrowUpDown, 
  ChevronRight, FileText, RefreshCw 
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function PageQueue() {
  const [pages, setPages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [familyFilter, setFamilyFilter] = useState('');
  const [sortField, setSortField] = useState('priority_score');
  const [sortDir, setSortDir] = useState('desc');
  const [showCreateModal, setShowCreateModal] = useState(false);

  useEffect(() => {
    fetchPages();
  }, [statusFilter, familyFilter]);

  const fetchPages = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (statusFilter) params.append('status', statusFilter);
      if (familyFilter) params.append('family', familyFilter);
      
      const res = await axios.get(`${API}/pages?${params}`, { withCredentials: true });
      setPages(res.data.pages || []);
    } catch (error) {
      console.error('Failed to fetch pages:', error);
    }
    setLoading(false);
  };

  const filteredPages = pages
    .filter(page => 
      page.page_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      page.page_family.toLowerCase().includes(searchTerm.toLowerCase())
    )
    .sort((a, b) => {
      const aVal = a[sortField] || 0;
      const bVal = b[sortField] || 0;
      return sortDir === 'desc' ? bVal - aVal : aVal - bVal;
    });

  const toggleSort = (field) => {
    if (sortField === field) {
      setSortDir(sortDir === 'desc' ? 'asc' : 'desc');
    } else {
      setSortField(field);
      setSortDir('desc');
    }
  };

  const getStatusBadge = (status) => {
    const styles = {
      'Approved': 'border-[#34C759] text-[#34C759] bg-[#34C759]/10',
      'Needs Review': 'border-[#FFCC00] text-[#FFCC00] bg-[#FFCC00]/10',
      'Draft Ready': 'border-[#FFCC00] text-[#FFCC00] bg-[#FFCC00]/10',
      'Needs Rewrite': 'border-[#FF3B30] text-[#FF3B30] bg-[#FF3B30]/10',
      'Planned': 'border-zinc-600 text-zinc-400 bg-zinc-800/50',
      'Deferred': 'border-zinc-600 text-zinc-500 bg-zinc-800/50',
      'Generating': 'border-[#FFCC00] text-[#FFCC00] bg-[#FFCC00]/10'
    };
    return styles[status] || 'border-zinc-600 text-zinc-400';
  };

  const statuses = ['Planned', 'Generating', 'Draft Ready', 'Needs Review', 'Needs Rewrite', 'Approved', 'Deferred'];
  const families = ['Core Hub', 'District', 'Trust', 'Guided Path', 'Category Support', 'FAQ/Support', 'Conversion', 'Media/Asset'];

  return (
    <div className="p-6 md:p-8 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-['Outfit'] text-4xl font-light tracking-tight text-white" data-testid="queue-title">
            Page Queue
          </h1>
          <p className="text-zinc-500 text-sm mt-1">
            {filteredPages.length} pages {statusFilter || familyFilter ? '(filtered)' : ''}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={fetchPages}
            className="p-2 border border-zinc-800 hover:bg-zinc-800 transition-colors duration-150"
            data-testid="refresh-queue-btn"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-2 bg-white text-black px-4 py-2 text-sm font-medium hover:bg-zinc-200 transition-colors duration-150"
            data-testid="create-page-btn"
          >
            <Plus className="w-4 h-4" />
            New Page
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-4">
        <div className="relative flex-1 min-w-[200px] max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search pages..."
            className="w-full bg-transparent border border-zinc-800 text-white pl-10 pr-4 py-2 text-sm focus:border-zinc-500 focus:outline-none"
            data-testid="search-input"
          />
        </div>
        
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="bg-transparent border border-zinc-800 text-zinc-300 px-3 py-2 text-sm focus:border-zinc-500 focus:outline-none"
          data-testid="status-filter"
        >
          <option value="">All Statuses</option>
          {statuses.map(s => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>

        <select
          value={familyFilter}
          onChange={(e) => setFamilyFilter(e.target.value)}
          className="bg-transparent border border-zinc-800 text-zinc-300 px-3 py-2 text-sm focus:border-zinc-500 focus:outline-none"
          data-testid="family-filter"
        >
          <option value="">All Families</option>
          {families.map(f => (
            <option key={f} value={f}>{f}</option>
          ))}
        </select>

        {(statusFilter || familyFilter || searchTerm) && (
          <button
            onClick={() => {
              setStatusFilter('');
              setFamilyFilter('');
              setSearchTerm('');
            }}
            className="text-xs text-zinc-400 hover:text-white"
            data-testid="clear-filters-btn"
          >
            Clear filters
          </button>
        )}
      </div>

      {/* Table */}
      <div className="border border-zinc-800 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-zinc-800">
                <th className="table-dense text-left">Page Name</th>
                <th className="table-dense text-left">Family</th>
                <th className="table-dense text-left">Type</th>
                <th 
                  className="table-dense text-left cursor-pointer hover:text-white"
                  onClick={() => toggleSort('priority_score')}
                  data-testid="sort-priority"
                >
                  <span className="flex items-center gap-1">
                    Priority
                    <ArrowUpDown className="w-3 h-3" />
                  </span>
                </th>
                <th className="table-dense text-left">Status</th>
                <th 
                  className="table-dense text-left cursor-pointer hover:text-white"
                  onClick={() => toggleSort('quality_score')}
                  data-testid="sort-score"
                >
                  <span className="flex items-center gap-1">
                    Score
                    <ArrowUpDown className="w-3 h-3" />
                  </span>
                </th>
                <th className="table-dense text-right">Action</th>
              </tr>
            </thead>
            <tbody data-testid="pages-table-body">
              {loading ? (
                <tr>
                  <td colSpan={7} className="text-center py-12">
                    <div className="animate-pulse text-zinc-500">Loading pages...</div>
                  </td>
                </tr>
              ) : filteredPages.length === 0 ? (
                <tr>
                  <td colSpan={7} className="text-center py-12">
                    <FileText className="w-8 h-8 mx-auto mb-3 text-zinc-600" />
                    <p className="text-zinc-500 text-sm">No pages found</p>
                  </td>
                </tr>
              ) : (
                filteredPages.map((page) => (
                  <tr 
                    key={page.id} 
                    className="border-b border-zinc-800 last:border-b-0 hover:bg-zinc-900 transition-colors"
                    data-testid={`page-row-${page.id}`}
                  >
                    <td className="table-dense">
                      <div className="text-white">{page.page_name}</div>
                      <div className="text-xs text-zinc-500 mt-0.5">{page.district_or_pillar}</div>
                    </td>
                    <td className="table-dense text-zinc-400">{page.page_family}</td>
                    <td className="table-dense text-zinc-400">{page.page_type}</td>
                    <td className="table-dense">
                      <span className="font-mono text-zinc-300">P{page.priority_score}</span>
                    </td>
                    <td className="table-dense">
                      <span className={`badge-flat border ${getStatusBadge(page.status)}`}>
                        {page.status}
                      </span>
                    </td>
                    <td className="table-dense">
                      {page.quality_score ? (
                        <span className={`font-mono ${
                          page.quality_score >= 85 ? 'text-[#34C759]' :
                          page.quality_score >= 70 ? 'text-[#FFCC00]' : 'text-[#FF3B30]'
                        }`}>
                          {page.quality_score}/100
                        </span>
                      ) : (
                        <span className="text-zinc-600">—</span>
                      )}
                    </td>
                    <td className="table-dense text-right">
                      <Link
                        to={`/workspace/${page.id}`}
                        className="inline-flex items-center gap-1 text-zinc-400 hover:text-white transition-colors"
                        data-testid={`open-page-${page.id}`}
                      >
                        Open
                        <ChevronRight className="w-4 h-4" />
                      </Link>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Create Modal */}
      {showCreateModal && (
        <CreatePageModal 
          onClose={() => setShowCreateModal(false)} 
          onCreated={() => {
            setShowCreateModal(false);
            fetchPages();
          }}
        />
      )}
    </div>
  );
}

function CreatePageModal({ onClose, onCreated }) {
  const [formData, setFormData] = useState({
    page_name: '',
    page_family: 'Core Hub',
    page_type: 'Landing',
    district_or_pillar: '',
    audience: '',
    purpose: '',
    CTA_type: 'Learn More',
    notes: ''
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.page_name.trim()) {
      setError('Page name is required');
      return;
    }

    setLoading(true);
    setError('');

    try {
      await axios.post(`${API}/pages`, formData, { withCredentials: true });
      onCreated();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create page');
    }
    setLoading(false);
  };

  const families = ['Core Hub', 'District', 'Trust', 'Guided Path', 'Category Support', 'FAQ/Support', 'Conversion', 'Media/Asset'];
  const types = ['Homepage', 'Landing', 'Collection', 'Service', 'Guide', 'Article', 'FAQ', 'Resource', 'About', 'Contact'];
  const ctas = ['Learn More', 'Shop Now', 'Explore', 'Sign Up', 'Contact Us', 'Get Started', 'Join', 'Read More'];

  return (
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center p-4 z-50">
      <div 
        className="bg-[#09090B] border border-zinc-800 w-full max-w-lg max-h-[90vh] overflow-y-auto"
        data-testid="create-page-modal"
      >
        <div className="p-4 border-b border-zinc-800 flex items-center justify-between">
          <h2 className="font-['Outfit'] text-xl font-medium">Create New Page</h2>
          <button 
            onClick={onClose}
            className="text-zinc-500 hover:text-white"
            data-testid="close-modal-btn"
          >
            ×
          </button>
        </div>
        
        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          <div>
            <label className="label-uppercase block mb-2">Page Name *</label>
            <input
              type="text"
              value={formData.page_name}
              onChange={(e) => setFormData({ ...formData, page_name: e.target.value })}
              className="input-flat w-full"
              placeholder="e.g., Welcome Hub"
              data-testid="input-page-name"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label-uppercase block mb-2">Page Family</label>
              <select
                value={formData.page_family}
                onChange={(e) => setFormData({ ...formData, page_family: e.target.value })}
                className="input-flat w-full"
                data-testid="select-family"
              >
                {families.map(f => <option key={f} value={f}>{f}</option>)}
              </select>
            </div>
            <div>
              <label className="label-uppercase block mb-2">Page Type</label>
              <select
                value={formData.page_type}
                onChange={(e) => setFormData({ ...formData, page_type: e.target.value })}
                className="input-flat w-full"
                data-testid="select-type"
              >
                {types.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
          </div>

          <div>
            <label className="label-uppercase block mb-2">District / Pillar</label>
            <input
              type="text"
              value={formData.district_or_pillar}
              onChange={(e) => setFormData({ ...formData, district_or_pillar: e.target.value })}
              className="input-flat w-full"
              placeholder="e.g., Wellness, Trust, Education"
              data-testid="input-district"
            />
          </div>

          <div>
            <label className="label-uppercase block mb-2">Target Audience</label>
            <input
              type="text"
              value={formData.audience}
              onChange={(e) => setFormData({ ...formData, audience: e.target.value })}
              className="input-flat w-full"
              placeholder="e.g., New visitors, Health-conscious adults"
              data-testid="input-audience"
            />
          </div>

          <div>
            <label className="label-uppercase block mb-2">Purpose</label>
            <input
              type="text"
              value={formData.purpose}
              onChange={(e) => setFormData({ ...formData, purpose: e.target.value })}
              className="input-flat w-full"
              placeholder="e.g., Convert visitors to members"
              data-testid="input-purpose"
            />
          </div>

          <div>
            <label className="label-uppercase block mb-2">CTA Type</label>
            <select
              value={formData.CTA_type}
              onChange={(e) => setFormData({ ...formData, CTA_type: e.target.value })}
              className="input-flat w-full"
              data-testid="select-cta"
            >
              {ctas.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>

          <div>
            <label className="label-uppercase block mb-2">Notes</label>
            <textarea
              value={formData.notes}
              onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
              className="input-flat w-full h-20 resize-none"
              placeholder="Any additional notes..."
              data-testid="input-notes"
            />
          </div>

          {error && (
            <div className="text-[#FF3B30] text-sm p-3 border border-[#FF3B30]/30 bg-[#FF3B30]/10">
              {error}
            </div>
          )}

          <div className="flex gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 btn-secondary"
              data-testid="cancel-create-btn"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 btn-primary disabled:opacity-50"
              data-testid="submit-create-btn"
            >
              {loading ? 'Creating...' : 'Create Page'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
