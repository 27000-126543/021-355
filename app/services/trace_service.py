from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime

from app.models.models import (
    SalaryTrace, TraceType, SalaryBatch, SalaryItem, Project, Worker
)
from app.schemas.trace import (
    TraceQueryParams, SalaryTraceResponse, TraceTypeInfo,
    WorkerGroupedTimelineResponse, WorkerProjectGroup,
    WorkerMonthGroup, WorkerBatchTraceItem
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

    @staticmethod
    def get_worker_grouped_timeline(
        db: Session,
        id_card: str,
        project_code: Optional[str] = None,
        salary_month: Optional[str] = None
    ) -> WorkerGroupedTimelineResponse:
        worker = db.query(Worker).filter(Worker.id_card == id_card).first()
        worker_name = worker.name if worker else None
        worker_phone = worker.phone if worker else None

        query = db.query(SalaryItem).filter(SalaryItem.id_card == id_card)
        if project_code:
            query = query.filter(SalaryItem.project_code == project_code)
        if salary_month:
            query = query.filter(SalaryItem.salary_month == salary_month)
        items = query.order_by(SalaryItem.created_at.desc()).all()

        if not items:
            return WorkerGroupedTimelineResponse(
                message=f"未查询到身份证号 {id_card} 的发薪记录",
                id_card=id_card,
                worker_name=worker_name,
                phone=worker_phone,
                total_records=0,
                total_projects=0,
                total_months=0,
                project_groups=[]
            )

        batch_ids = [item.batch_id for item in items]
        all_batch_map = {}
        for item in items:
            if item.batch_id not in all_batch_map:
                all_batch_map[item.batch_id] = []

        all_batch_traces = db.query(SalaryTrace).filter(
            SalaryTrace.batch_id.in_(batch_ids)
        ).order_by(SalaryTrace.trace_time.asc()).all()

        per_worker_traces = db.query(SalaryTrace).filter(
            SalaryTrace.id_card == id_card
        ).order_by(SalaryTrace.trace_time.asc()).all()

        worker_trace_by_batch: Dict[int, List[SalaryTrace]] = {}
        for t in all_batch_traces:
            if t.batch_id not in worker_trace_by_batch:
                worker_trace_by_batch[t.batch_id] = []
            worker_trace_by_batch[t.batch_id].append(t)

        for t in per_worker_traces:
            if t.batch_id and t.batch_id not in worker_trace_by_batch:
                worker_trace_by_batch[t.batch_id] = []
            if t.batch_id:
                worker_trace_by_batch[t.batch_id].append(t)

        for bid in worker_trace_by_batch:
            seen_ids = set()
            unique_traces = []
            for t in worker_trace_by_batch[bid]:
                if t.id not in seen_ids:
                    seen_ids.add(t.id)
                    unique_traces.append(t)
            worker_trace_by_batch[bid] = unique_traces

        project_map = {p.project_code: p for p in db.query(Project).all()}

        project_groups_dict: Dict[str, WorkerProjectGroup] = {}
        month_set = set()

        for item in items:
            proj_code = item.project_code or "UNKNOWN"
            month = item.salary_month or "UNKNOWN"

            if proj_code not in project_groups_dict:
                proj = project_map.get(proj_code)
                project_groups_dict[proj_code] = WorkerProjectGroup(
                    project_code=proj_code,
                    project_name=proj.project_name if proj else None,
                    months=[],
                    total_count=0,
                    total_payable=0.0,
                    total_actual=0.0
                )

            proj_group = project_groups_dict[proj_code]

            month_obj = None
            for m in proj_group.months:
                if m.salary_month == month:
                    month_obj = m
                    break
            if not month_obj:
                month_obj = WorkerMonthGroup(
                    salary_month=month,
                    records=[],
                    total_count=0,
                    total_payable=0.0,
                    total_actual=0.0
                )
                proj_group.months.append(month_obj)
            month_set.add((proj_code, month))

            trace_list = []
            batch_traces = worker_trace_by_batch.get(item.batch_id, [])
            for idx, t in enumerate(sorted(batch_traces, key=lambda x: x.trace_time)):
                resp = SalaryTraceResponse.model_validate(t)
                resp.trace_type_name = TraceTypeInfo.get_name(t.trace_type)
                resp.timeline_index = idx + 1
                trace_list.append(resp)

            status_name_map = {
                "PENDING": "待处理",
                "VERIFIED": "校验通过",
                "VERIFY_FAILED": "校验失败",
                "APPROVED": "审核通过",
                "REJECTED": "审核驳回",
                "BANK_PROCESSING": "银行处理中",
                "SUCCESS": "代发成功",
                "FAILED": "代发失败",
                "REFUNDED": "已退票",
                "RETRY_SUCCESS": "重试成功",
                "RETRY_FAILED": "重试失败"
            }

            record = WorkerBatchTraceItem(
                batch_no=item.batch_no,
                salary_month=item.salary_month,
                project_code=item.project_code,
                project_name=project_map.get(item.project_code).project_name if project_map.get(item.project_code) else None,
                team_name=item.team_name,
                payable_amount=item.payable_amount,
                actual_amount=item.actual_amount,
                status=item.status.value,
                status_name=status_name_map.get(item.status.value, item.status.value),
                verify_errors=item.verify_errors,
                fail_reason=item.fail_reason,
                last_fail_reason=getattr(item, 'last_fail_reason', None),
                refund_reason=item.refund_reason,
                bank_trade_no=item.bank_trade_no,
                last_bank_trade_no=getattr(item, 'last_bank_trade_no', None),
                retry_count=item.retry_count or 0,
                created_at=item.created_at,
                traces=trace_list
            )
            month_obj.records.append(record)
            month_obj.total_count += 1
            month_obj.total_payable += item.payable_amount or 0
            month_obj.total_actual += item.actual_amount or 0

            proj_group.total_count += 1
            proj_group.total_payable += item.payable_amount or 0
            proj_group.total_actual += item.actual_amount or 0

        project_groups = list(project_groups_dict.values())
        for pg in project_groups:
            pg.months.sort(key=lambda m: m.salary_month, reverse=True)
        project_groups.sort(key=lambda p: p.project_code)

        return WorkerGroupedTimelineResponse(
            message=f"查询成功，共找到{len(items)}条记录",
            id_card=id_card,
            worker_name=worker_name,
            phone=worker_phone,
            total_records=len(items),
            total_projects=len(project_groups),
            total_months=len(month_set),
            project_groups=project_groups
        )
