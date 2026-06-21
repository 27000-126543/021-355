from typing import Optional, List
from sqlalchemy.orm import Session
from datetime import datetime

from app.models.models import (
    SalaryTrace, TraceType, SalaryBatch, SalaryItem
)
from app.schemas.trace import (
    TraceQueryParams, SalaryTraceResponse, TraceTypeInfo
)


class TraceService:
    @staticmethod
    def add_trace(
        db: Session,
        trace_type: TraceType,
        batch: Optional[SalaryBatch] = None,
        batch_id: Optional[int] = None,
        batch_no: Optional[str] = None,
        project_code: Optional[str] = None,
        salary_month: Optional[str] = None,
        id_card: Optional[str] = None,
        trace_title: Optional[str] = None,
        from_status: Optional[str] = None,
        to_status: Optional[str] = None,
        operator: Optional[str] = None,
        operator_role: Optional[str] = None,
        detail: Optional[str] = None,
        remark: Optional[str] = None,
        trace_time: Optional[datetime] = None
    ) -> SalaryTrace:
        if batch is not None:
            batch_id = batch.id
            batch_no = batch.batch_no
            project_code = batch.project_code
            salary_month = batch.salary_month

        trace = SalaryTrace(
            batch_id=batch_id,
            batch_no=batch_no,
            project_code=project_code,
            salary_month=salary_month,
            id_card=id_card,
            trace_type=trace_type,
            trace_title=trace_title or TraceTypeInfo.get_name(trace_type),
            from_status=from_status,
            to_status=to_status,
            operator=operator,
            operator_role=operator_role,
            detail=detail,
            remark=remark,
            trace_time=trace_time or datetime.now()
        )
        db.add(trace)
        db.flush()
        return trace

    @staticmethod
    def query_traces(
        db: Session,
        params: TraceQueryParams
    ) -> tuple[List[SalaryTraceResponse], int]:
        query = db.query(SalaryTrace)

        if params.id_card:
            batch_ids = db.query(SalaryItem.batch_id).filter(
                SalaryItem.id_card == params.id_card
            ).distinct().all()
            batch_ids = [bid[0] for bid in batch_ids]
            query = query.filter(
                (SalaryTrace.id_card == params.id_card) |
                (SalaryTrace.batch_id.in_(batch_ids))
            )

        if params.project_code:
            query = query.filter(SalaryTrace.project_code == params.project_code)

        if params.salary_month:
            query = query.filter(SalaryTrace.salary_month == params.salary_month)

        if params.batch_no:
            query = query.filter(SalaryTrace.batch_no == params.batch_no)

        if params.trace_type:
            query = query.filter(SalaryTrace.trace_type == params.trace_type)

        if params.start_time:
            query = query.filter(SalaryTrace.trace_time >= params.start_time)

        if params.end_time:
            query = query.filter(SalaryTrace.trace_time <= params.end_time)

        total = query.count()

        query = query.order_by(SalaryTrace.trace_time.desc(), SalaryTrace.id.desc())

        offset = (params.page - 1) * params.page_size
        query = query.offset(offset).limit(params.page_size)

        traces = query.all()

        responses = []
        for idx, trace in enumerate(traces):
            resp = SalaryTraceResponse.model_validate(trace)
            resp.trace_type_name = TraceTypeInfo.get_name(trace.trace_type)
            resp.timeline_index = idx + 1
            responses.append(resp)

        return responses, total

    @staticmethod
    def get_traces_by_id_card(
        db: Session,
        id_card: str,
        project_code: Optional[str] = None,
        salary_month: Optional[str] = None,
        limit: int = 100
    ) -> List[SalaryTraceResponse]:
        batch_ids = db.query(SalaryItem.batch_id).filter(
            SalaryItem.id_card == id_card
        ).distinct().all()
        batch_ids = [bid[0] for bid in batch_ids]

        query = db.query(SalaryTrace).filter(
            (SalaryTrace.id_card == id_card) |
            (SalaryTrace.batch_id.in_(batch_ids) if batch_ids else SalaryTrace.id == -1)
        )

        if project_code:
            query = query.filter(SalaryTrace.project_code == project_code)
        if salary_month:
            query = query.filter(SalaryTrace.salary_month == salary_month)

        query = query.order_by(SalaryTrace.trace_time.desc()).limit(limit)
        traces = query.all()

        responses = []
        for idx, trace in enumerate(traces):
            resp = SalaryTraceResponse.model_validate(trace)
            resp.trace_type_name = TraceTypeInfo.get_name(trace.trace_type)
            resp.timeline_index = idx + 1
            responses.append(resp)

        return responses

    @staticmethod
    def get_traces_by_batch(
        db: Session,
        batch_id: Optional[int] = None,
        batch_no: Optional[str] = None
    ) -> List[SalaryTraceResponse]:
        query = db.query(SalaryTrace)
        if batch_id:
            query = query.filter(SalaryTrace.batch_id == batch_id)
        elif batch_no:
            query = query.filter(SalaryTrace.batch_no == batch_no)
        else:
            return []

        query = query.order_by(SalaryTrace.trace_time.asc(), SalaryTrace.id.asc())
        traces = query.all()

        responses = []
        for idx, trace in enumerate(traces):
            resp = SalaryTraceResponse.model_validate(trace)
            resp.trace_type_name = TraceTypeInfo.get_name(trace.trace_type)
            resp.timeline_index = idx + 1
            responses.append(resp)

        return responses

    @staticmethod
    def get_statistics(
        db: Session,
        project_code: Optional[str] = None,
        salary_month: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> dict:
        from app.schemas.trace import TraceStatistics

        query = db.query(SalaryTrace)

        if project_code:
            query = query.filter(SalaryTrace.project_code == project_code)
        if salary_month:
            query = query.filter(SalaryTrace.salary_month == salary_month)
        if start_time:
            query = query.filter(SalaryTrace.trace_time >= start_time)
        if end_time:
            query = query.filter(SalaryTrace.trace_time <= end_time)

        traces = query.all()

        stats = TraceStatistics()
        for trace in traces:
            if trace.trace_type == TraceType.BATCH_SUBMIT:
                stats.total_submit += 1
            elif trace.trace_type == TraceType.BATCH_VERIFY:
                if "通过" in (trace.trace_title or "") or "校验" in (trace.detail or ""):
                    stats.total_verify_pass += 1
            elif trace.trace_type == TraceType.BATCH_APPROVE:
                stats.total_approve += 1
            elif trace.trace_type == TraceType.BANK_SUBMIT:
                stats.total_bank_submit += 1
            elif trace.trace_type == TraceType.BANK_FEEDBACK:
                detail = trace.detail or ""
                if "成功" in detail:
                    stats.total_bank_success += 1
                if "失败" in detail:
                    stats.total_bank_fail += 1
            elif trace.trace_type == TraceType.BANK_REFUND:
                stats.total_refund += 1
            elif trace.trace_type == TraceType.ITEM_RETRY:
                stats.total_retry += 1

        failed_batches = db.query(SalaryBatch).filter(
            SalaryBatch.status == "VERIFY_FAILED"
        )
        if project_code:
            failed_batches = failed_batches.filter(SalaryBatch.project_code == project_code)
        if salary_month:
            failed_batches = failed_batches.filter(SalaryBatch.salary_month == salary_month)
        stats.total_verify_fail = failed_batches.count()

        return stats
