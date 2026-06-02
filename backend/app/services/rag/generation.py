import os
import re
import json
import uuid
from app.services.rag.intent import Intent, classify_intent_llm
from app.services.rag.hybrid_retrieval import hybrid_retrieve
from app.services.rag.tools import TOOLS, execute_tool

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

SYSTEM_PROMPTS = {
    Intent.RECOMMEND: "你是基金销售助手。根据客户的风险偏好和基金产品数据，推荐最合适的基金并说明理由。回答简洁实用。",
    Intent.FUND_QUERY: "你是基金销售助手。根据基金产品数据，回答用户关于基金产品的问题。回答简洁准确。",
    Intent.CUSTOMER_QUERY: "你是基金销售助手。根据客户数据，回答用户关于客户情况的问题。如果用户描述了与客户的沟通情况（如打电话、发微信、见面聊了什么），你必须调用 add_follow_up 工具将其记录为跟进记录。回答简洁准确。",
    Intent.MARKET: "你是基金销售助手。根据基金产品数据，提供市场分析和配置建议。回答简洁专业。",
    Intent.CHART: """你是基金销售助手。用户需要生成数据图表。你需要：
1. 调用 query_chart_data 工具获取数据
2. 根据获取到的数据，生成一个完整的 ECharts option JSON 配置
3. 将 ECharts option JSON 放在 ```chart-json 和 ``` 之间
4. 在 JSON 之外用一两句话描述图表内容

图表要求：
- option 必须是合法 JSON，不要有注释或尾逗号
- 必须包含 title、tooltip、series
- legend 放底部（bottom: 0）
- 所有文本用中文
- 不需要手动指定 color，使用 ECharts 默认配色

示例输出格式：
以下是按产品类型分组的基金数量分布饼图：

```chart-json
{"title":{"text":"产品类型分布","left":"center"},"tooltip":{"trigger":"item","formatter":"{b}: {c} ({d}%)"},"legend":{"bottom":0},"series":[{"type":"pie","radius":["40%","70%"],"data":[{"name":"股票型","value":5},{"name":"债券型","value":5}]}]}
```""",
    Intent.CHAT: "你是基金销售助手，可以帮助销售人员推荐基金、分析客户、了解市场。如果用户的问题与基金销售无关，友好引导回业务话题。",
}

FALLBACK_RESPONSES = {
    Intent.RECOMMEND: "根据客户的风险偏好，建议保守型客户配置债券型和货币型基金，稳健型客户可以混合配置，激进型客户可以考虑股票型基金。",
    Intent.FUND_QUERY: "系统中有股票型、债券型、混合型、货币型共 20 只基金产品。请告诉我您想了解哪只基金或哪种类型？",
    Intent.CUSTOMER_QUERY: "请告诉我您想查询哪位客户的信息，我可以帮您分析其风险偏好和持仓情况。",
    Intent.MARKET: "当前市场整体呈现结构性行情，建议关注业绩确定性强的行业龙头。债券市场收益率处于相对低位，货币基金收益稳定。",
    Intent.CHART: "抱歉，当前无法生成图表。您可以尝试：\n- 帮我生成产品类型分布饼图\n- 画一个销售趋势图\n- 生成客户风险偏好分布图",
    Intent.CHAT: "我是您的 AI 销售助手，可以帮您：\n- 根据客户风险偏好推荐基金\n- 查询基金产品信息\n- 分析客户持仓\n- 提供市场分析\n\n请告诉我您想了解什么？",
}


