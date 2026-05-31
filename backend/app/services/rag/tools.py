"""
Function Calling 工具集。
当 RAG 检索置信度不够时，LLM 通过这些工具直接查 SQL 获取精确数据。
"""

from datetime import datetime
from sqlalchemy import select, func
from app.db.database import async_session
from app.models.fund import Fund
from app.models.customer import Customer
from app.models.holding import Holding
from app.models.follow_up import FollowUp
from app.models.transaction import Transaction
from app.models.nav_history import NAVHistory

# 工具定义（OpenAI function calling 格式）
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_funds_by_type",
            "description": "按类型查询基金产品列表",
            "parameters": {
                "type": "object",
                "properties": {
                    "fund_type": {
                        "type": "string",
                        "enum": ["stock", "bond", "mixed", "money"],
                        "description": "基金类型：stock=股票型, bond=债券型, mixed=混合型, money=货币型"
                    }
                },
                "required": ["fund_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_fund_by_name",
            "description": "按名称模糊查询基金产品详情",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "基金名称关键词"
                    }
                },
                "required": ["keyword"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_customer_info",
            "description": "查询客户基本信息和风险偏好",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "客户姓名"
                    }
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_customer_holdings",
            "description": "查询客户的持仓明细，包括持有基金、份额、盈亏",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "客户姓名"
                    }
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_follow_up",
            "description": "为客户添加跟进记录。当用户描述了与客户的沟通情况时调用此工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {
                        "type": "string",
                        "description": "客户姓名"
                    },
                    "contact_method": {
                        "type": "string",
                        "enum": ["phone", "wechat", "meeting", "email"],
                        "description": "沟通方式：phone=电话, wechat=微信, meeting=面谈, email=邮件"
                    },
                    "content": {
                        "type": "string",
                        "description": "跟进内容摘要"
                    }
                },
                "required": ["customer_name", "contact_method", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_chart_data",
            "description": "查询用于生成图表的数据。支持：product_distribution(按基金类型统计数量和规模), sales_trend(销售趋势), customer_risk(客户风险偏好分布), nav_history(基金净值走势)",
            "parameters": {
                "type": "object",
                "properties": {
                    "data_type": {
                        "type": "string",
                        "enum": ["product_distribution", "sales_trend", "customer_risk", "nav_history"],
                        "description": "数据类型"
                    },
                    "period": {
                        "type": "string",
                        "enum": ["day", "week", "month"],
                        "description": "时间粒度，仅 sales_trend 使用，默认 day"
                    },
                    "days": {
                        "type": "integer",
                        "description": "查询天数，仅 sales_trend 和 nav_history 使用，默认 30"
                    },
                    "fund_name": {
                        "type": "string",
                        "description": "基金名称关键词，仅 nav_history 使用。不传则返回所有基金"
                    }
                },
                "required": ["data_type"]
            }
        }
    },
]


async def execute_tool(name: str, arguments: dict) -> str:
    """执行工具调用，返回结果文本。"""
    if name == "search_funds_by_type":
        return await _search_funds_by_type(arguments["fund_type"])
    elif name == "get_fund_by_name":
        return await _get_fund_by_name(arguments["keyword"])
    elif name == "get_customer_info":
        return await _get_customer_info(arguments["name"])
    elif name == "get_customer_holdings":
        return await _get_customer_holdings(arguments["name"])
    elif name == "add_follow_up":
        return await _add_follow_up(arguments["customer_name"], arguments["contact_method"], arguments["content"])
    elif name == "query_chart_data":
        return await _query_chart_data(arguments)
    return "未知工具"


async def _search_funds_by_type(fund_type: str) -> str:
    type_labels = {"stock": "股票型", "bond": "债券型", "mixed": "混合型", "money": "货币型"}
    async with async_session() as session:
        result = await session.execute(
            select(Fund).where(Fund.type == fund_type, Fund.status == "active")
        )
        funds = result.scalars().all()
        if not funds:
            return f"未找到{type_labels.get(fund_type, fund_type)}基金"
        lines = [f"{type_labels.get(fund_type, fund_type)}基金共{len(funds)}只："]
        for f in funds:
            lines.append(f"- {f.name}({f.code}) 净值:{float(f.nav):.4f} 风险:{f.risk_level} 经理:{f.manager}")
        return "\n".join(lines)


async def _get_fund_by_name(keyword: str) -> str:
    async with async_session() as session:
        result = await session.execute(
            select(Fund).where(Fund.name.contains(keyword))
        )
        funds = result.scalars().all()
        if not funds:
            return f"未找到名称包含'{keyword}'的基金"
        lines = []
        for f in funds:
            lines.append(
                f"{f.name}({f.code})\n"
                f"  类型:{f.type} 净值:{float(f.nav):.4f} 日涨跌:{float(f.daily_change or 0)*100:.2f}%\n"
                f"  风险:{f.risk_level} 经理:{f.manager} 费率:{float(f.management_fee or 0)*100:.2f}%\n"
                f"  简介:{f.description or '无'}"
            )
        return "\n".join(lines)


async def _get_customer_info(name: str) -> str:
    async with async_session() as session:
        result = await session.execute(
            select(Customer).where(Customer.name.contains(name))
        )
        customer = result.scalar_one_or_none()
        if not customer:
            return f"未找到客户'{name}'"
        risk_labels = {"conservative": "保守型", "moderate": "稳健型", "aggressive": "激进型"}
        return (
            f"客户: {customer.name}\n"
            f"风险偏好: {risk_labels.get(customer.risk_preference, customer.risk_preference)}\n"
            f"总资产: ¥{float(customer.total_assets):,.2f}\n"
            f"联系方式: {customer.phone or '无'}\n"
            f"备注: {customer.notes or '无'}"
        )


