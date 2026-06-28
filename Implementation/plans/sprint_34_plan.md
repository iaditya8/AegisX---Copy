Implementation Plan - Sprint 34: Unified Security Intelligence Graph

Transform AegisX from a Threat Intelligence Fusion Intelligence Platform into a Unified Security Intelligence Graph Platform.

User Review Required

[!IMPORTANT]

All graph nodes, edges, path metrics, cross-domain correlation records, histories, and snapshots operate strictly in-memory.

Zero database migrations.

Zero external graph databases.

Zero external vector/semantic stores.

AI Security Copilot remains strictly advisory-only and cannot perform mutations on the security intelligence graph topology, mappings, or edge weights.

Architectural Constraints (Sprint 1–34 Compliance)

Registry-driven design: All node types, edge categories, and relationship weights must be validated against registries.

Deterministic fingerprinting: Node and relationship fingerprints must be generated using SHA-256 and remain stable.

Identity preservation: Syncs and graph updates must preserve unique node and edge identifiers.

Terminal-state enforcement: DEPRECATED graph components must never transition back to active/stable states.

Immutable historical records: History entries must never be modified, deleted, or reordered.

Snapshot rebuild consistency: Snapshots are non-authoritative caches and must be fully rebuildable from active source data.

In-memory storage only: Zero database migrations.

No external integrations: Zero external graph indexing engines.

No breaking API changes: Keep all existing endpoints and routers backward compatible.

Full backward compatibility: Guarantee that all previous sprints (1-33) run without regression.

AI Advisory-only enforcement: Physically block the AI Security Copilot from executing any graph modifications.

Lifecycle & Hardening Rules

Graph Component Terminal State Rule

DEPRECATED is a terminal state.

Requirements:

synchronization cannot reactivate DEPRECATED node or relationship components

worker refresh cycles cannot reactivate DEPRECATED components

correlation mapping updates cannot reactivate DEPRECATED components

pathfinding traversals cannot reactivate DEPRECATED components

drift processing cannot reactivate DEPRECATED components

snapshot rebuilds cannot reactivate DEPRECATED components

A new component may only be created if the fingerprint changes.

Graph Identity Preservation Rule

If synchronization generates an identical fingerprint:

preserve node_id / relationship_id

preserve fingerprint

preserve created_at

preserve history

preserve links

Do not create duplicate nodes or edges.

Graph Correlation Preservation Rule

Correlation mappings are authoritative graph intelligence.

Requirements:

correlation recalculations must never modify:

source entities

graph history

snapshots

correlation recalculations are read-only mapping determinations

Graph History Preservation Rule

History entries are immutable.

Requirements:

never modify history

never delete history

never reorder history

History must survive:

worker refreshes

graph traversals

correlation mapping

drift processing

snapshot rebuilds

History is the authoritative audit trail. Only append new events.

Graph Traversal Determinism Rule

Graph mapping calculations are derived intelligence.

Requirements:

cross-domain correlations must be deterministic

pathfinding traversals must be deterministic

node centrality calculations must be deterministic

impact propagation metrics must be deterministic

Identical inputs must always produce identical outputs.

Calculations must never mutate:

graph records

histories

mappings

snapshots

Calculations are read-only intelligence generation.

Graph Snapshot Consistency Rule

Snapshots are:

cache-only

rebuildable

non-authoritative

If cache is:

missing

deleted

corrupted

generate_snapshot() and get_snapshot() must rebuild from source nodes and edges.No state may exist exclusively inside snapshots. Source graph records remain authoritative.

Proposed Changes

Domain Models

[NEW] security_intelligence_graph.py

Define enums:

NodeType (ASSET, RISK, COMPLIANCE, POSTURE, RESILIENCE, KNOWLEDGE, THREAT_INTEL, INCIDENT, CASE, INVESTIGATION)

EdgeType (AFFECTS, CONTAINED_IN, MITIGATES, MAPS_TO, CORRELATES_WITH, TRIGGERS)

GraphComponentStatus (ACTIVE, STABLE, DEPRECATED)

Define Pydantic models:

GraphNodeResponse: Represents a node in the intelligence graph.

GraphEdgeResponse: Represents a relationship between two nodes.

GraphPathResponse: Represents a multi-hop traversal path.

GraphAnalysisResponse: Traversal and analysis results.

GraphSnapshotResponse: Summarizes graph density and metrics.

GraphHistoryEntry: Audit logs.

Registries

[NEW] graph_node_type_registry.py

