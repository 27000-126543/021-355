from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.schemas.salary import (
    SalaryBatchSubmitRequest, VerifyResultResponse,
    VerifyOnlyResponse, BatchListResponse,
    BatchDetailResponse, WorkerStatusListResponse,
    WorkerStatusQueryParams, PendingReviewListResponse,
    BatchReviewRequest, BatchReviewResponse
)
from app.services.salary_service import SalaryService

router = APIRouter(prefix="/project", tags=["项目系统对接"])


@router.post("/batch/verify-only", response_model=VerifyOnlyResponse, summary="工资批次预校验(不入库)")
async def verify_batch_only(
    request: SalaryBatchSubmitRequest,
    db: Session = Depends(get_db)
):
    """
    项目系统在正式提交前可先调用此接口进行预校验，仅返回校验结果不入库
    """
    try:
        return SalaryService.verify_batch_only(db, request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"校验失败: {str(e)}")


@router.post("/batch/submit", response_model=VerifyResultResponse, summary="提交工资批次")
async def submit_salary_batch(
    request: SalaryBatchSubmitRequest,
    db: Session = Depends(get_db)
):
    """
    项目系统提交工资批次，服务端自动完成校验并返回校验结果。\n
    需传入：工程名称、总包单位、班组、工人实名信息、应发金额、发薪月份\n
    校验问题包含：未实名、银行卡缺失、重复人员、格式错误等
    """
    try:
        return SalaryService.submit_batch(db, request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"提交失败: {str(e)}")


@router.get("/batch/list", response_model=BatchListResponse, summary="查询工资批次列表")
async def get_batch_list(
    project_code: Optional[str] = Query(None, description="项目编号"),
    salary_month: Optional[str] = Query(None, description="发薪月份 YYYY-MM"),
    batch_no: Optional[str] = Query(None, description="批次号"),
    status: Optional[str] = Query(None, description="批次状态"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    db: Session = Depends(get_db)
):
    """
    项目系统查询工资批次列表及汇总统计信息
    """
    try:
        data, total = SalaryService.get_batch_list(
            db, project_code, salary_month, batch_no, status, page, page_size
        )
        return BatchListResponse(message="查询成功", total=total, data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.get("/batch/detail", response_model=BatchDetailResponse, summary="查询批次详情(含每人到账状态)")
async def get_batch_detail(
    batch_no: str = Query(..., description="批次号"),
    db: Session = Depends(get_db)
):
    """
    项目系统查询批次详情，包含每个工人的到账状态：待处理/校验通过/审核中/银行处理中/代发成功/代发失败/已退票/重试成功等
    """
    try:
        data = SalaryService.get_batch_detail(db, batch_no)
        if not data:
            raise HTTPException(status_code=404, detail=f"批次 {batch_no} 不存在")
        return BatchDetailResponse(message="查询成功", data=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.get("/worker/status", response_model=WorkerStatusListResponse, summary="按条件查询工人到账状态")
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
    项目系统按条件查询工人工资到账状态，支持多维度组合查询
    """
    try:
        params = WorkerStatusQueryParams(
            id_card=id_card, project_code=project_code,
            salary_month=salary_month, batch_no=batch_no,
            page=page, page_size=page_size
        )
        data, total = SalaryService.query_worker_status(db, params)
        return WorkerStatusListResponse(message="查询成功", total=total, data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.get("/batch/pending-review", response_model=PendingReviewListResponse, summary="待审核批次列表")
async def get_pending_review_list(
    project_code: Optional[str] = Query(None, description="项目编号"),
    salary_month: Optional[str] = Query(None, description="发薪月份 YYYY-MM"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    db: Session = Depends(get_db)
):
    """
    专户审核人员查看待审核的工资批次列表，按提交时间倒序
    """
    try:
        data, total = SalaryService.get_pending_review_list(
            db, project_code, salary_month, page, page_size
        )
        return PendingReviewListResponse(message="查询成功", total=total, data=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")


@router.post("/batch/review", response_model=BatchReviewResponse, summary="专户审核(通过/驳回)")
async def review_batch(
    request: BatchReviewRequest,
    db: Session = Depends(get_db)
):
    """
    专户审核：审核通过或驳回，驳回时需填写驳回原因。\n
    - 审核通过后批次状态变为 APPROVED，可提交银行代发\n
    - 审核驳回后批次状态变为 REJECTED，项目系统需调整后重新提交\n
    审核人、审核时间、审核结果、审核备注都会记录在批次详情和轨迹时间线中
    """
    try:
        result = SalaryService.review_batch(
            db, request.batch_no, request.action.value,
            request.review_by, request.review_remark
        )
        if not result.get("success"):
            raise HTTPException(status_code=result.get("code", 400), detail=result.get("message"))
        return BatchReviewResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"审核失败: {str(e)}")
