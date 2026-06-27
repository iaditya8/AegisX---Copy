import uuid
from typing import Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.workflow_event_service import WorkflowEventService


class ProgramDriftService:
    @classmethod
    async def check_drift(
        cls,
        db: AsyncSession,
        scope_id: Optional[uuid.UUID] = None,
        prev_snapshot: Optional[dict] = None,
    ) -> None:
        """Compare current program metrics against baseline snapshots to identify score or indicator regressions."""
        if not prev_snapshot or "summary" not in prev_snapshot:
            return

        from src.services.security_program_snapshot_service import SecurityProgramSnapshotService

        curr_snap = await SecurityProgramSnapshotService.generate_snapshot(db, scope_id)

        curr_summary = curr_snap["summary"]
        prev_summary = prev_snapshot["summary"]

        # 1. Score decrease
        curr_score = curr_summary.get("average_program_score", 100.0)
        prev_score = prev_summary.get("average_program_score", 100.0)
        if curr_score < prev_score:
            await WorkflowEventService.emit_event(
                db=db,
                event_type="security_program.drift",
                payload={
                    "drift_type": "PROGRAM_SCORE_DECREASED",
                    "previous_score": prev_score,
                    "current_score": curr_score,
                },
            )

        # Compare individual programs
        curr_programs = curr_snap.get("programs", {})
        prev_programs = prev_snapshot.get("programs", {})

        for pid_str, prev_prog in prev_programs.items():
            curr_prog = curr_programs.get(pid_str)
            if not curr_prog:
                continue

            # Status changed
            if prev_prog["status"] != curr_prog["status"]:
                await WorkflowEventService.emit_event(
                    db=db,
                    event_type="security_program.drift",
                    payload={
                        "drift_type": "PROGRAM_STATUS_CHANGED",
                        "program_id": pid_str,
                        "previous_status": prev_prog["status"],
                        "current_status": curr_prog["status"],
                    },
                )

            # Check KPIs
            curr_kpis = {k["name"]: k for k in curr_prog.get("kpis", [])}
            prev_kpis = {k["name"]: k for k in prev_prog.get("kpis", [])}
            for kname, prev_k in prev_kpis.items():
                curr_k = curr_kpis.get(kname)
                if curr_k and prev_k["status"] == "ON_TARGET" and curr_k["status"] == "OFF_TARGET":
                    await WorkflowEventService.emit_event(
                        db=db,
                        event_type="security_program.drift",
                        payload={
                            "drift_type": "KPI_REGRESSED",
                            "program_id": pid_str,
                            "kpi_name": kname,
                        },
                    )

            # Check KRIs
            curr_kris = {k["name"]: k for k in curr_prog.get("kris", [])}
            prev_kris = {k["name"]: k for k in prev_prog.get("kris", [])}
            for kname, prev_k in prev_kris.items():
                curr_k = curr_kris.get(kname)
                if curr_k and prev_k["status"] != "CRITICAL_RISK" and curr_k["status"] == "CRITICAL_RISK":
                    await WorkflowEventService.emit_event(
                        db=db,
                        event_type="security_program.drift",
                        payload={
                            "drift_type": "KRI_REGRESSED",
                            "program_id": pid_str,
                            "kri_name": kname,
                        },
                    )
