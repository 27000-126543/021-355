from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from app.database import get_db
from app.schemas.trace import (
    TraceListResponse, TraceQueryParams,
    WorkerSalaryTimelineResponse,
    WorkerSalaryTraceDetail,
    BatchTimelineResponse,
    TraceStatisticsResponse,
    TraceStatistics,
    SalaryTraceResponse,
    TraceTypeInfo,
    TraceTypeEnum
)
from app.schemas.salary import (
    WorkerStatusListResponse, WorkerStatusResponse,
    WorkerStatusQueryParams
)
from app.services.trace_service import TraceService
from app.services.salary_service import SalaryService
from app.models.models import SalaryBatch, SalaryItem, Project

router = APIRouter(prefix="/query", tags=["监管/客服系统查询"])


@router.get("/trace", response_model=TraceListResponse, summary="查询发薪轨迹列表")
async def query_traces(
    id_card: Optional[str] = Query(None, description="身份证号"),
    project_code: Optional[str] = Query(None, description="项目编号"),
    salary_month: Optional[str] = Query(None, description="发薪月份 YYYY-MM"),
    batch_no: Optional[str] = Query(None, description="批次号"),
    trace_type: Optional[TraceTypeEnum] = Query(None, description="轨迹类型"),
    start_time: Optional[datetime] = Query(None, description="开始时间"),
    end_time: Optional[datetime] = Query(None, description="结束时间"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(50, ge=1, le=500, description="每页条数"),
    db: Session = Depends(get_db)
):
    """
    监管系统或客服系统按条件查询发薪轨迹。\n
    可查看所有操作的完整轨迹：从工资表提交→系统校验→专户审核→银行代发→失败重发的每一步。
    """
    try:
        params = TraceQueryParams(
            id_card=id_card,
            project_code=project_code,
            salary_month=salary_month,
            batch_no=batch_no,
            trace_type=trace_type,
            start_time=start_time,
            end_time=end_time,
            page=page,
            page_size=page_size
        )
        data, total = TraceService.query_traces(db, params)
        return TraceListResponse(message="查询成功", total=total, data=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.get("/worker/timeline", response_model=WorkerSalaryTimelineResponse, summary="按工人查询发薪时间线")
async def get_worker_salary_timeline(
    id_card: str = Query(..., description="身份证号"),
    project_code: Optional[str] = Query(None, description="项目编号"),
    salary_month: Optional[str] = Query(None, description="发薪月份 YYYY-MM"),
    db: Session = Depends(get_db)
):
    """
    按身份证号查询单个工人的完整发薪轨迹（用于投诉处理和热线咨询）。\n
    返回工人基本信息+当前工资状态+每一步操作时间线，便于客服向工人清晰解释当前处于哪个环节、因何原因失败或退票。
    """
    try:
        if not id_card:
            raise HTTPException(status_code=400, detail="请提供身份证号")

        status_params = WorkerStatusQueryParams(
            id_card=id_card,
            project_code=project_code,
            salary_month=salary_month,
            page=1,
            page_size=100
        )
        items, _ = SalaryService.query_worker_status(db, status_params)

        if not items:
            return WorkerSalaryTimelineResponse(
                message=f"未查询到身份证号 {id_card} 的发薪记录",
                worker_info=None,
                total_records=0
            )

        latest: WorkerStatusResponse = items[0]

        project = db.query(Project).filter(
            Project.project_code == latest.project_code
        ).first() if latest.project_code else None

        worker_info = WorkerSalaryTraceDetail(
            id_card=latest.id_card,
            worker_name=latest.worker_name,
            project_code=latest.project_code,
            project_name=project.project_name if project else None,
            team_name=latest.team_name,
            batch_no=latest.batch_no,
            salary_month=latest.salary_month,
            payable_amount=latest.payable_amount,
            actual_amount=latest.actual_amount,
            current_status=latest.status.value,
            current_status_name={
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
            }.get(latest.status.value, latest.status.value),
            verify_errors=latest.verify_errors,
            fail_reason=latest.fail_reason,
            refund_reason=latest.refund_reason,
            traces=[]
        )

        traces = TraceService.get_traces_by_id_card(
            db, id_card, project_code, salary_month, limit=200
        )
        worker_info.traces = traces

        return WorkerSalaryTimelineResponse(
            message=f"查询成功，共找到{len(items)}条发薪记录",
            worker_info=worker_info,
            total_records=len(items)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.get("/batch/timeline", response_model=BatchTimelineResponse, summary="按批次查询发薪时间线")
async def get_batch_timeline(
    batch_no: str = Query(..., description="批次号"),
    db: Session = Depends(get_db)
):
    """
    按批次号查询整批工资的处理进度时间线。\n
    监管人员可查看批次从提交到最终完成的每一步操作时间、操作人、状态变更详情。
    """
    try:
        batch = db.query(SalaryBatch).filter(SalaryBatch.batch_no == batch_no).first()
        if not batch:
            raise HTTPException(status_code=404, detail=f"批次 {batch_no} 不存在")

        traces = TraceService.get_traces_by_batch(db, batch_id=batch.id)

        status_name_map = {
            "DRAFT": "草稿",
            "SUBMITTED": "已提交",
            "VERIFIED": "校验通过",
            "VERIFY_FAILED": "校验失败",
            "REVIEWING": "审核中",
            "APPROVED": "专户审核通过",
            "REJECTED": "专户审核驳回",
            "BANK_SUBMITTED": "已提交银行",
            "BANK_PROCESSING": "银行处理中",
            "PARTIAL_SUCCESS": "部分成功",
            "ALL_SUCCESS": "全部成功",
            "ALL_FAILED": "全部失败",
            "RETRYING": "重试中"
        }

        return BatchTimelineResponse(
            message="查询成功",
            batch_no=batch.batch_no,
            project_code=batch.project_code,
            salary_month=batch.salary_month,
            current_status=batch.status.value,
            current_status_name=status_name_map.get(batch.status.value, batch.status.value),
            total_count=batch.total_count,
            total_amount=batch.total_amount,
            success_count=batch.success_count,
            fail_count=batch.fail_count,
            refund_count=batch.refund_count,
            traces=traces,
            total_traces=len(traces)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.get("/statistics", response_model=TraceStatisticsResponse, summary="轨迹统计概览")
async def get_trace_statistics(
    project_code: Optional[str] = Query(None, description="项目编号"),
    salary_month: Optional[str] = Query(None, description="发薪月份 YYYY-MM"),
    start_time: Optional[datetime] = Query(None, description="开始时间"),
    end_time: Optional[datetime] = Query(None, description="结束时间"),
    db: Session = Depends(get_db)
):
    """
    查询指定条件范围内的发薪统计概览。\n
    包含：提交批次、校验通过率、专户审批、银行代发成功/失败/退票/重发等各环节数量统计。
    """
    try:
        stats_dict = TraceService.get_statistics(
            db, project_code, salary_month, start_time, end_time
        )
        return TraceStatisticsResponse(
            message="统计查询成功",
            statistics=TraceStatistics(**stats_dict)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"统计查询失败: {str(e)}")


@router.get("/worker/status", response_model=WorkerStatusListResponse, summary="工人到账状态查询(客服热线用)")
async def query_worker_status(
    id_card: Optional[str] = Query(None, description="身份证号"),
    project_code: Optional[str] = Query(None, description="项目编号"),
    salary_month: Optional[str] = Query(None, description="发薪月份 YYYY-MM"),
    batch_no: Optional[str] = Query(None, description="批次号"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(50, ge=1, le=200, description="每页条数"),
    db: Session = Depends(get_db)
):
    """
    客服热线处理工资投诉时查询工人到账状态：\n
    - 按身份证号查：查该工人所有项目所有月份的发薪记录\n
    - 按项目+月份查：该项目某月所有工人到账情况\n
    - 按批次号查：该批次内所有工人到账情况
    """
    try:
        if not any([id_card, project_code, salary_month, batch_no]):
            raise HTTPException(status_code=400, detail="请至少提供一个查询条件：身份证号/项目编号/发薪月份/批次号")

        params = WorkerStatusQueryParams(
            id_card=id_card, project_code=project_code,
            salary_month=salary_month, batch_no=batch_no,
            page=page, page_size=page_size
        )
        data, total = SalaryService.query_worker_status(db, params)
        return WorkerStatusListResponse(message="查询成功", total=total, data=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")
