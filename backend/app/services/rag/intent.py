"""
三层意图识别模块。
Layer 1: 关键词规则匹配（快，覆盖明确表达）
Layer 2: Embedding 相似度（中，覆盖模糊表达）
Layer 3: LLM 分类（慢，兜底复杂表达）

命中即停，不往下走。
"""

import os
import json
import numpy as np
from enum import Enum


class Intent(Enum):
    RECOMMEND = "recommend"
    FUND_QUERY = "fund_query"
    CUSTOMER_QUERY = "customer"
    MARKET = "market"
    CHART = "chart"
    CHAT = "chat"


# ============================================================
# Layer 1: 关键词规则
# ============================================================

def _layer1_keywords(message: str) -> Intent | None:
    """明确关键词命中，直接返回意图。"""
    if any(k in message for k in ["饼图", "柱状图", "折线图", "趋势图", "可视化", "画个图", "生成图", "画一个"]):
        return Intent.CHART
    if any(k in message for k in ["图表", "画图"]) and any(k in message for k in ["生成", "画", "做", "帮"]):
        return Intent.CHART
    if ("推荐" in message or "适合" in message or "配置" in message) and \
       any(k in message for k in ["客户", "给", "帮"]):
        return Intent.RECOMMEND
    if any(k in message for k in ["持仓", "盈亏", "亏了", "赚了"]) and \
       any(k in message for k in ["客户", "他", "她"]):
        return Intent.CUSTOMER_QUERY
    if any(k in message for k in ["跟进", "沟通", "聊了", "打了电话", "发了微信", "见了面", "记录一下"]):
        return Intent.CUSTOMER_QUERY
    if any(k in message for k in ["净值", "费率", "基金经理", "成立日期"]):
        return Intent.FUND_QUERY
    if any(k in message for k in ["市场行情", "大盘走势", "市场趋势"]):
        return Intent.MARKET
    if "股市" in message or ("行情" in message and "客户" not in message):
        return Intent.MARKET
    # 明确的打招呼
    if message.strip() in ("你好", "hi", "hello", "在吗", "你是谁"):
        return Intent.CHAT
    return None


# ============================================================
# Layer 2: Embedding 相似度
# ============================================================

# 每种意图的示例句（用于计算相似度）
INTENT_EXAMPLES = {
    Intent.RECOMMEND: [
        "给客户张三推荐什么基金",
        "帮李明选一个合适的产品",
        "这个客户适合买什么",
        "根据风险偏好推荐基金",
        "保守型客户应该买什么",
        "帮老王看看买什么合适",
        "给他推荐个产品",
        "客户该怎么配置",
    ],
    Intent.FUND_QUERY: [
        "华夏成长混合怎么样",
        "这只基金的净值是多少",
        "有哪些债券型基金",
        "管理费率多少",
        "基金经理是谁",
    ],
    Intent.CUSTOMER_QUERY: [
        "李明的持仓情况",
        "这个客户买了什么",
        "客户的风险偏好是什么",
        "他的总资产多少",
        "客户赚了还是亏了",
    ],
    Intent.MARKET: [
        "最近市场怎么样",
        "股市行情如何",
        "债券市场走势",
        "现在适合买入吗",
        "市场趋势分析",
        "最近股市怎么样",
        "大盘涨了还是跌了",
        "行情好不好",
    ],
    Intent.CHAT: [
        "你好",
        "谢谢",
        "今天天气怎么样",
        "你能做什么",
        "再见",
    ],
    Intent.CHART: [
        "帮我生成一个按产品类型分组的规模占比饼图",
        "画一个最近30天的销售趋势图",
        "生成客户风险偏好分布柱状图",
        "做个各基金净值走势的折线图",
        "可视化一下产品分布",
        "画个图看看销售情况",
        "帮我画一个饼图",
        "生成图表分析一下",
    ],
}

_embeddings_cache: dict[Intent, np.ndarray] | None = None