async def _get_customer_holdings(name: str) -> str:
    async with async_session() as session:
        result = await session.execute(
            select(Customer).where(Customer.name.contains(name))
        )
        customer = result.scalar_one_or_none()
        if not customer:
            return f"未找到客户'{name}'"

        result = await session.execute(
            select(Holding).where(Holding.customer_id == customer.id)
        )
        holdings = result.scalars().all()
        if not holdings:
            return f"客户{customer.name}暂无持仓"

        lines = [f"客户{customer.name}的持仓明细："]
        total_value = 0.0
        total_profit = 0.0

        for h in holdings:
            fund_result = await session.execute(select(Fund).where(Fund.id == h.fund_id))
            fund = fund_result.scalar_one()
            shares = float(h.shares)
            cost = float(h.cost_price)
            nav = float(fund.nav)
            market_value = shares * nav
            profit = market_value - shares * cost
            profit_rate = profit / (shares * cost) * 100

            total_value += market_value
            total_profit += profit

            lines.append(
                f"- {fund.name}({fund.code}): "
                f"份额{shares:.0f} 成本{cost:.4f} 现价{nav:.4f} "
                f"市值¥{market_value:,.0f} 盈亏{'+' if profit >= 0 else ''}¥{profit:,.0f}({profit_rate:+.1f}%)"
            )

        lines.append(f"\n总市值: ¥{total_value:,.0f} 总盈亏: {'+' if total_profit >= 0 else ''}¥{total_profit:,.0f}")
        return "\n".join(lines)


async def _add_follow_up(customer_name: str, contact_method: str, content: str) -> str:
    method_labels = {"phone": "电话", "wechat": "微信", "meeting": "面谈", "email": "邮件"}
    async with async_session() as session:
        result = await session.execute(
            select(Customer).where(Customer.name.contains(customer_name))
        )
        customer = result.scalar_one_or_none()
        if not customer:
            return f"未找到客户'{customer_name}'，无法添加跟进记录"

        record = FollowUp(
            customer_id=customer.id,
            contact_method=contact_method,
            content=content,
            follow_date=datetime.now(),
        )
        session.add(record)
        await session.commit()

        return f"已为客户{customer.name}添加跟进记录：{method_labels.get(contact_method, contact_method)} - {content}"


async def _query_chart_data(arguments: dict) -> str:
    """查询图表所需数据，返回 JSON 格式。"""
    import json
    from datetime import timedelta

    data_type = arguments["data_type"]
    days = arguments.get("days", 30)

    async with async_session() as session:
        if data_type == "product_distribution":
            result = await session.execute(
                select(Fund.type, func.count(Fund.id)).where(Fund.status == "active").group_by(Fund.type)
            )
            rows = result.all()
            type_labels = {"stock": "股票型", "bond": "债券型", "mixed": "混合型", "money": "货币型"}
            data = [{"name": type_labels.get(r[0], r[0]), "value": r[1]} for r in rows]
            return json.dumps({"type": "product_distribution", "data": data}, ensure_ascii=False)

        elif data_type == "sales_trend":
            since = datetime.now() - timedelta(days=days)
            result = await session.execute(
                select(Transaction.trade_date, func.sum(Transaction.amount))
                .where(Transaction.trade_date >= since)
                .group_by(Transaction.trade_date)
                .order_by(Transaction.trade_date)
            )
            rows = result.all()
            data = [{"date": r[0].strftime("%m-%d"), "amount": float(r[1])} for r in rows]
            return json.dumps({"type": "sales_trend", "data": data, "days": days}, ensure_ascii=False)

        elif data_type == "customer_risk":
            result = await session.execute(
                select(Customer.risk_preference, func.count(Customer.id)).group_by(Customer.risk_preference)
            )
            rows = result.all()
            risk_labels = {"conservative": "保守型", "moderate": "稳健型", "aggressive": "激进型"}
            data = [{"name": risk_labels.get(r[0], r[0]), "value": r[1]} for r in rows]
            return json.dumps({"type": "customer_risk", "data": data}, ensure_ascii=False)

        elif data_type == "nav_history":
            fund_name = arguments.get("fund_name")
            query = select(NAVHistory.date, NAVHistory.nav, Fund.name).join(Fund, NAVHistory.fund_id == Fund.id)
            if fund_name:
                query = query.where(Fund.name.contains(fund_name))
            else:
                query = query.where(Fund.id <= 3)
            since = datetime.now() - timedelta(days=days)
            query = query.where(NAVHistory.date >= since.strftime("%Y-%m-%d")).order_by(NAVHistory.date)
            result = await session.execute(query)
            rows = result.all()
            series_map = {}
            for date, nav, name in rows:
                date_str = date if isinstance(date, str) else date.strftime("%m-%d")
                if name not in series_map:
                    series_map[name] = []
                series_map[name].append({"date": date_str, "nav": float(nav)})
            data = [{"fund_name": k, "values": v} for k, v in series_map.items()]
            return json.dumps({"type": "nav_history", "data": data, "days": days}, ensure_ascii=False)

    return json.dumps({"error": "不支持的数据类型"}, ensure_ascii=False)
