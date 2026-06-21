import requests
import json
import time

BASE = "http://localhost:8000/api/v1"

def test_full_flow():
    print("=" * 60)
    print("【测试1】提交工资批次（校验通过后进入待审核）")
    print("=" * 60)
    req = {
        "project_code": "PRJ2025001",
        "project_name": "新城家园一期项目",
        "general_contractor": "中建八局第一建设有限公司",
        "salary_month": "2025-06",
        "team_name": "钢筋班组",
        "submit_by": "张经理",
        "remark": "6月份第一批工资",
        "workers": [
            {"id_card": "110101199001011234", "name": "王大伟", "payable_amount": 8500.00},
            {"id_card": "110101199203042345", "name": "刘强", "payable_amount": 9200.00},
            {"id_card": "110101198805063456", "name": "陈建国", "payable_amount": 7800.00},
        ]
    }
    res = requests.post(f"{BASE}/project/batch/submit", json=req)
    data = res.json()
    print(f"状态码: {res.status_code}")
    print(f"消息: {data.get('message')}")
    batch_no = data.get('batch_no')
    print(f"批次号: {batch_no}")
    print(f"校验通过: {data.get('verified_count')}人, 失败: {data.get('failed_count')}人")
    print(f"是否全部通过: {data.get('is_passed')}")

    if data.get('fail_count', 0) > 0:
        for err in data.get('errors', []):
            print(f"  错误: {err['id_card']} {err['name']} - {err['error_type']}: {err['error_message']}")

    print()

    print("=" * 60)
    print("【测试2】查询待审核批次列表")
    print("=" * 60)
    res = requests.get(f"{BASE}/project/batch/pending-review", params={"page": 1, "page_size": 10})
    data = res.json()
    print(f"状态码: {res.status_code}")
    print(f"总数: {data.get('total')}")
    for b in data.get('data', []):
        print(f"  {b['batch_no']} - {b['project_name']} - {b['salary_month']} - {b['status_name']}")

    print()

    print("=" * 60)
    print("【测试3】专户审核通过")
    print("=" * 60)
    req3 = {
        "batch_no": batch_no,
        "action": "APPROVED",
        "review_by": "李审核员",
        "review_remark": "资料齐全，同意发放"
    }
    res = requests.post(f"{BASE}/project/batch/review", json=req3)
    data = res.json()
    print(f"状态码: {res.status_code}")
    print(f"消息: {data.get('message')}")
    print(f"批次状态: {data.get('status')}")
    print(f"审核人: {data.get('review_by')}, 审核时间: {data.get('review_at')}")
    print(f"审核结果: {data.get('review_result')}, 审核备注: {data.get('review_remark')}")

    print()

    print("=" * 60)
    print("【测试4】提交银行代发")
    print("=" * 60)
    req4 = {"batch_no": batch_no, "bank_batch_no": f"BANK{int(time.time())}"}
    res = requests.post(f"{BASE}/bank/submit", json=req4)
    data = res.json()
    print(f"状态码: {res.status_code}")
    print(f"消息: {data.get('message')}")
    print(f"银行批次号: {data.get('bank_batch_no')}")
    print(f"代发人数: {data.get('total_count')}")

    print()

    print("=" * 60)
    print("【测试5】银行回传（1成功1失败1退票）")
    print("=" * 60)
    bank_batch_no = data.get('bank_batch_no')
    req5 = {
        "batch_no": batch_no,
        "bank_batch_no": bank_batch_no,
        "feedback_at": "2025-06-15 14:30:00",
        "details": [
            {"id_card": "110101199001011234", "worker_name": "王大伟", "trade_status": "SUCCESS", "amount": 8500.00, "trade_time": "2025-06-15 14:30:01"},
            {"id_card": "110101199203042345", "worker_name": "刘强", "trade_status": "FAILED", "fail_reason": "账户余额不足", "trade_time": "2025-06-15 14:30:02"},
            {"id_card": "110101198805063456", "worker_name": "陈建国", "trade_status": "REFUND", "refund_reason": "账户已销户", "trade_time": "2025-06-15 16:00:00"},
        ]
    }
    res = requests.post(f"{BASE}/bank/feedback", json=req5)
    data = res.json()
    print(f"状态码: {res.status_code}")
    print(f"消息: {data.get('message')}")
    print(f"成功: {data.get('success_count')}, 失败: {data.get('failed_count')}, 退票: {data.get('refund_count')}")

    print()

    print("=" * 60)
    print("【测试6】失败重发（刘强 + 陈建国）")
    print("=" * 60)
    req6 = {
        "batch_no": batch_no,
        "id_cards": ["110101199203042345", "110101198805063456"],
        "operator": "王客服"
    }
    res = requests.post(f"{BASE}/bank/retry", json=req6)
    data = res.json()
    print(f"状态码: {res.status_code}")
    print(f"消息: {data.get('message')}")
    print(f"新银行批次号: {data.get('bank_batch_no')}")
    print(f"重发人数: {data.get('retry_count')}")
    new_bank_batch_no = data.get('bank_batch_no')

    print()

    print("=" * 60)
    print("【测试7】重发后银行回传（1成功1失败）")
    print("=" * 60)
    req7 = {
        "batch_no": batch_no,
        "bank_batch_no": new_bank_batch_no,
        "feedback_at": "2025-06-16 10:00:00",
        "details": [
            {"id_card": "110101198805063456", "worker_name": "陈建国", "trade_status": "SUCCESS", "amount": 7800.00, "trade_time": "2025-06-16 10:00:01"},
            {"id_card": "110101199203042345", "worker_name": "刘强", "trade_status": "FAILED", "fail_reason": "身份证号与账户名不符", "trade_time": "2025-06-16 10:00:02"},
        ]
    }
    res = requests.post(f"{BASE}/bank/feedback", json=req7)
    data = res.json()
    print(f"状态码: {res.status_code}")
    print(f"消息: {data.get('message')}")
    print(f"成功: {data.get('success_count')}, 失败: {data.get('fail_count')}")

    print()

    print("=" * 60)
    print("【测试8】批次详情（查看审核信息+重发信息）")
    print("=" * 60)
    res = requests.get(f"{BASE}/project/batch/detail", params={"batch_no": batch_no})
    data = res.json()
    print(f"状态码: {res.status_code}")
    batch = data.get('data')
    print(f"批次号: {batch['batch_no']}")
    print(f"状态: {batch['status']} ({batch['status_name']})")
    print(f"审核人: {batch.get('review_by')}, 审核时间: {batch.get('review_at')}")
    print(f"审核结果: {batch.get('review_result')}, 审核备注: {batch.get('review_remark')}")
    print(f"批注明细数: {len(batch.get('items', []))}")
    for item in batch.get('items', []):
        print(f"  {item['worker_name']} {item['id_card']}: {item['status']} ({item['status_name']})")
        if item.get('last_fail_reason'):
            print(f"    上次失败原因: {item['last_fail_reason']}")
        if item.get('last_bank_trade_no'):
            print(f"    上次银行流水: {item['last_bank_trade_no']}")
        if item.get('retry_count'):
            print(f"    重试次数: {item['retry_count']}")

    print()

    print("=" * 60)
    print("【测试9】项目月度汇总")
    print("=" * 60)
    res = requests.get(f"{BASE}/query/project/monthly-summary")
    data = res.json()
    print(f"状态码: {res.status_code}")
    print(f"消息: {data.get('message')}")
    print(f"汇总记录数: {data.get('total')}")
    for item in data.get('data', []):
        print(f"  {item['project_name']} {item['salary_month']}:")
        print(f"    总批次: {item['total_batches']}, 总人数: {item['total_workers']}, 应发: {item['total_payable_amount']}")
        print(f"    待审核: {item['pending_review_count']}人 ({item['pending_review_amount']}元)")
        print(f"    审核通过: {item['approved_count']}人")
        print(f"    银行处理中: {item['bank_processing_count']}人")
        print(f"    已到账: {item['success_count']}人 ({item['success_amount']}元)")
        print(f"    失败: {item['failed_count']}人 ({item['failed_amount']}元)")
        print(f"    退票: {item['refunded_count']}人 ({item['refunded_amount']}元)")
        print(f"    重试中: {item['retry_count']}人")

    print()

    print("=" * 60)
    print("【测试10】工人分组时间线查询（陈建国）")
    print("=" * 60)
    res = requests.get(f"{BASE}/query/worker/grouped-timeline", params={"id_card": "110101198805063456"})
    data = res.json()
    print(f"状态码: {res.status_code}")
    print(f"消息: {data.get('message')}")
    print(f"工人: {data.get('worker_name')} {data.get('id_card')}")
    print(f"总记录数: {data.get('total_records')}, 项目数: {data.get('total_projects')}, 月份数: {data.get('total_months')}")
    for pg in data.get('project_groups', []):
        print(f"\n  项目: {pg['project_name']} ({pg['project_code']})")
        print(f"  总记录: {pg['total_count']}条, 应发: {pg['total_payable']}, 实发: {pg['total_actual']}")
        for mg in pg.get('months', []):
            print(f"    月份: {mg['salary_month']}, 记录: {mg['total_count']}条")
            for rec in mg.get('records', []):
                print(f"      批次: {rec['batch_no']}, 状态: {rec['status_name']}")
                print(f"      应发: {rec['payable_amount']}, 实发: {rec['actual_amount']}")
                if rec.get('last_fail_reason'):
                    print(f"      上次失败: {rec['last_fail_reason']}")
                print(f"      时间线 ({len(rec['traces'])}个节点):")
                for t in rec['traces']:
                    print(f"        [{t['timeline_index']}] {t['trace_time']} {t['trace_type_name']} - {t['trace_title']}")
                    if t.get('detail'):
                        print(f"            {t['detail'][:80]}")

    print()
    print("=" * 60)
    print("【全部测试完成】")
    print("=" * 60)


if __name__ == "__main__":
    test_full_flow()