def _get_embedding_model():
    """懒加载 embedding 模型。用 ChromaDB 自带的 default embedding function。"""
    try:
        from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
        return DefaultEmbeddingFunction()
    except Exception:
        return None


def _build_intent_embeddings():
    """预计算所有示例句的 embedding。"""
    global _embeddings_cache
    if _embeddings_cache is not None:
        return _embeddings_cache

    model = _get_embedding_model()
    if model is None:
        _embeddings_cache = {}
        return _embeddings_cache

    _embeddings_cache = {}
    for intent, examples in INTENT_EXAMPLES.items():
        vectors = model(examples)
        _embeddings_cache[intent] = np.array(vectors)

    return _embeddings_cache


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    dot = np.dot(a, b)
    norm = np.linalg.norm(a) * np.linalg.norm(b)
    return float(dot / norm) if norm > 0 else 0.0


def _layer2_embedding(message: str, threshold: float = 0.65) -> Intent | None:
    """用 embedding 相似度匹配意图。超过阈值则命中。"""
    model = _get_embedding_model()
    if model is None:
        return None

    intent_embeddings = _build_intent_embeddings()
    if not intent_embeddings:
        return None

    query_vec = np.array(model([message])[0])

    best_intent = None
    best_score = 0.0

    for intent, example_vecs in intent_embeddings.items():
        # 取与所有示例的最大相似度
        similarities = [_cosine_similarity(query_vec, ev) for ev in example_vecs]
        max_sim = max(similarities) if similarities else 0.0
        if max_sim > best_score:
            best_score = max_sim
            best_intent = intent

    if best_score >= threshold:
        return best_intent
    return None


# ============================================================
# Layer 3: LLM 分类
# ============================================================

INTENT_PROMPT = """你是一个意图分类器。根据用户的输入，判断属于以下哪种意图：

- recommend: 用户想为某个客户推荐基金、做资产配置建议
- fund_query: 用户想查询某只基金或某类基金的信息（净值、费率、经理等）
- customer: 用户想查询某个客户的信息（持仓、风险偏好、资产）
- market: 用户想了解市场行情、趋势分析
- chart: 用户想生成图表、数据可视化（饼图、柱状图、折线图、趋势图等）
- chat: 闲聊、打招呼、与基金销售无关的问题

只返回一个 JSON：{"intent": "xxx"}
不要返回其他内容。"""


async def _layer3_llm(message: str) -> Intent:
    """LLM 兜底分类。"""
    api_key = os.getenv("OPENAI_API_KEY", "")
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")

    if not api_key:
        return Intent.CHAT

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": INTENT_PROMPT},
                {"role": "user", "content": message},
            ],
            max_tokens=30,
            temperature=0,
        )

        content = response.choices[0].message.content or ""
        result = json.loads(content.strip().strip("`").replace("json", "").strip())
        intent_str = result.get("intent", "chat")

        for intent in Intent:
            if intent.value == intent_str:
                return intent
        return Intent.CHAT

    except Exception:
        return Intent.CHAT


# ============================================================
# 统一入口：三层递进
# ============================================================

async def classify_intent_llm(message: str) -> Intent:
    """
    三层意图识别，命中即停：
    1. 关键词规则 → 命中直接返回
    2. Embedding 相似度 → 超过阈值返回
    3. LLM 分类 → 兜底
    """
    # Layer 1
    result = _layer1_keywords(message)
    if result is not None:
        return result

    # Layer 2
    result = _layer2_embedding(message)
    if result is not None:
        return result

    # Layer 3
    return await _layer3_llm(message)


def classify_intent(message: str) -> Intent:
    """同步版本降级：只走 Layer 1 + Layer 2。"""
    result = _layer1_keywords(message)
    if result is not None:
        return result
    result = _layer2_embedding(message)
    if result is not None:
        return result
    return Intent.CHAT
