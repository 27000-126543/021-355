from typing import List, Tuple
from sqlalchemy.orm import Session
from datetime import datetime
import uuid

from app.models.models import (
    SalaryBatch, SalaryItem, BankDisbursement, BankDisbursementDetail,
    BatchStatus, ItemStatus, TraceType
)
from app.schemas.bank import (
    BankFeedbackRequest, BankFeedbackResponse, BankFeedbackResultItem,
    BankSubmitRequest, BankSubmitResponse, TradeStatusEnum
)
from app.services.trace_service import TraceService


class BankService:
    @staticmethod
    def _generate_bank_batch_no() -> str:
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        random_str = uuid.uuid4().hex[:8].upper()
        return f"BK{timestamp}{random_str}"

    @staticmethod
    def submit_to_bank(
        db: Session,
        request: BankSubmitRequest
    ) -> BankSubmitResponse:
        batch = db.query(SalaryBatch).filter(SalaryBatch.batch_no == request.batch_no).first()
        if not batch:
            return BankSubmitResponse(
                success=False,
                code=404,
                message=f"批次号 {request.batch_no} 不存在",
                batch_no=request.batch_no,
                bank_batch_no=""
            )

        if batch.status not in [BatchStatus.APPROVED, BatchStatus.VERIFIED,
                                 BatchStatus.ALL_FAILED, BatchStatus.PARTIAL_SUCCESS]:
            return BankSubmitResponse(
                success=False,
                code=400,
                message=f"批次状态 {batch.status.value} 不允许提交银行",
                batch_no=request.batch_no,
                bank_batch_no=""
            )

        items_to_submit = db.query(SalaryItem).filter(
            SalaryItem.batch_id == batch.id,
            SalaryItem.status.in_([
                ItemStatus.VERIFIED, ItemStatus.APPROVED,
                ItemStatus.FAILED, ItemStatus.RETRY_FAILED, ItemStatus.REFUNDED
            ])
        ).all()

        if not items_to_submit:
            return BankSubmitResponse(
                success=False,
                code=400,
                message="没有可提交银行代发的工资明细",
                batch_no=request.batch_no,
                bank_batch_no=""
            )

        submit_count = len(items_to_submit)
        submit_amount = sum(item.payable_amount for item in items_to_submit)

        bank_batch_no = BankService._generate_bank_batch_no()
        submit_at = request.submit_at or datetime.now()

        bank_record = BankDisbursement(
            batch_id=batch.id,
            batch_no=batch.batch_no,
            bank_batch_no=bank_batch_no,
            bank_code=request.bank_code,
            bank_name=request.bank_name,
            submit_count=submit_count,
            submit_amount=submit_amount,
            submit_at=submit_at,
            status="SUBMITTED"
        )
        db.add(bank_record)
        db.flush()

        for item in items_to_submit:
            item.status = ItemStatus.BANK_PROCESSING
            item.actual_amount = item.payable_amount
            detail = BankDisbursementDetail(
                disbursement_id=bank_record.id,
                bank_batch_no=bank_batch_no,
                salary_item_id=item.id,
                id_card=item.id_card,
                worker_name=item.worker_name,
                bank_card_no=item.bank_card_no,
                amount=item.payable_amount,
                trade_status="PENDING"
            )
            db.add(detail)

        old_status = batch.status.value
        batch.status = BatchStatus.BANK_SUBMITTED
        batch.bank_submit_at = submit_at

        db.flush()

        TraceService.add_trace(
            db=db,
            trace_type=TraceType.BANK_SUBMIT,
            batch=batch,
            from_status=old_status,
            to_status=BatchStatus.BANK_SUBMITTED.value,
            operator=request.operator,
            operator_role="BANK_SYSTEM",
            detail=f"提交银行代发：{submit_count}人，金额{submit_amount:.2f}元，银行批次号{bank_batch_no}",
            remark=f"银行：{request.bank_name or '未指定'}"
        )

        db.commit()

        return BankSubmitResponse(
            message="工资批次已成功提交银行代发",
            batch_no=batch.batch_no,
            bank_batch_no=bank_batch_no,
            submit_count=submit_count,
            submit_amount=submit_amount,
            submit_at=submit_at
        )

    @staticmethod
    def process_bank_feedback(
        db: Session,
        request: BankFeedbackRequest
    ) -> BankFeedbackResponse:
        batch = db.query(SalaryBatch).filter(SalaryBatch.batch_no == request.batch_no).first()
        if not batch:
            return BankFeedbackResponse(
                success=False,
                code=404,
                message=f"批次号 {request.batch_no} 不存在",
                batch_no=request.batch_no,
                bank_batch_no=request.bank_batch_no
            )

        bank_record = db.query(BankDisbursement).filter(
            BankDisbursement.bank_batch_no == request.bank_batch_no
        ).first()

        if not bank_record:
            bank_record = db.query(BankDisbursement).filter(
                BankDisbursement.batch_no == request.batch_no
            ).order_by(BankDisbursement.id.desc()).first()
            if bank_record:
                bank_record.bank_batch_no = request.bank_batch_no

        if not bank_record:
            bank_record = BankDisbursement(
                batch_id=batch.id,
                batch_no=batch.batch_no,
                bank_batch_no=request.bank_batch_no,
                bank_code=request.bank_code,
                bank_name=request.bank_name,
                status="FEEDBACK_RECEIVED"
            )
            db.add(bank_record)
            db.flush()

        old_status = batch.status.value
        feedback_at = request.feedback_at or datetime.now()

        success_count = 0
        success_amount = 0.0
        failed_count = 0
        failed_amount = 0.0
        refund_count = 0
        refund_amount = 0.0
        processed_count = 0
        results: List[BankFeedbackResultItem] = []

        detail_map: dict = {}
        for d in db.query(BankDisbursementDetail).filter(
            BankDisbursementDetail.bank_batch_no == request.bank_batch_no
        ).all():
            detail_map[d.id_card] = d

        item_map: dict = {}
        for item in db.query(SalaryItem).filter(
            SalaryItem.batch_id == batch.id
        ).all():
            item_map[item.id_card] = item

        for detail in request.details:
            salary_item = item_map.get(detail.id_card)
            bank_detail = detail_map.get(detail.id_card)

            if not salary_item:
                results.append(BankFeedbackResultItem(
                    id_card=detail.id_card,
                    worker_name=detail.worker_name,
                    trade_status=detail.trade_status.value,
                    updated=False,
                    message="未找到对应工资明细"
                ))
                continue

            processed_count += 1
            trade_time = detail.trade_time or feedback_at
            update_msg = ""

            if detail.trade_status == TradeStatusEnum.SUCCESS:
                old_item_status = salary_item.status.value
                salary_item.status = (ItemStatus.RETRY_SUCCESS
                                       if salary_item.retry_count > 0 else ItemStatus.SUCCESS)
                salary_item.bank_trade_no = detail.bank_trade_no
                salary_item.bank_success_time = trade_time
                salary_item.fail_reason = None
                salary_item.actual_amount = detail.amount or salary_item.payable_amount
                success_count += 1
                success_amount += detail.amount or salary_item.payable_amount
                update_msg = f"代发成功，{old_item_status}→{salary_item.status.value}"

                if salary_item.id_card not in detail_map:
                    new_bd = BankDisbursementDetail(
                        disbursement_id=bank_record.id,
                        bank_batch_no=request.bank_batch_no,
                        salary_item_id=salary_item.id,
                        id_card=detail.id_card,
                        worker_name=detail.worker_name,
                        bank_card_no=detail.bank_card_no or salary_item.bank_card_no,
                        amount=detail.amount or salary_item.payable_amount,
                        trade_status="SUCCESS",
                        bank_trade_no=detail.bank_trade_no,
                        trade_time=trade_time
                    )
                    db.add(new_bd)

                TraceService.add_trace(
                    db=db,
                    trace_type=TraceType.BANK_FEEDBACK,
                    batch_id=batch.id,
                    batch_no=batch.batch_no,
                    project_code=batch.project_code,
                    salary_month=batch.salary_month,
                    id_card=detail.id_card,
                    from_status=old_item_status,
                    to_status=salary_item.status.value,
                    operator="BANK_SYSTEM",
                    operator_role="BANK",
                    detail=f"【{detail.worker_name}】代发成功，金额{detail.amount or salary_item.payable_amount:.2f}元，流水号{detail.bank_trade_no}",
                    remark=f"银行卡尾号：{(detail.bank_card_no or salary_item.bank_card_no or '')[-4:]}"
                )

            elif detail.trade_status == TradeStatusEnum.FAILED:
                old_item_status = salary_item.status.value
                salary_item.status = (ItemStatus.RETRY_FAILED
                                       if salary_item.retry_count > 0 else ItemStatus.FAILED)
                salary_item.bank_trade_no = detail.bank_trade_no
                salary_item.fail_reason = detail.fail_reason
                salary_item.fail_code = getattr(detail, 'fail_code', None)
                failed_count += 1
                failed_amount += detail.amount or salary_item.payable_amount
                update_msg = f"代发失败，{old_item_status}→{salary_item.status.value}，原因：{detail.fail_reason}"

                if salary_item.id_card not in detail_map:
                    new_bd = BankDisbursementDetail(
                        disbursement_id=bank_record.id,
                        bank_batch_no=request.bank_batch_no,
                        salary_item_id=salary_item.id,
                        id_card=detail.id_card,
                        worker_name=detail.worker_name,
                        bank_card_no=detail.bank_card_no or salary_item.bank_card_no,
                        amount=detail.amount or salary_item.payable_amount,
                        trade_status="FAILED",
                        bank_trade_no=detail.bank_trade_no,
                        fail_code=getattr(detail, 'fail_code', None),
                        fail_reason=detail.fail_reason,
                        trade_time=trade_time
                    )
                    db.add(new_bd)

                TraceService.add_trace(
                    db=db,
                    trace_type=TraceType.BANK_FEEDBACK,
                    batch_id=batch.id,
                    batch_no=batch.batch_no,
                    project_code=batch.project_code,
                    salary_month=batch.salary_month,
                    id_card=detail.id_card,
                    from_status=old_item_status,
                    to_status=salary_item.status.value,
                    operator="BANK_SYSTEM",
                    operator_role="BANK",
                    detail=f"【{detail.worker_name}】代发失败，金额{detail.amount or salary_item.payable_amount:.2f}元，原因：{detail.fail_reason}",
                    remark=f"错误码：{getattr(detail, 'fail_code', None) or '未知'}"
                )

            elif detail.trade_status == TradeStatusEnum.REFUND:
                old_item_status = salary_item.status.value
                salary_item.status = ItemStatus.REFUNDED
                salary_item.bank_trade_no = detail.bank_trade_no
                salary_item.refund_reason = detail.refund_reason or detail.fail_reason
                salary_item.refund_time = trade_time
                refund_count += 1
                refund_amount += detail.amount or salary_item.payable_amount
                update_msg = f"已退票，{old_item_status}→REFUNDED，原因：{detail.refund_reason or detail.fail_reason}"

                if salary_item.id_card not in detail_map:
                    new_bd = BankDisbursementDetail(
                        disbursement_id=bank_record.id,
                        bank_batch_no=request.bank_batch_no,
                        salary_item_id=salary_item.id,
                        id_card=detail.id_card,
                        worker_name=detail.worker_name,
                        bank_card_no=detail.bank_card_no or salary_item.bank_card_no,
                        amount=detail.amount or salary_item.payable_amount,
                        trade_status="REFUND",
                        bank_trade_no=detail.bank_trade_no,
                        refund_reason=detail.refund_reason or detail.fail_reason,
                        trade_time=trade_time
                    )
                    db.add(new_bd)

                TraceService.add_trace(
                    db=db,
                    trace_type=TraceType.BANK_REFUND,
                    batch_id=batch.id,
                    batch_no=batch.batch_no,
                    project_code=batch.project_code,
                    salary_month=batch.salary_month,
                    id_card=detail.id_card,
                    from_status=old_item_status,
                    to_status="REFUNDED",
                    operator="BANK_SYSTEM",
                    operator_role="BANK",
                    detail=f"【{detail.worker_name}】银行退票，金额{detail.amount or salary_item.payable_amount:.2f}元，原因：{detail.refund_reason or detail.fail_reason}",
                    remark=f"原流水号：{detail.bank_trade_no}"
                )

            results.append(BankFeedbackResultItem(
                id_card=detail.id_card,
                worker_name=detail.worker_name,
                trade_status=detail.trade_status.value,
                updated=True,
                message=update_msg
            ))

        all_items = db.query(SalaryItem).filter(SalaryItem.batch_id == batch.id).all()
        batch_success = sum(1 for i in all_items if i.status in [ItemStatus.SUCCESS, ItemStatus.RETRY_SUCCESS])
        batch_fail = sum(1 for i in all_items if i.status in [ItemStatus.FAILED, ItemStatus.RETRY_FAILED])
        batch_refund = sum(1 for i in all_items if i.status == ItemStatus.REFUNDED)

        batch.success_count = batch_success
        batch.success_amount = sum(
            i.actual_amount for i in all_items if i.status in [ItemStatus.SUCCESS, ItemStatus.RETRY_SUCCESS]
        )
        batch.fail_count = batch_fail
        batch.fail_amount = sum(
            i.payable_amount for i in all_items if i.status in [ItemStatus.FAILED, ItemStatus.RETRY_FAILED]
        )
        batch.refund_count = batch_refund
        batch.refund_amount = sum(
            i.payable_amount for i in all_items if i.status == ItemStatus.REFUNDED
        )
        batch.bank_feedback_at = feedback_at

        batch_total = batch.total_count
        if batch_success == batch_total and batch_fail == 0 and batch_refund == 0:
            batch.status = BatchStatus.ALL_SUCCESS
        elif batch_success > 0 and (batch_fail > 0 or batch_refund > 0):
            batch.status = BatchStatus.PARTIAL_SUCCESS
        elif batch_success == 0 and (batch_fail > 0 or batch_refund > 0):
            batch.status = BatchStatus.ALL_FAILED
        else:
            batch.status = BatchStatus.BANK_PROCESSING

        bank_record.feedback_count = processed_count
        bank_record.success_count = success_count
        bank_record.success_amount = success_amount
        bank_record.failed_count = failed_count
        bank_record.failed_amount = failed_amount
        bank_record.refund_count = refund_count
        bank_record.refund_amount = refund_amount
        bank_record.feedback_at = feedback_at
        bank_record.remark = request.remark
        bank_record.status = "PROCESSED"

        db.flush()

        TraceService.add_trace(
            db=db,
            trace_type=TraceType.BANK_FEEDBACK,
            batch=batch,
            from_status=old_status,
            to_status=batch.status.value,
            operator="BANK_SYSTEM",
            operator_role="BANK",
            detail=(f"银行代发回传完成：共{processed_count}笔，"
                    f"成功{success_count}笔({success_amount:.2f}元)，"
                    f"失败{failed_count}笔({failed_amount:.2f}元)，"
                    f"退票{refund_count}笔({refund_amount:.2f}元)"),
            remark=f"银行批次号：{request.bank_batch_no}"
        )

        db.commit()

        return BankFeedbackResponse(
            message="银行回传数据处理完成",
            batch_no=batch.batch_no,
            bank_batch_no=request.bank_batch_no,
            processed_count=processed_count,
            success_count=success_count,
            failed_count=failed_count,
            refund_count=refund_count,
            batch_status=batch.status.value,
            results=results,
            feedback_at=feedback_at
        )

    @staticmethod
    def retry_failed_items(
        db: Session,
        batch_no: str,
        operator: Optional[str] = None,
        id_cards: Optional[List[str]] = None
    ) -> dict:
        batch = db.query(SalaryBatch).filter(SalaryBatch.batch_no == batch_no).first()
        if not batch:
            return {"success": False, "code": 404, "message": f"批次 {batch_no} 不存在"}

        query = db.query(SalaryItem).filter(
            SalaryItem.batch_id == batch.id,
            SalaryItem.status.in_([ItemStatus.FAILED, ItemStatus.RETRY_FAILED, ItemStatus.REFUNDED])
        )
        if id_cards:
            query = query.filter(SalaryItem.id_card.in_(id_cards))

        items_to_retry = query.all()
        if not items_to_retry:
            return {"success": False, "code": 400, "message": "没有可重试的失败明细"}

        retry_count = len(items_to_retry)
        retry_amount = sum(item.payable_amount for item in items_to_retry)
        old_status = batch.status.value

        for item in items_to_retry:
            item.retry_count += 1
            item.last_retry_time = datetime.now()
            item.status = ItemStatus.BANK_PROCESSING
            item.fail_reason = None
            item.refund_reason = None

        batch.status = BatchStatus.RETRYING
        db.flush()

        TraceService.add_trace(
            db=db,
            trace_type=TraceType.ITEM_RETRY,
            batch=batch,
            from_status=old_status,
            to_status=BatchStatus.RETRYING.value,
            operator=operator or "SYSTEM",
            operator_role="OPERATOR",
            detail=(f"发起失败重发：共{retry_count}人，金额{retry_amount:.2f}元，"
                    f"涉及：{'、'.join([f'{i.worker_name}({i.id_card[-4:]})' for i in items_to_retry[:5]])}"
                    + ("等" if retry_count > 5 else "")),
            remark=f"针对失败/退票人员重新提交银行代发"
        )

        db.commit()

        return {
            "success": True,
            "code": 200,
            "message": f"已提交{retry_count}条失败明细进行重发",
            "batch_no": batch_no,
            "retry_count": retry_count,
            "retry_amount": retry_amount
        }
