Implementation Plan - Sprint 33: Threat Intelligence Fusion Intelligence

Transform AegisX from a Security Knowledge Intelligence Platform into a Threat Intelligence Fusion Intelligence Platform.

User Review Required

[!IMPORTANT]

All threat intelligence records, indicators, threat actor profiles, feeds, fusion mappings, histories, and snapshots operate strictly in-memory.

Zero database migrations.

Zero external threat intelligence platforms.

Zero external security feeds.

Zero external threat search platforms.

AI Security Copilot remains strictly advisory-only and cannot execute modifications on threat records, indicators, or fusion parameters.

Architectural Constraints (Sprint 1–33 Compliance)

Registry-driven design: All threat sources, indicator types, severities, and threat classifications must be validated against registries.

Deterministic fingerprinting: Threat intelligence fingerprints must be generated using SHA-256 and remain stable.

Identity preservation: Syncs and updates must preserve unique threat intelligence identifiers.

Terminal-state enforcement: ARCHIVED threat intelligence records must never transition back to active states.

Immutable historical records: History entries must never be modified, deleted, or reordered.

Snapshot rebuild consistency: Snapshots are non-authoritative caches and must be fully rebuildable from active source threat intelligence.

In-memory storage only: Zero database migrations.

No external integrations: Zero external threat intel engines.

No breaking API changes: Keep all existing endpoints and routers backward compatible.

Full backward compatibility: Guarantee that all previous sprints (1-32) run without regression.

AI Advisory-only enforcement: Physically block the AI Security Copilot from executing any threat intelligence mutations.

Lifecycle & Hardening Rules

Threat Intel Terminal State Rule

ARCHIVED is a terminal state.

Requirements:

synchronization cannot reactivate ARCHIVED threat intelligence records

worker refresh cycles cannot reactivate ARCHIVED threat intelligence records

indicator mapping updates cannot reactivate ARCHIVED threat intelligence records

fusion scoring calculations cannot reactivate ARCHIVED threat intelligence records

drift processing cannot reactivate ARCHIVED threat intelligence records

snapshot rebuilds cannot reactivate ARCHIVED threat intelligence records

A new threat intelligence record may only be created if the fingerprint changes.

Threat Intel Identity Preservation Rule

If synchronization generates an identical fingerprint:

preserve threat_intel_id

preserve fingerprint

preserve created_at

preserve history

preserve indicators

preserve actors

Do not create duplicates.

Threat Indicator Preservation Rule

Threat indicators are authoritative threat artifacts.

Requirements:

indicator enrichment, fusion scoring, severity calculations, drift processing, and snapshot rebuilds must never modify indicators

indicators are preserved and remain authoritative in memory

Threat Intel History Preservation Rule

History entries are immutable.

Requirements:

never modify history

never delete history

never reorder history

History must survive:

worker refreshes

fusion scoring

indicator mapping

drift processing

snapshot rebuilds

History is the authoritative audit trail. Only append new events.

Threat Intel Fusion Determinism Rule

Threat calculations are derived intelligence.

Requirements:

fusion score calculations must be deterministic

actor confidence calculations must be deterministic

severity level classifications must be deterministic

recommendation scoring must be deterministic

Identical inputs must always produce identical outputs.

Calculations must never mutate:

threat records

histories

indicators

snapshots

Calculations are read-only intelligence generation.

Threat Intel Snapshot Consistency Rule

Snapshots are:

cache-only

rebuildable

non-authoritative

If cache is:

missing

deleted

corrupted

generate_snapshot() and get_snapshot() must rebuild from source threat intelligence.No state may exist exclusively inside snapshots. Source threat records remain authoritative.

Proposed Changes

Domain Models

[NEW] threat_intel.py

Define enums:

ThreatSeverity (LOW, MEDIUM, HIGH, CRITICAL)

ThreatIntelStatus (ACTIVE, IN_TRIAGE, FUSED, ARCHIVED)

ThreatIndicatorType (IP, DOMAIN, URL, SHA256, EMAIL, CVE)

Define Pydantic models:

ThreatIntelRecordResponse: Represents a threat indicator/intelligence feed item.

ThreatIndicatorResponse: Represents extracted threat indicators.

ThreatActorResponse: Threat actor details.

ThreatFusionResponse: Represents fused threat record metrics.

ThreatIntelSnapshotResponse: Summarizes threat metrics.

ThreatIntelHistoryEntry: Audit logs.

Registries

[NEW] threat_source_registry.py

Pre-seeded: OSINT, COMMERCIAL, INTERNAL_HONEYPOT, PARTNER_FEED, NATIONAL_CERT.

