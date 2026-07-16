/**
 * Execution Manifest Intake API client — Phase 3 workspace.
 * Thin wrappers around the existing, unmodified Phase 3 backend
 * endpoints. No schema validation, checksum, HMAC, or idempotency logic
 * is duplicated here — the backend is authoritative for all of it.
 */
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

export async function submitManualIntake(envelope) {
  const res = await axios.post(`${API}/execution-manifest-intake/manual`, { envelope }, { withCredentials: true });
  return res.data;
}

export async function listReceipts(filters = {}) {
  const res = await axios.get(`${API}/execution-manifest-intake/receipts`, { params: filters, withCredentials: true });
  return res.data;
}

export async function getReceipt(receiptId) {
  const res = await axios.get(`${API}/execution-manifest-intake/receipts/${receiptId}`, { withCredentials: true });
  return res.data;
}

export async function retryReceipt(receiptId) {
  const res = await axios.post(`${API}/execution-manifest-intake/receipts/${receiptId}/retry`, {}, { withCredentials: true });
  return res.data;
}
