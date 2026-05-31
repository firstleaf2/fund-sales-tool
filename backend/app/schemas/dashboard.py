from pydantic import BaseModel


class DashboardSummary(BaseModel):
    total_sales: float
    total_customers: int
    total_aum: float
    monthly_sales: float


class SalesTrendItem(BaseModel):
    date: str
    amount: float


class SalesTrendResponse(BaseModel):
    period: str
    data: list[SalesTrendItem]


class ProductDistributionItem(BaseModel):
    type: str
    label: str
    amount: float
    percentage: float


class ProductDistributionResponse(BaseModel):
    data: list[ProductDistributionItem]
