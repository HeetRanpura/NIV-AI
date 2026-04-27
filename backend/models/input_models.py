"""Input models for Niv AI analysis requests."""
from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class EmploymentType(str, Enum):
    SALARIED = "salaried"
    FREELANCE = "freelance"
    BUSINESS = "business"


class BuyerGender(str, Enum):
    MALE = "male"
    FEMALE = "female"


class Configuration(str, Enum):
    ONE_BHK = "1BHK"
    TWO_BHK = "2BHK"
    THREE_BHK = "3BHK"
    FOUR_BHK = "4BHK"
    FIVE_PLUS_BHK = "5+BHK"


class OutputLanguage(str, Enum):
    ENGLISH = "english"
    HINDI = "hindi"
    MARATHI = "marathi"


class FinancialInput(BaseModel):
    monthly_income: float = Field(..., gt=0)
    employment_type: EmploymentType = EmploymentType.SALARIED
    years_in_current_job: float = Field(default=2.0, ge=0, le=50)
    expected_annual_growth_pct: float = Field(default=8.0, ge=0, le=50)
    existing_emis: float = Field(default=0.0, ge=0)
    monthly_expenses: float = Field(default=0.0, ge=0)
    current_rent: float = Field(default=0.0, ge=0)
    liquid_savings: float = Field(default=0.0, ge=0)
    other_investments: float = Field(default=0.0, ge=0)
    dependents: int = Field(default=0, ge=0, le=20)
    spouse_income: float = Field(default=0.0, ge=0)
    financial_notes: str = Field(default="", max_length=2000)

    @field_validator("monthly_expenses", mode="before")
    @classmethod
    def default_expenses(cls, v, info):
        if (v == 0.0 or v is None) and "monthly_income" in info.data:
            return round(info.data["monthly_income"] * 0.40, 2)
        return v


class PropertyInput(BaseModel):
    property_price: float = Field(..., gt=100000)
    location_area: str = Field(..., min_length=2, max_length=100)
    location_city: str = Field(default="Mumbai")
    configuration: Configuration = Configuration.TWO_BHK
    carpet_area_sqft: float = Field(..., gt=50, le=50000)
    is_ready_to_move: bool = True
    is_rera_registered: Optional[bool] = None
    builder_name: str = Field(default="", max_length=200)
    possession_date: str = Field(default="", max_length=50)
    commute_distance_km: float = Field(default=0.0, ge=0)
    down_payment_available: float = Field(..., ge=0)
    loan_tenure_years: int = Field(default=20, ge=1, le=30)
    expected_interest_rate: float = Field(default=8.5, gt=0, le=20)
    buyer_gender: BuyerGender = BuyerGender.MALE
    is_first_property: bool = True
    property_notes: str = Field(default="", max_length=2000)

    @field_validator("down_payment_available")
    @classmethod
    def dp_sanity(cls, v, info):
        price = info.data.get("property_price", 0)
        if price > 0 and v >= price:
            raise ValueError("Down payment cannot exceed property price")
        return v


class AnalysisRequest(BaseModel):
    financial: FinancialInput
    property: PropertyInput
    output_language: OutputLanguage = OutputLanguage.ENGLISH
    behavioral_checklist_responses: Optional[dict] = None
