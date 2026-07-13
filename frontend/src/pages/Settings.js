import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Save, RefreshCw, AlertTriangle, Check } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function Settings() {
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/settings`, { withCredentials: true });
      setSettings(res.data);
    } catch (err) {
      setError('Failed to load settings');
    }
    setLoading(false);
  };

  const saveSettings = async () => {
    setSaving(true);
    setError('');
    setSuccess('');
    try {
      const res = await axios.put(`${API}/settings`, {
        scoring_threshold_strong: settings.scoring_threshold_strong,
        scoring_threshold_usable: settings.scoring_threshold_usable,
        default_tone: settings.default_tone,
        default_cta: settings.default_cta
      }, { withCredentials: true });
      setSettings(res.data);
      setSuccess('Settings saved successfully');
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError('Failed to save settings');
    }
    setSaving(false);
  };

  if (loading) {
    return (
      <div className="p-6 md:p-8">
        <div className="animate-pulse space-y-6">
          <div className="h-8 bg-zinc-800 w-48"></div>
          <div className="h-64 bg-zinc-800"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 md:p-8 max-w-3xl">
      {/* Header */}
      <div className="mb-8">
        <h1 className="font-['Outfit'] text-4xl font-light tracking-tight text-white" data-testid="settings-title">
          Settings
        </h1>
        <p className="text-zinc-500 text-sm mt-1">Configure operator preferences</p>
      </div>

      {/* Messages */}
      {error && (
        <div className="mb-6 p-4 border border-[#FF3B30]/30 bg-[#FF3B30]/10 text-[#FF3B30] text-sm flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          {error}
        </div>
      )}
      {success && (
        <div className="mb-6 p-4 border border-[#34C759]/30 bg-[#34C759]/10 text-[#34C759] text-sm flex items-center gap-2">
          <Check className="w-4 h-4" />
          {success}
        </div>
      )}

      {/* Quality Scoring Thresholds */}
      <div className="border border-zinc-800 mb-6">
        <div className="p-4 border-b border-zinc-800">
          <h2 className="font-['Outfit'] text-lg font-medium">Quality Scoring</h2>
          <p className="text-zinc-500 text-sm mt-1">Define score thresholds for page classification</p>
        </div>
        <div className="p-4 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="label-uppercase block mb-2">Strong Threshold (Pass)</label>
              <div className="flex items-center gap-3">
                <input
                  type="number"
                  min={0}
                  max={100}
                  value={settings?.scoring_threshold_strong || 85}
                  onChange={(e) => setSettings({ ...settings, scoring_threshold_strong: parseInt(e.target.value) })}
                  className="input-flat w-24"
                  data-testid="input-threshold-strong"
                />
                <span className="text-zinc-500 text-sm">and above = Strong / Ready for Review</span>
              </div>
            </div>
            <div>
              <label className="label-uppercase block mb-2">Usable Threshold</label>
              <div className="flex items-center gap-3">
                <input
                  type="number"
                  min={0}
                  max={100}
                  value={settings?.scoring_threshold_usable || 70}
                  onChange={(e) => setSettings({ ...settings, scoring_threshold_usable: parseInt(e.target.value) })}
                  className="input-flat w-24"
                  data-testid="input-threshold-usable"
                />
                <span className="text-zinc-500 text-sm">and above = Usable / Needs Edits</span>
              </div>
            </div>
          </div>
          <p className="text-xs text-zinc-600">Below usable threshold = Rewrite Recommended</p>
        </div>
      </div>

      {/* Default Generation Settings */}
      <div className="border border-zinc-800 mb-6">
        <div className="p-4 border-b border-zinc-800">
          <h2 className="font-['Outfit'] text-lg font-medium">Generation Defaults</h2>
          <p className="text-zinc-500 text-sm mt-1">Default values for page generation</p>
        </div>
        <div className="p-4 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="label-uppercase block mb-2">Default Tone</label>
              <select
                value={settings?.default_tone || 'professional'}
                onChange={(e) => setSettings({ ...settings, default_tone: e.target.value })}
                className="input-flat w-full"
                data-testid="select-default-tone"
              >
                <option value="professional">Professional</option>
                <option value="friendly">Friendly</option>
                <option value="playful">Playful</option>
                <option value="authoritative">Authoritative</option>
                <option value="casual">Casual</option>
              </select>
            </div>
            <div>
              <label className="label-uppercase block mb-2">Default CTA</label>
              <select
                value={settings?.default_cta || 'Learn More'}
                onChange={(e) => setSettings({ ...settings, default_cta: e.target.value })}
                className="input-flat w-full"
                data-testid="select-default-cta"
              >
                <option value="Learn More">Learn More</option>
                <option value="Shop Now">Shop Now</option>
                <option value="Explore">Explore</option>
                <option value="Sign Up">Sign Up</option>
                <option value="Contact Us">Contact Us</option>
                <option value="Get Started">Get Started</option>
                <option value="Join">Join</option>
                <option value="Read More">Read More</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      {/* Model Configuration (Read Only) */}
      <div className="border border-zinc-800 mb-6">
        <div className="p-4 border-b border-zinc-800">
          <h2 className="font-['Outfit'] text-lg font-medium">Model Configuration</h2>
          <p className="text-zinc-500 text-sm mt-1">Current LLM model assignments (configured in environment)</p>
        </div>
        <div className="p-4 space-y-3">
          <div className="flex justify-between items-center py-2 border-b border-zinc-800">
            <span className="text-zinc-400 text-sm">Page Generation</span>
            <span className="font-mono text-sm text-white" data-testid="model-generation">{settings?.page_generation_model}</span>
          </div>
          <div className="flex justify-between items-center py-2 border-b border-zinc-800">
            <span className="text-zinc-400 text-sm">Quality Scoring</span>
            <span className="font-mono text-sm text-white" data-testid="model-scoring">{settings?.quality_scoring_model}</span>
          </div>
          <div className="flex justify-between items-center py-2">
            <span className="text-zinc-400 text-sm">Rewrite Model</span>
            <span className="font-mono text-sm text-white" data-testid="model-rewrite">{settings?.rewrite_model}</span>
          </div>
        </div>
      </div>

      {/* Save Button */}
      <div className="flex gap-3">
        <button
          onClick={saveSettings}
          disabled={saving}
          className="btn-primary flex items-center gap-2 disabled:opacity-50"
          data-testid="save-settings-btn"
        >
          {saving ? (
            <>
              <RefreshCw className="w-4 h-4 animate-spin" />
              Saving...
            </>
          ) : (
            <>
              <Save className="w-4 h-4" />
              Save Settings
            </>
          )}
        </button>
        <button
          onClick={fetchSettings}
          className="btn-secondary"
          data-testid="reset-settings-btn"
        >
          Reset
        </button>
      </div>
    </div>
  );
}
