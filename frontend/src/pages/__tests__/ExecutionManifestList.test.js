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

function makeTask(overrides = {}) {
  return {
    task_id: 'task-x', worker: 'jenny', worker_name: 'Jenny', task_type: 'wp_content_draft',
    status: 'completed', auto_execute: true, founder_action_needed: false,
    next_action: 'Draft content update for WordPress page',
    result: {}, warnings: [], created_at: '2026-07-14T00:00:00Z',
    started_at: '2026-07-14T00:00:01Z', completed_at: '2026-07-14T00:00:02Z',
    ...overrides,
  };
}

// Empty-chain trace: item hasn't been queued at all (item.status='ready')
// or was never queueable (unsupported destination, e.g. Metricool) -- both
// cases produce zero worker_tasks, so worker_chain must be [].
function emptyTraceItem(item) {
  return {
    item_id: item.item_id, title: item.title, destination: item.destination,
    execution_type: item.execution_type, item_status: item.status,
    worker_task_id: null, worker: item.recommended_worker || null,
    task_status: null, task_result: {}, task_warnings: [], worker_chain: [],
  };
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

// Full REAL chain: Jenny completed -> Rene completed -> WP Placement
// queued, founder_action_needed=true (this is the exact shape the
// real-browser review found was previously invisible to the trace and
// Founder Action Center).
const gatedQueuedItem = {
  item_id: 'item-3',
  manifest_id: 'man-2',
  title: 'Publish trust page draft',
  destination: 'wordpress',
  execution_type: 'content_draft',
  status: 'queued',
  recommended_worker: 'jenny',
  priority: 'high',
  warnings: [],
  worker_task_id: 'task-jenny',
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

function traceResponseFor(manifest, items) {
  return { data: { manifest_id: manifest.manifest_id, manifest_status: manifest.status, items } };
}

describe('ExecutionManifestList', () => {
  afterEach(() => jest.resetAllMocks());

  test('renders manifest list rows with campaign name, status, and counts', async () => {
    axios.get.mockResolvedValueOnce({ data: { manifests: [manifest1, manifest2], count: 2 } });
    axios.get.mockResolvedValueOnce(traceResponseFor(manifest1, [emptyTraceItem(wpItem), emptyTraceItem(metricoolItem)]));
    axios.get.mockResolvedValueOnce(traceResponseFor(manifest2, [emptyTraceItem(gatedQueuedItem)]));
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

  test('Founder Action Center surfaces the downstream founder-gated WP Placement task, not just the item', async () => {
    axios.get.mockResolvedValueOnce({ data: { manifests: [manifest1, manifest2], count: 2 } });
    axios.get.mockResolvedValueOnce(traceResponseFor(manifest1, [emptyTraceItem(wpItem), emptyTraceItem(metricoolItem)]));
    axios.get.mockResolvedValueOnce(traceResponseFor(manifest2, [{
      item_id: 'item-3', title: gatedQueuedItem.title, destination: 'wordpress', execution_type: 'content_draft',
      item_status: 'queued', worker_task_id: 'task-wp', worker: 'wp_placement', task_status: 'queued',
      task_result: {}, task_warnings: [],
      worker_chain: [
        makeTask({ task_id: 'task-jenny', worker: 'jenny', worker_name: 'Jenny', task_type: 'wp_content_draft', status: 'completed', founder_action_needed: false }),
        makeTask({ task_id: 'task-rene', worker: 'rene', worker_name: 'Rene', task_type: 'wp_content_qa', status: 'completed', founder_action_needed: false }),
        makeTask({ task_id: 'task-wp', worker: 'wp_placement', worker_name: 'WP Placement', task_type: 'wp_page_update', status: 'queued', auto_execute: false, founder_action_needed: true, next_action: 'Update existing WordPress page' }),
      ],
    }]));
    renderList();
    await waitFor(() => expect(screen.getByTestId('manifest-table')).toBeInTheDocument());

    fireEvent.click(screen.getByTestId('view-founder-action-center'));

    await waitFor(() => expect(screen.getByTestId('founder-action-list')).toBeInTheDocument());
    const founderRow = screen.getByTestId('founder-action-item-item-3-wp_placement');
    expect(founderRow).toBeInTheDocument();
    expect(within(founderRow).getAllByText('queued').length).toBeGreaterThan(0);
    expect(within(founderRow).getByText(/WP Placement/)).toBeInTheDocument();
    // The metricool item is blocked (connector unavailable) with an empty
    // worker chain -- it has no founder_action_needed task and must NOT appear.
    expect(screen.queryByTestId(/founder-action-item-item-2/)).not.toBeInTheDocument();
  });

  test('Founder Action Center does not surface a blocked Metricool item merely because it is blocked', async () => {
    // Metricool item explicitly never gets a worker task (unsupported
    // destination) -- confirm an empty worker_chain never produces a
    // founder-action row for it, even though the item itself is "blocked".
    axios.get.mockResolvedValueOnce({ data: { manifests: [manifest1], count: 1 } });
    axios.get.mockResolvedValueOnce(traceResponseFor(manifest1, [emptyTraceItem(wpItem), emptyTraceItem(metricoolItem)]));
    renderList();
    await waitFor(() => expect(screen.getByTestId('manifest-table')).toBeInTheDocument());

    fireEvent.click(screen.getByTestId('view-founder-action-center'));
    await waitFor(() => expect(screen.getByTestId('founder-action-empty-state')).toBeInTheDocument());
    expect(screen.queryByTestId(/founder-action-item-item-2/)).not.toBeInTheDocument();
  });

  test('Founder Action Center shows an honest empty state when nothing needs action', async () => {
    const cleanManifest = { ...manifest1, execution_items: [wpItem] };
    axios.get.mockResolvedValueOnce({ data: { manifests: [cleanManifest], count: 1 } });
    axios.get.mockResolvedValueOnce(traceResponseFor(cleanManifest, [emptyTraceItem(wpItem)]));
    renderList();
    await waitFor(() => expect(screen.getByTestId('manifest-table')).toBeInTheDocument());

    fireEvent.click(screen.getByTestId('view-founder-action-center'));
    await waitFor(() => expect(screen.getByTestId('founder-action-empty-state')).toBeInTheDocument());
  });

  test('filtering by blocked-only hides manifests with no blocked items', async () => {
    const cleanManifest = { ...manifest2, manifest_id: 'man-3', campaign_name: 'Clean Manifest', execution_items: [wpItem] };
    axios.get.mockResolvedValueOnce({ data: { manifests: [manifest1, cleanManifest], count: 2 } });
    axios.get.mockResolvedValueOnce(traceResponseFor(manifest1, [emptyTraceItem(wpItem), emptyTraceItem(metricoolItem)]));
    axios.get.mockResolvedValueOnce(traceResponseFor(cleanManifest, [emptyTraceItem(wpItem)]));
    renderList();
    await waitFor(() => expect(screen.getByTestId('manifest-table')).toBeInTheDocument());

    fireEvent.click(screen.getByTestId('filter-blocked-only'));

    expect(screen.getByTestId('manifest-row-man-1')).toBeInTheDocument();
    expect(screen.queryByTestId('manifest-row-man-3')).not.toBeInTheDocument();
  });
});
