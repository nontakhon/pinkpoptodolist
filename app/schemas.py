from pydantic import BaseModel
from typing import Optional, List
from datetime import date

class MemberBase(BaseModel):
    name: str
    avatar_emoji: Optional[str] = None
    phone_number: Optional[str] = None

class MemberCreate(MemberBase):
    pass

class MemberUpdate(BaseModel):
    name: str
    avatar_emoji: str

class Member(MemberBase):
    id: int
    class Config:
        from_attributes = True

class CategoryRuleBase(BaseModel):
    rule_type: str
    last_assigned_member_id: Optional[int] = None

class CategoryRuleCreate(CategoryRuleBase):
    pass

class CategoryRule(CategoryRuleBase):
    id: int
    category_id: int
    class Config:
        from_attributes = True

class CategoryBase(BaseModel):
    name: str
    color_code: str
    icon_emoji: str

class CategoryCreate(CategoryBase):
    rule: Optional[CategoryRuleCreate] = None

class Category(CategoryBase):
    id: int
    rule: Optional[CategoryRule] = None
    class Config:
        from_attributes = True

class TaskBase(BaseModel):
    category_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    status: Optional[str] = "Pending"
    assigned_member_id: Optional[int] = None
    assignment_type: Optional[str] = "UNASSIGNED"
    created_by_member_id: Optional[int] = None
    task_type: str = "MANUAL"
    due_date: Optional[date] = None
    is_recurring: Optional[bool] = False
    cron_expression: Optional[str] = None
    note: Optional[str] = None
    admin_note: Optional[str] = None
    is_reviewed: Optional[bool] = False
    has_penalty: bool = False
    is_habit: bool = False
    time_block: str = "ANYTIME"
    value_amount: int = 0
    template_task_id: Optional[int] = None
    recurrence_interval_days: Optional[int] = None
    last_generated_date: Optional[date] = None
    recurrence_limit: Optional[int] = None
    recurrence_count: Optional[int] = 0
    action_history: Optional[list] = []

class TaskNoteUpdate(BaseModel):
    note: str

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    category_id: Optional[int] = None
    assigned_member_id: Optional[int] = None
    status: Optional[str] = None
    note: Optional[str] = None
    admin_note: Optional[str] = None
    is_reviewed: Optional[bool] = None
    value_amount: Optional[int] = None

class TaskCreate(TaskBase):
    pass

class Task(TaskBase):
    id: int
    category: Optional[Category] = None
    assigned_member: Optional[Member] = None
    created_by_member: Optional[Member] = None
    class Config:
        from_attributes = True
