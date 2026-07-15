import React from 'react';
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import axios from 'axios';
import ExecutionManifestDetail from '../ExecutionManifestDetail';

jest.mock('axios');

function renderDetail(manifestId = 'man-1') {
  return render(
    <MemoryRouter initialEntries={[`/execution-manifests/${manifestId}`]}>
      <Routes>
        <Route path="/execution-manifests/:manifestId" element={<ExecutionManifestDetail />} />
      </Routes>
    </MemoryRouter>,
  );
}

const wpReadyItem = {
  item_id: 'item-1',
  manifest_id: 'man-1',
  title: 'Update trust page',
  description: 'Add a verification section',
  destination: 'wordpress',
  execution_type: 'content_draft',
  status: 'ready',
  recommended_worker: 'jenny',
  priority: 'normal',
  copy: 'Final ready-to-place copy.',
  placement: { page_id: 'page-1', wp_page_id: '354951' },
  warnings: [],
  asset_refs: [],
  dependencies: [],
  qa_requirements: [],
  worker_task_id: null,
};

const metricoolBlockedItem = {
  item_id: 'item-2',
  manifest_id: 'man-1',
  title: 'Schedule Instagram post',
  destination: 'metricool',
  execution_type: 'social_post',
  status: 'blocked',
  recommended_worker: null,
  priority: 'normal',
  warnings: ['connector unavailable: No Metricool execution connector exists in this backend yet. Planned for a future phase.'],
  asset_refs: ['asset-1'],
  dependencies: [],
  qa_requirements: [],
  worker_task_id: null,
};

const dependencyBlockedItem = {
  item_id: 'item-3',
  manifest_id: 'man-1',
  title: 'Follow-up post',
  destination: 'wordpress',
  execution_type: 'content_draft',
  status: 'needs_review',
  recommended_worker: null,
  priority: 'normal',
  warnings: ["dependency 'item-does-not-exist' does not reference a valid item_id in this manifest"],
  asset_refs: [],
  dependencies: ['item-does-not-exist'],
  qa_requirements: [],
  worker_task_id: null,
};

const queuedItem = {
  item_id: 'item-4',
  manifest_id: 'man-1',
  title: 'Already queued item',
  destination: 'wordpress',
  execution_type: 'content_draft',
  status: 'queued',
  recommended_worker: 'jenny',
  priority: 'normal',
  warnings: [],
  asset_refs: [],
  dependencies: [],
  qa_requirements: [],
  worker_task_id: 'task-existing-123',
};

function baseManifest(overrides = {}) {
  return {
    manifest_id: 'man-1',
    campaign_name: 'Confidence Content Batch 01',
    source_system: 'TSAF',
    source_packet_id: 'packet-abc-123',
    status: 'validated',
    priority: 'normal',
    due_at: null,
    notes: null,
    assets: [{ asset_id: 'asset-1', type: 'image', url: 'https://example.test/a.jpg' }],
    metadata: {},
    execution_items: [wpReadyItem, metricoolBlockedItem],
    ...overrides,
  };
}

