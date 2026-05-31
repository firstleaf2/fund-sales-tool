import random
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy import select
from app.db.database import async_session, init_db
from app.services.rag.vector_store import embed_fund, embed_customer
from app.models import Fund, Customer, Holding, Transaction, NAVHistory

FUND_DATA = [
    {"code": "000001", "name": "华夏成长混合A", "type": "mixed", "risk_level": "medium", "manager": "张明", "fee": 0.015, "desc": "主要投资于具有良好成长性的上市公司股票，追求资本长期增值"},
    {"code": "000002", "name": "易方达蓝筹精选", "type": "stock", "risk_level": "high", "manager": "李华", "fee": 0.015, "desc": "精选A股蓝筹龙头企业，分享中国经济增长红利"},
    {"code": "000003", "name": "南方稳健成长", "type": "mixed", "risk_level": "medium", "manager": "王强", "fee": 0.012, "desc": "在控制风险的前提下追求基金资产的稳健增值"},
    {"code": "000004", "name": "招商中证白酒", "type": "stock", "risk_level": "high", "manager": "赵伟", "fee": 0.015, "desc": "跟踪中证白酒指数，投资白酒行业龙头企业"},
    {"code": "000005", "name": "工银瑞信核心价值", "type": "stock", "risk_level": "high", "manager": "刘洋", "fee": 0.015, "desc": "投资于具有核心竞争力和持续增长能力的优质企业"},
    {"code": "000006", "name": "博时信用债券A", "type": "bond", "risk_level": "low", "manager": "陈静", "fee": 0.007, "desc": "主要投资于信用债券，追求稳定的当期收益"},
    {"code": "000007", "name": "中欧纯债A", "type": "bond", "risk_level": "low", "manager": "周磊", "fee": 0.006, "desc": "纯债策略，不参与股票投资，风险较低"},
    {"code": "000008", "name": "富国信用债A", "type": "bond", "risk_level": "low", "manager": "吴芳", "fee": 0.007, "desc": "投资于高信用等级债券，追求稳健收益"},
    {"code": "000009", "name": "广发聚利债券", "type": "bond", "risk_level": "low", "manager": "孙鹏", "fee": 0.006, "desc": "以利率债和高等级信用债为主要投资标的"},
    {"code": "000010", "name": "华安纯债A", "type": "bond", "risk_level": "low", "manager": "郑涛", "fee": 0.005, "desc": "纯债投资策略，适合风险偏好较低的投资者"},
    {"code": "000011", "name": "嘉实增长混合", "type": "mixed", "risk_level": "medium", "manager": "黄勇", "fee": 0.015, "desc": "灵活配置股票和债券，平衡风险与收益"},
    {"code": "000012", "name": "汇添富价值精选", "type": "mixed", "risk_level": "medium", "manager": "林峰", "fee": 0.015, "desc": "精选低估值优质企业，追求长期稳健回报"},
    {"code": "000013", "name": "天弘余额宝", "type": "money", "risk_level": "low", "manager": "马超", "fee": 0.003, "desc": "货币市场基金，流动性好，风险极低"},
    {"code": "000014", "name": "华夏现金增利", "type": "money", "risk_level": "low", "manager": "杨帆", "fee": 0.003, "desc": "投资于短期货币工具，提供现金管理服务"},
    {"code": "000015", "name": "南方现金通A", "type": "money", "risk_level": "low", "manager": "徐明", "fee": 0.003, "desc": "货币基金，适合短期闲置资金理财"},
    {"code": "000016", "name": "易方达货币A", "type": "money", "risk_level": "low", "manager": "何丽", "fee": 0.003, "desc": "低风险货币基金，每日计算收益"},
    {"code": "000017", "name": "博时货币A", "type": "money", "risk_level": "low", "manager": "罗刚", "fee": 0.003, "desc": "优质货币基金，兼顾安全性和收益性"},
    {"code": "000018", "name": "中欧医疗健康", "type": "stock", "risk_level": "high", "manager": "葛兰", "fee": 0.015, "desc": "聚焦医疗健康产业，投资创新药和医疗器械龙头"},
    {"code": "000019", "name": "景顺长城新兴成长", "type": "mixed", "risk_level": "medium", "manager": "刘彦春", "fee": 0.015, "desc": "投资新兴产业中的成长型企业"},
    {"code": "000020", "name": "兴全合润混合", "type": "mixed", "risk_level": "medium", "manager": "谢治宇", "fee": 0.015, "desc": "自下而上精选个股，追求绝对收益"},
]

