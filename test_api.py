import urllib.request
import json

BASE_URL = "http://localhost:8000"

def http_request(url, method="GET", data=None):
    headers = {"Content-Type": "application/json"}
    if data:
        data_bytes = json.dumps(data, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(url, data=data_bytes, method=method, headers=headers)
    else:
        req = urllib.request.Request(url, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read()
            return resp.status, json.loads(body.decode("utf-8")) if body else {}
    except urllib.error.HTTPError as e:
        body = e.read()
        try:
            return e.code, json.loads(body.decode("utf-8")) if body else {"detail": str(e)}
        except:
            return e.code, {"http_error": str(e), "raw": body.decode("utf-8", errors="replace")}

print("=" * 60)
print("【1】健康检查")
code, res = http_request(f"{BASE_URL}/health")
print(f"状态码: {code}")
print(json.dumps(res, ensure_ascii=False, indent=2))

print("\n" + "=" * 60)
print("【2】项目系统 - 预校验工资批次（发现问题：未实名、银行卡缺失、重复人员）")
batch_data = {
    "project_code": "PRJ2025001",
    "project_name": "阳光花园住宅小区一期工程",
    "general_contractor": "中天建设集团有限公司",
    "team_name": "综合班组",
    "salary_month": "2025-06",
    "submit_by": "项目劳资员张三",
    "remark": "6月份工资发放",
    "workers": [
        {"id_card": "110101199001011234", "name": "王大伟", "team_name": "钢筋班组", "phone": "13900139001", "bank_card_no": "6222021234567890101", "bank_name": "中国工商银行", "work_days": 26, "payable_amount": 9500},
        {"id_card": "110101199203042345", "name": "刘强", "team_name": "钢筋班组", "phone": "13900139002", "bank_card_no": "6222021234567890102", "bank_name": "中国工商银行", "work_days": 25, "payable_amount": 8800},
        {"id_card": "110101199001011234", "name": "王大伟", "team_name": "木工班组", "payable_amount": 3000},
        {"id_card": "110101198911126789", "name": "周明华", "team_name": "架子工班组", "payable_amount": 7200},
        {"id_card": "110101199001018888", "name": "吴德胜", "team_name": "瓦工班组", "payable_amount": 8000},
        {"id_card": "12345", "name": "身份证错误", "payable_amount": 5000}
    ]
}
code, res = http_request(f"{BASE_URL}/api/v1/project/batch/verify-only", "POST", batch_data)
print(f"状态码: {code}, 是否通过: {res.get('is_passed')}, 问题数: {len(res.get('errors', []))}")
print(f"总数: {res.get('total_count')}人/{res.get('total_amount')}元, 通过: {res.get('verified_count')}人/{res.get('verified_amount')}元, 失败: {res.get('failed_count')}人")
for err in res.get("errors", []):
    print(f"  ⚠️  {err['name']}({err['id_card'][-4:] if len(err['id_card'])>4 else err['id_card']}) - {err['error_type']}: {err['error_detail']}")

print("\n" + "=" * 60)
print("【3】项目系统 - 正式提交工资批次（正常人员提交）")
good_batch = {
    "project_code": "PRJ2025001",
    "project_name": "阳光花园住宅小区一期工程",
    "general_contractor": "中天建设集团有限公司",
    "team_name": "钢筋班组",
    "salary_month": "2025-06",
    "submit_by": "项目劳资员张三",
    "remark": "6月份钢筋班组工资",
    "workers": [
        {"id_card": "110101199001011234", "name": "王大伟", "team_name": "钢筋班组", "phone": "13900139001", "bank_card_no": "6222021234567890101", "bank_name": "中国工商银行", "work_days": 26, "base_salary": 8000, "overtime_pay": 1500, "payable_amount": 9500},
        {"id_card": "110101199203042345", "name": "刘强", "team_name": "钢筋班组", "phone": "13900139002", "bank_card_no": "6222021234567890102", "bank_name": "中国工商银行", "work_days": 25, "base_salary": 7500, "overtime_pay": 1300, "payable_amount": 8800},
        {"id_card": "110101198805063456", "name": "陈建国", "team_name": "木工班组", "phone": "13900139003", "bank_card_no": "6222021234567890103", "bank_name": "中国工商银行", "work_days": 26, "payable_amount": 9200}
    ]
}
code, res = http_request(f"{BASE_URL}/api/v1/project/batch/submit", "POST", good_batch)
print(f"状态码: {code}")
batch_no = res.get("batch_no")
print(f"批次号: {batch_no}")
print(f"结果: {res.get('message')}")
print(f"总数: {res.get('total_count')}人/{res.get('total_amount')}元, 通过: {res.get('verified_count')}人, 是否通过: {res.get('is_passed')}")

if batch_no:
    print("\n" + "=" * 60)
    print("【4】银行系统 - 提交批次到银行代发")
    code, res = http_request(f"{BASE_URL}/api/v1/bank/submit", "POST", {
        "batch_no": batch_no,
        "bank_code": "ICBC",
        "bank_name": "中国工商银行",
        "operator": "银行操作员李四"
    })
    print(f"状态码: {code}")
    bank_batch_no = res.get("bank_batch_no")
    print(f"结果: {res.get('message')}")
    print(f"银行批次号: {bank_batch_no}, 提交: {res.get('submit_count')}人/{res.get('submit_amount')}元")

    if bank_batch_no:
        print("\n" + "=" * 60)
        print("【5】银行系统 - 代发结果回传（2成功1失败）")
        code, res = http_request(f"{BASE_URL}/api/v1/bank/feedback", "POST", {
            "batch_no": batch_no,
            "bank_batch_no": bank_batch_no,
            "bank_code": "ICBC",
            "bank_name": "中国工商银行",
            "details": [
                {"id_card": "110101199001011234", "worker_name": "王大伟", "bank_card_no": "6222021234567890101", "amount": 9500, "trade_status": "SUCCESS", "bank_trade_no": "ICBC202506210001", "trade_time": "2025-06-21T10:30:00"},
                {"id_card": "110101199203042345", "worker_name": "刘强", "bank_card_no": "6222021234567890102", "amount": 8800, "trade_status": "SUCCESS", "bank_trade_no": "ICBC202506210002", "trade_time": "2025-06-21T10:30:01"},
                {"id_card": "110101198805063456", "worker_name": "陈建国", "bank_card_no": "6222021234567890103", "amount": 9200, "trade_status": "FAILED", "fail_code": "E1001", "fail_reason": "账户已挂失，请更换银行卡", "trade_time": "2025-06-21T10:30:02"}
            ]
        })
        print(f"状态码: {code}")
        print(f"批次状态: {res.get('batch_status')}")
        print(f"处理: {res.get('processed_count')}笔, 成功{res.get('success_count')}, 失败{res.get('failed_count')}, 退票{res.get('refund_count')}")
        for r in res.get("results", []):
            print(f"  ✅/❌ {r['worker_name']}: {r['trade_status']} - {r['message']}")

    print("\n" + "=" * 60)
    print("【6】项目系统 - 查询批次详情（看每人到账状态）")
    code, res = http_request(f"{BASE_URL}/api/v1/project/batch/detail?batch_no={batch_no}")
    print(f"状态码: {code}, 批次状态: {res['data']['status']}")
    for item in res['data']['items']:
        icon = {"SUCCESS": "✅", "RETRY_SUCCESS": "✅", "FAILED": "❌", "REFUNDED": "↩️", "VERIFIED": "🔍", "BANK_PROCESSING": "⏳"}.get(item['status'], "❓")
        print(f"  {icon} {item['worker_name']} 应发{item['payable_amount']}实发{item['actual_amount']} 状态:{item['status']} 失败原因:{item.get('fail_reason') or '-'}")

    print("\n" + "=" * 60)
    print("【7】监管/客服系统 - 按身份证查工人发薪时间线（处理投诉热线）")
    code, res = http_request(f"{BASE_URL}/api/v1/query/worker/timeline?id_card=110101198805063456")
    print(f"状态码: {code}, 记录数: {res.get('total_records')}")
    if res.get('worker_info'):
        w = res['worker_info']
        print(f"  👷 工人: {w['worker_name']}({w['id_card'][:6]}****{w['id_card'][-4:]})")
        print(f"  💰 工资: 应发{w['payable_amount']} 实发{w['actual_amount']} 当前状态: {w['current_status_name']}")
        if w.get('fail_reason'):
            print(f"  ❌ 失败原因: {w['fail_reason']}")
        print(f"  📋 处理轨迹 ({len(w['traces'])}条):")
        for t in w['traces']:
            print(f"    [{t['trace_time'][:19]}] {t['trace_type_name']}: {t.get('detail', '')[:60]}")

    print("\n" + "=" * 60)
    print("【8】监管系统 - 批次发薪全链路时间线")
    code, res = http_request(f"{BASE_URL}/api/v1/query/batch/timeline?batch_no={batch_no}")
    print(f"状态码: {code}, 批次: {res['batch_no']} 状态: {res['current_status_name']}")
    print(f"统计: 总{res['total_count']}人/{res['total_amount']}元, 成功{res['success_count']}, 失败{res['fail_count']}, 退票{res['refund_count']}")
    print(f"📋 全链路轨迹 ({res['total_traces']}条):")
    for t in res['traces']:
        icon = {"BATCH_SUBMIT": "📝", "BATCH_VERIFY": "🔍", "BANK_SUBMIT": "🏦", "BANK_FEEDBACK": "📨", "BANK_REFUND": "↩️", "ITEM_RETRY": "🔄"}.get(t.get('trace_type', ''), "•")
        print(f"  {icon} [{t['trace_time'][:19]}] {t['trace_type_name']}: {t.get('detail', '')[:70]}")

print("\n" + "=" * 60)
print("【9】客服热线 - 按身份证查工人工资到账状态")
code, res = http_request(f"{BASE_URL}/api/v1/query/worker/status?id_card=110101198805063456")
print(f"状态码: {code}, 共{res['total']}条")
for s in res['data']:
    print(f"  {s['worker_name']} 月份{s['salary_month']} 应发{s['payable_amount']} 状态:{s['status']} 批次:{s['batch_no']}")

print("\n✅ 全流程测试完成！")
