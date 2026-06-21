from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import settings
from app.database import engine, Base, SessionLocal
from app.routers import project_router, bank_router, query_router
from app.models.models import (
    Project, Worker, ProjectStatus
)


def init_database():
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        if db.query(Project).count() == 0:
            demo_projects = [
                Project(
                    project_code="PRJ2025001",
                    project_name="阳光花园住宅小区一期工程",
                    general_contractor="中天建设集团有限公司",
                    general_contractor_code="91330000MA001ABC12",
                    special_account_no="6222021234567890001",
                    special_account_bank="中国工商银行杭州市分行",
                    status=ProjectStatus.ACTIVE,
                    address="浙江省杭州市余杭区文一西路999号",
                    manager="张建国",
                    manager_phone="13800138001"
                ),
                Project(
                    project_code="PRJ2025002",
                    project_name="滨江科技园办公楼项目",
                    general_contractor="浙江建工集团有限责任公司",
                    general_contractor_code="91330000MA002DEF34",
                    special_account_no="6227001234567890002",
                    special_account_bank="中国建设银行杭州市滨江支行",
                    status=ProjectStatus.ACTIVE,
                    address="浙江省杭州市滨江区江南大道888号",
                    manager="李明辉",
                    manager_phone="13800138002"
                )
            ]
            db.add_all(demo_projects)
            db.flush()

        if db.query(Worker).count() == 0:
            demo_workers = [
                Worker(
                    id_card="110101199001011234",
                    name="王大伟",
                    gender="男",
                    phone="13900139001",
                    id_card_verified=1,
                    bank_card_no="6222021234567890101",
                    bank_name="中国工商银行",
                    bank_card_verified=1,
                    team_name="钢筋班组",
                    project_code="PRJ2025001",
                    work_type="钢筋工",
                    entry_date=None
                ),
                Worker(
                    id_card="110101199203042345",
                    name="刘强",
                    gender="男",
                    phone="13900139002",
                    id_card_verified=1,
                    bank_card_no="6222021234567890102",
                    bank_name="中国工商银行",
                    bank_card_verified=1,
                    team_name="钢筋班组",
                    project_code="PRJ2025001",
                    work_type="钢筋工",
                    entry_date=None
                ),
                Worker(
                    id_card="110101198805063456",
                    name="陈建国",
                    gender="男",
                    phone="13900139003",
                    id_card_verified=1,
                    bank_card_no="6222021234567890103",
                    bank_name="中国工商银行",
                    bank_card_verified=1,
                    team_name="木工班组",
                    project_code="PRJ2025001",
                    work_type="木工",
                    entry_date=None
                ),
                Worker(
                    id_card="110101199107084567",
                    name="赵秀兰",
                    gender="女",
                    phone="13900139004",
                    id_card_verified=1,
                    bank_card_no="6222021234567890104",
                    bank_name="中国工商银行",
                    bank_card_verified=1,
                    team_name="混凝土班组",
                    project_code="PRJ2025002",
                    work_type="混凝土工",
                    entry_date=None
                ),
                Worker(
                    id_card="110101199309105678",
                    name="孙志远",
                    gender="男",
                    phone="13900139005",
                    id_card_verified=1,
                    bank_card_no="6227001234567890105",
                    bank_name="中国建设银行",
                    bank_card_verified=1,
                    team_name="混凝土班组",
                    project_code="PRJ2025002",
                    work_type="混凝土工",
                    entry_date=None
                ),
                Worker(
                    id_card="110101198911126789",
                    name="周明华",
                    gender="男",
                    phone="13900139006",
                    id_card_verified=0,
                    bank_card_no=None,
                    bank_name=None,
                    bank_card_verified=0,
                    team_name="架子工班组",
                    project_code="PRJ2025002",
                    work_type="架子工",
                    entry_date=None
                ),
                Worker(
                    id_card="110101199001018888",
                    name="吴德胜",
                    gender="男",
                    phone="13900139007",
                    id_card_verified=1,
                    bank_card_no="",
                    bank_name="",
                    bank_card_verified=0,
                    team_name="瓦工班组",
                    project_code="PRJ2025001",
                    work_type="瓦工",
                    entry_date=None
                )
            ]
            db.add_all(demo_workers)

        db.commit()
    except Exception as e:
        print(f"初始化数据库演示数据失败: {e}")
        db.rollback()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_database()
    yield
    pass


app = FastAPI(
    title=settings.APP_NAME,
    description="""
## 农民工工资专户后端服务

### 服务目标
面向施工企业自有项目系统、银行代发系统和实名制平台对接使用，**统一专户发薪流程口径**。

### 三大核心能力
1. **工资批次提交校验**：项目系统提交工资表，服务返回校验结果（未实名/银行卡缺失/重复人员等）
2. **银行代发回传处理**：银行回传成功/失败/退票明细，服务统一整理每人到账状态给项目系统查询
3. **发薪轨迹全链路查询**：监管/客服系统按身份证号、项目编号、月份查询从工资表提交→专户审核→银行代发→失败重发的每一步，处理投诉和热线咨询

### 对接系统
- 👷 **施工企业项目系统** → `/api/v1/project/*`
- 🏦 **银行代发系统** → `/api/v1/bank/*`
- 🔍 **监管/客服热线系统** → `/api/v1/query/*`
    """,
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_prefix = settings.API_V1_PREFIX
app.include_router(project_router.router, prefix=api_prefix)
app.include_router(bank_router.router, prefix=api_prefix)
app.include_router(query_router.router, prefix=api_prefix)


@app.get("/", tags=["根路径"])
async def root():
    return {
        "app": settings.APP_NAME,
        "version": "1.0.0",
        "status": "running",
        "docs": {
            "swagger_ui": "/docs",
            "redoc": "/redoc"
        },
        "api_endpoints": {
            "project_system": f"{api_prefix}/project/*",
            "bank_system": f"{api_prefix}/bank/*",
            "supervision_query": f"{api_prefix}/query/*"
        }
    }


@app.get("/health", tags=["健康检查"])
async def health_check():
    return {"status": "ok", "service": settings.APP_NAME}
