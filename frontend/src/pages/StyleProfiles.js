import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  Palette, Crown, ChevronDown, ChevronUp, 
  RefreshCw, Plus, Power, Trash2, Pencil, 
  Check, X, Sparkles
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const TONAL_LABELS = {
  warmth: 'Warmth',
  formality: 'Formality',
  confidence: 'Confidence',
  intimacy: 'Intimacy',
  playfulness: 'Playfulness',
  authority: 'Authority'
};

const FAMILIES = [
  'Core Hub', 'District', 'Trust', 'Guided Path',
  'Category Support', 'Conversion', 'FAQ/Support', 'Media/Asset'
];

function TonalBar({ label, value, color }) {
  return (
    <div className="flex items-center gap-3">
      <span className="text-[10px] text-zinc-500 w-20 text-right">{label}</span>
      <div className="flex-1 h-1.5 bg-zinc-800 relative">
        <div
          className="h-full transition-all duration-300"
          style={{ width: `${value * 10}%`, backgroundColor: color }}
        />
      </div>
      <span className="text-[10px] text-zinc-400 font-mono w-6">{value}</span>
    </div>
  );
}

function TagList({ tags, color = 'zinc' }) {
  if (!tags?.length) return null;
  return (
    <div className="flex flex-wrap gap-1.5">
      {tags.map((tag, i) => (
        <span
          key={i}
          className={`text-[10px] border px-2 py-0.5 ${
            color === 'green'
              ? 'border-[#34C759]/30 text-[#34C759]'
              : color === 'red'
                ? 'border-[#FF3B30]/30 text-[#FF3B30]'
                : 'border-zinc-700 text-zinc-400'
          }`}
        >
          {tag}
        </span>
      ))}
    </div>
  );
}