CUSTOMER_DATA = [
    {"name": "李明", "phone": "13800138001", "email": "liming@example.com", "risk": "moderate", "notes": "企业主，投资经验丰富"},
    {"name": "张芳", "phone": "13800138002", "email": "zhangfang@example.com", "risk": "conservative", "notes": "退休教师，偏好稳健产品"},
    {"name": "王伟", "phone": "13800138003", "email": "wangwei@example.com", "risk": "aggressive", "notes": "IT从业者，愿意承担高风险"},
    {"name": "刘洋", "phone": "13800138004", "email": "liuyang@example.com", "risk": "moderate", "notes": "公务员，中等风险偏好"},
    {"name": "陈静", "phone": "13800138005", "email": "chenjing@example.com", "risk": "conservative", "notes": "家庭主妇，追求保本"},
    {"name": "赵强", "phone": "13800138006", "email": "zhaoqiang@example.com", "risk": "aggressive", "notes": "金融从业者，熟悉市场"},
    {"name": "孙丽", "phone": "13800138007", "email": "sunli@example.com", "risk": "moderate", "notes": "医生，稳健投资为主"},
    {"name": "周涛", "phone": "13800138008", "email": "zhoutao@example.com", "risk": "conservative", "notes": "临近退休，保守配置"},
    {"name": "吴磊", "phone": "13800138009", "email": "wulei@example.com", "risk": "aggressive", "notes": "年轻创业者，高风险高回报"},
    {"name": "郑欣", "phone": "13800138010", "email": "zhengxin@example.com", "risk": "moderate", "notes": "白领，定投为主"},
]


def _generate_nav_base(fund_type: str) -> float:
    if fund_type == "money":
        return 1.0
    elif fund_type == "bond":
        return round(random.uniform(1.0, 1.5), 4)
    elif fund_type == "mixed":
        return round(random.uniform(1.2, 3.0), 4)
    else:
        return round(random.uniform(1.5, 5.0), 4)


def _daily_volatility(fund_type: str) -> float:
    if fund_type == "money":
        return 0.0001
    elif fund_type == "bond":
        return 0.002
    elif fund_type == "mixed":
        return 0.01
    else:
        return 0.02


async def seed_database():
    async with async_session() as session:
        result = await session.execute(select(Fund).limit(1))
        if result.scalar_one_or_none() is not None:
            return

        today = date.today()
        funds = []
        for i, fd in enumerate(FUND_DATA):
            base_nav = _generate_nav_base(fd["type"])
            established = today - timedelta(days=random.randint(365, 3650))
            # 给部分基金设不同状态
            if i >= 18:
                fund_status = "liquidated"
            elif i >= 16:
                fund_status = "raising"
            else:
                fund_status = "active"
            fund = Fund(
                code=fd["code"],
                name=fd["name"],
                type=fd["type"],
                nav=Decimal(str(base_nav)),
                daily_change=Decimal(str(round(random.uniform(-0.03, 0.03), 4))),
                risk_level=fd["risk_level"],
                manager=fd["manager"],
                established_date=established,
                management_fee=Decimal(str(fd["fee"])),
                description=fd["desc"],
                status=fund_status,
            )
            session.add(fund)
            funds.append(fund)

        await session.flush()

        # NAV history (180 days)
        for fund in funds:
            vol = _daily_volatility(fund.type)
            nav = float(fund.nav)
            nav_records = []
            for i in range(180, 0, -1):
                d = today - timedelta(days=i)
                change = round(random.gauss(0.0002, vol), 4)
                nav = round(nav * (1 + change), 4)
                nav_records.append(NAVHistory(
                    fund_id=fund.id,
                    date=d,
                    nav=Decimal(str(nav)),
                    daily_change=Decimal(str(change)),
                ))
            session.add_all(nav_records)
            fund.nav = Decimal(str(nav))

        # Customers
        customers = []
        for cd in CUSTOMER_DATA:
            customer = Customer(
                name=cd["name"],
                phone=cd["phone"],
                email=cd["email"],
                risk_preference=cd["risk"],
                notes=cd["notes"],
                created_at=datetime.now() - timedelta(days=random.randint(30, 365)),
            )
            session.add(customer)
            customers.append(customer)

        await session.flush()

        # Holdings and Transactions
        for customer in customers:
            num_holdings = random.randint(2, 5)
            held_funds = random.sample(funds, num_holdings)
            total_assets = Decimal("0")

            for fund in held_funds:
                buy_date = today - timedelta(days=random.randint(1, 150))
                shares = Decimal(str(round(random.uniform(1000, 50000), 2)))
                cost = Decimal(str(round(float(fund.nav) * random.uniform(0.85, 1.05), 4)))
                amount = shares * cost

                holding = Holding(
                    customer_id=customer.id,
                    fund_id=fund.id,
                    shares=shares,
                    cost_price=cost,
                    purchase_date=buy_date,
                )
                session.add(holding)

                transaction = Transaction(
                    customer_id=customer.id,
                    fund_id=fund.id,
                    type="buy",
                    amount=amount,
                    shares=shares,
                    nav_at_trade=cost,
                    trade_date=datetime.combine(buy_date, datetime.min.time()),
                )
                session.add(transaction)

                market_value = shares * fund.nav
                total_assets += market_value

            customer.total_assets = total_assets

        await session.commit()

        # Embed to vector store
        for fund in funds:
            embed_fund(
                fund_id=fund.id,
                code=fund.code,
                name=fund.name,
                fund_type=fund.type,
                risk_level=fund.risk_level,
                manager=fund.manager or "",
                description=fund.description or "",
            )

        for customer in customers:
            holdings_summary = f"总资产约{float(customer.total_assets):.0f}元"
            embed_customer(
                customer_id=customer.id,
                name=customer.name,
                risk_preference=customer.risk_preference,
                holdings_summary=holdings_summary,
            )
