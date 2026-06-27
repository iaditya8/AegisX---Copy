Implementation Plan - Architecture Hardening Sprint (Sprints 30–37 Verification & Remediation)

Conduct a comprehensive verification and remediation for AegisX Sprints 30–37 potential defects. This is a hardening sprint only: zero new features, zero database migrations, zero external dependencies, and complete backward compatibility must be maintained.

Verification & Finding Status

Based on active codebase analysis, here is the verification status for each of the 7 findings:

Finding

Description

Status

Evidence

Finding 1

Background worker cascading failure

CONFIRMED

In worker.py lines 988-1084, Sprints 34–37 are nested within the Sprint 33 try/except block. A failure in Sprint 33 completely skips Sprints 34–37.

Finding 2

Threat fusion result persistence

CONFIRMED

In worker.py lines 1012-1017, the calculated fusion result is never passed back to ThreatIntelligenceService.fuse_threat to update the status to FUSED or save the confidence score.

Finding 3

Security decision framework mapping

CONFIRMED

In security_decision_service.py line 188, GRC assessments query assess.get('framework_name'), which does not exist (the keys are framework_type and assessment_name).

Finding 4

Threat actor model collision

CONFIRMED

Both threat_intelligence.py and threat_intel.py define Pydantic models named ThreatActorResponse with different fields.

Finding 5

AI context coverage

CONFIRMED

GRC (Sprint 31), Knowledge (Sprint 32), and other contexts are either nested incorrectly (leading to duplication) or entirely omitted (like resilience Sprint 28) from asset, finding, and executive contexts.

Finding 6

GRC worker recalculation

CONFIRMED

GRC sync_assessments skips updating compliance and coverage scores of existing assessments when Control/Risk/Posture mappings shift.

Finding 7

Knowledge worker recalculation

CONFIRMED

Playbooks relevance, confidence, and severity scores are never recalculated inside background worker runs.

Proposed Changes

1. Worker Isolation (Finding 1)

[MODIFY] worker.py

Un-nest the execution blocks of Sprints 34, 35, 36, and 37 from the Sprint 33 try/except block.

Encase each sprint block in its own independent try/except Exception block.

Keep the existing logging formats and messages unchanged.

2. Threat Fusion Result Persistence & History Preservation (Finding 2)

[MODIFY] threat_intelligence_service.py

Initialize record["confidence"] = None in sync_threat.

Modify fuse_threat(cls, threat_intel_id: uuid.UUID, confidence: float) -> dict:

Fetch existing record.

Enforce Threat Fusion Terminal State Protection:

If the record's status is a terminal state (e.g., if record["status"] in ThreatStatus.terminal_states():), skip execution, do not modify confidence, status, or history, and return the record unchanged. This dynamic check ensures all Sprint 33 terminal states are respected without hard-coding enum values.

Read existing confidence and status values.

If confidence changes, append FUSION_CONFIDENCE_UPDATED event to the immutable history.

If status transitions to FUSED, append FUSED event to history.

Persist record["confidence"] = float(confidence).

Save changes back to _THREAT_RECORDS.

Enforce history rules: Never modify, reorder, or delete existing history entries.

[MODIFY] threat_intel.py

Add confidence: Optional[float] = None to the ThreatIntelRecordResponse Pydantic model for schema consistency.

[MODIFY] worker.py

In the background loop, skip calling calculate_fusion or fuse_threat for threats whose status is ARCHIVED.

Call ThreatIntelligenceService.fuse_threat(tid, fusion_result["confidence"]) to save the score and transition status to FUSED.

3. Security Decision GRC Framework Mapping (Finding 3)

[MODIFY] security_decision_service.py

In sync_decision_recommendations, query GRC assessments using:

fw_type = assess.get("framework_type") or assess.get("framework_name") or "Framework"
fw_formatted = fw_type.replace("_", " ")

Use fw_formatted to title control recommendations dynamically, e.g., "Implement Control: ISO27001" instead of "Implement Control: Framework".

[MODIFY] security_intelligence_graph_service.py

Fix the same bug in graph synchronization: change assess.get("framework_name") to retrieve and format framework_type.

Fix the Knowledge node sync bug by changing SecurityKnowledgeService.get_all_knowledge_records() to SecurityKnowledgeService.get_all_knowledge().

4. Threat Actor Model Rename (Finding 4)

[MODIFY] threat_intel.py

Rename Pydantic model ThreatActorResponse to ThreatIntelActorResponse.

Keep ThreatActorResponse defined in threat_intelligence.py as-is.

This resolves the FastAPI schema warning cleanly with zero other side-effects since the model has no active code dependencies.

5. AI Context Completeness & Duplication Clean-up (Finding 5)

[MODIFY] ai_context_builder.py

Remove context coupling inside private helper blocks:

