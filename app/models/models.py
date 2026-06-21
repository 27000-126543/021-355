from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum, Text
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.database import Base


class ProjectStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    SUSPENDED = "SUSPENDED"


class BatchStatus(str, enum.Enum):
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


class ItemStatus(str, enum.Enum):
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


class TraceType(str, enum.Enum):
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


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    project_code = Column(String(64), unique=True, index=True, nullable=False, comment="项目编号")
    project_name = Column(String(255), nullable=False, comment="工程名称")
    general_contractor = Column(String(255), nullable=False, comment="总包单位")
    general_contractor_code = Column(String(64), comment="总包单位统一社会信用代码")
    special_account_no = Column(String(64), comment="工资专户账号")
    special_account_bank = Column(String(128), comment="专户开户行")
    status = Column(Enum(ProjectStatus), default=ProjectStatus.ACTIVE, comment="项目状态")
    address = Column(String(512), comment="项目地址")
    manager = Column(String(64), comment="项目负责人")
    manager_phone = Column(String(32), comment="负责人电话")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    batches = relationship("SalaryBatch", back_populates="project")


class Worker(Base):
    __tablename__ = "workers"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    id_card = Column(String(32), unique=True, index=True, nullable=False, comment="身份证号")
    name = Column(String(64), nullable=False, comment="姓名")
    gender = Column(String(8), comment="性别")
    phone = Column(String(32), comment="手机号")
    id_card_verified = Column(Integer, default=0, comment="实名认证状态: 0未认证 1已认证 2认证失败")
    realname_verified_at = Column(DateTime, comment="实名认证时间")
    bank_card_no = Column(String(64), comment="银行卡号")
    bank_name = Column(String(128), comment="开户行")
    bank_card_verified = Column(Integer, default=0, comment="银行卡验证状态: 0未验证 1已验证 2验证失败")
    team_name = Column(String(128), comment="所属班组")
    project_code = Column(String(64), index=True, comment="所属项目编号")
    work_type = Column(String(64), comment="工种")
    entry_date = Column(DateTime, comment="进场日期")
    exit_date = Column(DateTime, comment="退场日期")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")


class SalaryBatch(Base):
    __tablename__ = "salary_batches"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    batch_no = Column(String(64), unique=True, index=True, nullable=False, comment="批次号")
    project_code = Column(String(64), ForeignKey("projects.project_code"), nullable=False, index=True, comment="项目编号")
    salary_month = Column(String(16), nullable=False, index=True, comment="发薪月份 YYYY-MM")
    team_name = Column(String(128), comment="班组")
    total_count = Column(Integer, default=0, comment="总人数")
    total_amount = Column(Float, default=0.0, comment="总金额")
    verified_count = Column(Integer, default=0, comment="校验通过人数")
    verified_amount = Column(Float, default=0.0, comment="校验通过金额")
    failed_count = Column(Integer, default=0, comment="校验失败人数")
    success_count = Column(Integer, default=0, comment="代发成功人数")
    success_amount = Column(Float, default=0.0, comment="代发成功金额")
    fail_count = Column(Integer, default=0, comment="代发失败人数")
    fail_amount = Column(Float, default=0.0, comment="代发失败金额")
    refund_count = Column(Integer, default=0, comment="退票人数")
    refund_amount = Column(Float, default=0.0, comment="退票金额")
    status = Column(Enum(BatchStatus), default=BatchStatus.DRAFT, comment="批次状态")
    submit_by = Column(String(64), comment="提交人")
    submit_at = Column(DateTime, comment="提交时间")
    verify_at = Column(DateTime, comment="校验时间")
    review_by = Column(String(64), comment="审核人")
    review_at = Column(DateTime, comment="审核时间")
    review_result = Column(String(32), comment="审核结果: APPROVED/REJECTED")
    review_remark = Column(Text, comment="审核备注/驳回原因")
    approve_by = Column(String(64), comment="专户审批人")
    approve_at = Column(DateTime, comment="专户审批时间")
    bank_submit_at = Column(DateTime, comment="提交银行时间")
    bank_feedback_at = Column(DateTime, comment="银行回传时间")
    remark = Column(Text, comment="备注")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    project = relationship("Project", back_populates="batches")
    items = relationship("SalaryItem", back_populates="batch", cascade="all, delete-orphan")
    traces = relationship("SalaryTrace", back_populates="batch", cascade="all, delete-orphan")
    bank_records = relationship("BankDisbursement", back_populates="batch", cascade="all, delete-orphan")


