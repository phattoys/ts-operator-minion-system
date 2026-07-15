/**
 * Execution Manifest API client — Phase 2 workspace.
 *
 * Thin wrappers around the existing, unmodified Phase 1 backend endpoints.
 * No manifest validation, routing, or write-safety logic is duplicated
 * here — every decision (support level, routing, approval requirements)
 * comes from the backend response and is only ever displayed, never
 * recomputed client-side.
 */
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

export async function listManifests(status) {
  const params = status ? { status } : {};
  const res = await axios.get(`${API}/execution-manifests`, { params, withCredentials: true });
  return res.data; // { manifests, count }
}

export async function getManifest(manifestId) {
  const res = await axios.get(`${API}/execution-manifests/${manifestId}`, { withCredentials: true });
  return res.data;
}

export async function validateManifest(manifestId) {
  const res = await axios.post(`${API}/execution-manifests/${manifestId}/validate`, {}, { withCredentials: true });
  return res.data;
}

export async function queueAllReady(manifestId) {
  const res = await axios.post(`${API}/execution-manifests/${manifestId}/queue`, {}, { withCredentials: true });
  return res.data;
}

export async function queueItem(manifestId, itemId) {
  const res = await axios.post(
    `${API}/execution-manifests/${manifestId}/items/${itemId}/queue`,
    {},
    { withCredentials: true },
  );
  return res.data;
}

export async function getTrace(manifestId) {
  const res = await axios.get(`${API}/execution-manifests/${manifestId}/trace`, { withCredentials: true });
  return res.data;
}