describe('ExecutionManifestDetail', () => {
  afterEach(() => jest.clearAllMocks());

  test('renders manifest detail header fields', async () => {
    axios.get.mockResolvedValueOnce({ data: baseManifest() });
    renderDetail();

    await waitFor(() => expect(screen.getByTestId('execution-manifest-detail')).toBeInTheDocument());
    expect(screen.getByText('Confidence Content Batch 01')).toBeInTheDocument();
    expect(screen.getByText(/packet-abc-123/)).toBeInTheDocument();
    expect(screen.getByText(/man-1/)).toBeInTheDocument();
  });

  test('shows SUPPORTED NOW badge for the ready WordPress item and a Queue Item button', async () => {
    axios.get.mockResolvedValueOnce({ data: baseManifest() });
    renderDetail();

    await waitFor(() => expect(screen.getByTestId('support-badge-item-1')).toBeInTheDocument());
    expect(screen.getByTestId('support-badge-item-1')).toHaveTextContent('SUPPORTED NOW');
    expect(screen.getByTestId('queue-item-btn-item-1')).toBeInTheDocument();
  });

  test('shows CONNECTOR UNAVAILABLE / FUTURE CONNECTOR PLANNED badge for Metricool and never a queue button', async () => {
    axios.get.mockResolvedValueOnce({ data: baseManifest() });
    renderDetail();

    await waitFor(() => expect(screen.getByTestId('support-badge-item-2')).toBeInTheDocument());
    const badge = screen.getByTestId('support-badge-item-2');
    expect(badge.textContent).toMatch(/CONNECTOR UNAVAILABLE|FUTURE CONNECTOR PLANNED/);
    expect(screen.queryByTestId('queue-item-btn-item-2')).not.toBeInTheDocument();
    expect(screen.getByTestId('cannot-queue-item-2')).toBeInTheDocument();
    expect(screen.getByTestId('item-reason-item-2')).toHaveTextContent(/connector unavailable/i);
  });

  test('blocked-dependency item shows needs_review status and the dependency warning honestly', async () => {
    axios.get.mockResolvedValueOnce({
      data: baseManifest({ execution_items: [dependencyBlockedItem], status: 'needs_review' }),
    });
    renderDetail();

    await waitFor(() => expect(screen.getByTestId('execution-item-item-3')).toBeInTheDocument());
    expect(screen.getByTestId('item-reason-item-3')).toHaveTextContent(/does not reference a valid item_id/i);
    expect(screen.queryByTestId('queue-item-btn-item-3')).not.toBeInTheDocument();
  });

  test('clicking Validate shows real validation errors from the backend (failed validation state)', async () => {
    axios.get.mockResolvedValueOnce({ data: baseManifest() });
    axios.post.mockResolvedValueOnce({
      data: { manifest_id: 'man-1', status: 'needs_review', errors: ["circular dependency detected: a -> b -> a"], execution_items: [] },
    });
    axios.get.mockResolvedValueOnce({ data: baseManifest({ status: 'needs_review' }) }); // reload after validate

    renderDetail();
    await waitFor(() => expect(screen.getByTestId('validate-manifest-btn')).toBeInTheDocument());
    fireEvent.click(screen.getByTestId('validate-manifest-btn'));

    await waitFor(() => expect(screen.getByTestId('manifest-action-message')).toHaveTextContent(/circular dependency detected/));
  });

  test('queueing a ready item calls the existing Phase 1 endpoint and reports the result honestly', async () => {
    axios.get.mockResolvedValueOnce({ data: baseManifest() });
    axios.post.mockResolvedValueOnce({
      data: { item_id: 'item-1', queued: true, worker_task_id: 'task-xyz', worker: 'jenny', task_type: 'wp_content_draft', task_status: 'completed' },
    });
    axios.get.mockResolvedValueOnce({ data: baseManifest() }); // reload after queue

    renderDetail();
    await waitFor(() => expect(screen.getByTestId('queue-item-btn-item-1')).toBeInTheDocument());
    fireEvent.click(screen.getByTestId('queue-item-btn-item-1'));

    await waitFor(() => expect(axios.post).toHaveBeenCalledWith(
      expect.stringContaining('/execution-manifests/man-1/items/item-1/queue'),
      {},
      expect.objectContaining({ withCredentials: true }),
    ));
    await waitFor(() => expect(screen.getByTestId('manifest-action-message')).toHaveTextContent(/queued as a jenny task/i));
  });

  test('duplicate queue response is displayed honestly, not as a fresh success', async () => {
    axios.get.mockResolvedValueOnce({ data: baseManifest() });
    axios.post.mockResolvedValueOnce({
      data: { item_id: 'item-1', queued: false, already_queued: true, worker_task_id: 'task-xyz', reason: 'item already has a worker task; not creating a duplicate' },
    });
    axios.get.mockResolvedValueOnce({ data: baseManifest() });

    renderDetail();
    await waitFor(() => expect(screen.getByTestId('queue-item-btn-item-1')).toBeInTheDocument());
    fireEvent.click(screen.getByTestId('queue-item-btn-item-1'));

    await waitFor(() => expect(screen.getByTestId('manifest-action-message')).toHaveTextContent(/already queued/i));
  });

  test('Queue All Ready Items summarizes results and is disabled when there are zero ready items', async () => {
    const noReadyManifest = baseManifest({ execution_items: [metricoolBlockedItem] });
    axios.get.mockResolvedValueOnce({ data: noReadyManifest });
    renderDetail();

    await waitFor(() => expect(screen.getByTestId('queue-all-ready-btn')).toBeInTheDocument());
    expect(screen.getByTestId('queue-all-ready-btn')).toBeDisabled();
  });

  test('Queue All Ready Items queues ready items via the manifest-level endpoint', async () => {
    axios.get.mockResolvedValueOnce({ data: baseManifest() });
    axios.post.mockResolvedValueOnce({
      data: { manifest_id: 'man-1', items: [{ item_id: 'item-1', queued: true, worker_task_id: 'task-xyz' }] },
    });
    axios.get.mockResolvedValueOnce({ data: baseManifest() });

    renderDetail();
    await waitFor(() => expect(screen.getByTestId('queue-all-ready-btn')).toBeInTheDocument());
    fireEvent.click(screen.getByTestId('queue-all-ready-btn'));

    await waitFor(() => expect(axios.post).toHaveBeenCalledWith(
      expect.stringContaining('/execution-manifests/man-1/queue'),
      {},
      expect.objectContaining({ withCredentials: true }),
    ));
    await waitFor(() => expect(screen.getByTestId('manifest-action-message')).toHaveTextContent(/Queued 1 item/));
  });

  test('trace view shows manifest -> item -> worker task -> status chain when queued', async () => {
    axios.get.mockResolvedValueOnce({ data: baseManifest({ execution_items: [queuedItem] }) });
    axios.get.mockResolvedValueOnce({
      data: {
        manifest_id: 'man-1',
        items: [{
          item_id: 'item-4', title: 'Already queued item', destination: 'wordpress', execution_type: 'content_draft',
          item_status: 'queued', worker_task_id: 'task-existing-123', worker: 'jenny', task_status: 'completed',
          task_result: { success: true }, task_warnings: [],
        }],
      },
    });

    renderDetail();
    await waitFor(() => expect(screen.getByTestId('execution-item-item-4')).toBeInTheDocument());
    fireEvent.click(screen.getByText('Already queued item'));

    await waitFor(() => expect(screen.getByTestId('trace-item-4')).toBeInTheDocument(), { timeout: 5000 });
    const trace = screen.getByTestId('trace-item-4');
    expect(within(trace).getByText(/task-exi/)).toBeInTheDocument();
  });

  test('trace view is honest about items that are not yet queued (no worker task)', async () => {
    axios.get.mockResolvedValueOnce({ data: baseManifest() });
    renderDetail();
    await waitFor(() => expect(screen.getByTestId('execution-item-item-1')).toBeInTheDocument());
    fireEvent.click(screen.getByText('Update trust page'));

    await waitFor(() => expect(screen.getByTestId('trace-item-1')).toBeInTheDocument());
    expect(screen.getByTestId('trace-item-1')).toHaveTextContent(/Not yet queued/i);
  });

  test('asset index displays assets and which items reference them', async () => {
    axios.get.mockResolvedValueOnce({ data: baseManifest() });
    renderDetail();

    await waitFor(() => expect(screen.getByTestId('toggle-asset-index')).toBeInTheDocument());
    fireEvent.click(screen.getByTestId('toggle-asset-index'));

    await waitFor(() => expect(screen.getByTestId('asset-asset-1')).toBeInTheDocument());
    const assetCard = screen.getByTestId('asset-asset-1');
    expect(within(assetCard).getByText(/item-2/)).toBeInTheDocument(); // metricool item references asset-1
  });

  test('shows a clear error state for a manifest that does not exist, not a blank page', async () => {
    const err = new Error('Not Found');
    err.response = { status: 404 };
    axios.get.mockRejectedValueOnce(err);
    renderDetail('does-not-exist');

    await waitFor(() => expect(screen.getByTestId('manifest-detail-error')).toBeInTheDocument());
    expect(screen.getByTestId('manifest-detail-error')).toHaveTextContent(/not found/i);
  });
});