async def generate_response(message: str, conversation_id: str | None = None, history: list[dict] | None = None, episodic_context: str = "") -> dict:
    """
    完整流程：意图识别 → RAG 检索 → 置信度判断 → RAG 回答 / Function Calling 回答
    """
    if not conversation_id:
        conversation_id = f"conv_{uuid.uuid4().hex[:8]}"

    if history is None:
        history = []

    # 如果有情景记忆，插入到 history 最前面作为系统上下文
    if episodic_context:
        history = [{"role": "system", "content": episodic_context}] + history

    # Step 1: 意图识别
    intent = await classify_intent_llm(message)

    # Step 2: 混合检索（向量 + BM25 + 重排）
    retrieval_result = hybrid_retrieve(message, intent)
    results = retrieval_result["results"]
    confident = retrieval_result["confident"]

    # 构建 context 和 sources
    context = ""
    sources = []
    if results:
        context_parts = []
        for item in results:
            context_parts.append(f"- {item['document']}")
            meta = item.get("metadata", {})
            if "fund_id" in meta:
                sources.append({
                    "type": "fund",
                    "id": meta["fund_id"],
                    "name": item["document"].split(" (")[0] if " (" in item["document"] else "基金",
                })
            elif "customer_id" in meta:
                doc = item["document"]
                name = doc.split("客户:")[1].split(" -")[0] if "客户:" in doc else "客户"
                sources.append({
                    "type": "customer",
                    "id": meta["customer_id"],
                    "name": name,
                })
        context = "\n".join(context_parts)

    if not OPENAI_API_KEY:
        reply = FALLBACK_RESPONSES.get(intent, FALLBACK_RESPONSES[Intent.CHAT])
        return {"reply": reply, "sources": sources, "conversation_id": conversation_id}

    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)

        if intent == Intent.CHART:
            chart_result = await _generate_chart(client, message)
            return {"reply": chart_result["reply"], "sources": sources, "conversation_id": conversation_id, "chart": chart_result.get("chart")}
        elif confident and context and intent not in (Intent.CUSTOMER_QUERY,):
            reply = await _generate_with_context(client, message, context, intent, history)
        else:
            reply = await _generate_with_tools(client, message, intent, history)

        return {"reply": reply, "sources": sources, "conversation_id": conversation_id}

    except Exception as e:
        reply = FALLBACK_RESPONSES.get(intent, FALLBACK_RESPONSES[Intent.CHAT])
        return {"reply": reply, "sources": sources, "conversation_id": conversation_id}


async def _generate_with_context(client, message: str, context: str, intent: Intent, history: list[dict]) -> str:
    """RAG 路径：用检索到的 context 生成回答。"""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPTS[intent]},
        *history,
        {"role": "user", "content": f"用户问题: {message}\n\n系统数据:\n{context}\n\n请基于以上数据回答。"},
    ]
    response = await client.chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        max_tokens=500,
        temperature=0.7,
    )
    return response.choices[0].message.content or "抱歉，无法生成回答。"


async def _generate_with_tools(client, message: str, intent: Intent, history: list[dict], max_tokens: int = 500) -> str:
    """Function Calling 路径：Agent Loop，最多循环 10 次直到 LLM 不再调用工具。"""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPTS[intent] + "\n\n你可以使用工具查询系统数据库获取精确信息。需要多少信息就调用多少次工具，直到你能给出完整回答。"},
        *history,
        {"role": "user", "content": message},
    ]

    max_iterations = 10

    for _ in range(max_iterations):
        response = await client.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            max_tokens=max_tokens,
            temperature=0.7,
        )

        assistant_message = response.choices[0].message

        # LLM 没有调用工具，说明信息够了，返回最终回答
        if not assistant_message.tool_calls:
            return assistant_message.content or "抱歉，无法生成回答。"

        # 执行工具调用
        messages.append(assistant_message)

        for tool_call in assistant_message.tool_calls:
            func_name = tool_call.function.name
            func_args = json.loads(tool_call.function.arguments)
            result = await execute_tool(func_name, func_args)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result,
            })

        # 继续循环，让 LLM 决定是否还需要调用更多工具

    # 达到最大循环次数，强制生成回答
    response = await client.chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        max_tokens=max_tokens,
        temperature=0.7,
    )
    return response.choices[0].message.content or "抱歉，无法生成回答。"


async def generate_response_stream(message: str, conversation_id: str | None = None, history: list[dict] | None = None, episodic_context: str = ""):
    """
    流式生成。yield 每个 token chunk。
    先做意图识别和检索（非流式），然后流式生成回答。
    """
    if not conversation_id:
        conversation_id = f"conv_{uuid.uuid4().hex[:8]}"

    if history is None:
        history = []

    if episodic_context:
        history = [{"role": "system", "content": episodic_context}] + history

    intent = await classify_intent_llm(message)

    retrieval_result = hybrid_retrieve(message, intent)
    results = retrieval_result["results"]
    confident = retrieval_result["confident"]

    context = ""
    sources = []
    if results:
        context_parts = []
        for item in results:
            context_parts.append(f"- {item['document']}")
            meta = item.get("metadata", {})
            if "fund_id" in meta:
                sources.append({"type": "fund", "id": meta["fund_id"], "name": item["document"].split(" (")[0] if " (" in item["document"] else "基金"})
            elif "customer_id" in meta:
                doc = item["document"]
                name = doc.split("客户:")[1].split(" -")[0] if "客户:" in doc else "客户"
                sources.append({"type": "customer", "id": meta["customer_id"], "name": name})
        context = "\n".join(context_parts)

    if not OPENAI_API_KEY:
        reply = FALLBACK_RESPONSES.get(intent, FALLBACK_RESPONSES[Intent.CHAT])
        yield {"type": "meta", "sources": sources, "conversation_id": conversation_id}
        yield {"type": "content", "data": reply}
        yield {"type": "done"}
        return

    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)

        yield {"type": "meta", "sources": sources, "conversation_id": conversation_id}

        # Function Calling 路径不支持流式，先执行完再一次性输出
        if not (confident and context) or intent == Intent.CUSTOMER_QUERY:
            tool_result = await _generate_with_tools(client, message, intent, history)
            yield {"type": "content", "data": tool_result}
            yield {"type": "done"}
            return

        # RAG 路径：流式输出
        messages = [
            {"role": "system", "content": SYSTEM_PROMPTS[intent]},
            *history,
            {"role": "user", "content": f"用户问题: {message}\n\n系统数据:\n{context}\n\n请基于以上数据回答。"},
        ]

        stream = await client.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            max_tokens=500,
            temperature=0.7,
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield {"type": "content", "data": chunk.choices[0].delta.content}

        yield {"type": "done"}

    except Exception:
        reply = FALLBACK_RESPONSES.get(intent, FALLBACK_RESPONSES[Intent.CHAT])
        yield {"type": "content", "data": reply}
        yield {"type": "done"}