_build_security_program_context_block must only build program context (remove nested executive and SOC calls).

_build_global_security_program_context_block must only build global program context (remove nested executive and SOC calls).

_build_cyber_resilience_context_block must only build resilience context (remove nested SOC calls).

_build_security_operations_analytics_context_block must only build SOC performance and queue metrics (remove nested risk, compliance, knowledge, graph, decision, and fabric context calls).

Flatten context builder methods (build_asset_context, build_finding_context, build_executive_context, build_incident_context, build_case_context) to explicitly call each private helper block in order, ensuring complete coverage of Sprints 27–37 and avoiding any duplication or nested overwriting.

6. GRC Assessment Recalculation Support & Determinism (Finding 6)

[MODIFY] governance_risk_compliance_service.py

Implement recalculate_assessments(cls) following the GRC Recalculation Determinism Rule:

Recalculations are derived intelligence and identical inputs must always produce identical outputs.

Recalculation must never mutate: assessment identity, fingerprints, history ordering, or terminal states.

closed assessments are skipped or preserved in their closed terminal state.

Recalculation is read-only except for derived score updates (compliance_score, coverage_score, severity, and updated_at).

Log RECALCULATED history event only if scores actually change.

[MODIFY] worker.py

Call GovernanceRiskComplianceService.recalculate_assessments() during the GRC background task.

7. Knowledge Recalculation History Events (Finding 7)

[MODIFY] security_knowledge_service.py

Implement recalculate_knowledge(cls):

Loop over active knowledge records and store old relevance, confidence, and severity values.

Invoke update_relationships_and_scores(knowledge_id).

Compare new values to old values.

Append specific history events instead of a generic RECALCULATED event:

If relevance changes, append RELEVANCE_CHANGED event.

If confidence changes, append CONFIDENCE_CHANGED event.

If severity changes, append SEVERITY_CHANGED event.

Only emit these events if values actually change.

Ensure recommendations are preserved.

[MODIFY] worker.py

Call SecurityKnowledgeService.recalculate_knowledge() during the background knowledge task execution.

Verification Plan

Automated Tests

We will implement a comprehensive, dedicated integration test suite in test_architecture_hardening.py.

Hardening Test Cases:

Worker Isolation:

test_worker_isolation_33_to_34(): Verify failure in Sprint 33 does not prevent Sprint 34.

test_worker_isolation_33_to_35(): Verify failure in Sprint 33 does not prevent Sprint 35.

test_worker_isolation_33_to_36(): Verify failure in Sprint 33 does not prevent Sprint 36.

test_worker_isolation_33_to_37(): Verify failure in Sprint 33 does not prevent Sprint 37.

Threat Intelligence Fusion:

test_fusion_persistence(): Validate worker fusion task runs and persists FUSED status and confidence scores.

test_fusion_identity_preservation(): Ensure record identity, creation times, and historical details are preserved.

test_fusion_history_preservation(): Verify confidence changes append FUSION_CONFIDENCE_UPDATED and transitions append FUSED without mutating, reordering, or deleting past history logs.

test_fusion_terminal_state_protection(): Verify that if a threat is in a Sprint 33 terminal state (derived dynamically from ThreatStatus.terminal_states()), fusion recalculation/persistence skips it, and its confidence, status, and history remain unaltered.

Decision & Graph Mapping:

test_framework_mapping(): Verify compliance decisions map to their actual framework name (e.g. ISO27001) instead of "Framework".

test_graph_knowledge_sync(): Verify playbooks are correctly synced to graph nodes on rebuild (confirming fix of non-existent attribute bug).

AI Context Completeness:

Verify build_asset_context returns all Sprint 27–37 context keys without duplication or nested overrides.

Verify build_finding_context contains GRC, playbooks, and graph contexts.

GRC Recalculation:

Verify that score recalculation is deterministic, maps identical inputs to identical outputs, preserves identity/fingerprints/history ordering, and keeps closed assessments in their terminal state.

Knowledge Recalculation:

Verify that relevance, confidence, and severity shifts emit specific RELEVANCE_CHANGED, CONFIDENCE_CHANGED, and SEVERITY_CHANGED events respectively.

Architecture Regression Tests:

Verify that:

Identity preservation remains unchanged.

Snapshot rebuild behavior remains unchanged.

Terminal state enforcement remains unchanged.

Fingerprint stability remains unchanged.

History immutability remains unchanged.For Sprints 30, 31, 32, 33, 34, 35, 36, and 37.

Worker Execution Regression:

Verify that execution ordering in worker.py remains unchanged for Sprints 30 through 37 (except for isolation separation).

Ensure no sprint executes earlier than before, and no dependency ordering is altered.

To run:

.venv\Scripts\pytest backend/tests/integration/test_architecture_hardening.py
