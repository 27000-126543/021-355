from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum


class TradeStatusEnum(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    REFUND = "REFUND"


class BankFeedbackDetail(BaseModel):
    id_card: str = Field(..., max_length=32, description="身份证号")
    worker_name: Optional[str] = Field(None, max_length=64, description="姓名")
    bank_card_no: Optional[str] = Field(None, max_length=64, description="银行卡号")
    amount: Optional[float] = Field(0.0, description="代发金额")
    trade_status: TradeStatusEnum = Field(..., description="交易状态: SUCCESS/FAILED/REFUND")
    bank_trade_no: Optional[str] = Field(None, max_length=128, description="银行流水号")
    fail_code: Optional[str] = Field(None, max_length=64, description="失败代码")
    fail_reason: Optional[str] = Field(None, max_length=512, description="失败原因")
    refund_reason: Optional[str] = Field(None, max_length=512, description="退票原因")
    trade_time: Optional[datetime] = Field(None, description="交易时间")


class BankFeedbackRequest(BaseModel):
    batch_no: str = Field(..., max_length=64, description="工资批次号")
    bank_batch_no: str = Field(..., max_length=128, description="银行批次号")
    bank_code: Optional[str] = Field(None, max_length=64, description="银行编码")
    bank_name: Optional[str] = Field(None, max_length=128, description="银行名称")
    feedback_at: Optional[datetime] = Field(None, description="回传时间")
    remark: Optional[str] = Field(None, description="备注")
    details: List[BankFeedbackDetail] = Field(..., min_length=1, description="交易明细列表")


class BankFeedbackResultItem(BaseModel):
    id_card: str
    worker_name: Optional[str]
    trade_status: str
    updated: bool
    message: str


class BankFeedbackResponse(BaseModel):
    success: bool = True
    code: int = 200
    message: str
    batch_no: str
    bank_batch_no: str
    processed_count: int = 0
    success_count: int = 0
    failed_count: int = 0
    refund_count: int = 0
    batch_status: Optional[str] = None
    results: List[BankFeedbackResultItem] = []
    feedback_at: Optional[datetime] = None


class BankSubmitRequest(BaseModel):
    batch_no: str = Field(..., max_length=64, description="工资批次号")
    bank_code: Optional[str] = Field(None, max_length=64, description="银行编码")
    bank_name: Optional[str] = Field(None, max_length=128, description="银行名称")
    submit_at: Optional[datetime] = Field(None, description="提交时间")
    operator: Optional[str] = Field(None, max_length=64, description="操作人")


class BankSubmitResponse(BaseModel):
    success: bool = True
    code: int = 200
    message: str
    batch_no: str
    bank_batch_no: str
    submit_count: int = 0
    submit_amount: float = 0.0
    submit_at: Optional[datetime] = None
