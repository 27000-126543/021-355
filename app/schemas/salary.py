from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class WorkerSalaryItem(BaseModel):
    id_card: str = Field(..., min_length=3, max_length=64, description="身份证号")
    name: str = Field(..., max_length=64, description="姓名")
    team_name: Optional[str] = Field(None, max_length=128, description="班组")
    phone: Optional[str] = Field(None, max_length=32, description="手机号")
    bank_card_no: Optional[str] = Field(None, max_length=64, description="银行卡号")
    bank_name: Optional[str] = Field(None, max_length=128, description="开户行")
    work_days: Optional[float] = Field(0.0, description="出勤天数")
    base_salary: Optional[float] = Field(0.0, description="基本工资")
    overtime_pay: Optional[float] = Field(0.0, description="加班费")
    bonus: Optional[float] = Field(0.0, description="奖金")
    deduction: Optional[float] = Field(0.0, description="扣款")
    payable_amount: float = Field(..., gt=0, description="应发金额")


class SalaryBatchSubmitRequest(BaseModel):
    project_code: str = Field(..., max_length=64, description="项目编号")
    project_name: Optional[str] = Field(None, max_length=255, description="工程名称")
    general_contractor: Optional[str] = Field(None, max_length=255, description="总包单位")
    team_name: Optional[str] = Field(None, max_length=128, description="班组")
    salary_month: str = Field(..., pattern=r"^\d{4}-\d{2}$", description="发薪月份 YYYY-MM")
    submit_by: Optional[str] = Field(None, max_length=64, description="提交人")
    remark: Optional[str] = Field(None, description="备注")
    workers: List[WorkerSalaryItem] = Field(..., min_length=1, description="工人工资明细列表")


class VerifyErrorItem(BaseModel):
    id_card: str
    name: str
    error_type: str
    error_detail: str


class VerifyResultResponse(BaseModel):
    success: bool = True
    code: int = 200
    message: str
    batch_no: Optional[str] = None
    total_count: int = 0
    total_amount: float = 0.0
    verified_count: int = 0
    verified_amount: float = 0.0
    failed_count: int = 0
    is_passed: bool = True
    errors: List[VerifyErrorItem] = []
    verify_at: Optional[datetime] = None


class VerifyOnlyResponse(BaseModel):
    success: bool = True
    code: int = 200
    message: str
    total_count: int = 0
    total_amount: float = 0.0
    verified_count: int = 0
    verified_amount: float = 0.0
    failed_count: int = 0
    is_passed: bool = True
    errors: List[VerifyErrorItem] = []


