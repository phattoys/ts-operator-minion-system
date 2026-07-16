import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import axios from 'axios';
import ExecutionManifestIntake from '../ExecutionManifestIntake';

jest.mock('axios');

function renderIntake() {
  return render(
    <MemoryRouter>
      <ExecutionManifestIntake />
    </MemoryRouter>,
  );
}

const validEnvelope = {
  packet_id: 'packet-ui-1',
  source_system: 'tsaf',
  campaign_name: 'UI Test Campaign',
  idempotency_key: 'idem-ui-1',
  manifest: {
    schema_version: '1.0',
    source_system: 'TSAF',
    source_packet_id: 'packet-ui-1',
    execution_items: [
      { item_id: 'item-1', destination: 'wordpress', execution_type: 'content_draft', status: 'pending', copy: 'x' },
      { item_id: 'item-2', destination: 'metricool', execution_type: 'social_post', status: 'pending', copy: 'y' },
    ],
    assets: [],
  },
  asset_index: [{ asset_id: 'asset-1' }],
};

describe('ExecutionManifestIntake', () => {
  afterEach(() => jest.resetAllMocks());

  test('shows a parse-error state for invalid JSON without calling the backend', async () => {
    axios.get.mockResolvedValueOnce({ data: { receipts: [], count: 0 } });
    renderIntake();
    await waitFor(() => expect(screen.getByTestId('receipts-empty-state')).toBeInTheDocument());

    fireEvent.change(screen.getByTestId('intake-json-textarea'), { target: { value: '{not valid json' } });
    expect(screen.getByTestId('intake-parse-error')).toBeInTheDocument();
    expect(screen.getByTestId('intake-submit-btn')).toBeDisabled();
    expect(axios.post).not.toHaveBeenCalled();
  });

  test('shows a live local preview (packet identity, source, campaign, item count, destinations, asset refs) for valid JSON', async () => {
    axios.get.mockResolvedValueOnce({ data: { receipts: [], count: 0 } });
    renderIntake();
    await waitFor(() => expect(screen.getByTestId('receipts-empty-state')).toBeInTheDocument());

    fireEvent.change(screen.getByTestId('intake-json-textarea'), { target: { value: JSON.stringify(validEnvelope) } });
    const preview = screen.getByTestId('intake-preview');
    expect(preview).toHaveTextContent('packet-ui-1');
    expect(preview).toHaveTextContent('tsaf');
    expect(preview).toHaveTextContent('UI Test Campaign');
    expect(preview).toHaveTextContent('2'); // item count
    expect(preview).toHaveTextContent('wordpress');
    expect(preview).toHaveTextContent('metricool');
    expect(preview).toHaveTextContent('1'); // asset ref count
  });

  test('successful intake UI state shows accepted status, receipt ID, manifest ID, and a link to the manifest', async () => {
    axios.get.mockResolvedValueOnce({ data: { receipts: [], count: 0 } });
    axios.post.mockResolvedValueOnce({
      data: { receipt_id: 'rcpt-1', packet_id: 'packet-ui-1', status: 'accepted', manifest_id: 'man-ui-1', errors: [], warnings: [] },
    });
    axios.get.mockResolvedValueOnce({ data: { receipts: [], count: 0 } }); // reload after submit

    renderIntake();
    await waitFor(() => expect(screen.getByTestId('receipts-empty-state')).toBeInTheDocument());

    fireEvent.change(screen.getByTestId('intake-json-textarea'), { target: { value: JSON.stringify(validEnvelope) } });
    fireEvent.click(screen.getByTestId('intake-submit-btn'));

    await waitFor(() => expect(screen.getByTestId('intake-result')).toBeInTheDocument());
    const result = screen.getByTestId('intake-result');
    expect(result).toHaveTextContent('accepted');
    expect(result).toHaveTextContent('rcpt-1');
    expect(result).toHaveTextContent('man-ui-1');
    expect(screen.getByTestId('intake-result-manifest-link')).toBeInTheDocument();

    expect(axios.post).toHaveBeenCalledWith(
      expect.stringContaining('/execution-manifest-intake/manual'),
      { envelope: validEnvelope },
      expect.objectContaining({ withCredentials: true }),
    );
  });

  test('rejected/quarantined intake UI state shows the real errors, not a generic message', async () => {
    axios.get.mockResolvedValueOnce({ data: { receipts: [], count: 0 } });
    axios.post.mockResolvedValueOnce({
      data: {
        receipt_id: 'rcpt-2', packet_id: 'packet-ui-2', status: 'quarantined', manifest_id: null,
        errors: ["packet_checksum mismatch: supplied=abc calculated=def"], warnings: [],
      },
    });
    axios.get.mockResolvedValueOnce({ data: { receipts: [], count: 0 } });

    renderIntake();
    await waitFor(() => expect(screen.getByTestId('receipts-empty-state')).toBeInTheDocument());

    fireEvent.change(screen.getByTestId('intake-json-textarea'), { target: { value: JSON.stringify(validEnvelope) } });
    fireEvent.click(screen.getByTestId('intake-submit-btn'));

    await waitFor(() => expect(screen.getByTestId('intake-result')).toBeInTheDocument());
    const result = screen.getByTestId('intake-result');
    expect(result).toHaveTextContent('quarantined');
    expect(result).toHaveTextContent('packet_checksum mismatch');
    expect(screen.queryByTestId('intake-result-manifest-link')).not.toBeInTheDocument();
  });

  test('receipt list renders with status/source/transport and manifest linkage', async () => {
    axios.get.mockResolvedValueOnce({
      data: {
        receipts: [
          {
            receipt_id: 'rcpt-3', packet_id: 'packet-3', source_system: 'tsaf', transport: 'server_to_server',
            status: 'accepted', authentication_status: 'authenticated', checksum_status: 'match', schema_status: 'valid',
            manifest_id: 'man-3', received_at: '2026-07-16T00:00:00Z', errors: [], warnings: [],
          },
        ],
        count: 1,
      },
    });
    renderIntake();

    await waitFor(() => expect(screen.getByTestId('receipts-list')).toBeInTheDocument());
    const row = screen.getByTestId('receipt-row-rcpt-3');
    expect(row).toHaveTextContent('rcpt-3');
    expect(row).toHaveTextContent('accepted');
    expect(row).toHaveTextContent('man-3');
  });

  test('receipt detail expands to show auth/checksum/schema status and errors/warnings', async () => {
    axios.get.mockResolvedValueOnce({
      data: {
        receipts: [
          {
            receipt_id: 'rcpt-4', packet_id: 'packet-4', source_system: 'tsaf', transport: 'server_to_server',
            status: 'quarantined', authentication_status: 'authenticated', checksum_status: 'mismatch', schema_status: 'not_evaluated',
            manifest_id: null, received_at: '2026-07-16T00:00:00Z',
            errors: ['packet_checksum mismatch'], warnings: [],
          },
        ],
        count: 1,
      },
    });
    renderIntake();
    await waitFor(() => expect(screen.getByTestId('receipt-row-rcpt-4')).toBeInTheDocument());

    fireEvent.click(screen.getByText('rcpt-4'));
    await waitFor(() => expect(screen.getByTestId('receipt-detail-rcpt-4')).toBeInTheDocument());
    const detail = screen.getByTestId('receipt-detail-rcpt-4');
    expect(detail).toHaveTextContent('authenticated');
    expect(detail).toHaveTextContent('mismatch');
    expect(detail).toHaveTextContent('packet_checksum mismatch');
  });

  test('receipt filters narrow the list honestly', async () => {
    axios.get.mockResolvedValueOnce({
      data: {
        receipts: [
          { receipt_id: 'rcpt-a', packet_id: 'p-a', source_system: 'tsaf', transport: 'server_to_server', status: 'accepted', authentication_status: 'authenticated', checksum_status: 'match', schema_status: 'valid', manifest_id: 'man-a', received_at: '2026-07-16T00:00:00Z', errors: [], warnings: [] },
          { receipt_id: 'rcpt-b', packet_id: 'p-b', source_system: 'manual', transport: 'manual', status: 'quarantined', authentication_status: 'founder_session', checksum_status: 'not_supplied', schema_status: 'invalid', manifest_id: null, received_at: '2026-07-16T00:01:00Z', errors: ['bad'], warnings: [] },
        ],
        count: 2,
      },
    });
    renderIntake();
    await waitFor(() => expect(screen.getByTestId('receipts-list')).toBeInTheDocument());

    fireEvent.click(screen.getByTestId('receipt-filter-rejected-only'));
    expect(screen.getByTestId('receipt-row-rcpt-b')).toBeInTheDocument();
    expect(screen.queryByTestId('receipt-row-rcpt-a')).not.toBeInTheDocument();
  });

  test('empty state when no receipts exist at all', async () => {
    axios.get.mockResolvedValueOnce({ data: { receipts: [], count: 0 } });
    renderIntake();
    await waitFor(() => expect(screen.getByTestId('receipts-empty-state')).toBeInTheDocument());
    expect(screen.getByText(/No intake packets have been received yet/)).toBeInTheDocument();
  });
});