def _extract_chart(reply: str) -> dict | None:
    """从 LLM 回复中提取 chart-json 代码块，解析为 dict。"""
    match = re.search(r'```chart-json\s*\n?(.*?)\n?```', reply, re.DOTALL)
    if not match:
        match = re.search(r'```json\s*\n?(.*?)\n?```', reply, re.DOTALL)
    if not match:
        return None
    try:
        option = json.loads(match.group(1).strip())
        if not isinstance(option, dict) or "series" not in option:
            return None
        title = ""
        if "title" in option and isinstance(option["title"], dict):
            title = option["title"].get("text", "")
        return {"title": title, "option": option}
    except (json.JSONDecodeError, KeyError):
        return None


CHART_OPTION_PROMPT = """根据以下数据，生成一个 ECharts option JSON 对象。

用户需求：{user_request}

数据：
{data}

要求：
1. 返回一个完整的 ECharts option JSON 对象，不要有其他文字
2. 必须包含 title、tooltip、series 字段
3. legend 放底部（bottom: 0）
4. 所有文本用中文
5. 根据数据特征选择合适的图表类型（饼图用 pie，趋势用 line，分布用 bar）
6. 只返回 JSON，不要 markdown 代码块标记"""


async def _generate_chart(client, message: str) -> dict:
    """两步生成图表：先查数据，再生成 ECharts option。"""
    from app.services.rag.tools import execute_tool

    # Step 1: 让 LLM 决定查什么数据
    decide_messages = [
        {"role": "system", "content": "你是数据助手。根据用户的图表需求，决定调用 query_chart_data 查询什么数据。"},
        {"role": "user", "content": message},
    ]
    response = await client.chat.completions.create(
        model=LLM_MODEL,
        messages=decide_messages,
        tools=[t for t in TOOLS if t["function"]["name"] == "query_chart_data"],
        tool_choice={"type": "function", "function": {"name": "query_chart_data"}},
        max_tokens=200,
        temperature=0,
    )

    assistant_msg = response.choices[0].message
    if not assistant_msg.tool_calls:
        return {"reply": "无法理解您的图表需求，请描述得更具体一些。"}

    tool_call = assistant_msg.tool_calls[0]
    args = json.loads(tool_call.function.arguments)
    data_str = await execute_tool("query_chart_data", args)

    # Step 2: 用数据生成 ECharts option
    option_messages = [
        {"role": "user", "content": CHART_OPTION_PROMPT.format(user_request=message, data=data_str)},
    ]
    response2 = await client.chat.completions.create(
        model=LLM_MODEL,
        messages=option_messages,
        max_tokens=2000,
        temperature=0.3,
    )
    option_text = response2.choices[0].message.content or ""

    # 清理可能的 markdown 标记
    option_text = option_text.strip()
    if option_text.startswith("```"):
        option_text = re.sub(r'^```\w*\n?', '', option_text)
        option_text = re.sub(r'\n?```$', '', option_text)

    try:
        option = json.loads(option_text.strip())
        if not isinstance(option, dict) or "series" not in option:
            return {"reply": f"已查询到数据但图表生成失败，数据如下：\n{data_str}"}
        title = ""
        if "title" in option and isinstance(option["title"], dict):
            title = option["title"].get("text", "")
        chart = {"title": title, "option": option}

        # 生成简短文字描述
        data = json.loads(data_str)
        desc = f"已为您生成{title or '图表'}。"
        return {"reply": desc, "chart": chart}
    except json.JSONDecodeError:
        return {"reply": f"已查询到数据但图表生成失败，数据如下：\n{data_str}"}
