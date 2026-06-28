import { http, HttpResponse } from 'msw';

export const handlers = [
  // Scopes router
  http.get('/api/v1/scopes', () => {
    return HttpResponse.json({
      success: true,
      data: [
        {
          id: 'scope-123',
          name: 'Default Target Scope',
          type: 'domain',
          definition: { targets: ['example.com'] },
          owner_id: 'user-123',
          created_at: '2026-06-20T00:00:00Z',
        },
      ],
    });
  }),

  http.post('/api/v1/scopes', async ({ request }) => {
    const body = (await request.json()) as any;
    return HttpResponse.json({
      success: true,
      data: {
        id: 'scope-new',
        name: body.name || 'New Scope',
        type: body.type || 'domain',
        definition: body.definition || {},
        owner_id: 'user-123',
        created_at: new Date().toISOString(),
      },
    });
  }),

  http.get('/api/v1/scopes/:id', ({ params }) => {
    return HttpResponse.json({
      success: true,
      data: {
        id: params.id,
        name: 'Detailed Scope',
        type: 'cidr',
        definition: { targets: ['192.168.1.0/24'] },
        owner_id: 'user-123',
        created_at: '2026-06-20T00:00:00Z',
      },
    });
  }),

  http.put('/api/v1/scopes/:id', async ({ params, request }) => {
    const body = (await request.json()) as any;
    return HttpResponse.json({
      success: true,
      data: {
        id: params.id,
        name: body.name || 'Updated Scope',
        type: body.type || 'cidr',
        definition: body.definition || {},
        owner_id: 'user-123',
        created_at: '2026-06-20T00:00:00Z',
      },
    });
  }),

  http.delete('/api/v1/scopes/:id', () => {
    return HttpResponse.json({
      success: true,
      data: true,
    });
  }),

  http.get('/api/v1/scopes/:id/assets', () => {
    return HttpResponse.json({
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
    });
  }),

  // Assets router
  http.get('/api/v1/assets/:id', ({ params }) => {
    return HttpResponse.json({
      success: true,
      data: {
        id: params.id,
        scope_id: 'scope-123',
        host: 'host.example.com',
        ip: '192.168.1.5',
        asset_type: 'domain',
        metadata_json: { server: 'nginx' },
        first_seen: '2026-06-20T00:00:00Z',
        last_seen: '2026-06-20T12:00:00Z',
        fingerprint: 'sha256-signature',
      },
    });
  }),

  http.get('/api/v1/assets/:id/relationships', ({ params }) => {
    return HttpResponse.json({
      success: true,
      data: [
        {
          id: 'rel-123',
          source_asset_id: params.id,
          target_asset_id: 'asset-parent',
          relationship_type: 'dns-cname',
          metadata_json: {},
          created_at: '2026-06-20T00:00:00Z',
        },
      ],
    });
  }),

  http.get('/api/v1/assets/:id/history', ({ params }) => {
    return HttpResponse.json({
      success: true,
      data: [
        {
          id: 'hist-123',
          asset_id: params.id,
          change_type: 'update',
          old_value: { ip: '192.168.1.4' },
          new_value: { ip: '192.168.1.5' },
          timestamp: '2026-06-20T06:00:00Z',
        },
      ],
    });
  }),

  // Findings router
  http.get('/api/v1/findings', () => {
    return HttpResponse.json({
      success: true,
      data: [
        {
          id: 'finding-123',
          asset_id: 'asset-123',
          title: 'Outdated Nginx Version Detection',
          description: 'Nginx server version 1.18.0 detected which has multiple CVSS 7.5 vulnerabilities.',
          severity: 'high',
          status: 'open',
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
    });
  }),

  http.get('/api/v1/findings/:id', ({ params }) => {
    return HttpResponse.json({
      success: true,
      data: {
        id: params.id,
        asset_id: 'asset-123',
        title: 'Outdated Nginx Version Detection',
        description: 'Nginx server version 1.18.0 detected.',
        severity: 'high',
        status: 'open',
        template_id: 'nginx-version-check',
        template_name: 'Nginx Version Scanner',
        source_plugin: 'nuclei',
        first_seen: '2026-06-20T00:00:00Z',
        last_seen: '2026-06-20T12:00:00Z',
        created_at: '2026-06-20T00:00:00Z',
        updated_at: '2026-06-20T12:00:00Z',
        fingerprint: 'nginx-vulnerability-hash',
      },
    });
  }),

  http.post('/api/v1/findings/:id/ack', ({ params }) => {
    return HttpResponse.json({
      success: true,
      data: {
        id: params.id,
        asset_id: 'asset-123',
        title: 'Outdated Nginx Version Detection',
        severity: 'high',
        status: 'acknowledged',
        template_id: 'nginx-version-check',
        template_name: 'Nginx Version Scanner',
        source_plugin: 'nuclei',
        first_seen: '2026-06-20T00:00:00Z',
        last_seen: '2026-06-20T12:00:00Z',
        created_at: '2026-06-20T00:00:00Z',
        updated_at: '2026-06-21T00:00:00Z',
      },
    });
  }),

  http.post('/api/v1/findings/:id/resolve', ({ params }) => {
    return HttpResponse.json({
      success: true,
      data: {
        id: params.id,
        asset_id: 'asset-123',
        title: 'Outdated Nginx Version Detection',
        severity: 'high',
        status: 'resolved',
        template_id: 'nginx-version-check',
        template_name: 'Nginx Version Scanner',
        source_plugin: 'nuclei',
        first_seen: '2026-06-20T00:00:00Z',
        last_seen: '2026-06-20T12:00:00Z',
        created_at: '2026-06-20T00:00:00Z',
        updated_at: '2026-06-21T00:00:00Z',
      },
    });
  }),

  http.post('/api/v1/findings/:id/suppress', ({ params }) => {
    return HttpResponse.json({
      success: true,
      data: {
        id: params.id,
        asset_id: 'asset-123',
        title: 'Outdated Nginx Version Detection',
        severity: 'high',
        status: 'suppressed',
        template_id: 'nginx-version-check',
        template_name: 'Nginx Version Scanner',
        source_plugin: 'nuclei',
        first_seen: '2026-06-20T00:00:00Z',
        last_seen: '2026-06-20T12:00:00Z',
        created_at: '2026-06-20T00:00:00Z',
        updated_at: '2026-06-21T00:00:00Z',
      },
    });
  }),

  http.get('/api/v1/findings/:id/evidence', ({ params }) => {
    return HttpResponse.json({
      success: true,
      data: [
        {
          id: 'ev-123',
          finding_id: params.id,
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
    });
  }),

  // Workflows router
  http.get('/api/v1/workflows', () => {
    return HttpResponse.json({
      success: true,
      data: [
        {
          id: 'wf-123',
          name: 'Basic Vulnerability Scan',
          definition: { plugins: ['dnsx', 'nmap', 'nuclei'] },
          owner_id: 'user-123',
          state: 'active',
          created_at: '2026-06-20T00:00:00Z',
          updated_at: '2026-06-20T00:00:00Z',
        },
      ],
    });
  }),

  http.post('/api/v1/workflows', async ({ request }) => {
    const body = (await request.json()) as any;
    return HttpResponse.json({
      success: true,
      data: {
        id: 'wf-new',
        name: body.name || 'New Workflow',
        definition: body.definition || {},
        owner_id: 'user-123',
        state: 'draft',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      },
    });
  }),

  http.get('/api/v1/workflows/:id', ({ params }) => {
    return HttpResponse.json({
      success: true,
      data: {
        id: params.id,
        name: 'Basic Vulnerability Scan',
        definition: { plugins: ['dnsx', 'nmap', 'nuclei'] },
        owner_id: 'user-123',
        state: 'active',
        created_at: '2026-06-20T00:00:00Z',
        updated_at: '2026-06-20T00:00:00Z',
      },
    });
  }),

  http.post('/api/v1/workflows/:id/start', ({ params }) => {
    return HttpResponse.json({
      success: true,
      data: {
        workflow_id: params.id,
        run_id: 'run-123',
        status: 'pending',
      },
    });
  }),

  http.get('/api/v1/workflows/:id/events', () => {
    return HttpResponse.json({
      success: true,
      data: [
        {
          id: 'evt-1',
          workflow_id: 'wf-123',
          event_type: 'run_started',
          correlation_id: 'corr-123',
          payload: { message: 'Celery background task launched successfully' },
          timestamp: '2026-06-20T12:00:00Z',
        },
        {
          id: 'evt-2',
          workflow_id: 'wf-123',
          event_type: 'plugin_executing',
          correlation_id: 'corr-123',
          payload: { message: 'Executing Nmap port scan module' },
          timestamp: '2026-06-20T12:01:00Z',
        },
      ],
    });
  }),

  // Scan runs router
  http.get('/api/v1/scan_runs/:id', ({ params }) => {
    return HttpResponse.json({
      success: true,
      data: {
        id: params.id,
        workflow_id: 'wf-123',
        scope_id: 'scope-123',
        type: 'on-demand',
        status: 'running',
        start_ts: '2026-06-20T12:00:00Z',
        end_ts: null,
        metrics: { findings_discovered: 1, hosts_scanned: 1 },
        created_at: '2026-06-20T12:00:00Z',
      },
    });
  }),

  http.post('/api/v1/scan_runs/:id/cancel', () => {
    return HttpResponse.json({
      success: true,
      data: true,
    });
  }),

  // Reports & Dashboards router
  http.get('/api/v1/dashboard/summary', () => {
    return HttpResponse.json({
      success: true,
      data: {
        asset_count: 10,
        internet_exposed_assets: 2,
        open_ports: 5,
        services: 4,
        findings: { critical: 0, high: 1, medium: 2, low: 4, info: 1 },
        risk: { critical: 0, high: 1, medium: 1, low: 8 },
      },
    });
  }),

  http.get('/api/v1/dashboard/trends', () => {
    return HttpResponse.json({
      success: true,
      data: {
        window_days: 30,
        risk_trend: [{ timestamp: '2026-06-20T00:00:00Z', value: 85 }],
        finding_trend: [{ timestamp: '2026-06-20T00:00:00Z', value: 12 }],
        critical_finding_trend: [{ timestamp: '2026-06-20T00:00:00Z', value: 0 }],
      },
    });
  }),

  http.get('/api/v1/reports/executive', () => {
    return HttpResponse.json({
      success: true,
      data: {
        summary: { total: 10 },
        top_risky_assets: [],
        critical_findings: [],
        risk_distribution: {},
        exposure_distribution: {},
      },
    });
  }),

  http.get('/api/v1/reports/exposure', () => {
    return HttpResponse.json({
      success: true,
      data: {
        external_assets: [],
        internal_assets: [],
        unknown_assets: [],
        internet_exposed_count: 2,
      },
    });
  }),

  http.get('/api/v1/reports/findings', () => {
    return HttpResponse.json({
      success: true,
      data: {
        findings: [],
        total_count: 0,
      },
    });
  }),

  http.get('/api/v1/reports/risk', () => {
    return HttpResponse.json({
      success: true,
      data: {
        risk_distribution: {},
        critical_assets: [],
        high_risk_assets: [],
        risk_history: [],
      },
    });
  }),

  http.get('/api/v1/reports/assets/:id', () => {
    return HttpResponse.json({
      success: true,
      data: {
        asset: {},
        exposure: {},
        risk: {},
        ports: [],
        services: [],
        technologies: [],
        findings: [
          {
            id: 'finding-123',
            title: 'Outdated Nginx Version Detection',
            severity: 'high',
            status: 'open',
            template_name: 'Nginx Version Scanner',
          },
        ],
      },
    });
  }),

  // Export endpoints
  http.get('/api/v1/reports/executive/export/json', () => {
    const blobData = JSON.stringify({ report: 'executive_json_data' });
    return new HttpResponse(blobData, {
      headers: {
        'Content-Type': 'application/json',
        'Content-Disposition': 'attachment; filename="executive_report.json"',
      },
    });
  }),

  http.get('/api/v1/reports/executive/export/csv', () => {
    const csvData = 'id,name,value\n1,ExecutiveReport,100';
    return new HttpResponse(csvData, {
      headers: {
        'Content-Type': 'text/csv',
        'Content-Disposition': 'attachment; filename="executive_report.csv"',
      },
    });
  }),

  http.get('/api/v1/reports/assets/:id/export/json', ({ params }) => {
    const blobData = JSON.stringify({ asset_id: params.id, report: 'asset_json_data' });
    return new HttpResponse(blobData, {
      headers: {
        'Content-Type': 'application/json',
        'Content-Disposition': `attachment; filename="asset_report_${params.id}.json"`,
      },
    });
  }),

  http.get('/api/v1/reports/assets/:id/export/csv', ({ params }) => {
    const csvData = `id,asset_id,value\n1,${params.id},100`;
    return new HttpResponse(csvData, {
      headers: {
        'Content-Type': 'text/csv',
        'Content-Disposition': `attachment; filename="asset_report_${params.id}.csv"`,
      },
    });
  }),

  // Self Profile endpoint
  http.get('/api/v1/users/:user_id', ({ params }) => {
    return HttpResponse.json({
      success: true,
      data: {
        id: params.user_id,
        username: 'analyst_admin',
        display_name: 'System Admin',
        email: 'admin@aegisx.local',
        role: 'admin',
      },
    });
  }),

  // Threat Intelligence
  http.get('/api/v1/threat-intelligence', () => {
    return HttpResponse.json([
      {
        id: 'threat-123',
        value: 'APT29 Spearphishing Campaign',
        indicator_type: 'campaign',
        status: 'active',
        source: 'mitre-att&ck',
        tags: ['phishing', 'apt29'],
        scope_id: 'scope-123',
        fusion_score: 82,
        created_at: '2026-06-20T00:00:00Z',
        updated_at: '2026-06-20T00:00:00Z',
      },
    ]);
  }),

  http.get('/api/v1/threat-intelligence/active', () => {
    return HttpResponse.json([
      {
        id: 'threat-123',
        value: 'APT29 Spearphishing Campaign',
        indicator_type: 'campaign',
        status: 'active',
        source: 'mitre-att&ck',
        tags: ['phishing', 'apt29'],
        scope_id: 'scope-123',
        fusion_score: 82,
        created_at: '2026-06-20T00:00:00Z',
        updated_at: '2026-06-20T00:00:00Z',
      },
    ]);
  }),

  http.post('/api/v1/threat-intelligence/:id/fuse', async ({ params, request }) => {
    const body = (await request.json()) as any;
    return HttpResponse.json({
      id: params.id,
      value: 'Fused Threat Indicator',
      status: 'fused',
      fusion_score: body.confidence || 90,
    });
  }),

  // Cyber Risk Quantification
  http.get('/api/v1/cyber-risk-quantification', () => {
    return HttpResponse.json({
      success: true,
      data: [
        {
          id: 'risk-123',
          title: 'Database Ransomware Exposure',
          description: 'Risk of unauthorized access leading to ransomware deployment on DB assets.',
          scenario_type: 'ransomware',
          frequency_label: 'high',
          impact_label: 'critical',
          exposure_value: 250000,
          annualized_loss_expectancy: 120000,
          inherent_risk_score: 85.5,
          residual_risk_score: 30.0,
          status: 'open',
          scope_id: 'scope-123',
          created_at: '2026-06-20T00:00:00Z',
        },
      ],
    });
  }),

  http.get('/api/v1/cyber-risk-quantification/forecasts', () => {
    return HttpResponse.json({
      success: true,
      data: [
        {
          scenario_type: 'ransomware',
          p10_loss: 40000,
          p50_loss: 110000,
          p90_loss: 230000,
          simulated_mean: 120000,
        },
      ],
    });
  }),

  http.get('/api/v1/cyber-risk-quantification/trends', () => {
    return HttpResponse.json({
      success: true,
      data: [85.5, 82.0, 78.5, 75.0],
    });
  }),

  http.get('/api/v1/cyber-risk-quantification/summary', () => {
    return HttpResponse.json({
      success: true,
      data: {
        total_risk_scenarios: 1,
        average_inherent_score: 85.5,
        total_exposure_value: 250000,
      },
    });
  }),

  // Security Decisions
  http.get('/api/v1/security-decision', () => {
    return HttpResponse.json([
      {
        id: 'decision-123',
        decision_type: 'mitigation_plan',
        target_entity_id: 'asset-123',
        option_name: 'Deploy WAF & Restrict Ingress Port 8080',
        status: 'recommended',
        scope_id: 'scope-123',
        created_at: '2026-06-20T00:00:00Z',
      },
    ]);
  }),

  http.get('/api/v1/security-decision/recommended', () => {
    return HttpResponse.json([
      {
        id: 'decision-123',
        decision_type: 'mitigation_plan',
        target_entity_id: 'asset-123',
        option_name: 'Deploy WAF & Restrict Ingress Port 8080',
        status: 'recommended',
        scope_id: 'scope-123',
        created_at: '2026-06-20T00:00:00Z',
      },
    ]);
  }),

  http.post('/api/v1/security-decision/:id/commit', ({ params }) => {
    return HttpResponse.json({
      id: params.id,
      decision_type: 'mitigation_plan',
      target_entity_id: 'asset-123',
      option_name: 'Deploy WAF & Restrict Ingress Port 8080',
      status: 'committed',
      scope_id: 'scope-123',
      created_at: '2026-06-20T00:00:00Z',
    });
  }),

  // Graph Topology
  http.get('/api/v1/security-intelligence-graph/topology', () => {
    return HttpResponse.json({
      nodes: [
        {
          id: 'asset-123',
          node_type: 'asset',
          entity_id: 'asset-123',
          scope_id: 'scope-123',
          status: 'active',
        },
      ],
      edges: [],
    });
  }),

  // Autonomous Planning
  http.get('/api/v1/autonomous-planning', () => {
    return HttpResponse.json([
      {
        id: 'plan-123',
        category: 'remediation',
        name: 'Autonomous Patching for Port 8080 Vulnerability',
        status: 'pending_approval',
        priority: 'medium',
        scope_id: 'scope-123',
        created_at: '2026-06-20T00:00:00Z',
      },
    ]);
  }),

  http.post('/api/v1/autonomous-planning/:id/approve', ({ params }) => {
    return HttpResponse.json({
      id: params.id,
      category: 'remediation',
      name: 'Autonomous Patching for Port 8080 Vulnerability',
      status: 'approved',
      priority: 'medium',
      scope_id: 'scope-123',
      created_at: '2026-06-20T00:00:00Z',
    });
  }),
];

