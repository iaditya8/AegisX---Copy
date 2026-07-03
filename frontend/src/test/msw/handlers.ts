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
        {
          id: 'threat-123',
          node_type: 'threat',
          entity_id: 'threat-123',
          scope_id: 'scope-123',
          status: 'active',
        },
      ],
      edges: [
        {
          id: 'edge-123',
          source_id: 'threat-123',
          target_id: 'asset-123',
          edge_type: 'threatens',
          weight: 85,
          scope_id: 'scope-123',
          status: 'active',
        },
      ],
    });
  }),

  http.get('/api/v1/security-intelligence-graph/paths', () => {
    return HttpResponse.json({
      path_id: 'path-123',
      nodes: [
        {
          id: 'node-threat-123',
          node_type: 'threat',
          entity_id: 'threat-123',
          scope_id: 'scope-123',
          status: 'active',
        },
        {
          id: 'node-asset-123',
          node_type: 'asset',
          entity_id: 'asset-123',
          scope_id: 'scope-123',
          status: 'active',
        },
      ],
      edges: [
        {
          id: 'edge-123',
          source_id: 'threat-123',
          target_id: 'asset-123',
          edge_type: 'threatens',
          weight: 85,
          scope_id: 'scope-123',
          status: 'active',
        },
      ],
      metrics: {
        cost: 1.5,
      },
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

  // GRC Assessments
  http.get('/api/v1/governance-risk-compliance', () => {
    return HttpResponse.json([
      {
        id: 'assessment-123',
        name: 'ISO 27001 Compliance Audit',
        description: 'Annual ISO 27001 compliance audit for production scopes.',
        framework_type: 'ISO 27001',
        status: 'draft',
        scope_id: 'scope-123',
        created_at: '2026-06-20T00:00:00Z',
        updated_at: '2026-06-20T00:00:00Z',
        evidence_list: [],
      },
    ]);
  }),

  http.get('/api/v1/governance-risk-compliance/frameworks', () => {
    return HttpResponse.json(['ISO 27001', 'SOC2', 'NIST CSF']);
  }),

  http.get('/api/v1/governance-risk-compliance/gaps', () => {
    return HttpResponse.json([
      {
        id: 'gap-1',
        control_code: 'A.12.6.1',
        control_name: 'Management of technical vulnerabilities',
        status: 'gap',
        notes: 'Outdated server versions discovered on public interfaces.',
        remediation_action: 'Patch Nginx vulnerabilities',
      },
      {
        id: 'gap-2',
        control_code: 'A.9.1.1',
        control_name: 'Access control policy',
        status: 'compliant',
        notes: 'SSO and IAM roles enforced across all tenant directories.',
      },
    ]);
  }),

  http.post('/api/v1/governance-risk-compliance/:id/:status', ({ params }) => {
    return HttpResponse.json({
      id: params.id,
      name: 'ISO 27001 Compliance Audit',
      description: 'Annual ISO 27001 compliance audit for production scopes.',
      framework_type: 'ISO 27001',
      status: params.status === 'compliant' ? 'compliant' : params.status === 'review' ? 'in_review' : 'closed',
      scope_id: 'scope-123',
      created_at: '2026-06-20T00:00:00Z',
      updated_at: new Date().toISOString(),
      evidence_list: [],
    });
  }),

  http.post('/api/v1/governance-risk-compliance/:id/evidence', async ({ params, request }) => {
    const body = (await request.json()) as any;
    return HttpResponse.json({
      id: 'evidence-999',
      file_name: body.file_name || 'uploaded_doc.pdf',
      file_hash: body.file_hash || 'sha256-mock-hash-value',
      uploaded_at: new Date().toISOString(),
    });
  }),

  // SOC Operations & Analytics
  http.get('/api/v1/security-operations-analytics/queues', () => {
    return HttpResponse.json({
      queue_name: 'Primary SOC Triage Queue',
      active_tickets_count: 14,
      oldest_ticket_age_hours: 4.5,
      unassigned_tickets_count: 3,
      critical_tickets_count: 2,
      backlog_metrics: {
        total_backlog_count: 45,
        growth_rate_percent: 12.5,
        estimated_clearance_days: 3,
      },
    });
  }),

  http.get('/api/v1/security-operations-analytics/kpis', () => {
    return HttpResponse.json([
      {
        id: 'kpi-1',
        metric_name: 'Mean Time to Resolution (MTTR)',
        metric_value: 32,
        unit: 'm',
        target_value: 45,
        status: 'optimal',
      },
      {
        id: 'kpi-2',
        metric_name: 'Mean Time to Detect (MTTD)',
        metric_value: 4.5,
        unit: 'm',
        target_value: 5,
        status: 'optimal',
      },
    ]);
  }),

  http.get('/api/v1/security-operations-analytics/analysts', () => {
    return HttpResponse.json([
      {
        id: 'analyst-1',
        analyst_name: 'Sarah Connor',
        cases_closed: 24,
        mean_time_to_resolution_minutes: 28,
        satisfaction_score: 9.4,
      },
      {
        id: 'analyst-2',
        analyst_name: 'John Miller',
        cases_closed: 19,
        mean_time_to_resolution_minutes: 36,
        satisfaction_score: 8.8,
      },
    ]);
  }),

  // Cyber Resilience
  http.get('/api/v1/cyber-resilience', () => {
    return HttpResponse.json([
      {
        id: 'resilience-123',
        title: 'Primary Database Failover Drill',
        description: 'Validate secondary DB replication and DNS transition response metrics.',
        service_name: 'Main Database Cluster',
        service_criticality: 'critical',
        status: 'draft',
        scope_id: 'scope-123',
        created_at: '2026-06-20T00:00:00Z',
        updated_at: '2026-06-20T00:00:00Z',
      },
    ]);
  }),

  http.get('/api/v1/cyber-resilience/objectives', () => {
    return HttpResponse.json([
      {
        id: 'obj-1',
        objective_name: 'DNS Failover Switchover Time',
        target_rto_minutes: 15,
        target_rpo_minutes: 5,
        actual_rto_minutes: 11,
        actual_rpo_minutes: 2,
        status: 'achieved',
      },
      {
        id: 'obj-2',
        objective_name: 'Data Integrity Sync Check',
        target_rto_minutes: 30,
        target_rpo_minutes: 10,
        actual_rto_minutes: 34,
        actual_rpo_minutes: 4,
        status: 'missed',
      },
    ]);
  }),

  http.post('/api/v1/cyber-resilience/:id/:action', ({ params }) => {
    return HttpResponse.json({
      id: params.id,
      title: 'Primary Database Failover Drill',
      description: 'Validate secondary DB replication and DNS transition response metrics.',
      service_name: 'Main Database Cluster',
      service_criticality: 'critical',
      status: params.action === 'activate' ? 'active' : params.action === 'validate' ? 'validated' : params.action === 'complete' ? 'completed' : 'closed',
      scope_id: 'scope-123',
      created_at: '2026-06-20T00:00:00Z',
      updated_at: new Date().toISOString(),
    });
  }),

  // Executive Posture & Reports
  http.get('/api/v1/executive-reporting', () => {
    return HttpResponse.json([
      {
        id: 'report-123',
        title: 'Q2 2026 Security Posture Review',
        description: 'Comprehensive posture scorecard review for stakeholders.',
        report_period: 'Q2 2026',
        report_type: 'Quarterly',
        status: 'draft',
        scope_id: 'scope-123',
        created_at: '2026-06-20T00:00:00Z',
      },
    ]);
  }),

  http.get('/api/v1/executive-reporting/scorecard', () => {
    return HttpResponse.json({
      grade: 'B+',
      risk_score: 78,
      total_findings_count: 14,
      critical_findings_count: 2,
      high_findings_count: 4,
      status: 'warning',
    });
  }),

  http.get('/api/v1/executive-reporting/heatmap', () => {
    return HttpResponse.json({
      coordinates: [
        { likelihood: 4, impact: 4, count: 2, risk_level: 'high' },
        { likelihood: 2, impact: 5, count: 1, risk_level: 'high' },
      ],
    });
  }),

  http.post('/api/v1/executive-reporting', async ({ request }) => {
    const body = (await request.json()) as any;
    return HttpResponse.json({
      id: 'report-new',
      title: body.title || 'Executive Posture Report',
      description: body.description || 'Auto-generated report',
      report_period: body.report_period || 'Monthly',
      report_type: body.report_type || 'Executive Posture',
      status: 'draft',
      scope_id: 'scope-123',
      created_at: new Date().toISOString(),
    });
  }),

  http.post('/api/v1/executive-reporting/:id/transition', async ({ params, request }) => {
    const body = (await request.json()) as any;
    return HttpResponse.json({
      id: params.id,
      title: 'Q2 2026 Security Posture Review',
      description: 'Comprehensive posture scorecard review for stakeholders.',
      report_period: 'Q2 2026',
      report_type: 'Quarterly',
      status: body.status || 'published',
      scope_id: 'scope-123',
      created_at: '2026-06-20T00:00:00Z',
    });
  }),

  // Security Postures
  http.get('/api/v1/security-posture', () => {
    return HttpResponse.json([
      {
        id: 'posture-123',
        title: 'MFA Disabled on Root Account',
        description: 'Exposed root admin accounts found without multi-factor authentication enforced.',
        category: 'Identity Drift',
        severity: 'critical',
        status: 'open',
        risk_source: 'AWS IAM Audit',
        owner: 'SecOps Team',
        scope_id: 'scope-123',
        created_at: '2026-06-20T00:00:00Z',
      },
    ]);
  }),

  http.get('/api/v1/security-posture/summary', () => {
    return HttpResponse.json({
      total_count: 6,
      open_count: 5,
      critical_count: 1,
      high_count: 2,
      medium_count: 2,
      low_count: 1,
      drift_index: 8,
    });
  }),

  http.get('/api/v1/security-posture/drift', () => {
    return HttpResponse.json({
      snapshot: {
        total_count: 6,
        open_count: 5,
        critical_count: 1,
        high_count: 2,
        medium_count: 2,
        low_count: 1,
        drift_index: 4,
      },
    });
  }),

  http.post('/api/v1/security-posture/:id/:action', ({ params }) => {
    return HttpResponse.json({
      id: params.id,
      title: 'MFA Disabled on Root Account',
      description: 'Exposed root admin accounts found without multi-factor authentication enforced.',
      category: 'Identity Drift',
      severity: 'critical',
      status: params.action === 'accept' ? 'accepted' : params.action === 'mitigate' ? 'mitigated' : 'closed',
      risk_source: 'AWS IAM Audit',
      owner: 'SecOps Team',
      scope_id: 'scope-123',
      created_at: '2026-06-20T00:00:00Z',
    });
  }),

  // SaaS Tenants & SSO Configuration
  http.get('/api/v1/tenants', () => {
    return HttpResponse.json([
      {
        id: 'tenant-123',
        name: 'Aegis Corp Primary',
        domain_pattern: 'aegiscorp.com',
        subscription_plan: 'enterprise',
        status: 'active',
        created_at: '2026-06-20T00:00:00Z',
      },
    ]);
  }),

  http.post('/api/v1/tenants', async ({ request }) => {
    const body = (await request.json()) as any;
    return HttpResponse.json({
      id: 'tenant-new',
      name: body.name || 'New Tenant',
      domain_pattern: body.domain_pattern || 'domain.com',
      subscription_plan: body.subscription_plan || 'starter',
      status: 'active',
      created_at: new Date().toISOString(),
    });
  }),

  http.get('/api/v1/sso/config', () => {
    return HttpResponse.json({
      id: 'config-123',
      saml_enabled: true,
      idp_entity_id: 'urn:amazon:cognito:sp:aegisx',
      idp_sso_url: 'https://idp.aegiscorp.com/adfs/ls/',
      x509_certificate: '-----BEGIN CERTIFICATE-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...\n-----END CERTIFICATE-----',
      auto_provision_users: true,
      enforce_sso_for_operators: false,
      session_timeout_hours: 12,
    });
  }),

  http.post('/api/v1/sso/config', async ({ request }) => {
    const body = (await request.json()) as any;
    return HttpResponse.json({
      id: 'config-123',
      saml_enabled: body.saml_enabled !== undefined ? body.saml_enabled : true,
      idp_entity_id: body.idp_entity_id || 'urn:amazon:cognito:sp:aegisx',
      idp_sso_url: body.idp_sso_url || 'https://idp.aegiscorp.com/adfs/ls/',
      x509_certificate: body.x509_certificate || '',
      auto_provision_users: body.auto_provision_users !== undefined ? body.auto_provision_users : true,
      enforce_sso_for_operators: body.enforce_sso_for_operators !== undefined ? body.enforce_sso_for_operators : false,
      session_timeout_hours: body.session_timeout_hours || 12,
    });
  }),

  // Saved Whiteboards
  http.get('/api/v1/whiteboards', () => {
    return HttpResponse.json([
      {
        id: 'wb-123',
        title: 'APT-41 Exploit Path Analysis',
        description: 'Topology nodes linking compromised web interface to primary databases.',
        elements: [
          { id: 'el-1', type: 'asset', label: 'Primary DB Instance', x: 100, y: 150 },
          { id: 'el-2', type: 'finding', label: 'MFA Disabled on Admin Account', x: 250, y: 150 },
        ],
        notes: [
          { id: 'note-1', note_text: 'Threat correlation shows APT-41 actors leveraging exposed SSH ports.', author: 'analyst_bob', created_at: '2026-06-21T10:00:00Z' },
        ],
        created_by: 'analyst_bob',
        created_at: '2026-06-20T00:00:00Z',
      },
    ]);
  }),

  http.get('/api/v1/whiteboards/:id', ({ params }) => {
    return HttpResponse.json({
      id: params.id,
      title: 'APT-41 Exploit Path Analysis',
      description: 'Topology nodes linking compromised web interface to primary databases.',
      elements: [
        { id: 'el-1', type: 'asset', label: 'Primary DB Instance', x: 100, y: 150 },
        { id: 'el-2', type: 'finding', label: 'MFA Disabled on Admin Account', x: 250, y: 150 },
      ],
      notes: [
        { id: 'note-1', note_text: 'Threat correlation shows APT-41 actors leveraging exposed SSH ports.', author: 'analyst_bob', created_at: '2026-06-21T10:00:00Z' },
      ],
      created_by: 'analyst_bob',
      created_at: '2026-06-20T00:00:00Z',
    });
  }),

  http.post('/api/v1/whiteboards', async ({ request }) => {
    const body = (await request.json()) as any;
    return HttpResponse.json({
      id: 'wb-new',
      title: body.title || 'New Board',
      description: body.description || '',
      elements: body.elements || [],
      notes: [],
      created_by: 'analyst_admin',
      created_at: new Date().toISOString(),
    });
  }),

  http.post('/api/v1/whiteboards/:id/notes', async ({ params, request }) => {
    const body = (await request.json()) as any;
    return HttpResponse.json({
      id: 'note-new',
      note_text: body.note_text || '',
      author: body.author || 'analyst_admin',
      created_at: new Date().toISOString(),
    });
  }),

  // Copilot
  http.post('/api/v1/copilot/ask', async ({ request }) => {
    const body = (await request.json()) as any;
    return HttpResponse.json({
      answer: `Based on risk audits, I recommend verifying [MFA Disabled on Admin Account](finding:posture-123) which exposes the [Primary DB Instance](asset:asset-456).`,
      citations: [
        { id: 'posture-123', type: 'finding', label: 'MFA Disabled on Admin Account', link_url: '/posture' },
        { id: 'asset-456', type: 'asset', label: 'Primary DB Instance', link_url: '/inventory' },
      ],
    });
  }),

  http.get('/api/v1/copilot/history', () => {
    return HttpResponse.json([
      {
        id: 'audit-123',
        user_id: 'user-admin',
        scope_id: 'scope-123',
        prompt: 'Show posture issues',
        response_text: 'Verify MFA Disabled finding.',
        created_at: '2026-06-20T12:00:00Z',
      },
    ]);
  }),
];

