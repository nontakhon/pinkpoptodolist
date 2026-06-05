from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Date, JSON
from sqlalchemy.orm import relationship
from .database import Base

class Member(Base):
    __tablename__ = "members"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    avatar_emoji = Column(String)
    phone_number = Column(String)

class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    color_code = Column(String, nullable=False)
    icon_emoji = Column(String, nullable=False)
    rule = relationship("CategoryRule", back_populates="category", uselist=False, cascade="all, delete-orphan")

class CategoryRule(Base):
    __tablename__ = "category_rules"
    id = Column(Integer, primary_key=True, index=True)
    category_id = Column(Integer, ForeignKey("categories.id"))
    rule_type = Column(String, nullable=False, default="NONE") # 'ROUND_ROBIN', 'RANDOM', 'NONE'
    last_assigned_member_id = Column(Integer, ForeignKey("members.id"), nullable=True)
    
    category = relationship("Category", back_populates="rule")
    last_assigned_member = relationship("Member")

class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    title = Column(String, nullable=False)
    description = Column(String)
    status = Column(String, default="Pending") # 'Pending', 'Completed'
    assigned_member_id = Column(Integer, ForeignKey("members.id"), nullable=True)
    assignment_type = Column(String, default="UNASSIGNED") # UNASSIGNED, ANYONE, MEMBER
    created_by_member_id = Column(Integer, ForeignKey("members.id"), nullable=True)
    task_type = Column(String, nullable=False, default="MANUAL") # 'AUTO' or 'MANUAL'
    due_date = Column(Date, nullable=True)
    is_recurring = Column(Boolean, default=False)
    cron_expression = Column(String, nullable=True)
    note = Column(String, nullable=True)
    has_penalty = Column(Boolean, default=False)
    is_habit = Column(Boolean, default=False)
    time_block = Column(String, default="ANYTIME") # 'MORNING', 'AFTERNOON', 'EVENING', 'ANYTIME'
    value_amount = Column(Integer, default=0)
    
    template_task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
    recurrence_interval_days = Column(Integer, nullable=True)
    last_generated_date = Column(Date, nullable=True)
    recurrence_limit = Column(Integer, nullable=True)
    recurrence_count = Column(Integer, default=0)
    
    action_history = Column(JSON, default=list)
    
    category = relationship("Category")
    assigned_member = relationship("Member", foreign_keys=[assigned_member_id])
    created_by_member = relationship("Member", foreign_keys=[created_by_member_id])

class MemberLogin(Base):
    __tablename__ = "member_logins"
    id = Column(Integer, primary_key=True, index=True)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    login_date = Column(Date, nullable=False)
    created_at = Column(String, nullable=True) # ISO format timestamp
    
    member = relationship("Member")

