import { test, expect } from '@playwright/test';

test.describe('Sprint 39 Platform Portals E2E browser Tests', () => {
  // Stateful mock registers
  let mockScopes = [
    {
      id: 'scope-123',
      name: 'Default Target Scope',
      type: 'domain',
      definition: { targets: ['example.com'] },
      owner_id: 'user-123',
      created_at: '2026-06-20T00:00:00Z',
    },
  ];

  let mockFindingStatus = 'open';

  test.beforeEach(async ({ page }) => {
    // Reset state before each test run
    mockScopes = [
      {
        id: 'scope-123',
        name: 'Default Target Scope',
        type: 'domain',
        definition: { targets: ['example.com'] },
        owner_id: 'user-123',
        created_at: '2026-06-20T00:00:00Z',
      },
    ];
    mockFindingStatus = 'open';

    // Inject mock auth stores in localStorage before navigating to page
    await page.addInitScript(() => {
      window.localStorage.setItem('access_token', 'mock-access-token');
      window.localStorage.setItem('refresh_token', 'mock-refresh-token');
      window.localStorage.setItem('user_profile', JSON.stringify({
        id: 'user-123',
        username: 'analyst_admin',
        display_name: 'System Admin',
        role: 'admin',
      }));
      window.localStorage.setItem('selected_scope_id', 'scope-123');
    });

    // Mock all api routes globally for the test context using exact URL paths
    await page.route('**/api/v1/**', async (route) => {
      const url = route.request().url();
      const method = route.request().method();
      const path = new URL(url).pathname;

      // Scopes list
      if (path === '/api/v1/scopes' && method === 'GET') {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            success: true,
            data: mockScopes,
          }),
        });
      }

      // Create Scope
      if (path === '/api/v1/scopes' && method === 'POST') {
        const body = JSON.parse(route.request().postData() || '{}');
        const newScope = {
          id: `scope-${Date.now()}`,
          name: body.name || 'CIDR External Audit',
          type: body.type || 'cidr',
          definition: body.definition || {},
          owner_id: 'user-123',
          created_at: new Date().toISOString(),
        };
        mockScopes.push(newScope);
        return route.fulfill({
          status: 201,
          contentType: 'application/json',
          body: JSON.stringify({
            success: true,
            data: newScope,
          }),
        });
      }

      // Scope assets list
      if (path.startsWith('/api/v1/scopes/') && path.endsWith('/assets') && method === 'GET') {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            success: true,
            data: [
              {
                id: 'asset-123',
                scope_id: 'scope-123',
                host: 'host.example.com',
                ip: '192.168.1.5',
                asset_type: 'domain',
                metadata_json: { ports: [80, 443] },
                first_seen: '2026-06-20T00:00:00Z',
                last_seen: '2026-06-20T12:00:00Z',
                fingerprint: 'sha256-signature',
              },
            ],
          }),
        });
      }

      // Get Scope Details
      if (path.startsWith('/api/v1/scopes/') && method === 'GET') {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            success: true,
            data: {
              id: 'scope-123',
              name: 'Default Target Scope',
              type: 'domain',
              definition: { targets: ['example.com'] },
              owner_id: 'user-123',
              created_at: '2026-06-20T00:00:00Z',
            },
          }),
        });
      }

      // Workflows list
      if (path === '/api/v1/workflows' && method === 'GET') {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            success: true,
            data: [
              {
                id: 'wf-123',
                name: 'Basic Vulnerability Scan',
                definition: { plugins: ['dnsx', 'nmap', 'nuclei'] },
                state: 'active',
                created_at: '2026-06-20T00:00:00Z',
                updated_at: '2026-06-20T00:00:00Z',
              },
            ],
          }),
        });
      }

      // Start Workflow Run execution
      if (path.startsWith('/api/v1/workflows/') && path.endsWith('/start') && method === 'POST') {
        return route.fulfill({
          status: 202,
          contentType: 'application/json',
          body: JSON.stringify({
            success: true,
            data: {
              workflow_id: 'wf-123',
              run_id: 'run-123',
              status: 'pending',
            },
          }),
        });
      }

      // Workflow events list
      if (path.startsWith('/api/v1/workflows/') && path.endsWith('/events') && method === 'GET') {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            success: true,
            data: [
              {
                id: 'evt-1',
                workflow_id: 'wf-123',
                event_type: 'run_started',
                payload: { message: 'Celery background task launched successfully' },
                timestamp: new Date().toISOString(),
              },
            ],
          }),
        });
      }

      // Scan run details
      if (path.startsWith('/api/v1/scan_runs/') && method === 'GET') {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            success: true,
            data: {
              id: 'run-123',
              workflow_id: 'wf-123',
              scope_id: 'scope-123',
              type: 'on-demand',
              status: 'completed',
              start_ts: '2026-06-20T12:00:00Z',
              end_ts: '2026-06-20T12:05:00Z',
              metrics: { findings_discovered: 1, hosts_scanned: 1 },
              created_at: '2026-06-20T12:00:00Z',
            },
          }),
        });
      }

      // Findings list
      if (path === '/api/v1/findings' && method === 'GET') {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            success: true,
            data: [
              {
                id: 'finding-123',
                asset_id: 'asset-123',
                title: 'Outdated Nginx Version Detection',
                description: 'Nginx server version 1.18.0 detected.',
                severity: 'high',
                status: mockFindingStatus,
                template_id: 'nginx-version-check',
                template_name: 'Nginx Version Scanner',
                source_plugin: 'nuclei',
                first_seen: '2026-06-20T00:00:00Z',
                last_seen: '2026-06-20T12:00:00Z',
                created_at: '2026-06-20T00:00:00Z',
                updated_at: '2026-06-20T12:00:00Z',
                fingerprint: 'nginx-vulnerability-hash',
              },
            ],
          }),
        });
      }

      // Finding evidences list
      if (path.startsWith('/api/v1/findings/') && path.endsWith('/evidence') && method === 'GET') {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            success: true,
            data: [
              {
                id: 'ev-123',
                finding_id: 'finding-123',
                evidence_type: 'http',
                raw_request: 'GET / HTTP/1.1\nHost: example.com',
                raw_response: 'HTTP/1.1 200 OK\nServer: nginx/1.18.0',
                matched_at: 'Server: nginx/1.18.0',
                matcher_name: 'version',
                matcher_value: '1.18.0',
                metadata_json: {},
                evidence_hash: 'hash-value',
                created_at: '2026-06-20T00:00:00Z',
              },
            ],
          }),
        });
      }

      // Finding Acknowledge triage mutation
      if (path.startsWith('/api/v1/findings/') && path.endsWith('/ack') && method === 'POST') {
        mockFindingStatus = 'acknowledged';
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            success: true,
            data: {
              id: 'finding-123',
              asset_id: 'asset-123',
              title: 'Outdated Nginx Version Detection',
              severity: 'high',
              status: mockFindingStatus,
              template_id: 'nginx-version-check',
              template_name: 'Nginx Version Scanner',
              source_plugin: 'nuclei',
              first_seen: '2026-06-20T00:00:00Z',
              last_seen: '2026-06-20T12:00:00Z',
              created_at: '2026-06-20T00:00:00Z',
              updated_at: '2026-06-21T00:00:00Z',
            },
          }),
        });
      }

      // Get Finding Details
      if (path.startsWith('/api/v1/findings/') && method === 'GET') {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            success: true,
            data: {
              id: 'finding-123',
              asset_id: 'asset-123',
              title: 'Outdated Nginx Version Detection',
              description: 'Nginx server version 1.18.0 detected.',
              severity: 'high',
              status: mockFindingStatus,
              template_id: 'nginx-version-check',
              template_name: 'Nginx Version Scanner',
              source_plugin: 'nuclei',
              first_seen: '2026-06-20T00:00:00Z',
              last_seen: '2026-06-20T12:00:00Z',
              created_at: '2026-06-20T00:00:00Z',
              updated_at: '2026-06-20T12:00:00Z',
              fingerprint: 'nginx-vulnerability-hash',
            },
          }),
        });
      }

      // Dashboard summaries and trends
      if (path === '/api/v1/dashboard/summary' && method === 'GET') {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            success: true,
            data: {
              asset_count: 10,
              internet_exposed_assets: 2,
              open_ports: 5,
              services: 4,
              findings: { critical: 0, high: 1, medium: 2, low: 4, info: 1 },
              risk: { critical: 0, high: 1, medium: 1, low: 8 },
            },
          }),
        });
      }

      if (path === '/api/v1/dashboard/trends' && method === 'GET') {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            success: true,
            data: {
              window_days: 30,
              risk_trend: [{ timestamp: '2026-06-20T00:00:00Z', value: 85 }],
              finding_trend: [{ timestamp: '2026-06-20T00:00:00Z', value: 12 }],
              critical_finding_trend: [{ timestamp: '2026-06-20T00:00:00Z', value: 0 }],
            },
          }),
        });
      }

      if (path === '/api/v1/reports/exposure' && method === 'GET') {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            success: true,
            data: {
              external_assets: [],
              internal_assets: [],
              unknown_assets: [],
              internet_exposed_count: 2,
            },
          }),
        });
      }

      if (path === '/api/v1/reports/executive/export/csv' && method === 'GET') {
        return route.fulfill({
          status: 200,
          contentType: 'text/csv',
          headers: {
            'Content-Disposition': 'attachment; filename="executive_report.csv"',
          },
          body: 'id,name,value\n1,ExecutiveReport,100',
        });
      }

      // Default fallback
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, data: {} }),
      });
    });
  });

  test('Onboarding target Scope Loop', async ({ page }) => {
    await page.goto('/scopes');

    // Verify scope details render inside the table specifically (strict check solution)
    await expect(page.locator('tbody').locator('text=Default Target Scope')).toBeVisible();

    // Trigger form onboarding modal
    await page.click('text=Onboard Scope');

    // Fill form (specifying scope select precisely inside modal form)
    await page.fill('input[placeholder="e.g. Corp External Assets"]', 'CIDR External Audit');
    await page.selectOption('form select', 'cidr');
    await page.fill('textarea', JSON.stringify({ targets: ['10.0.0.0/8'] }));

    // Click submit
    await page.click('button[type="submit"]');

    // Verify modal closes and CIDR External Audit is added to table
    await expect(page.locator('tbody').locator('text=CIDR External Audit')).toBeVisible();
  });

  test('Trigger Scan Workflow and track Celery progress log', async ({ page }) => {
    await page.goto('/workflows');

    // Verify workflow definition renders
    await expect(page.locator('text=Basic Vulnerability Scan')).toBeVisible();

    // Trigger run execution ConfirmDialog modal
    await page.click('text=Launch Run');

    // Confirm scan start
    await page.click('text=Execute Run');

    // Verify redirection to tracking details portal
    await page.waitForURL('**/workflows/run-123');

    // Verify ScanRun details display completed status (strict selector check)
    await expect(page.locator('span.rounded-full:has-text("completed")')).toBeVisible();

    // Verify Celery log stream
    await expect(page.locator('text=Celery background task launched successfully')).toBeVisible();
  });

  test('Vulnerability Log filter and Finding detail Triage Decisions', async ({ page }) => {
    await page.goto('/findings');

    // Verify master vulnerability table
    await expect(page.locator('text=Outdated Nginx Version Detection')).toBeVisible();

    // Select Details redirection
    await page.click('a[href="/findings/finding-123"]');
    await page.waitForURL('**/findings/finding-123');

    // Verify triage buttons display and click Acknowledge
    await expect(page.locator('button:has-text("Acknowledge")')).toBeVisible();
    await page.click('button:has-text("Acknowledge")');

    // Confirm that status is updated to acknowledged
    await expect(page.locator('span:has-text("acknowledged")')).toBeVisible();

    // Verify forensic raw request and response details
    await expect(page.locator('text=Server: nginx/1.18.0')).toBeVisible();
  });

  test('Dashboard analytical posture widgets and Reports exports trigger', async ({ page }) => {
    await page.goto('/reports');

    // Verify main analytic posture gauges
    await expect(page.locator('text=Exposed Interfaces')).toBeVisible();
    await expect(page.locator('text=Vulnerability severity Distribution')).toBeVisible();

    // Click Exporter CSV download trigger
    const downloadPromise = page.waitForEvent('download');
    await page.click('text=Export Platform CSV');
    const download = await downloadPromise;

    expect(download.suggestedFilename()).toContain('executive_report_');
    expect(download.suggestedFilename()).toContain('.csv');
  });
});
