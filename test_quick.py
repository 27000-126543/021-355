import requests

BASE = "http://localhost:8000/api/v1"

def main():
    print("=" * 50)
    print("测试：失败重发完整闭环")
    print("=" * 50)

    req = {
        "project_code": "PRJ2025002",
        "project_name": "市民中心项目",
        "general_contractor": "中建五局",
        "salary_month": "2025-06",
        "team_name": "混凝土班组",
        "submit_by": "王工",
        "workers": [
            {"id_card": "110101199107084567", "name": "赵秀兰", "payable_amount": 7500.00},
            {"id_card": "110101199309105678", "name": "孙志远", "payable_amount": 8800.00},
        ]
    }
    res = requests.post(f"{BASE}/project/batch/submit", json=req)
    data = res.json()
    batch_no = data["batch_no"]
    print(f"1. 提交批次: {batch_no}, 通过: {data['verified_count']}人")

    requests.post(f"{BASE}/project/batch/review", json={
        "batch_no": batch_no, "action": "APPROVED",
        "review_by": "张审核", "review_remark": "资料齐全"
    })
    print("2. 专户审核通过 ✓")

    res = requests.post(f"{BASE}/bank/submit", json={"batch_no": batch_no})
    bank_batch_no = res.json()["bank_batch_no"]
    print(f"3. 提交银行代发: {bank_batch_no}")

    res = requests.post(f"{BASE}/bank/feedback", json={
        "batch_no": batch_no, "bank_batch_no": bank_batch_no,
        "details": [
            {"id_card": "110101199107084567", "trade_status": "SUCCESS", "amount": 7500.0},
            {"id_card": "110101199309105678", "trade_status": "FAILED", "fail_reason": "账户冻结", "amount": 8800.0}
        ]
    })
    print(f"4. 银行回传: 成功{res.json()['success_count']}, 失败{res.json()['failed_count']}")

    res = requests.post(f"{BASE}/bank/retry", json={
        "batch_no": batch_no,
        "id_cards": ["110101199309105678"],
        "operator": "李客服"
    })
    r = res.json()
    new_bank = r["bank_batch_no"]
    print(f"5. 发起重发: {r['retry_count']}人, 新银行批次: {new_bank}")

    res = requests.post(f"{BASE}/bank/feedback", json={
        "batch_no": batch_no, "bank_batch_no": new_bank,
        "details": [
            {"id_card": "110101199309105678", "trade_status": "SUCCESS", "amount": 8800.0}
        ]
    })
    print(f"6. 重放回传: 状态码{res.status_code}")
    if res.status_code == 200:
        print(f"   成功{res.json()['success_count']}, 失败{res.json()['failed_count']}")
    else:
        print(f"   错误: {res.text[:200]}")

    res = requests.get(f"{BASE}/project/batch/detail", params={"batch_no": batch_no})
    batch = res.json()["data"]
    print()
    print("7. 批次详情:")
    print(f"   批次状态: {batch['status_name']}")
    for item in batch["items"]:
        print(f"   {item['worker_name']}: {item['status_name']}")
        if item.get("last_fail_reason"):
            print(f"     上次失败原因: {item['last_fail_reason']}")
        if item.get("retry_count"):
            print(f"     重试次数: {item['retry_count']}")

    res = requests.get(f"{BASE}/query/worker/grouped-timeline",
                       params={"id_card": "110101199309105678"})
    data = res.json()
    print()
    print("8. 孙志远分组时间线:")
    print(f"   总记录: {data['total_records']}条, 项目数: {data['total_projects']}")
    for pg in data["project_groups"]:
        print(f"   项目: {pg['project_name']}")
        for mg in pg["months"]:
            print(f"     月份: {mg['salary_month']}, {mg['total_count']}条记录")
            for rec in mg["records"][:1]:
                print(f"       批次: {rec['batch_no']}, 状态: {rec['status_name']}")
                print(f"       时间线节点: {len(rec['traces'])}个")
                for t in rec["traces"]:
                    print(f"         [{t['timeline_index']}] {t['trace_time'][:19]} {t['trace_type_name']}")

    res = requests.get(f"{BASE}/query/project/monthly-summary")
    data = res.json()
    print()
    print("9. 项目月度汇总:")
    print(f"   共 {data['total']} 条汇总")
    for item in data["data"][:2]:
        print(f"   {item['project_name']} {item['salary_month']}:")
        print(f"     总人数: {item['total_workers']}, 应发: {item['total_payable_amount']}")
        print(f"     成功: {item['success_count']}, 失败: {item['failed_count']}, 退票: {item['refunded_count']}")
        print(f"     待审核: {item['pending_review_count']}, 重试中: {item['retry_count']}")

    print()
    print("=" * 50)
    print("测试完成")
    print("=" * 50)

if __name__ == "__main__":
    main()
