import { describe, it, expect, vi, beforeEach, afterEach, afterAll, beforeAll } from 'vitest';
import React from 'react';
import { screen, fireEvent } from '@testing-library/react';
import { StatusBadge } from './components/shared/StatusBadge';
import { EmptyState } from './components/shared/EmptyState';
import { ConfirmDialog } from './components/shared/ConfirmDialog';
import { DataTable } from './components/shared/DataTable';
import { renderWithProviders } from './test/utils/renderWithProviders';
import { server } from './test/msw/server';
import { scopeService } from './services/scopes';
import { findingService } from './services/findings';
import { workflowService } from './services/workflows';
import { reportService } from './services/reports';

// Setup MSW Server Lifecycle
beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('Sprint 39 Shared Components Unit Tests', () => {
  it('verifies StatusBadge correctly translates severities and Celery states', () => {
    const { rerender } = renderWithProviders(<StatusBadge value="critical" />);
    expect(screen.getByText('critical')).toBeDefined();

    rerender(<StatusBadge value="completed" />);
    expect(screen.getByText('completed')).toBeDefined();

    rerender(<StatusBadge value="failed" />);
    expect(screen.getByText('failed')).toBeDefined();
  });

  it('renders EmptyState successfully with action buttons', () => {
    const actionMock = <button data-testid="empty-cta">Initialize Scan</button>;
    renderWithProviders(
      <EmptyState
        title="Database Empty"
        description="Launch scanning tasks to aggregate security posture data."
        action={actionMock}
      />
    );

    expect(screen.getByText('Database Empty')).toBeDefined();
    expect(screen.getByText('Launch scanning tasks to aggregate security posture data.')).toBeDefined();
    expect(screen.getByTestId('empty-cta')).toBeDefined();
  });

  it('verifies ConfirmDialog action triggers and keyboard escape bindings', () => {
    const onConfirm = vi.fn();
    const onClose = vi.fn();

    const { rerender } = renderWithProviders(
      <ConfirmDialog
        isOpen={true}
        title="Trigger scanner Execution"
        description="Verify scope borders before starting tasks."
        onConfirm={onConfirm}
        onClose={onClose}
      />
    );

    expect(screen.getByText('Trigger scanner Execution')).toBeDefined();

    // Verify click handlers
    fireEvent.click(screen.getByText('Confirm'));
    expect(onConfirm).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByText('Cancel'));
    expect(onClose).toHaveBeenCalledTimes(1);

    // Verify Escape key trigger
    fireEvent.keyDown(window, { key: 'Escape', code: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(2);

    // Render closed
    rerender(
      <ConfirmDialog
        isOpen={false}
        title="Trigger scanner Execution"
        description="Verify scope borders before starting tasks."
        onConfirm={onConfirm}
        onClose={onClose}
      />
    );
    expect(screen.queryByText('Trigger scanner Execution')).toBeNull();
  });

  it('verifies DataTable rendering, paging and sorting triggers', () => {
    const columns = [
      { key: 'name', label: 'Item Name', sortable: true },
      { key: 'val', label: 'Value' },
    ];
    const data = [
      { id: '1', name: 'Alpha', val: '100' },
      { id: '2', name: 'Beta', val: '200' },
    ];
    const onSort = vi.fn();
    const onPageChange = vi.fn();

    renderWithProviders(
      <DataTable
        columns={columns}
        data={data}
        sortBy="name"
        sortOrder="asc"
        onSort={onSort}
        currentPage={1}
        totalPages={2}
        onPageChange={onPageChange}
      />
    );

    expect(screen.getByText('Alpha')).toBeDefined();
    expect(screen.getByText('Beta')).toBeDefined();

    // Verify sort triggers
    fireEvent.click(screen.getByText('Item Name'));
    expect(onSort).toHaveBeenCalledWith('name');

    // Verify page change click
    const nextButtons = screen.getAllByRole('button');
    fireEvent.click(nextButtons[1]); // Next page button
    expect(onPageChange).toHaveBeenCalledWith(2);
  });
});

describe('Sprint 39 Service Integrations with MSW Mocks', () => {
  it('fetches scope listings correctly', async () => {
    const res = await scopeService.getScopes();
    expect(res.success).toBe(true);
    expect(res.data.length).toBe(1);
    expect(res.data[0].name).toBe('Default Target Scope');
  });

  it('creates scope targets correctly', async () => {
    const res = await scopeService.createScope({
      name: 'Ad-hoc CIDR Scan',
      type: 'cidr',
      definition: { targets: ['10.0.0.0/8'] },
    });
    expect(res.success).toBe(true);
    expect(res.data.name).toBe('Ad-hoc CIDR Scan');
    expect(res.data.type).toBe('cidr');
  });

  it('performs finding triage mutations correctly', async () => {
    const ackRes = await findingService.acknowledgeFinding('finding-123');
    expect(ackRes.success).toBe(true);
    expect(ackRes.data.status).toBe('acknowledged');

    const resRes = await findingService.resolveFinding('finding-123');
    expect(resRes.success).toBe(true);
    expect(resRes.data.status).toBe('resolved');

    const supRes = await findingService.suppressFinding('finding-123');
    expect(supRes.success).toBe(true);
    expect(supRes.data.status).toBe('suppressed');
  });

  it('handles scan run executions and status checks', async () => {
    const runRes = await workflowService.startWorkflow('wf-123', { scope_id: 'scope-123' });
    expect(runRes.success).toBe(true);
    expect(runRes.data.run_id).toBe('run-123');

    const details = await workflowService.getScanRunDetails('run-123');
    expect(details.success).toBe(true);
    expect(details.data.status).toBe('running');
  });

  it('verifies reporting exporter blob responses', async () => {
    const jsonBlob = await reportService.exportExecutiveReportJson();
    expect(jsonBlob).toBeDefined();
    expect(jsonBlob.size).toBeGreaterThan(0);

    const csvBlob = await reportService.exportExecutiveReportCsv();
    expect(csvBlob).toBeDefined();
    expect(csvBlob.size).toBeGreaterThan(0);
  });
});