export default function StyleProfiles() {
  const [profiles, setProfiles] = useState([]);
  const [defaultsByFamily, setDefaultsByFamily] = useState({});
  const [loading, setLoading] = useState(true);
  const [expandedProfile, setExpandedProfile] = useState(null);
  const [filterFamily, setFilterFamily] = useState('');
  const [editingId, setEditingId] = useState(null);
  const [editForm, setEditForm] = useState({});
  const [showCreate, setShowCreate] = useState(false);
  const [createForm, setCreateForm] = useState({
    profile_name: '',
    description: '',
    tonal_controls: { warmth: 5, formality: 5, confidence: 5, intimacy: 5, playfulness: 5, authority: 5 },
    include_language: '',
    avoid_language: '',
    page_families: [],
    is_default: false
  });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchProfiles();
  }, [filterFamily]);

  const fetchProfiles = async () => {
    setLoading(true);
    try {
      const url = filterFamily
        ? `${API}/style-profiles?family=${encodeURIComponent(filterFamily)}`
        : `${API}/style-profiles`;
      const res = await axios.get(url, { withCredentials: true });
      setProfiles(res.data.profiles || []);
      setDefaultsByFamily(res.data.defaults_by_family || {});
    } catch (err) {
      console.error('Failed to fetch profiles:', err);
    }
    setLoading(false);
  };

  const seedProfiles = async () => {
    try {
      await axios.post(`${API}/style-profiles/seed`, {}, { withCredentials: true });
      fetchProfiles();
    } catch (err) {
      console.error('Failed to seed:', err);
    }
  };

  const setDefault = async (profileId) => {
    try {
      await axios.post(`${API}/style-profiles/${profileId}/set-default`, {}, { withCredentials: true });
      fetchProfiles();
    } catch (err) {
      console.error('Failed to set default:', err);
    }
  };

  const toggleStatus = async (profileId) => {
    try {
      await axios.post(`${API}/style-profiles/${profileId}/toggle-status`, {}, { withCredentials: true });
      fetchProfiles();
    } catch (err) {
      console.error('Failed to toggle:', err);
    }
  };

  const deleteProfile = async (profileId) => {
    if (!window.confirm('Delete this style profile?')) return;
    try {
      await axios.delete(`${API}/style-profiles/${profileId}`, { withCredentials: true });
      fetchProfiles();
    } catch (err) {
      console.error('Failed to delete:', err);
    }
  };

  const startEdit = (p) => {
    setEditingId(p.id);
    setEditForm({
      profile_name: p.profile_name,
      description: p.description,
      tonal_controls: { ...p.tonal_controls },
      include_language: (p.include_language || []).join(', '),
      avoid_language: (p.avoid_language || []).join(', '),
      page_families: [...(p.page_families || [])],
    });
  };

  const saveEdit = async () => {
    setSaving(true);
    try {
      await axios.put(`${API}/style-profiles/${editingId}`, {
        ...editForm,
        include_language: editForm.include_language.split(',').map(s => s.trim()).filter(Boolean),
        avoid_language: editForm.avoid_language.split(',').map(s => s.trim()).filter(Boolean),
      }, { withCredentials: true });
      setEditingId(null);
      fetchProfiles();
    } catch (err) {
      console.error('Failed to update:', err);
    }
    setSaving(false);
  };

  const handleCreate = async () => {
    if (!createForm.profile_name.trim()) return;
    setSaving(true);
    try {
      await axios.post(`${API}/style-profiles`, {
        ...createForm,
        include_language: createForm.include_language.split(',').map(s => s.trim()).filter(Boolean),
        avoid_language: createForm.avoid_language.split(',').map(s => s.trim()).filter(Boolean),
      }, { withCredentials: true });
      setShowCreate(false);
      setCreateForm({
        profile_name: '', description: '',
        tonal_controls: { warmth: 5, formality: 5, confidence: 5, intimacy: 5, playfulness: 5, authority: 5 },
        include_language: '', avoid_language: '', page_families: [], is_default: false
      });
      fetchProfiles();
    } catch (err) {
      console.error('Failed to create:', err);
    }
    setSaving(false);
  };

  const toggleFamilyInForm = (fam, form, setForm) => {
    const current = form.page_families || [];
    setForm({
      ...form,
      page_families: current.includes(fam)
        ? current.filter(f => f !== fam)
        : [...current, fam]
    });
  };

  const updateTonalControl = (key, value, form, setForm) => {
    setForm({
      ...form,
      tonal_controls: { ...form.tonal_controls, [key]: parseInt(value) }
    });
  };

  const profileCountByFamily = {};
  profiles.forEach(p => {
    (p.page_families || []).forEach(fam => {
      profileCountByFamily[fam] = (profileCountByFamily[fam] || 0) + 1;
    });
  });

  if (loading) {
    return (
      <div className="p-6 md:p-8">
        <div className="animate-pulse space-y-6">
          <div className="h-8 bg-zinc-800 w-64"></div>
          <div className="h-48 bg-zinc-800"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 md:p-8 space-y-8" data-testid="style-profiles-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-['Outfit'] text-4xl font-light tracking-tight text-white" data-testid="style-profiles-title">
            Style Profiles
          </h1>
          <p className="text-zinc-500 text-sm mt-1">Brand-approved writing modes that shape how pages feel</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowCreate(true)}
            className="p-2 border border-zinc-700 hover:bg-zinc-800 transition-colors"
            data-testid="create-profile-btn"
          >
            <Plus className="w-4 h-4" />
          </button>
          <button
            onClick={fetchProfiles}
            className="p-2 border border-zinc-800 hover:bg-zinc-800 transition-colors"
            data-testid="refresh-profiles-btn"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Family Summary */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {FAMILIES.map(fam => {
          const count = profileCountByFamily[fam] || 0;
          const hasDefault = !!defaultsByFamily[fam];
          return (
            <button
              key={fam}
              onClick={() => setFilterFamily(filterFamily === fam ? '' : fam)}
              className={`p-4 border text-left transition-colors duration-150 ${
                filterFamily === fam
                  ? 'border-white bg-zinc-900'
                  : count > 0
                    ? 'border-zinc-700 hover:border-zinc-500 hover:bg-zinc-900/50'
                    : 'border-zinc-800 opacity-50 hover:opacity-75'
              }`}
              data-testid={`family-filter-${fam.toLowerCase().replace(/[/ ]/g, '-')}`}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="font-mono text-2xl font-semibold text-white">{count}</span>
                {hasDefault && <Sparkles className="w-4 h-4 text-[#AF52DE]" />}
              </div>
              <div className="text-xs text-zinc-500 tracking-[0.1em] uppercase">{fam}</div>
            </button>
          );
        })}
      </div>

      {/* Active Filter */}
      {filterFamily && (
        <div className="flex items-center gap-2">
          <span className="text-xs text-zinc-500">Filtered by:</span>
          <span className="text-xs text-white border border-zinc-700 px-2 py-1">{filterFamily}</span>
          <button onClick={() => setFilterFamily('')} className="text-xs text-zinc-500 hover:text-white" data-testid="clear-filter-btn">
            Clear
          </button>
        </div>
      )}

      {/* Create Form */}
      {showCreate && (
        <div className="border border-[#AF52DE]/30 bg-[#AF52DE]/5 p-6 space-y-4" data-testid="create-profile-form">
          <h2 className="font-['Outfit'] text-lg text-white">New Style Profile</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <span className="label-uppercase block mb-2">Profile Name</span>
              <input value={createForm.profile_name} onChange={(e) => setCreateForm({...createForm, profile_name: e.target.value})} className="input-flat w-full text-sm" placeholder="e.g. Quiet Luxury" data-testid="create-name" />
            </div>
            <div>
              <span className="label-uppercase block mb-2">Description</span>
              <input value={createForm.description} onChange={(e) => setCreateForm({...createForm, description: e.target.value})} className="input-flat w-full text-sm" placeholder="What this profile does..." data-testid="create-description" />
            </div>
          </div>
          <div>
            <span className="label-uppercase block mb-3">Tonal Controls</span>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {Object.entries(TONAL_LABELS).map(([key, label]) => (
                <div key={key} className="flex items-center gap-3">
                  <span className="text-xs text-zinc-500 w-24">{label}</span>
                  <input type="range" min="1" max="10" value={createForm.tonal_controls[key]} onChange={(e) => updateTonalControl(key, e.target.value, createForm, setCreateForm)} className="flex-1 accent-[#AF52DE]" data-testid={`create-tonal-${key}`} />
                  <span className="text-xs text-zinc-400 font-mono w-6">{createForm.tonal_controls[key]}</span>
                </div>
              ))}
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <span className="label-uppercase block mb-2">Include / Emphasize (comma-separated)</span>
              <textarea value={createForm.include_language} onChange={(e) => setCreateForm({...createForm, include_language: e.target.value})} className="input-flat w-full text-xs h-16 resize-none" placeholder="welcome, at your pace, curiosity..." data-testid="create-include" />
            </div>
            <div>
              <span className="label-uppercase block mb-2">Avoid / Reduce (comma-separated)</span>
              <textarea value={createForm.avoid_language} onChange={(e) => setCreateForm({...createForm, avoid_language: e.target.value})} className="input-flat w-full text-xs h-16 resize-none" placeholder="hurry, limited time, act now..." data-testid="create-avoid" />
            </div>
          </div>
          <div>
            <span className="label-uppercase block mb-2">Assign to Families</span>
            <div className="flex flex-wrap gap-2">
              {FAMILIES.map(fam => (
                <button key={fam} onClick={() => toggleFamilyInForm(fam, createForm, setCreateForm)} className={`text-[11px] px-3 py-1 border transition-colors ${createForm.page_families.includes(fam) ? 'border-[#AF52DE] text-[#AF52DE] bg-[#AF52DE]/10' : 'border-zinc-700 text-zinc-400 hover:border-zinc-500'}`} data-testid={`create-family-${fam.toLowerCase().replace(/[/ ]/g, '-')}`}>
                  {fam}
                </button>
              ))}
            </div>
          </div>
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={createForm.is_default} onChange={(e) => setCreateForm({...createForm, is_default: e.target.checked})} className="accent-[#AF52DE]" data-testid="create-default-checkbox" />
            <span className="text-xs text-zinc-400">Set as default for assigned families</span>
          </label>
          <div className="flex items-center gap-2">
            <button onClick={handleCreate} disabled={saving || !createForm.profile_name.trim()} className="text-xs bg-[#AF52DE] text-white px-4 py-1.5 hover:bg-[#AF52DE]/80 transition-colors disabled:opacity-50 flex items-center gap-1.5" data-testid="save-create-btn">
              {saving ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Check className="w-3 h-3" />}
              {saving ? 'Saving...' : 'Create Profile'}
            </button>
            <button onClick={() => setShowCreate(false)} className="text-xs text-zinc-400 border border-zinc-700 px-3 py-1.5 hover:bg-zinc-800 transition-colors" data-testid="cancel-create-btn">
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Profile List */}
      {profiles.length === 0 ? (
        <div className="border border-zinc-800 p-12 text-center">
          <Palette className="w-10 h-10 mx-auto mb-4 text-zinc-600" />
          <h2 className="font-['Outfit'] text-xl text-white mb-2">No Style Profiles</h2>
          <p className="text-zinc-500 text-sm max-w-md mx-auto mb-4">
            Style profiles shape the tonal feel of generated content across page families.
          </p>
          <button onClick={seedProfiles} className="text-xs border border-[#AF52DE] text-[#AF52DE] px-4 py-2 hover:bg-[#AF52DE]/10 transition-colors" data-testid="seed-profiles-btn">
            Seed Default Profiles
          </button>
        </div>
      ) : (
        <div className="space-y-4" data-testid="profile-list">
          {profiles.map((p) => (
            <div key={p.id} className={`border transition-colors duration-150 ${p.status === 'inactive' ? 'border-zinc-800 opacity-60' : 'border-zinc-800 hover:border-zinc-700'}`} data-testid={`profile-item-${p.id}`}>
              {/* Header */}
              <div className="p-4 flex items-center justify-between">
                <div className="flex items-center gap-4 flex-1 min-w-0">
                  <Palette className={`w-5 h-5 ${p.is_default ? 'text-[#AF52DE]' : 'text-zinc-500'}`} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3">
                      <span className="text-white font-['Outfit'] font-medium truncate">{p.profile_name}</span>
                      {p.is_default && (
                        <span className="text-[10px] tracking-[0.15em] uppercase text-[#AF52DE] border border-[#AF52DE]/30 px-2 py-0.5">Default</span>
                      )}
                      {p.status === 'inactive' && (
                        <span className="text-[10px] tracking-[0.15em] uppercase text-zinc-500 border border-zinc-700 px-2 py-0.5">Inactive</span>
                      )}
                    </div>
                    <div className="flex items-center gap-2 mt-1 flex-wrap">
                      {(p.page_families || []).map((fam, i) => (
                        <span key={i} className="text-[10px] text-zinc-500 border border-zinc-800 px-1.5 py-0.5">{fam}</span>
                      ))}
                    </div>
                  </div>
                </div>
                <button onClick={() => setExpandedProfile(expandedProfile === p.id ? null : p.id)} className="p-2 text-zinc-500 hover:text-white transition-colors" data-testid={`toggle-profile-${p.id}`}>
                  {expandedProfile === p.id ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                </button>
              </div>

              {/* Description */}
              {expandedProfile !== p.id && (
                <div className="px-4 pb-3">
                  <p className="text-xs text-zinc-500 italic truncate">{p.description}</p>
                </div>
              )}

              {/* Expanded */}
              {expandedProfile === p.id && (
                <div className="border-t border-zinc-800">
                  {editingId === p.id ? (
                    /* Edit Mode */
                    <div className="p-4 space-y-4">
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                          <span className="label-uppercase block mb-2">Name</span>
                          <input value={editForm.profile_name} onChange={(e) => setEditForm({...editForm, profile_name: e.target.value})} className="input-flat w-full text-sm" data-testid="edit-profile-name" />
                        </div>
                        <div>
                          <span className="label-uppercase block mb-2">Description</span>
                          <input value={editForm.description} onChange={(e) => setEditForm({...editForm, description: e.target.value})} className="input-flat w-full text-sm" data-testid="edit-profile-description" />
                        </div>
                      </div>
                      <div>
                        <span className="label-uppercase block mb-3">Tonal Controls</span>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                          {Object.entries(TONAL_LABELS).map(([key, label]) => (
                            <div key={key} className="flex items-center gap-3">
                              <span className="text-xs text-zinc-500 w-24">{label}</span>
                              <input type="range" min="1" max="10" value={editForm.tonal_controls[key]} onChange={(e) => updateTonalControl(key, e.target.value, editForm, setEditForm)} className="flex-1 accent-[#AF52DE]" data-testid={`edit-tonal-${key}`} />
                              <span className="text-xs text-zinc-400 font-mono w-6">{editForm.tonal_controls[key]}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                          <span className="label-uppercase block mb-2">Include Language</span>
                          <textarea value={editForm.include_language} onChange={(e) => setEditForm({...editForm, include_language: e.target.value})} className="input-flat w-full text-xs h-14 resize-none" data-testid="edit-include" />
                        </div>
                        <div>
                          <span className="label-uppercase block mb-2">Avoid Language</span>
                          <textarea value={editForm.avoid_language} onChange={(e) => setEditForm({...editForm, avoid_language: e.target.value})} className="input-flat w-full text-xs h-14 resize-none" data-testid="edit-avoid" />
                        </div>
                      </div>
                      <div>
                        <span className="label-uppercase block mb-2">Families</span>
                        <div className="flex flex-wrap gap-2">
                          {FAMILIES.map(fam => (
                            <button key={fam} onClick={() => toggleFamilyInForm(fam, editForm, setEditForm)} className={`text-[11px] px-3 py-1 border transition-colors ${editForm.page_families.includes(fam) ? 'border-[#AF52DE] text-[#AF52DE] bg-[#AF52DE]/10' : 'border-zinc-700 text-zinc-400'}`} data-testid={`edit-family-${fam.toLowerCase().replace(/[/ ]/g, '-')}`}>
                              {fam}
                            </button>
                          ))}
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <button onClick={saveEdit} disabled={saving} className="text-xs bg-white text-black px-4 py-1.5 hover:bg-zinc-200 transition-colors flex items-center gap-1.5 disabled:opacity-50" data-testid="save-edit-btn">
                          <Check className="w-3 h-3" />{saving ? 'Saving...' : 'Save'}
                        </button>
                        <button onClick={() => setEditingId(null)} className="text-xs text-zinc-400 border border-zinc-700 px-3 py-1.5 hover:bg-zinc-800 transition-colors" data-testid="cancel-edit-btn">Cancel</button>
                      </div>
                    </div>
                  ) : (
                    /* View Mode */
                    <>
                      <div className="p-4 border-b border-zinc-800">
                        <span className="label-uppercase block mb-2">Description</span>
                        <p className="text-sm text-zinc-300">{p.description}</p>
                      </div>
                      <div className="p-4 border-b border-zinc-800">
                        <span className="label-uppercase block mb-3">Tonal Controls</span>
                        <div className="space-y-2">
                          {Object.entries(TONAL_LABELS).map(([key, label]) => (
                            <TonalBar key={key} label={label} value={p.tonal_controls?.[key] || 5} color="#AF52DE" />
                          ))}
                        </div>
                      </div>
                      {(p.include_language?.length > 0 || p.avoid_language?.length > 0) && (
                        <div className="p-4 border-b border-zinc-800 grid grid-cols-1 md:grid-cols-2 gap-4">
                          {p.include_language?.length > 0 && (
                            <div>
                              <span className="label-uppercase block mb-2">Emphasize</span>
                              <TagList tags={p.include_language} color="green" />
                            </div>
                          )}
                          {p.avoid_language?.length > 0 && (
                            <div>
                              <span className="label-uppercase block mb-2">Avoid</span>
                              <TagList tags={p.avoid_language} color="red" />
                            </div>
                          )}
                        </div>
                      )}
                      <div className="p-4 flex items-center gap-3 flex-wrap">
                        <button onClick={() => startEdit(p)} className="text-xs border border-zinc-700 text-zinc-400 px-3 py-1.5 hover:text-white hover:border-zinc-500 transition-colors flex items-center gap-1.5" data-testid={`edit-profile-${p.id}`}>
                          <Pencil className="w-3 h-3" />Edit
                        </button>
                        {!p.is_default && p.status === 'active' && (
                          <button onClick={() => setDefault(p.id)} className="text-xs border border-[#AF52DE]/30 text-[#AF52DE] px-3 py-1.5 hover:bg-[#AF52DE]/10 transition-colors flex items-center gap-1.5" data-testid={`set-default-${p.id}`}>
                            <Crown className="w-3 h-3" />Set Default
                          </button>
                        )}
                        <button onClick={() => toggleStatus(p.id)} className={`text-xs border px-3 py-1.5 transition-colors flex items-center gap-1.5 ${p.status === 'active' ? 'border-zinc-700 text-zinc-400 hover:border-[#FF3B30] hover:text-[#FF3B30]' : 'border-[#34C759]/30 text-[#34C759] hover:bg-[#34C759]/10'}`} data-testid={`toggle-status-${p.id}`}>
                          <Power className="w-3 h-3" />{p.status === 'active' ? 'Deactivate' : 'Activate'}
                        </button>
                        <button onClick={() => deleteProfile(p.id)} className="text-xs border border-zinc-700 text-zinc-400 px-3 py-1.5 hover:border-[#FF3B30] hover:text-[#FF3B30] transition-colors flex items-center gap-1.5" data-testid={`delete-profile-${p.id}`}>
                          <Trash2 className="w-3 h-3" />Delete
                        </button>
                      </div>
                      <div className="px-4 pb-4 text-[10px] text-zinc-600 font-mono">
                        Created: {new Date(p.created_at).toLocaleDateString()}
                      </div>
                    </>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