Validates node types against allowed domain entities.

[NEW] graph_edge_type_registry.py

Validates edge relationship types.

[NEW] graph_relationship_weight_registry.py

Pre-seeded: Maps EdgeType values to baseline connection weights (e.g., AFFECTS = 3.0, MITIGATES = 1.0, CORRELATES_WITH = 1.5).

Fingerprinting

[NEW] graph_fingerprint_service.py

Node: SHA256(node_type + "_" + str(entity_id))

Relationship: SHA256(str(source_id) + "_" + edge_type + "_" + str(target_id))

Core Services

[NEW] graph_history_service.py

Immutable append-only history tracking NODE_ADDED, EDGE_ADDED, STABLE, CORRELATED, DEPRECATED.

[NEW] security_intelligence_graph_service.py

Manages graph state, synchronization, lifecycle transitions, and duplicate prevention.

Enforces Graph Component Terminal State Rule.

[NEW] graph_correlation_service.py

Authoritative cross-domain correlation engine linking Assets, Risks, GRC, Posture, Resilience, Knowledge, Threat Intel, Incidents, Cases, and Investigations.

[NEW] graph_drift_service.py

Captures graph structural and weight drifts. Emits graph.drift and graph.structure_changed.

[NEW] graph_snapshot_service.py

Cache-only snapshot rebuild engine from active graph state.

Integrations

[MODIFY] worker.py

Add periodic background tasks for cross-domain graph assembly, pathfinding recalculation, structural drift checks, and graph snapshot cache updates.

Sprint 34 Worker Execution Order

SecurityIntelligenceGraphService.rebuild_graph_topology()

GraphCorrelationService.recalculate_cross_domain_links()

GraphDriftService.process_drift()

GraphSnapshotService.generate_snapshot()

[MODIFY] ai_context_builder.py

Injects cross-domain paths, impact maps, correlation lists, and graph density details into AI contexts.

[MODIFY] ai_prompt_builder.py

Prompt guardrails blocking AI Copilot mutations to graph structures, edges, weights, or nodes.

[MODIFY] main.py

Register security_intelligence_graph API router.

API Gateway

[NEW] security_intelligence_graph.py

POST: /nodes, /edges, /components/{id}/deprecate.

GET: /topology, /paths, /correlations, /drift, /summary.

Enforces RBAC and scope isolation.

Verification Plan

Automated Tests

Implement 120+ integration tests in test_security_intelligence_graph.py.Coverage target: >= 85% code coverage.

Sprint 34 Mandatory Test Cases

test_node_auto_creation()

test_edge_auto_creation()

test_graph_fingerprint_stability()

test_graph_identity_preservation()

test_graph_duplicate_prevention()

test_graph_deprecation_transition()

test_graph_terminal_state_enforcement()

test_deprecated_component_not_reactivated_by_sync()

test_deprecated_component_not_reactivated_by_worker()

test_deprecated_component_not_reactivated_by_snapshot()

test_deprecated_component_not_reactivated_by_drift()

test_deprecated_component_not_reactivated_by_correlation()

test_graph_history_preserved()

test_graph_history_immutable()

test_graph_history_order_preserved()

test_cross_domain_correlation_deterministic()

test_pathfinding_traversal_consistency()

test_centrality_metric_calculation()

test_graph_drift_detection()

test_graph_drift_clearing()

test_snapshot_rebuild_consistency()

test_snapshot_rebuild_after_cache_deletion()

test_snapshot_rebuild_after_cache_corruption()

test_snapshot_not_authoritative()

test_snapshot_rebuild_from_source_of_truth()

test_ai_context_graph_injection()

test_ai_advisory_only_enforcement()

test_rbac_graph_scope_validation()

test_worker_integration()

test_graph_identity_preserved_after_worker_refresh()

test_graph_identity_preserved_after_correlation_refresh()

test_graph_identity_preserved_after_snapshot_rebuild()

test_graph_identity_preserved_after_drift_processing()

test_correlation_determinism()

test_scope_isolation_for_graph_paths()

test_graph_score_stability()

Run:

.venv\Scripts\pytest backend/tests/integration/test_security_intelligence_graph.py
.venv\Scripts\pytest

Deliverables

1. Architecture Summary

Detailed description of cross-domain correlation models, graph edge weighting, traversal determinism, and snapshot caches.

2. File Manifest

List of all new and modified files.

3. Testing Results

Pytest verification outputs demonstrating zero regressions.

STOP.Wait for user approval before implementation.