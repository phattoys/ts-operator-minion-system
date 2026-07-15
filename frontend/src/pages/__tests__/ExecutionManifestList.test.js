import React from 'react';
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import axios from 'axios';
import ExecutionManifestList from '../ExecutionManifestList';

jest.mock('axios');

function renderList() {
  return render(
    <MemoryRouter>
      <ExecutionManifestList />
    </MemoryRouter>,
  );
}

const wpItem = {
  item_id: 'item-1',
  manifest_id: 'man-1',
  title: 'Update trust page',
  destination: 'wordpress',
  execution_type: 'content_draft',
  status: 'ready',
  recommended_worker: 'jenny',
  priority: 'normal',
  warnings: [],
  asset_refs: [],
};

const metricoolItem = {
  item_id: 'item-2',
  manifest_id: 'man-1',
  title: 'Schedule Instagram post',
  destination: 'metricool',
  execution_type: 'social_post',
  status: 'blocked',
  recommended_worker: null,
  priority: 'normal',
  warnings: ['connector unavailable: No Metricool execution connector exists in this backend yet. Planned for a future phase.'],
  asset_refs: [],
};

const gatedQueuedItem = {
  item_id: 'item-3',
  manifest_id: 'man-2',
  title: 'Publish trust page draft',
  destination: 'wordpress',
  execution_type: 'content_draft',
  status: 'queued',
  recommended_worker: 'wp_placement',
  priority: 'high',
  warnings: [],
  worker_task_id: 'task-abc',
  asset_refs: [],
};

const manifest1 = {
  manifest_id: 'man-1',
  campaign_name: 'Confidence Content Batch 01',
  source_system: 'TSAF',
  status: 'validated',
  priority: 'normal',
  created_at: '2026-07-10T00:00:00Z',
  due_at: '2026-07-20T00:00:00Z',
  execution_items: [wpItem, metricoolItem],
  assets: [],
};

const manifest2 = {
  manifest_id: 'man-2',
  campaign_name: 'Trust Page Refresh',
  source_system: 'TSAF',
  status: 'in_progress',
  priority: 'high',
  created_at: '2026-07-12T00:00:00Z',
  due_at: null,
  execution_items: [gatedQueuedItem],
  assets: [],
};

describe('ExecutionManifestList', () => {
  afterEach(() => jest.clearAllMocks());

  test('renders manifest list rows with campaign name, status, and counts', async () => {
    axios.get.mockResolvedValueOnce({ data: { manifests: [manifest1, manifest2], count: 2 } });
    renderList();

    await waitFor(() => expect(screen.getByTestId('manifest-table')).toBeInTheDocument());
    expect(screen.getByText('Confidence Content Batch 01')).toBeInTheDocument();
    expect(screen.getByText('Trust Page Refresh')).toBeInTheDocument();

    const row1 = screen.getByTestId('manifest-row-man-1');
    expect(within(row1).getByText('validated')).toBeInTheDocument();
  });

  test('shows the honest empty state when there are no manifests at all', async () => {
    axios.get.mockResolvedValueOnce({ data: { manifests: [], count: 0 } });
    renderList();

    await waitFor(() => expect(screen.getByTestId('manifest-empty-state')).toBeInTheDocument());
    expect(screen.getByText(/No execution manifests have been received yet/)).toBeInTheDocument();
  });

  test('shows a network-error state honestly rather than a fake success state', async () => {
    axios.get.mockRejectedValueOnce(new Error('Network Error'));
    renderList();

    await waitFor(() => expect(screen.getByTestId('manifest-list-error')).toBeInTheDocument());
  });

  test('Founder Action Center surfaces founder-gated queued items and needs_review items, honestly', async () => {
    axios.get.mockResolvedValueOnce({ data: { manifests: [manifest1, manifest2], count: 2 } });
    renderList();
    await waitFor(() => expect(screen.getByTestId('manifest-table')).toBeInTheDocument());

    fireEvent.click(screen.getByTestId('view-founder-action-center'));

    await waitFor(() => expect(screen.getByTestId('founder-action-list')).toBeInTheDocument());
    expect(screen.getByTestId('founder-action-item-item-3')).toBeInTheDocument();
    // The metricool item is blocked (connector unavailable), not a founder-action item -- must NOT appear here.
    expect(screen.queryByTestId('founder-action-item-item-2')).not.toBeInTheDocument();
  });

  test('Founder Action Center shows an honest empty state when nothing needs action', async () => {
    const cleanManifest = { ...manifest1, execution_items: [wpItem] };
    axios.get.mockResolvedValueOnce({ data: { manifests: [cleanManifest], count: 1 } });
    renderList();
    await waitFor(() => expect(screen.getByTestId('manifest-table')).toBeInTheDocument());

    fireEvent.click(screen.getByTestId('view-founder-action-center'));
    await waitFor(() => expect(screen.getByTestId('founder-action-empty-state')).toBeInTheDocument());
  });

  test('filtering by blocked-only hides manifests with no blocked items', async () => {
    const cleanManifest = { ...manifest2, manifest_id: 'man-3', campaign_name: 'Clean Manifest', execution_items: [wpItem] };
    axios.get.mockResolvedValueOnce({ data: { manifests: [manifest1, cleanManifest], count: 2 } });
    renderList();
    await waitFor(() => expect(screen.getByTestId('manifest-table')).toBeInTheDocument());

    fireEvent.click(screen.getByTestId('filter-blocked-only'));

    expect(screen.getByTestId('manifest-row-man-1')).toBeInTheDocument();
    expect(screen.queryByTestId('manifest-row-man-3')).not.toBeInTheDocument();
  });
});