[NEW] threat_indicator_type_registry.py

Pre-seeded: IP, DOMAIN, URL, SHA256, EMAIL, CVE.

[NEW] threat_severity_registry.py

Maps threat indicators and score ranges to threat severity levels.

Fingerprinting

[NEW] threat_intel_fingerprint_service.py

Generates SHA256(indicator_type + "_" + str(scope_id or "global") + "_" + value.strip().lower()) stable fingerprint.

Core Services

[NEW] threat_intel_history_service.py

Immutable append-only history tracking CREATED, UPDATED, FUSED, TRIAGED, DRIFT_DETECTED, ARCHIVED.

[NEW] threat_intelligence_service.py

Handles threat creation, synchronization, lifecycle transitions, and duplicates.

Enforces Threat Intel Terminal State Rule.

[NEW] threat_intel_fusion_service.py

Computes deterministic fusion scores and threat severity levels from multiple feeds.

[NEW] threat_intel_drift_service.py

Captures indicator reputation score shifts. Emits threat.drift and threat.score_changed.

[NEW] threat_intel_snapshot_service.py

Non-authoritative, cache-only rebuildable snapshots of threat metrics.

Integrations

[MODIFY] worker.py

Add periodic background tasks for threat intelligence synchronization, fusion calculations, drift analysis, and snapshot updates.

Sprint 33 Worker Execution Order

ThreatIntelligenceService.sync_threats()

ThreatIntelFusionService.calculate()

ThreatIntelDriftService.process_drift()

ThreatIntelSnapshotService.generate_snapshot()

[MODIFY] ai_context_builder.py

Inject threat intelligence, indicator profiles, fusion scores, and threat drift summaries into AI contexts.

[MODIFY] ai_prompt_builder.py

Physical guardrails preventing AI Copilot from executing mutations on threat intel records, severity, or fusion state.

[MODIFY] main.py

Register threat_intelligence API router.

API Gateway

[NEW] threat_intelligence.py

POST: /, /{id}/triage, /{id}/fuse, /{id}/archive.

GET: /, /active, /fused, /drift, /summary, /{id}.

Enforces RBAC and scope isolation.

Verification Plan

Automated Tests

Implement 110+ integration tests in test_threat_intelligence.py.Coverage target: >= 85% code coverage.

Sprint 33 Mandatory Test Cases

test_threat_intel_auto_creation()

test_threat_intel_fingerprint_stability()

test_threat_intel_identity_preservation()

test_threat_intel_duplicate_prevention()

test_threat_intel_triage_transition()

test_threat_intel_fuse_transition()

test_threat_intel_archive_transition()

test_threat_intel_terminal_state_enforcement()

test_archived_threat_intel_not_reactivated_by_sync()

test_archived_threat_intel_not_reactivated_by_worker()

test_archived_threat_intel_not_reactivated_by_snapshot()

test_archived_threat_intel_not_reactivated_by_drift()

test_archived_threat_intel_not_reactivated_by_fusion()

test_threat_intel_history_preserved()

test_threat_intel_history_immutable()

test_threat_intel_history_order_preserved()

test_fusion_scoring_deterministic()

test_threat_indicator_extraction_consistency()

test_threat_severity_calculation()

test_threat_intel_drift_detection()

test_threat_intel_drift_clearing()

test_snapshot_rebuild_consistency()

test_snapshot_rebuild_after_cache_deletion()

test_snapshot_rebuild_after_cache_corruption()

test_snapshot_not_authoritative()

test_snapshot_rebuild_from_source_of_truth()

test_ai_context_threat_intel_injection()

test_ai_advisory_only_enforcement()

test_rbac_threat_intel_scope_validation()

test_worker_integration()

test_threat_intel_identity_preserved_after_worker_refresh()

test_threat_intel_identity_preserved_after_fusion_refresh()

test_threat_intel_identity_preserved_after_snapshot_rebuild()

test_threat_intel_identity_preserved_after_drift_processing()

test_threat_severity_determinism()

test_scope_isolation_for_threat_indicators()

test_threat_score_stability()

Run:

.venv\Scripts\pytest backend/tests/integration/test_threat_intelligence.py
.venv\Scripts\pytest

Deliverables

1. Architecture Summary

Details of threat intelligence lifecycles, indicator registries, deterministic fusion scoring, drift calculations, and snapshot cached rebuilding.

2. File Manifest

List of all new and modified files.

3. Testing Results

Pytest verification outputs demonstrating zero regressions.

STOP.Wait for user approval before implementation.