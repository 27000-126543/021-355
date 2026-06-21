from typing import List, Tuple, Optional, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime
import uuid
import re

from app.models.models import (
    Project, Worker, SalaryBatch, SalaryItem,
    BatchStatus, ItemStatus, TraceType
)
from app.schemas.salary import (
    SalaryBatchSubmitRequest, WorkerSalaryItem,
    VerifyResultResponse, VerifyErrorItem,
    VerifyOnlyResponse, SalaryBatchInfoResponse,
    WorkerStatusResponse, SalaryItemResponse,
    WorkerStatusQueryParams
)
from app.services.trace_service import TraceService


class SalaryService:
    @staticmethod
    def _generate_batch_no() -> str:
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        random_str = uuid.uuid4().hex[:8].upper()
        return f"SB{timestamp}{random_str}"

    @staticmethod
    def _validate_id_card(id_card: str) -> bool:
        if not id_card:
            return False
        if len(id_card) not in [15, 18]:
            return False
        if len(id_card) == 18:
            if not re.match(r'^[1-9]\d{5}(18|19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[\dXx]$', id_card):
                return False
        return True

    @staticmethod
    def _validate_bank_card(card_no: str) -> bool:
        if not card_no:
            return False
        card_no = card_no.replace(" ", "").replace("-", "")
        if not re.match(r'^\d{16,19}$', card_no):
            return False
        return True

    @staticmethod
    def verify_workers(
        workers: List[WorkerSalaryItem],
        db: Optional[Session] = None,
        project_code: Optional[str] = None
    ) -> Tuple[List[VerifyErrorItem], Dict[str, Worker]]:
        errors: List[VerifyErrorItem] = []
        id_card_set: set = set()
        name_map: Dict[str, str] = {}
        worker_db_map: Dict[str, Worker] = {}

        for worker in workers:
            error_types = []

            if not SalaryService._validate_id_card(worker.id_card):
                errors.append(VerifyErrorItem(
                    id_card=worker.id_card,
                    name=worker.name,
                    error_type="ID_CARD_INVALID",
                    error_detail="身份证号格式不正确"
                ))
                continue

            if worker.id_card in id_card_set:
                errors.append(VerifyErrorItem(
                    id_card=worker.id_card,
                    name=worker.name,
                    error_type="DUPLICATE_PERSON",
                    error_detail=f"批次内重复人员，同名同身份证号已存在"
                ))
                continue

            id_card_set.add(worker.id_card)
            name_map[worker.id_card] = worker.name

            if db is not None:
                db_worker = db.query(Worker).filter(Worker.id_card == worker.id_card).first()
                if db_worker:
                    worker_db_map[worker.id_card] = db_worker

                    if db_worker.id_card_verified != 1:
                        errors.append(VerifyErrorItem(
                            id_card=worker.id_card,
                            name=worker.name,
                            error_type="NOT_REALNAME_VERIFIED",
                            error_detail="该人员未完成实名制认证，请先在实名制平台完成实名认证"
                        ))
                        error_types.append("NOT_REALNAME_VERIFIED")

                    has_bank_card = bool(worker.bank_card_no) or bool(db_worker.bank_card_no)
                    if not has_bank_card:
                        errors.append(VerifyErrorItem(
                            id_card=worker.id_card,
                            name=worker.name,
                            error_type="BANK_CARD_MISSING",
                            error_detail="银行卡号缺失，请提供有效的工资卡账号"
                        ))
                        error_types.append("BANK_CARD_MISSING")
                    else:
                        card_to_check = worker.bank_card_no or db_worker.bank_card_no
                        if card_to_check and not SalaryService._validate_bank_card(card_to_check):
                            errors.append(VerifyErrorItem(
                                id_card=worker.id_card,
                                name=worker.name,
                                error_type="BANK_CARD_INVALID",
                                error_detail="银行卡号格式不正确"
                            ))
                            error_types.append("BANK_CARD_INVALID")
                        if card_to_check and db_worker.bank_card_verified not in [0, 1]:
                            pass
                else:
                    errors.append(VerifyErrorItem(
                        id_card=worker.id_card,
                        name=worker.name,
                        error_type="NOT_IN_REALNAME_SYSTEM",
                        error_detail="该人员不在实名制平台名单中，请先完成实名制录入和认证"
                    ))
                    error_types.append("NOT_IN_REALNAME_SYSTEM")

                    if not worker.bank_card_no:
                        errors.append(VerifyErrorItem(
                            id_card=worker.id_card,
                            name=worker.name,
                            error_type="BANK_CARD_MISSING",
                            error_detail="银行卡号缺失，请提供有效的工资卡账号"
                        ))
                        error_types.append("BANK_CARD_MISSING")
                    elif not SalaryService._validate_bank_card(worker.bank_card_no):
                        errors.append(VerifyErrorItem(
                            id_card=worker.id_card,
                            name=worker.name,
                            error_type="BANK_CARD_INVALID",
                            error_detail="银行卡号格式不正确"
                        ))
                        error_types.append("BANK_CARD_INVALID")
            else:
                if not worker.bank_card_no:
                    errors.append(VerifyErrorItem(
                        id_card=worker.id_card,
                        name=worker.name,
                        error_type="BANK_CARD_MISSING",
                        error_detail="银行卡号缺失"
                    ))
                    error_types.append("BANK_CARD_MISSING")
                elif not SalaryService._validate_bank_card(worker.bank_card_no):
                    errors.append(VerifyErrorItem(
                        id_card=worker.id_card,
                        name=worker.name,
                        error_type="BANK_CARD_INVALID",
                        error_detail="银行卡号格式不正确"
                    ))
                    error_types.append("BANK_CARD_INVALID")

        return errors, worker_db_map

    @staticmethod
    def verify_batch_only(
        db: Session,
        request: SalaryBatchSubmitRequest
    ) -> VerifyOnlyResponse:
        errors, _ = SalaryService.verify_workers(request.workers, db, request.project_code)

        total_count = len(request.workers)
        total_amount = sum(w.payable_amount for w in request.workers)
        error_id_cards = set(e.id_card for e in errors)
        verified_count = total_count - len(error_id_cards)
        verified_amount = sum(
            w.payable_amount for w in request.workers
            if w.id_card not in error_id_cards
        )

        return VerifyOnlyResponse(
            message="工资批次预校验完成" if not errors else "工资批次预校验发现问题",
            total_count=total_count,
            total_amount=total_amount,
            verified_count=verified_count,
            verified_amount=verified_amount,
            failed_count=len(error_id_cards),
            is_passed=len(errors) == 0,
            errors=errors
        )

    @staticmethod
    def submit_batch(
        db: Session,
        request: SalaryBatchSubmitRequest
    ) -> VerifyResultResponse:
        project = db.query(Project).filter(Project.project_code == request.project_code).first()
        if not project:
            project = Project(
                project_code=request.project_code,
                project_name=request.project_name or request.project_code,
                general_contractor=request.general_contractor or "未知",
            )
            db.add(project)
            db.flush()

        batch_no = SalaryService._generate_batch_no()

        errors, worker_db_map = SalaryService.verify_workers(request.workers, db, request.project_code)

        error_id_cards = set(e.id_card for e in errors)
        error_map: Dict[str, List[str]] = {}
        for e in errors:
            if e.id_card not in error_map:
                error_map[e.id_card] = []
            error_map[e.id_card].append(f"{e.error_type}:{e.error_detail}")

        total_count = len(request.workers)
        total_amount = sum(w.payable_amount for w in request.workers)
        verified_count = total_count - len(error_id_cards)
        verified_amount = sum(
            w.payable_amount for w in request.workers
            if w.id_card not in error_id_cards
        )

        batch = SalaryBatch(
            batch_no=batch_no,
            project_code=request.project_code,
            salary_month=request.salary_month,
            team_name=request.team_name,
            total_count=total_count,
            total_amount=total_amount,
            verified_count=verified_count,
            verified_amount=verified_amount,
            failed_count=len(error_id_cards),
            status=BatchStatus.REVIEWING if len(errors) == 0 else BatchStatus.VERIFY_FAILED,
            submit_by=request.submit_by,
            submit_at=datetime.now(),
            verify_at=datetime.now(),
            remark=request.remark
        )
        db.add(batch)
        db.flush()

        for worker in request.workers:
            db_worker = worker_db_map.get(worker.id_card)
            bank_card_no = worker.bank_card_no or (db_worker.bank_card_no if db_worker else None)
            bank_name = worker.bank_name or (db_worker.bank_name if db_worker else None)
            phone = worker.phone or (db_worker.phone if db_worker else None)

            is_verified = worker.id_card not in error_id_cards
            verify_errors_str = "; ".join(error_map.get(worker.id_card, []))

            item = SalaryItem(
                batch_id=batch.id,
                batch_no=batch_no,
                project_code=request.project_code,
                salary_month=request.salary_month,
                id_card=worker.id_card,
                worker_name=worker.name,
                team_name=worker.team_name or request.team_name,
                work_days=worker.work_days,
                base_salary=worker.base_salary,
                overtime_pay=worker.overtime_pay,
                bonus=worker.bonus,
                deduction=worker.deduction,
                payable_amount=worker.payable_amount,
                actual_amount=worker.payable_amount if is_verified else 0.0,
                bank_card_no=bank_card_no,
                bank_name=bank_name,
                phone=phone,
                verify_status=1 if is_verified else 2,
                verify_errors=verify_errors_str if verify_errors_str else None,
                status=ItemStatus.VERIFIED if is_verified else ItemStatus.VERIFY_FAILED
            )
            db.add(item)

        db.flush()

        TraceService.add_trace(
            db=db,
            trace_type=TraceType.BATCH_SUBMIT,
            batch=batch,
            from_status=None,
            to_status=BatchStatus.SUBMITTED.value,
            operator=request.submit_by,
            operator_role="PROJECT_SYSTEM",
            detail=f"项目系统提交工资批次：{total_count}人，总金额{total_amount:.2f}元",
            remark=f"工程：{project.project_name}，总包：{project.general_contractor}"
        )

        verify_detail = (f"校验通过：{verified_count}人，金额{verified_amount:.2f}元；"
                        f"校验失败：{len(error_id_cards)}人。问题类型：" +
                        "、".join(sorted(set(e.error_type for e in errors))) if errors else "全部通过")

        TraceService.add_trace(
            db=db,
            trace_type=TraceType.BATCH_VERIFY,
            batch=batch,
            from_status=BatchStatus.SUBMITTED.value,
            to_status=batch.status.value,
            operator="SYSTEM",
            operator_role="SALARY_ACCOUNT_SERVICE",
            detail=verify_detail,
            remark=("、".join([f"{e.name}({e.id_card[-4:]})-{e.error_detail}" for e in errors[:5]]) +
                    ("等" if len(errors) > 5 else "")) if errors else "自动进入待审核环节"
        )

        if len(errors) == 0:
            TraceService.add_trace(
                db=db,
                trace_type=TraceType.BATCH_REVIEW,
                batch=batch,
                from_status=BatchStatus.VERIFIED.value,
                to_status=BatchStatus.REVIEWING.value,
                operator="SYSTEM",
                operator_role="SALARY_ACCOUNT_SERVICE",
                detail="校验通过，自动进入专户待审核环节，请审核人员及时处理",
                remark=f"待审核：{verified_count}人，{verified_amount:.2f}元"
            )

        db.commit()

        return VerifyResultResponse(
            message="工资批次提交并校验成功，已全部通过" if len(errors) == 0
            else f"工资批次提交完成，校验发现{len(errors)}个问题，请处理后重发",
            batch_no=batch_no,
            total_count=total_count,
            total_amount=total_amount,
            verified_count=verified_count,
            verified_amount=verified_amount,
            failed_count=len(error_id_cards),
            is_passed=len(errors) == 0,
            errors=errors,
            verify_at=batch.verify_at
        )

    @staticmethod
    def get_batch_list(
        db: Session,
        project_code: Optional[str] = None,
        salary_month: Optional[str] = None,
        batch_no: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[SalaryBatchInfoResponse], int]:
        query = db.query(SalaryBatch)

        if project_code:
            query = query.filter(SalaryBatch.project_code == project_code)
        if salary_month:
            query = query.filter(SalaryBatch.salary_month == salary_month)
        if batch_no:
            query = query.filter(SalaryBatch.batch_no == batch_no)
        if status:
            query = query.filter(SalaryBatch.status == status)

        total = query.count()
        query = query.order_by(SalaryBatch.created_at.desc())
        offset = (page - 1) * page_size
        batches = query.offset(offset).limit(page_size).all()

        responses = []
        for batch in batches:
            resp = SalaryBatchInfoResponse.model_validate(batch)
            responses.append(resp)

        return responses, total

    @staticmethod
    def get_batch_detail(
        db: Session,
        batch_no: str
    ) -> Optional[SalaryBatchInfoResponse]:
        batch = db.query(SalaryBatch).filter(SalaryBatch.batch_no == batch_no).first()
        if not batch:
            return None

        resp = SalaryBatchInfoResponse.model_validate(batch)
        items = db.query(SalaryItem).filter(SalaryItem.batch_id == batch.id).order_by(SalaryItem.id.asc()).all()
        resp.items = [SalaryItemResponse.model_validate(item) for item in items]
        return resp

    @staticmethod
    def query_worker_status(
        db: Session,
        params: WorkerStatusQueryParams
    ) -> Tuple[List[WorkerStatusResponse], int]:
        query = db.query(SalaryItem)

        if params.id_card:
            query = query.filter(SalaryItem.id_card == params.id_card)
        if params.project_code:
            query = query.filter(SalaryItem.project_code == params.project_code)
        if params.salary_month:
            query = query.filter(SalaryItem.salary_month == params.salary_month)
        if params.batch_no:
            query = query.filter(SalaryItem.batch_no == params.batch_no)

        total = query.count()
        query = query.order_by(SalaryItem.created_at.desc())
        offset = (params.page - 1) * params.page_size
        items = query.offset(offset).limit(params.page_size).all()

        responses = [WorkerStatusResponse.model_validate(item) for item in items]
        return responses, total

    @staticmethod
    def _enrich_batch_response(resp: SalaryBatchInfoResponse, project: Optional[Project] = None) -> SalaryBatchInfoResponse:
        status_name_map = {
            "DRAFT": "草稿",
            "SUBMITTED": "已提交",
            "VERIFIED": "校验通过",
            "VERIFY_FAILED": "校验失败",
            "REVIEWING": "待审核",
            "APPROVED": "审核通过",
            "REJECTED": "审核驳回",
            "BANK_SUBMITTED": "已提交银行",
            "BANK_PROCESSING": "银行处理中",
            "PARTIAL_SUCCESS": "部分成功",
            "ALL_SUCCESS": "全部成功",
            "ALL_FAILED": "全部失败",
            "RETRYING": "重试中"
        }
        resp.status_name = status_name_map.get(resp.status.value, resp.status.value)
        if project:
            resp.project_name = project.project_name
        for item in resp.items:
            item.status_name = {
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
            }.get(item.status.value, item.status.value)
        return resp

    @staticmethod
    def get_pending_review_list(
        db: Session,
        project_code: Optional[str] = None,
        salary_month: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[SalaryBatchInfoResponse], int]:
        query = db.query(SalaryBatch).filter(SalaryBatch.status == BatchStatus.REVIEWING)
        if project_code:
            query = query.filter(SalaryBatch.project_code == project_code)
        if salary_month:
            query = query.filter(SalaryBatch.salary_month == salary_month)

        total = query.count()
        query = query.order_by(SalaryBatch.created_at.asc())
        offset = (page - 1) * page_size
        batches = query.offset(offset).limit(page_size).all()

        project_map = {p.project_code: p for p in db.query(Project).all()}

        responses = []
        for batch in batches:
            resp = SalaryBatchInfoResponse.model_validate(batch)
            SalaryService._enrich_batch_response(resp, project_map.get(batch.project_code))
            responses.append(resp)

        return responses, total

    @staticmethod
    def get_batch_list(
        db: Session,
        project_code: Optional[str] = None,
        salary_month: Optional[str] = None,
        batch_no: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[SalaryBatchInfoResponse], int]:
        query = db.query(SalaryBatch)

        if project_code:
            query = query.filter(SalaryBatch.project_code == project_code)
        if salary_month:
            query = query.filter(SalaryBatch.salary_month == salary_month)
        if batch_no:
            query = query.filter(SalaryBatch.batch_no == batch_no)
        if status:
            query = query.filter(SalaryBatch.status == status)

        total = query.count()
        query = query.order_by(SalaryBatch.created_at.desc())
        offset = (page - 1) * page_size
        batches = query.offset(offset).limit(page_size).all()

        project_map = {p.project_code: p for p in db.query(Project).all()}

        responses = []
        for batch in batches:
            resp = SalaryBatchInfoResponse.model_validate(batch)
            SalaryService._enrich_batch_response(resp, project_map.get(batch.project_code))
            responses.append(resp)

        return responses, total

    @staticmethod
    def get_batch_detail(
        db: Session,
        batch_no: str
    ) -> Optional[SalaryBatchInfoResponse]:
        batch = db.query(SalaryBatch).filter(SalaryBatch.batch_no == batch_no).first()
        if not batch:
            return None

        project = db.query(Project).filter(Project.project_code == batch.project_code).first()
        resp = SalaryBatchInfoResponse.model_validate(batch)
        items = db.query(SalaryItem).filter(SalaryItem.batch_id == batch.id).order_by(SalaryItem.id.asc()).all()
        resp.items = [SalaryItemResponse.model_validate(item) for item in items]
        SalaryService._enrich_batch_response(resp, project)
        return resp

    @staticmethod
    def review_batch(
        db: Session,
        batch_no: str,
        action: str,
        review_by: Optional[str] = None,
        review_remark: Optional[str] = None
    ) -> dict:
        batch = db.query(SalaryBatch).filter(SalaryBatch.batch_no == batch_no).first()
        if not batch:
            return {"success": False, "code": 404, "message": f"批次 {batch_no} 不存在"}

        if batch.status != BatchStatus.REVIEWING:
            return {
                "success": False,
                "code": 400,
                "message": f"批次当前状态为 {batch.status.value}，不允许审核，仅待审核(REVIEWING)状态可审核"
            }

        old_status = batch.status.value
        review_at = datetime.now()

        if action == "APPROVED":
            batch.status = BatchStatus.APPROVED
            batch.review_result = "APPROVED"
            for item in db.query(SalaryItem).filter(SalaryItem.batch_id == batch.id).all():
                if item.status == ItemStatus.VERIFIED:
                    item.status = ItemStatus.APPROVED

            trace_type = TraceType.BATCH_APPROVE
            trace_title = "专户审核通过"
            detail = (f"专户审核通过：{batch.verified_count}人，"
                     f"金额{batch.verified_amount:.2f}元，可提交银行代发")

        elif action == "REJECTED":
            batch.status = BatchStatus.REJECTED
            batch.review_result = "REJECTED"
            for item in db.query(SalaryItem).filter(SalaryItem.batch_id == batch.id).all():
                if item.status == ItemStatus.VERIFIED:
                    item.status = ItemStatus.REJECTED

            trace_type = TraceType.BATCH_REJECT
            trace_title = "专户审核驳回"
            detail = (f"专户审核驳回：{batch.verified_count}人，"
                     f"金额{batch.verified_amount:.2f}元，驳回原因：{review_remark or '未填写'}")

        else:
            return {"success": False, "code": 400, "message": f"不支持的审核动作 {action}"}

        batch.review_by = review_by
        batch.review_at = review_at
        batch.review_remark = review_remark

        TraceService.add_trace(
            db=db,
            trace_type=trace_type,
            batch=batch,
            from_status=old_status,
            to_status=batch.status.value,
            operator=review_by,
            operator_role="REVIEWER",
            detail=detail,
            remark=review_remark,
            trace_time=review_at
        )

        db.commit()

        return {
            "success": True,
            "code": 200,
            "message": "审核成功",
            "batch_no": batch.batch_no,
            "old_status": old_status,
            "new_status": batch.status.value,
            "review_by": review_by,
            "review_at": review_at,
            "review_result": batch.review_result,
            "review_remark": review_remark
        }

    @staticmethod
    def get_project_monthly_summary(
        db: Session,
        project_code: Optional[str] = None,
        salary_month: Optional[str] = None
    ) -> List[dict]:
        query = db.query(SalaryBatch)
        if project_code:
            query = query.filter(SalaryBatch.project_code == project_code)
        if salary_month:
            query = query.filter(SalaryBatch.salary_month == salary_month)

        batches = query.all()
        if not batches:
            return []

        project_map = {p.project_code: p for p in db.query(Project).all()}

        summary_map: dict = {}
        for batch in batches:
            key = (batch.project_code, batch.salary_month)
            if key not in summary_map:
                summary_map[key] = {
                    "project_code": batch.project_code,
                    "project_name": project_map.get(batch.project_code, Project()).project_name if project_map.get(batch.project_code) else None,
                    "salary_month": batch.salary_month,
                    "total_batches": 0,
                    "total_workers": 0,
                    "total_payable_amount": 0.0,
                    "total_actual_amount": 0.0,
                    "pending_review_count": 0,
                    "pending_review_amount": 0.0,
                    "approved_count": 0,
                    "approved_amount": 0.0,
                    "bank_processing_count": 0,
                    "bank_processing_amount": 0.0,
                    "success_count": 0,
                    "success_amount": 0.0,
                    "failed_count": 0,
                    "failed_amount": 0.0,
                    "refunded_count": 0,
                    "refunded_amount": 0.0,
                    "retry_count": 0,
                    "retry_amount": 0.0,
                    "verify_failed_count": 0,
                    "verify_failed_amount": 0.0,
                    "rejected_count": 0,
                    "rejected_amount": 0.0,
                }

            s = summary_map[key]
            s["total_batches"] += 1
            s["total_workers"] += batch.total_count
            s["total_payable_amount"] += batch.total_amount
            s["total_actual_amount"] += batch.success_amount

            if batch.status == BatchStatus.REVIEWING:
                s["pending_review_count"] += batch.verified_count
                s["pending_review_amount"] += batch.verified_amount
            elif batch.status == BatchStatus.VERIFY_FAILED:
                s["verify_failed_count"] += batch.failed_count
                s["verify_failed_amount"] += batch.verified_amount
            elif batch.status == BatchStatus.REJECTED:
                s["rejected_count"] += batch.verified_count
                s["rejected_amount"] += batch.verified_amount
            elif batch.status in [BatchStatus.APPROVED]:
                s["approved_count"] += batch.verified_count
                s["approved_amount"] += batch.verified_amount
            elif batch.status in [BatchStatus.BANK_SUBMITTED, BatchStatus.BANK_PROCESSING]:
                s["bank_processing_count"] += batch.verified_count
                s["bank_processing_amount"] += batch.verified_amount
            elif batch.status in [BatchStatus.PARTIAL_SUCCESS, BatchStatus.ALL_SUCCESS, BatchStatus.ALL_FAILED, BatchStatus.RETRYING]:
                s["success_count"] += batch.success_count
                s["success_amount"] += batch.success_amount
                s["failed_count"] += batch.fail_count
                s["failed_amount"] += batch.fail_amount
                s["refunded_count"] += batch.refund_count
                s["refunded_amount"] += batch.refund_amount
                if batch.status == BatchStatus.RETRYING:
                    s["retry_count"] += batch.fail_count + batch.refund_count
                    s["retry_amount"] += batch.fail_amount + batch.refund_amount

        result = sorted(summary_map.values(), key=lambda x: (x["project_code"], x["salary_month"]), reverse=True)
        return result