class BatchStatusEnum(str, Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    VERIFIED = "VERIFIED"
    VERIFY_FAILED = "VERIFY_FAILED"
    REVIEWING = "REVIEWING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    BANK_SUBMITTED = "BANK_SUBMITTED"
    BANK_PROCESSING = "BANK_PROCESSING"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    ALL_SUCCESS = "ALL_SUCCESS"
    ALL_FAILED = "ALL_FAILED"
    RETRYING = "RETRYING"


class ItemStatusEnum(str, Enum):
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    VERIFY_FAILED = "VERIFY_FAILED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    BANK_PROCESSING = "BANK_PROCESSING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"
    RETRY_SUCCESS = "RETRY_SUCCESS"
    RETRY_FAILED = "RETRY_FAILED"


class SalaryItemResponse(BaseModel):
    id: int
    id_card: str
    worker_name: str
    team_name: Optional[str]
    payable_amount: float
    actual_amount: float
    bank_card_no: Optional[str]
    bank_name: Optional[str]
    phone: Optional[str]
    status: ItemStatusEnum
    status_name: Optional[str] = None
    verify_status: Optional[int] = None
    verify_errors: Optional[str]
    fail_reason: Optional[str]
    last_fail_reason: Optional[str]
    refund_reason: Optional[str]
    bank_trade_no: Optional[str]
    last_bank_trade_no: Optional[str]
    bank_success_time: Optional[datetime]
    retry_count: int
    last_retry_time: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SalaryBatchInfoResponse(BaseModel):
    id: int
    batch_no: str
    project_code: str
    project_name: Optional[str] = None
    salary_month: str
    team_name: Optional[str]
    total_count: int
    total_amount: float
    verified_count: int
    verified_amount: float
    failed_count: int
    success_count: int
    success_amount: float
    fail_count: int
    fail_amount: float
    refund_count: int
    refund_amount: float
    status: BatchStatusEnum
    status_name: Optional[str] = None
    submit_by: Optional[str]
    submit_at: Optional[datetime]
    verify_at: Optional[datetime]
    review_by: Optional[str]
    review_at: Optional[datetime]
    review_result: Optional[str]
    review_remark: Optional[str]
    approve_by: Optional[str]
    approve_at: Optional[datetime]
    bank_submit_at: Optional[datetime]
    bank_feedback_at: Optional[datetime]
    remark: Optional[str]
    items: List[SalaryItemResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BatchListResponse(BaseModel):
    success: bool = True
    code: int = 200
    message: str = "查询成功"
    total: int = 0
    data: List[SalaryBatchInfoResponse] = []


class BatchDetailResponse(BaseModel):
    success: bool = True
    code: int = 200
    message: str = "查询成功"
    data: Optional[SalaryBatchInfoResponse] = None


class WorkerStatusResponse(BaseModel):
    id_card: str
    worker_name: str
    project_code: Optional[str]
    team_name: Optional[str]
    batch_no: str
    salary_month: str
    payable_amount: float
    actual_amount: float
    status: ItemStatusEnum
    verify_errors: Optional[str]
    fail_reason: Optional[str]
    refund_reason: Optional[str]
    bank_trade_no: Optional[str]
    bank_success_time: Optional[datetime]
    retry_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WorkerStatusListResponse(BaseModel):
    success: bool = True
    code: int = 200
    message: str = "查询成功"
    total: int = 0
    data: List[WorkerStatusResponse] = []


class WorkerStatusQueryParams(BaseModel):
    id_card: Optional[str] = None
    project_code: Optional[str] = None
    salary_month: Optional[str] = None
    batch_no: Optional[str] = None
    page: int = 1
    page_size: int = 50


class ReviewActionEnum(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class BatchReviewRequest(BaseModel):
    batch_no: str = Field(..., max_length=64, description="批次号")
    action: ReviewActionEnum = Field(..., description="审核动作: APPROVED通过 / REJECTED驳回")
    review_by: Optional[str] = Field(None, max_length=64, description="审核人")
    review_remark: Optional[str] = Field(None, max_length=1000, description="审核备注/驳回原因")


class BatchReviewResponse(BaseModel):
    success: bool = True
    code: int = 200
    message: str
    batch_no: str
    old_status: str
    new_status: str
    review_by: Optional[str]
    review_at: Optional[datetime]
    review_result: Optional[str]
    review_remark: Optional[str]


class PendingReviewListResponse(BaseModel):
    success: bool = True
    code: int = 200
    message: str = "查询成功"
    total: int = 0
    data: List[SalaryBatchInfoResponse] = []


class ProjectMonthlySummaryItem(BaseModel):
    project_code: str
    project_name: Optional[str] = None
    salary_month: str
    total_batches: int = 0
    total_workers: int = 0
    total_payable_amount: float = 0.0
    total_actual_amount: float = 0.0
    pending_review_count: int = 0
    pending_review_amount: float = 0.0
    approved_count: int = 0
    approved_amount: float = 0.0
    bank_processing_count: int = 0
    bank_processing_amount: float = 0.0
    success_count: int = 0
    success_amount: float = 0.0
    failed_count: int = 0
    failed_amount: float = 0.0
    refunded_count: int = 0
    refunded_amount: float = 0.0
    retry_count: int = 0
    retry_amount: float = 0.0
    verify_failed_count: int = 0
    verify_failed_amount: float = 0.0
    rejected_count: int = 0
    rejected_amount: float = 0.0


class ProjectMonthlySummaryResponse(BaseModel):
    success: bool = True
    code: int = 200
    message: str = "查询成功"
    total: int = 0
    data: List[ProjectMonthlySummaryItem] = []