class SalaryItem(Base):
    __tablename__ = "salary_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    batch_id = Column(Integer, ForeignKey("salary_batches.id"), nullable=False, index=True, comment="批次ID")
    batch_no = Column(String(64), index=True, comment="批次号")
    project_code = Column(String(64), index=True, comment="项目编号")
    salary_month = Column(String(16), index=True, comment="发薪月份")
    id_card = Column(String(32), nullable=False, index=True, comment="身份证号")
    worker_name = Column(String(64), nullable=False, comment="姓名")
    team_name = Column(String(128), comment="班组")
    work_days = Column(Float, default=0.0, comment="出勤天数")
    base_salary = Column(Float, default=0.0, comment="基本工资")
    overtime_pay = Column(Float, default=0.0, comment="加班费")
    bonus = Column(Float, default=0.0, comment="奖金")
    deduction = Column(Float, default=0.0, comment="扣款")
    payable_amount = Column(Float, nullable=False, default=0.0, comment="应发金额")
    actual_amount = Column(Float, default=0.0, comment="实发金额")
    bank_card_no = Column(String(64), comment="银行卡号")
    bank_name = Column(String(128), comment="开户行")
    phone = Column(String(32), comment="手机号")
    verify_status = Column(Integer, default=0, comment="校验状态: 0未校验 1通过 2失败")
    verify_errors = Column(Text, comment="校验错误信息")
    status = Column(Enum(ItemStatus), default=ItemStatus.PENDING, comment="明细状态")
    fail_reason = Column(String(512), comment="失败原因")
    last_fail_reason = Column(String(512), comment="上次失败原因(重发前保存)")
    bank_trade_no = Column(String(128), comment="银行交易流水号")
    last_bank_trade_no = Column(String(128), comment="上次银行流水号(重发前保存)")
    bank_success_time = Column(DateTime, comment="银行成功时间")
    refund_reason = Column(String(512), comment="退票原因")
    refund_time = Column(DateTime, comment="退票时间")
    retry_count = Column(Integer, default=0, comment="重试次数")
    last_retry_time = Column(DateTime, comment="最后重试时间")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    batch = relationship("SalaryBatch", back_populates="items")


class BankDisbursement(Base):
    __tablename__ = "bank_disbursements"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    batch_id = Column(Integer, ForeignKey("salary_batches.id"), nullable=False, index=True, comment="批次ID")
    batch_no = Column(String(64), index=True, comment="批次号")
    bank_batch_no = Column(String(128), comment="银行批次号")
    bank_code = Column(String(64), comment="银行编码")
    bank_name = Column(String(128), comment="银行名称")
    submit_count = Column(Integer, default=0, comment="提交笔数")
    submit_amount = Column(Float, default=0.0, comment="提交金额")
    feedback_count = Column(Integer, default=0, comment="回传笔数")
    success_count = Column(Integer, default=0, comment="成功笔数")
    success_amount = Column(Float, default=0.0, comment="成功金额")
    failed_count = Column(Integer, default=0, comment="失败笔数")
    failed_amount = Column(Float, default=0.0, comment="失败金额")
    refund_count = Column(Integer, default=0, comment="退票笔数")
    refund_amount = Column(Float, default=0.0, comment="退票金额")
    submit_at = Column(DateTime, comment="银行提交时间")
    feedback_at = Column(DateTime, comment="回传时间")
    status = Column(String(32), comment="代发状态")
    remark = Column(Text, comment="备注")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    batch = relationship("SalaryBatch", back_populates="bank_records")
    details = relationship("BankDisbursementDetail", back_populates="disbursement", cascade="all, delete-orphan")


class BankDisbursementDetail(Base):
    __tablename__ = "bank_disbursement_details"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    disbursement_id = Column(Integer, ForeignKey("bank_disbursements.id"), nullable=False, index=True, comment="代发记录ID")
    bank_batch_no = Column(String(128), index=True, comment="银行批次号")
    salary_item_id = Column(Integer, index=True, comment="工资明细ID")
    id_card = Column(String(32), index=True, comment="身份证号")
    worker_name = Column(String(64), comment="姓名")
    bank_card_no = Column(String(64), comment="银行卡号")
    amount = Column(Float, default=0.0, comment="代发金额")
    trade_status = Column(String(32), comment="交易状态: SUCCESS/FAILED/REFUND")
    bank_trade_no = Column(String(128), comment="银行流水号")
    fail_code = Column(String(64), comment="失败代码")
    fail_reason = Column(String(512), comment="失败原因")
    refund_reason = Column(String(512), comment="退票原因")
    trade_time = Column(DateTime, comment="交易时间")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")

    disbursement = relationship("BankDisbursement", back_populates="details")


class SalaryTrace(Base):
    __tablename__ = "salary_traces"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    batch_id = Column(Integer, ForeignKey("salary_batches.id"), index=True, comment="批次ID")
    batch_no = Column(String(64), index=True, comment="批次号")
    project_code = Column(String(64), index=True, comment="项目编号")
    salary_month = Column(String(16), index=True, comment="发薪月份")
    id_card = Column(String(32), index=True, comment="身份证号(按人员追踪时)")
    trace_type = Column(Enum(TraceType), nullable=False, comment="轨迹类型")
    trace_title = Column(String(255), comment="轨迹标题")
    from_status = Column(String(64), comment="原状态")
    to_status = Column(String(64), comment="新状态")
    operator = Column(String(64), comment="操作人")
    operator_role = Column(String(64), comment="操作人角色")
    detail = Column(Text, comment="操作详情")
    remark = Column(String(512), comment="备注")
    trace_time = Column(DateTime, default=datetime.now, comment="轨迹时间")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")

    batch = relationship("SalaryBatch", back_populates="traces")
