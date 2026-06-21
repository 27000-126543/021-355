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
            status=BatchStatus.VERIFIED if len(errors) == 0 else BatchStatus.VERIFY_FAILED,
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
                    ("等" if len(errors) > 5 else "")) if errors else None
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
