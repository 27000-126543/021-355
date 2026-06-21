from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.schemas.bank import (
    BankFeedbackRequest, BankFeedbackResponse,
    BankSubmitRequest, BankSubmitResponse
)
from app.services.bank_service import BankService

router = APIRouter(prefix="/bank", tags=["银行代发系统对接"])


@router.post("/submit", response_model=BankSubmitResponse, summary="提交批次到银行代发")
async def submit_to_bank(
    request: BankSubmitRequest,
    db: Session = Depends(get_db)
):
    """
    专户系统将校验通过、审批通过的工资批次提交给银行进行代发。\n
    系统自动生成银行批次号，记录提交时间和金额笔数。
    """
    try:
        return BankService.submit_to_bank(db, request)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"提交银行失败: {str(e)}")


@router.post("/feedback", response_model=BankFeedbackResponse, summary="银行代发结果回传")
async def receive_bank_feedback(
    request: BankFeedbackRequest,
    db: Session = Depends(get_db)
):
    """
    银行完成代发后回传代发结果。\n
    支持三种状态：SUCCESS(成功)、FAILED(失败)、REFUND(退票)\n
    服务端自动：\n
    1. 更新每个工人的到账状态\n
    2. 记录失败原因和退票原因\n
    3. 更新批次整体状态(全部成功/部分成功/全部失败)\n
    4. 生成发薪轨迹供监管和项目系统查询
    """
    try:
        return BankService.process_bank_feedback(db, request)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"处理回传失败: {str(e)}")


@router.post("/retry", summary="失败明细重发")
async def retry_failed_items(
    batch_no: str = Body(..., embed=True, description="批次号"),
    id_cards: Optional[List[str]] = Body(None, description="指定重发的身份证号列表，为空则重发所有失败"),
    operator: Optional[str] = Body(None, description="操作人"),
    db: Session = Depends(get_db)
):
    """
    针对代发失败或退票的明细进行重新发放。\n
    可指定具体人员重发，也可批次内所有失败/退票人员一起重发。\n
    操作会生成失败重发轨迹记录。
    """
    try:
        result = BankService.retry_failed_items(db, batch_no, operator, id_cards)
        if not result.get("success"):
            raise HTTPException(status_code=result.get("code", 400), detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重发操作失败: {str(e)}")
