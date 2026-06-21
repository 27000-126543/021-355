from pydantic import BaseModel, Field
from typing import List, Optional, Any
from datetime import datetime
from enum import Enum


class TraceTypeEnum(str, Enum):
    BATCH_SUBMIT = "BATCH_SUBMIT"
    BATCH_VERIFY = "BATCH_VERIFY"
    BATCH_REVIEW = "BATCH_REVIEW"
    BATCH_APPROVE = "BATCH_APPROVE"
    BATCH_REJECT = "BATCH_REJECT"
    BANK_SUBMIT = "BANK_SUBMIT"
    BANK_FEEDBACK = "BANK_FEEDBACK"
    BANK_REFUND = "BANK_REFUND"
    ITEM_RETRY = "ITEM_RETRY"
    STATUS_SYNC = "STATUS_SYNC"


class TraceTypeInfo:
    type_info = {
        TraceTypeEnum.BATCH_SUBMIT: {"name": "工资表提交", "color": "blue", "desc": "项目系统提交工资表"},
        TraceTypeEnum.BATCH_VERIFY: {"name": "系统校验", "color": "cyan", "desc": "专户服务校验工人信息"},
        TraceTypeEnum.BATCH_REVIEW: {"name": "人工审核", "color": "orange", "desc": "管理人员审核工资表"},
        TraceTypeEnum.BATCH_APPROVE: {"name": "专户审核通过", "color": "green", "desc": "专户审批通过，待银行代发"},
        TraceTypeEnum.BATCH_REJECT: {"name": "专户审核驳回", "color": "red", "desc": "专户审批不通过"},
        TraceTypeEnum.BANK_SUBMIT: {"name": "银行代发提交", "color": "purple", "desc": "提交给银行进行代发"},
        TraceTypeEnum.BANK_FEEDBACK: {"name": "银行代发回传", "color": "teal", "desc": "银行返回代发结果"},
        TraceTypeEnum.BANK_REFUND: {"name": "退票处理", "color": "orange", "desc": "银行退票处理完成"},
        TraceTypeEnum.ITEM_RETRY: {"name": "失败重发", "color": "indigo", "desc": "对失败明细进行重试发放"},
        TraceTypeEnum.STATUS_SYNC: {"name": "状态同步", "color": "gray", "desc": "状态同步至监管或项目系统"},
    }

    @classmethod
    def get_name(cls, trace_type: str) -> str:
        return cls.type_info.get(trace_type, {}).get("name", "未知操作")

    @classmethod
    def get_desc(cls, trace_type: str) -> str:
        return cls.type_info.get(trace_type, {}).get("desc", "")

    @classmethod
    def get_color(cls, trace_type: str) -> str:
        return cls.type_info.get(trace_type, {}).get("color", "gray")


class SalaryTraceResponse(BaseModel):
    id: int
    batch_id: Optional[int]
    batch_no: Optional[str]
    project_code: Optional[str]
    salary_month: Optional[str]
    id_card: Optional[str]
    trace_type: TraceTypeEnum
    trace_type_name: str = ""
    trace_title: Optional[str]
    from_status: Optional[str]
    to_status: Optional[str]
    operator: Optional[str]
    operator_role: Optional[str]
    detail: Optional[str]
    remark: Optional[str]
    trace_time: datetime
    timeline_index: Optional[int] = None

    class Config:
        from_attributes = True


class TraceQueryParams(BaseModel):
    id_card: Optional[str] = Field(None, description="身份证号")
    project_code: Optional[str] = Field(None, description="项目编号")
    salary_month: Optional[str] = Field(None, description="发薪月份 YYYY-MM")
    batch_no: Optional[str] = Field(None, description="批次号")
    trace_type: Optional[TraceTypeEnum] = Field(None, description="轨迹类型")
    start_time: Optional[datetime] = Field(None, description="开始时间")
    end_time: Optional[datetime] = Field(None, description="结束时间")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(50, ge=1, le=500, description="每页条数")


class TraceListResponse(BaseModel):
    success: bool = True
    code: int = 200
    message: str = "查询成功"
    total: int = 0
    data: List[SalaryTraceResponse] = []


class WorkerSalaryTraceDetail(BaseModel):
    id_card: str
    worker_name: Optional[str]
    project_code: Optional[str]
    project_name: Optional[str]
    team_name: Optional[str]
    batch_no: Optional[str]
    salary_month: Optional[str]
    payable_amount: Optional[float]
    actual_amount: Optional[float]
    current_status: Optional[str]
    current_status_name: Optional[str]
    verify_errors: Optional[str]
    fail_reason: Optional[str]
    refund_reason: Optional[str]
    traces: List[SalaryTraceResponse] = []


class WorkerSalaryTimelineResponse(BaseModel):
    success: bool = True
    code: int = 200
    message: str = "查询成功"
    worker_info: Optional[WorkerSalaryTraceDetail] = None
    total_records: int = 0


class BatchTimelineResponse(BaseModel):
    success: bool = True
    code: int = 200
    message: str = "查询成功"
    batch_no: str
    project_code: str
    salary_month: str
    current_status: Optional[str]
    current_status_name: Optional[str]
    total_count: int
    total_amount: float
    success_count: int
    fail_count: int
    refund_count: int
    traces: List[SalaryTraceResponse] = []
    total_traces: int = 0


class TraceStatistics(BaseModel):
    total_submit: int = 0
    total_verify_pass: int = 0
    total_verify_fail: int = 0
    total_approve: int = 0
    total_bank_submit: int = 0
    total_bank_success: int = 0
    total_bank_fail: int = 0
    total_refund: int = 0
    total_retry: int = 0


class TraceStatisticsResponse(BaseModel):
    success: bool = True
    code: int = 200
    message: str = "查询成功"
    statistics: TraceStatistics = TraceStatistics()


class WorkerBatchTraceItem(BaseModel):
    batch_no: str
    salary_month: str
    project_code: Optional[str]
    project_name: Optional[str]
    team_name: Optional[str]
    payable_amount: Optional[float]
    actual_amount: Optional[float]
    status: Optional[str]
    status_name: Optional[str]
    verify_errors: Optional[str]
    fail_reason: Optional[str]
    last_fail_reason: Optional[str]
    refund_reason: Optional[str]
    bank_trade_no: Optional[str]
    last_bank_trade_no: Optional[str]
    retry_count: int
    created_at: Optional[datetime]
    traces: List[SalaryTraceResponse] = []


class WorkerMonthGroup(BaseModel):
    salary_month: str
    records: List[WorkerBatchTraceItem] = []
    total_count: int = 0
    total_payable: float = 0.0
    total_actual: float = 0.0


class WorkerProjectGroup(BaseModel):
    project_code: str
    project_name: Optional[str]
    months: List[WorkerMonthGroup] = []
    total_count: int = 0
    total_payable: float = 0.0
    total_actual: float = 0.0


class WorkerGroupedTimelineResponse(BaseModel):
    success: bool = True
    code: int = 200
    message: str = "查询成功"
    id_card: Optional[str]
    worker_name: Optional[str]
    phone: Optional[str]
    total_records: int = 0
    total_projects: int = 0
    total_months: int = 0
    project_groups: List[WorkerProjectGroup] = []
