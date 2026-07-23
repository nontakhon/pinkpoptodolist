from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect, UploadFile, File
import os
import shutil
import uuid
from pydantic import BaseModel
from typing import Optional
import datetime
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date, datetime, timedelta
import random
import os
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from croniter import croniter

from . import models, schemas
from .database import engine, get_db, SessionLocal

models.Base.metadata.create_all(bind=engine)


app = FastAPI(title="pinkpop")

# --- WebSocket Manager ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                pass

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)



scheduler = BackgroundScheduler()

def send_notification(message: str):
    print(f"🔔 MOCK NOTIFICATION: {message}")

def generate_recurring_tasks():
    print("⏰ Running recurring task generator...")
    db = SessionLocal()
    try:
        today = date.today()
        templates = db.query(models.Task).filter(models.Task.status == "Template", models.Task.is_active == True).all()
        for template in templates:
            if not template.cron_expression and not template.recurrence_interval_days:
                continue
            
            match = False
            today = date.today()
            now = datetime.combine(today, datetime.min.time())
            
            if template.cron_expression:
                match = croniter.match(template.cron_expression, now)
            elif template.recurrence_interval_days:
                if not template.last_generated_date:
                    match = True
                else:
                    days_diff = (today - template.last_generated_date).days
                    if days_diff >= template.recurrence_interval_days:
                        match = True

            if match:
                existing = db.query(models.Task).filter(
                    models.Task.template_task_id == template.id,
                    models.Task.due_date == today
                ).first()
                if not existing:
                    new_task_data = {
                        "category_id": template.category_id,
                        "title": template.title,
                        "description": template.description,
                        "status": "Pending",
                        "assigned_member_id": template.assigned_member_id,
                        "assignment_type": template.assignment_type,
                        "created_by_member_id": template.created_by_member_id,
                        "task_type": "AUTO",
                        "due_date": today,
                        "is_recurring": False,
                        "is_habit": template.is_habit,
                        "time_block": template.time_block,
                        "value_amount": template.value_amount,
                        "template_task_id": template.id
                    }
                    
                    category = template.category
                    if category and category.rule and not new_task_data.get("assigned_member_id"):
                        rule = category.rule
                        members = db.query(models.Member).all()
                        if members:
                            if rule.rule_type == "RANDOM":
                                chosen = random.choice(members)
                                new_task_data["assigned_member_id"] = chosen.id
                                new_task_data["assignment_type"] = "MEMBER"
                                send_notification(f"Recurring Task '{template.title}' assigned to {chosen.name} via RANDOM.")
                            elif rule.rule_type == "ROUND_ROBIN":
                                last_id = rule.last_assigned_member_id
                                if not last_id:
                                    chosen = members[0]
                                else:
                                    member_ids = [m.id for m in members]
                                    try:
                                        idx = member_ids.index(last_id)
                                        next_idx = (idx + 1) % len(member_ids)
                                        chosen = members[next_idx]
                                    except ValueError:
                                        chosen = members[0]
                                new_task_data["assigned_member_id"] = chosen.id
                                new_task_data["assignment_type"] = "MEMBER"
                                rule.last_assigned_member_id = chosen.id
                                db.commit()
                                if 'background_tasks' in locals():
                                    background_tasks.add_task(manager.broadcast, '{"event": "refresh"}')
                                send_notification(f"Recurring Task '{template.title}' assigned to {chosen.name} via ROUND_ROBIN.")

                    db_task = models.Task(**new_task_data)
                    db.add(db_task)
                    
                    # Update template
                    template.recurrence_count = (template.recurrence_count or 0) + 1
                    template.last_generated_date = today
                    if template.recurrence_limit and template.recurrence_count >= template.recurrence_limit:
                        template.status = "Completed_Template"
                        
                    db.commit()
                    if 'background_tasks' in locals():
                        background_tasks.add_task(manager.broadcast, '{"event": "refresh"}')
    except Exception as e:
        print(f"Error generating tasks: {e}")
    finally:
        db.close()

@app.on_event("startup")
def startup_event():
    scheduler.add_job(generate_recurring_tasks, CronTrigger(hour=0, minute=0))
    scheduler.add_job(generate_recurring_tasks, 'date', run_date=datetime.now())
    scheduler.start()

@app.post("/members/", response_model=schemas.Member)
def create_member(member: schemas.MemberCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    db_member = models.Member(**member.model_dump())
    db.add(db_member)
    db.commit()
    if 'background_tasks' in locals():
        background_tasks.add_task(manager.broadcast, '{"event": "refresh"}')
    db.refresh(db_member)
    return db_member

@app.get("/members/", response_model=List[schemas.Member])
def read_members(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(models.Member).offset(skip).limit(limit).all()

@app.put("/members/{member_id}", response_model=schemas.Member)
def update_member(member_id: int, payload: schemas.MemberUpdate, db: Session = Depends(get_db)):
    member = db.query(models.Member).filter(models.Member.id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    member.name = payload.name
    member.avatar_emoji = payload.avatar_emoji
    db.commit()
    if 'background_tasks' in locals():
        background_tasks.add_task(manager.broadcast, '{"event": "refresh"}')
    db.refresh(member)
    return member

@app.delete("/members/{member_id}")
def delete_member(member_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    member = db.query(models.Member).filter(models.Member.id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    
    # Nullify assigned tasks
    tasks = db.query(models.Task).filter(models.Task.assigned_member_id == member_id).all()
    for t in tasks:
        t.assigned_member_id = None
        
    db.delete(member)
    db.commit()
    if 'background_tasks' in locals():
        background_tasks.add_task(manager.broadcast, '{"event": "refresh"}')
    return {"message": "Member deleted successfully"}

@app.post("/categories/", response_model=schemas.Category)
def create_category(category: schemas.CategoryCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    rule_data = category.rule
    cat_data = category.model_dump(exclude={"rule"})
    db_category = models.Category(**cat_data)
    db.add(db_category)
    db.commit()
    if 'background_tasks' in locals():
        background_tasks.add_task(manager.broadcast, '{"event": "refresh"}')
    db.refresh(db_category)
    
    if rule_data:
        db_rule = models.CategoryRule(**rule_data.model_dump(), category_id=db_category.id)
        db.add(db_rule)
        db.commit()
        if 'background_tasks' in locals():
            background_tasks.add_task(manager.broadcast, '{"event": "refresh"}')
        db.refresh(db_category)
    return db_category

@app.delete("/categories/{category_id}")
def delete_category(category_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    category = db.query(models.Category).filter(models.Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    tasks = db.query(models.Task).filter(models.Task.category_id == category_id).all()
    for task in tasks:
        task.category_id = None
        
    db.delete(category)
    db.commit()
    if 'background_tasks' in locals():
        background_tasks.add_task(manager.broadcast, '{"event": "refresh"}')
    return {"message": "Category deleted successfully"}

@app.get("/categories/", response_model=List[schemas.Category])
def read_categories(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(models.Category).offset(skip).limit(limit).all()


os.makedirs("static/uploads", exist_ok=True)

@app.post("/upload/")
async def upload_image(file: UploadFile = File(...)):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    file_extension = file.filename.split(".")[-1]
    filename = f"{uuid.uuid4()}.{file_extension}"
    file_location = f"static/uploads/{filename}"
    
    with open(file_location, "wb+") as file_object:
        shutil.copyfileobj(file.file, file_object)
        
    return {"url": f"uploads/{filename}"}

@app.post("/tasks/", response_model=schemas.Task)
def create_task(task: schemas.TaskCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    task_data = task.model_dump()
    
    if task_data.get("is_recurring"):
        task_data["status"] = "Template"
        task_data["due_date"] = None
    elif not task_data.get("due_date"):
        task_data["due_date"] = date.today()
    
    if not task_data.get("category_id"):
        # "งานส่วนตัว (Personal Task)"
        personal_cat = db.query(models.Category).filter(models.Category.name == "งานส่วนตัว").first()
        if not personal_cat:
            personal_cat = models.Category(name="งานส่วนตัว", color_code="#E5E7EB", icon_emoji="👤")
            db.add(personal_cat)
            db.commit()
            if 'background_tasks' in locals():
                background_tasks.add_task(manager.broadcast, '{"event": "refresh"}')
            db.refresh(personal_cat)
        task_data["category_id"] = personal_cat.id
        if not task_data.get("assigned_member_id") and task_data.get("created_by_member_id"):
            task_data["assigned_member_id"] = task_data.get("created_by_member_id")
            task_data["assignment_type"] = "MEMBER"

    else:
        # Check routing
        category = db.query(models.Category).filter(models.Category.id == task_data["category_id"]).first()
        if category and category.rule and not task_data.get("assigned_member_id"):
            rule = category.rule
            members = db.query(models.Member).all()
            if members:
                if rule.rule_type == "RANDOM":
                    chosen = random.choice(members)
                    task_data["assigned_member_id"] = chosen.id
                    task_data["assignment_type"] = "MEMBER"
                    send_notification(f"Task '{task_data['title']}' assigned to {chosen.name} via RANDOM.")
                elif rule.rule_type == "ROUND_ROBIN":
                    last_id = rule.last_assigned_member_id
                    if not last_id:
                        chosen = members[0]
                    else:
                        member_ids = [m.id for m in members]
                        try:
                            idx = member_ids.index(last_id)
                            next_idx = (idx + 1) % len(member_ids)
                            chosen = members[next_idx]
                        except ValueError:
                            chosen = members[0]
                    task_data["assigned_member_id"] = chosen.id
                    task_data["assignment_type"] = "MEMBER"
                    rule.last_assigned_member_id = chosen.id
                    db.commit()
                    if 'background_tasks' in locals():
                        background_tasks.add_task(manager.broadcast, '{"event": "refresh"}')
                    send_notification(f"Task '{task_data['title']}' assigned to {chosen.name} via ROUND_ROBIN.")

    db_task = models.Task(**task_data)
    db.add(db_task)
    db.commit()
    
    if db_task.status == "Template":
        bulk_spawn_template(db, db_task)
        
    if background_tasks:
        background_tasks.add_task(manager.broadcast, '{"event": "refresh"}')
    db.refresh(db_task)
    return db_task

def bulk_spawn_template(db: Session, tpl: models.Task, max_horizon: int = 365):
    target_date = date.today()
    limit = tpl.recurrence_limit or 30  # Default horizon for 'forever' is 30 days to prevent excessive generation
    if tpl.recurrence_limit:
        limit = min(tpl.recurrence_limit, max_horizon)
        
    generated = 0
    checked_days = 0
    max_days_to_check = 1000 # Safety timeout
    
    while generated < limit and checked_days < max_days_to_check:
        should_generate = False
        if tpl.cron_expression:
            parts = tpl.cron_expression.split(" ")
            if len(parts) == 5:
                day_of_month = parts[2]
                day_of_week = parts[4]
                if day_of_month != '*':
                    if target_date.day == int(day_of_month): should_generate = True
                elif day_of_week != '*':
                    target_dow = (target_date.weekday() + 1) % 7 # 0=Sun, 1=Mon...
                    allowed_dows = [int(d) for d in day_of_week.split(',')]
                    if target_dow in allowed_dows: should_generate = True
                else:
                    should_generate = True
        elif tpl.recurrence_interval_days:
            if not tpl.last_generated_date:
                should_generate = True
            else:
                days_diff = (target_date - tpl.last_generated_date).days
                if days_diff >= 0 and days_diff % tpl.recurrence_interval_days == 0:
                    should_generate = True
        else:
            should_generate = True
            
        if should_generate:
            existing = db.query(models.Task).filter(
                models.Task.template_task_id == tpl.id,
                models.Task.due_date == target_date
            ).first()
            
            if not existing:
                new_task = models.Task(
                    category_id=tpl.category_id,
                    title=tpl.title,
                    description=tpl.description,
                    status="Pending",
                    assigned_member_id=tpl.assigned_member_id,
                    assignment_type=tpl.assignment_type,
                    created_by_member_id=tpl.created_by_member_id,
                    task_type="AUTO",
                    due_date=target_date,
                    note=tpl.note,
                    has_penalty=tpl.has_penalty,
                    is_habit=tpl.is_habit,
                    time_block=tpl.time_block,
                    value_amount=tpl.value_amount,
                    template_task_id=tpl.id
                )
                db.add(new_task)
                generated += 1
                tpl.recurrence_count += 1
                tpl.last_generated_date = target_date
                
        target_date += timedelta(days=1)
        checked_days += 1
        
    if tpl.recurrence_limit and tpl.recurrence_count >= tpl.recurrence_limit:
        tpl.status = "Completed_Template"
    db.commit()

def spawn_recurring_tasks(db: Session, target_date: date, background_tasks: BackgroundTasks = None):
    templates = db.query(models.Task).filter(models.Task.status == "Template", models.Task.is_active == True).all()
    for tpl in templates:
        if tpl.recurrence_limit and tpl.recurrence_count >= tpl.recurrence_limit:
            tpl.status = "Completed_Template"
            db.commit()
            if background_tasks:
                background_tasks.add_task(manager.broadcast, '{"event": "refresh"}')
            continue
            
        existing = db.query(models.Task).filter(
            models.Task.template_task_id == tpl.id,
            models.Task.due_date == target_date
        ).first()
        if existing: continue
            
        should_generate = False
        if tpl.cron_expression:
            parts = tpl.cron_expression.split(" ")
            if len(parts) == 5:
                day_of_month = parts[2]
                day_of_week = parts[4]
                if day_of_month != '*':
                    if target_date.day == int(day_of_month): should_generate = True
                elif day_of_week != '*':
                    target_dow = (target_date.weekday() + 1) % 7 # 0=Sun, 1=Mon...
                    allowed_dows = [int(d) for d in day_of_week.split(',')]
                    if target_dow in allowed_dows: should_generate = True
                else:
                    should_generate = True
        elif tpl.recurrence_interval_days:
            if not tpl.last_generated_date:
                should_generate = True
            else:
                days_diff = (target_date - tpl.last_generated_date).days
                if days_diff >= 0 and days_diff % tpl.recurrence_interval_days == 0:
                    should_generate = True
        else:
            should_generate = True
            
        if should_generate:
            new_task = models.Task(
                category_id=tpl.category_id,
                title=tpl.title,
                description=tpl.description,
                status="Pending",
                assigned_member_id=tpl.assigned_member_id,
                assignment_type=tpl.assignment_type,
                created_by_member_id=tpl.created_by_member_id,
                task_type="AUTO",
                due_date=target_date,
                note=tpl.note,
                has_penalty=tpl.has_penalty,
                is_habit=tpl.is_habit,
                time_block=tpl.time_block,
                value_amount=tpl.value_amount,
                template_task_id=tpl.id
            )
            db.add(new_task)
            tpl.recurrence_count += 1
            if not tpl.last_generated_date or target_date > tpl.last_generated_date:
                tpl.last_generated_date = target_date
            db.commit()
            if background_tasks:
                background_tasks.add_task(manager.broadcast, '{"event": "refresh"}')

@app.get("/tasks/", response_model=List[schemas.Task])
def read_tasks(background_tasks: BackgroundTasks, skip: int = 0, limit: int = 100, task_date: date = None, db: Session = Depends(get_db)):
    if task_date:
        spawn_recurring_tasks(db, task_date, background_tasks)
        
    query = db.query(models.Task).filter(models.Task.status != "Template").order_by(models.Task.id.desc())
    if task_date:
        query_pending = query.filter(models.Task.due_date <= task_date, models.Task.status == "Pending")
        query_done = db.query(models.Task).filter(
        models.Task.status.in_(["Completed", "Skipped"]),
        models.Task.due_date == task_date
    ).order_by(models.Task.id.desc())
        return query_pending.all() + query_done.all()
    return query.offset(skip).limit(limit).all()

@app.get("/templates/", response_model=List[schemas.Task])
def read_templates(db: Session = Depends(get_db)):
    return db.query(models.Task).filter(models.Task.status == "Template").all()

class ActionPayload(BaseModel):
    member_id: Optional[int] = None

class PlanPayload(BaseModel):
    new_date: date
    new_time_block: str
    member_id: Optional[int] = None

@app.put("/tasks/{task_id}/plan", response_model=schemas.Task)
def plan_task(task_id: int, payload: PlanPayload, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
        
    task.due_date = payload.new_date
    task.time_block = payload.new_time_block
    
    action = {"action": "RESCHEDULED", "timestamp": datetime.now().isoformat(), "new_date": str(payload.new_date), "new_time_block": payload.new_time_block}
    if payload.member_id:
        action["member_id"] = payload.member_id
        
    history = list(task.action_history or [])
    history.append(action)
    task.action_history = history
    
    db.commit()
    if background_tasks:
        background_tasks.add_task(manager.broadcast, '{"event": "refresh"}')
    db.refresh(task)
    return task

@app.put("/tasks/{task_id}/complete", response_model=schemas.Task)
def complete_task(task_id: int, background_tasks: BackgroundTasks, payload: ActionPayload = None, db: Session = Depends(get_db)):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.status = "Completed"
    task.due_date = date.today()
    
    action = {"action": "COMPLETED", "timestamp": datetime.now().isoformat()}
    if payload:
        if payload.member_id: 
            action["member_id"] = payload.member_id
            task.assigned_member_id = payload.member_id # Re-assign to whoever ticked it
        if payload.note: action["note"] = payload.note
        if payload.image_url: action["image_url"] = payload.image_url
        if payload.note: task.note = payload.note
    
    history = list(task.action_history) if task.action_history else []
    history.append(action)
    task.action_history = history
    
    db.commit()
    if 'background_tasks' in locals():
        background_tasks.add_task(manager.broadcast, '{"event": "refresh"}')
    db.refresh(task)
    return task

@app.put("/tasks/{task_id}/skip", response_model=schemas.Task)
def skip_task(task_id: int, background_tasks: BackgroundTasks, payload: ActionPayload = None, db: Session = Depends(get_db)):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.status = "Skipped"
    task.due_date = date.today()
    
    action = {"action": "SKIPPED", "timestamp": datetime.now().isoformat()}
    if payload:
        if payload.member_id: 
            action["member_id"] = payload.member_id
            task.assigned_member_id = payload.member_id # Re-assign to whoever ticked it
        if payload.note: action["note"] = payload.note
        if payload.image_url: action["image_url"] = payload.image_url
        if payload.note: task.note = payload.note
        
    history = list(task.action_history) if task.action_history else []
    history.append(action)
    task.action_history = history
    
    db.commit()
    if 'background_tasks' in locals():
        background_tasks.add_task(manager.broadcast, '{"event": "refresh"}')
    db.refresh(task)
    return task

@app.delete("/tasks/{task_id}")
def delete_task(task_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    db.delete(task)
    db.commit()
    if 'background_tasks' in locals():
        background_tasks.add_task(manager.broadcast, '{"event": "refresh"}')
    return {"message": "Task deleted successfully"}

@app.put("/tasks/{task_id}/note", response_model=schemas.Task)
def update_task_note(task_id: int, payload: schemas.TaskNoteUpdate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.note = payload.note
    db.commit()
    if 'background_tasks' in locals():
        background_tasks.add_task(manager.broadcast, '{"event": "refresh"}')
    db.refresh(task)
    return task

@app.put("/tasks/{task_id}", response_model=schemas.Task)
def update_task_full(task_id: int, payload: schemas.TaskUpdate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if payload.title is not None: task.title = payload.title
    if payload.description is not None: task.description = payload.description
    if payload.due_date is not None: task.due_date = payload.due_date
    if payload.category_id is not None: task.category_id = payload.category_id
    if payload.assigned_member_id is not None:
        task.assigned_member_id = payload.assigned_member_id
        task.assignment_type = "MEMBER" if payload.assigned_member_id else "UNASSIGNED"
    if payload.status is not None: task.status = payload.status
    if payload.note is not None: task.note = payload.note
    if payload.admin_note is not None: task.admin_note = payload.admin_note
    if payload.is_reviewed is not None: task.is_reviewed = payload.is_reviewed
    if payload.is_active is not None: task.is_active = payload.is_active
    if payload.value_amount is not None: task.value_amount = payload.value_amount
    
    db.commit()
    if 'background_tasks' in locals():
        background_tasks.add_task(manager.broadcast, '{"event": "refresh"}')
    db.refresh(task)
    return task

@app.get("/summary/")
def read_summary(db: Session = Depends(get_db)):
    today = datetime.now().date()
    
    completed_today = db.query(models.Task).filter(
        models.Task.status == "Completed",
        models.Task.due_date == today
    ).count()
    
    pending_today = db.query(models.Task).filter(
        models.Task.status == "Pending",
        models.Task.due_date == today
    ).count()

    members = db.query(models.Member).all()
    leaderboard = []
    for m in members:
        c = db.query(models.Task).filter(models.Task.status == "Completed", models.Task.assigned_member_id == m.id).count()
        p = db.query(models.Task).filter(models.Task.status == "Skipped", models.Task.has_penalty == True, models.Task.assigned_member_id == m.id).count()
        leaderboard.append({
            "member_id": m.id,
            "score": c - p
        })
    
    leaderboard.sort(key=lambda x: x["score"], reverse=True)
    
    total_members = len(members)
    total_templates = db.query(models.Task).filter(models.Task.status == "Template").count()
    total_tasks_ever = db.query(models.Task).filter(models.Task.status != "Template").count()
    
    return {
        "completed_today": completed_today,
        "pending_today": pending_today,
        "leaderboard": leaderboard,
        "total_members": total_members,
        "total_templates": total_templates,
        "total_tasks_ever": total_tasks_ever
    }

@app.get("/members/{member_id}/dashboard")
def read_member_dashboard(member_id: int, db: Session = Depends(get_db)):
    member = db.query(models.Member).filter(models.Member.id == member_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
        
    today = datetime.now().date()
    
    completed_all = db.query(models.Task).filter(models.Task.status == "Completed", models.Task.assigned_member_id == member_id).count()
    penalty_all = db.query(models.Task).filter(models.Task.status == "Skipped", models.Task.has_penalty == True, models.Task.assigned_member_id == member_id).count()
    total_score = completed_all - penalty_all
    
    completed_today = db.query(models.Task).filter(models.Task.status == "Completed", models.Task.assigned_member_id == member_id, models.Task.due_date == today).count()
    pending_today = db.query(models.Task).filter(models.Task.status == "Pending", models.Task.assigned_member_id == member_id, models.Task.due_date == today).count()
    skipped_today = db.query(models.Task).filter(models.Task.status == "Skipped", models.Task.assigned_member_id == member_id, models.Task.due_date == today).count()
    
    weekly_stats = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        c = db.query(models.Task).filter(models.Task.status == "Completed", models.Task.assigned_member_id == member_id, models.Task.due_date == d).count()
        weekly_stats.append({
            "date": d.strftime("%Y-%m-%d"),
            "label": d.strftime("%a"),
            "count": c
        })
        
    max_count = max([s["count"] for s in weekly_stats]) if weekly_stats else 0
    if max_count == 0: max_count = 1
    for s in weekly_stats:
        s["height_percent"] = (s["count"] / max_count) * 100
        
    this_year = today.year
    this_month = today.month
    
    habit_completed_year = db.query(models.Task).filter(
        models.Task.is_habit == True,
        models.Task.status == "Completed",
        models.Task.assigned_member_id == member_id,
        models.Task.due_date >= date(this_year, 1, 1)
    ).count()
    
    habit_completed_month = db.query(models.Task).filter(
        models.Task.is_habit == True,
        models.Task.status == "Completed",
        models.Task.assigned_member_id == member_id,
        models.Task.due_date >= date(this_year, this_month, 1)
    ).count()
    
    heatmap = []
    for i in range(89, -1, -1):
        d = today - timedelta(days=i)
        c = db.query(models.Task).filter(
            models.Task.is_habit == True,
            models.Task.status == "Completed",
            models.Task.assigned_member_id == member_id,
            models.Task.due_date == d
        ).count()
        heatmap.append({"date": d.strftime("%Y-%m-%d"), "count": c})
        
    max_habit_count = max([h["count"] for h in heatmap]) if heatmap else 0
    for h in heatmap:
        if max_habit_count == 0 or h["count"] == 0:
            h["intensity"] = 0
        else:
            h["intensity"] = int((h["count"] / max_habit_count) * 4)
            if h["intensity"] == 0 and h["count"] > 0:
                h["intensity"] = 1
                
    habit_titles_query = db.query(models.Task.title).filter(
        models.Task.is_habit == True,
        models.Task.status == "Template",
        models.Task.is_active == True,
        models.Task.assigned_member_id == member_id
    ).distinct().all()
    
    per_habit_stats = []
    thirty_days_ago = today - timedelta(days=29)
    for (title,) in habit_titles_query:
        completions = db.query(models.Task.due_date).filter(
            models.Task.is_habit == True,
            models.Task.assigned_member_id == member_id,
            models.Task.title == title,
            models.Task.status == "Completed",
            models.Task.due_date >= thirty_days_ago
        ).all()
        completed_dates = {c[0] for c in completions}
        
        history = []
        for i in range(29, -1, -1):
            d = today - timedelta(days=i)
            history.append({
                "date": d.strftime("%Y-%m-%d"),
                "completed": d in completed_dates
            })
            
        per_habit_stats.append({
            "title": title,
            "history": history
        })
        
    return {
        "score": total_score,
        "completed_today": completed_today,
        "pending_today": pending_today,
        "skipped_today": skipped_today,
        "weekly_stats": weekly_stats,
        "habit_completed_year": habit_completed_year,
        "habit_completed_month": habit_completed_month,
        "habit_heatmap": heatmap,
        "per_habit_stats": per_habit_stats
    }

@app.get("/finance/", response_model=List[schemas.Task])
def read_finance_tasks(member_id: Optional[int] = None, year: Optional[int] = None, month: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(models.Task).filter(
        models.Task.status == "Completed",
        models.Task.value_amount > 0
    )
    
    if member_id:
        query = query.filter(models.Task.assigned_member_id == member_id)
        
    if year and month:
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1)
        else:
            end_date = date(year, month + 1, 1)
        query = query.filter(models.Task.due_date >= start_date, models.Task.due_date < end_date)
        
    return query.order_by(models.Task.due_date.desc()).all()

@app.get("/admin")
def get_admin_page():
    return FileResponse('static/admin.html')

os.makedirs("static", exist_ok=True)
# --- Admin & Analytics APIs ---

@app.post("/members/{member_id}/login")
def log_member_login(member_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    today = datetime.now().date()
    # Check if already logged in today
    existing = db.query(models.MemberLogin).filter(
        models.MemberLogin.member_id == member_id,
        models.MemberLogin.login_date == today
    ).first()
    
    if not existing:
        new_log = models.MemberLogin(
            member_id=member_id,
            login_date=today,
            created_at=datetime.now().isoformat()
        )
        db.add(new_log)
        db.commit()
        if 'background_tasks' in locals():
            background_tasks.add_task(manager.broadcast, '{"event": "refresh"}')
    return {"status": "ok"}

@app.get("/admin/dashboard_stats")
def get_dashboard_stats(days: int = 7, db: Session = Depends(get_db)):
    import datetime as dt
    from sqlalchemy import func
    
    end_date = dt.datetime.now().date()
    start_date = end_date - dt.timedelta(days=days-1)
    
    # 1. Daily Logins
    daily_logins = db.query(
        models.MemberLogin.login_date, 
        func.count(models.MemberLogin.id)
    ).filter(
        models.MemberLogin.login_date >= start_date,
        models.MemberLogin.login_date <= end_date
    ).group_by(models.MemberLogin.login_date).all()
    
    # 2. Tasks Completed vs Pending per day
    tasks_stats = db.query(
        models.Task.due_date,
        models.Task.status,
        func.count(models.Task.id)
    ).filter(
        models.Task.due_date >= start_date,
        models.Task.due_date <= end_date,
        models.Task.status != "Template"
    ).group_by(models.Task.due_date, models.Task.status).all()
    
    # 3. Tasks Completed per Member (Current Month)
    first_day_of_month = end_date.replace(day=1)
    member_tasks = db.query(
        models.Task.assigned_member_id,
        func.count(models.Task.id)
    ).filter(
        models.Task.due_date >= first_day_of_month,
        models.Task.due_date <= end_date,
        models.Task.status == "Completed",
        models.Task.assignment_type == "MEMBER"
    ).group_by(models.Task.assigned_member_id).all()
    
    members = {m.id: m.name for m in db.query(models.Member).all()}
    
    # Format data
    date_labels = [(start_date + dt.timedelta(days=i)).isoformat() for i in range(days)]
    
    login_dict = {str(d): c for d, c in daily_logins}
    login_data = [login_dict.get(d, 0) for d in date_labels]
    
    completed_dict = {}
    pending_dict = {}
    for d, s, c in tasks_stats:
        if d is None: continue
        ds = str(d)
        if s == "Completed":
            completed_dict[ds] = completed_dict.get(ds, 0) + c
        elif s == "Pending":
            pending_dict[ds] = pending_dict.get(ds, 0) + c
            
    completed_data = [completed_dict.get(d, 0) for d in date_labels]
    pending_data = [pending_dict.get(d, 0) for d in date_labels]
    
    member_stats_labels = []
    member_stats_data = []
    for mid, count in member_tasks:
        if mid in members:
            member_stats_labels.append(members[mid])
            member_stats_data.append(count)
            
    return {
        "dates": date_labels,
        "logins": login_data,
        "tasks_completed": completed_data,
        "tasks_pending": pending_data,
        "member_labels": member_stats_labels,
        "member_tasks": member_stats_data
    }

@app.get("/admin/finance_stats")
def get_finance_stats(year: int, month: int, member_id: str = "", db: Session = Depends(get_db)):
    import datetime as dt
    from sqlalchemy import func
    
    # Start and end date for the month
    start_date = dt.date(year, month, 1)
    if month == 12:
        end_date = dt.date(year + 1, 1, 1) - dt.timedelta(days=1)
    else:
        end_date = dt.date(year, month + 1, 1) - dt.timedelta(days=1)
        
    query = db.query(models.Task).filter(
        models.Task.due_date >= start_date,
        models.Task.due_date <= end_date,
        models.Task.status == "Completed",
        models.Task.value_amount > 0
    )
    
    if member_id and member_id != "":
        query = query.filter(models.Task.assigned_member_id == int(member_id))
        
    tasks = query.order_by(models.Task.due_date.desc()).all()
    
    # Aggregate by member
    members = {m.id: m for m in db.query(models.Member).all()}
    
    records = []
    total_amount = 0
    
    for t in tasks:
        amount = t.value_amount or 0
        total_amount += amount
        records.append({
            "id": t.id,
            "title": t.title,
            "due_date": str(t.due_date),
            "amount": amount,
            "member_name": members[t.assigned_member_id].name if t.assigned_member_id in members else "Unknown"
        })
        
    return {
        "total_amount": total_amount,
        "records": records
    }

from fastapi import Query
@app.get("/tasks/overdue", response_model=List[schemas.Task])
def read_overdue_tasks(member_id: Optional[int] = None, db: Session = Depends(get_db)):
    today = datetime.now().date()
    query = db.query(models.Task).filter(
        models.Task.status == "Pending",
        models.Task.due_date < today
    )
    if member_id:
        query = query.filter(models.Task.assigned_member_id == member_id)
    return query.order_by(models.Task.due_date.asc()).all()

@app.get("/admin/advanced_stats")
def get_advanced_stats(
    year: int = Query(None),
    month: int = Query(None),
    day: int = Query(None),
    member_id: int = Query(None),
    category_id: int = Query(None),
    db: Session = Depends(get_db)
):
    import datetime as dt
    
    query = db.query(models.Task).filter(models.Task.status.in_(["Completed", "Pending"]))
    
    if year and month and day:
        target_date = dt.date(year, month, day)
        query = query.filter(models.Task.due_date == target_date)
    elif year and month:
        start_date = dt.date(year, month, 1)
        if month == 12:
            end_date = dt.date(year + 1, 1, 1) - dt.timedelta(days=1)
        else:
            end_date = dt.date(year, month + 1, 1) - dt.timedelta(days=1)
        query = query.filter(models.Task.due_date >= start_date, models.Task.due_date <= end_date)
    elif year:
        start_date = dt.date(year, 1, 1)
        end_date = dt.date(year, 12, 31)
        query = query.filter(models.Task.due_date >= start_date, models.Task.due_date <= end_date)
    else:
        query = query.filter(models.Task.due_date == dt.date.today())
        
    if member_id:
        query = query.filter(models.Task.assigned_member_id == member_id)
        
    if category_id:
        query = query.filter(models.Task.category_id == category_id)
        
    tasks = query.all()
    
    # 1. Overview Stats
    total_completed = 0
    total_pending = 0
    total_value = 0
    
    # 2. Task Summary
    task_counts = {}
    
    # 3. Member Contribution
    members = {m.id: m.name for m in db.query(models.Member).all()}
    member_stats = {}
    
    for t in tasks:
        # Overview
        if t.status == "Completed":
            total_completed += 1
            total_value += (t.value_amount or 0)
        elif t.status == "Pending":
            total_pending += 1
            
        # Task Summary
        title = t.title
        if title not in task_counts:
            task_counts[title] = {"title": title, "completed": 0, "pending": 0, "value": 0}
            
        if t.status == "Completed":
            task_counts[title]["completed"] += 1
            task_counts[title]["value"] += (t.value_amount or 0)
        elif t.status == "Pending":
            task_counts[title]["pending"] += 1
            
        # Member Contribution (only for completed tasks, since pending aren't done yet)
        if t.status == "Completed":
            m_id = t.assigned_member_id
            m_name = members.get(m_id, "ไม่ระบุสมาชิก")
            if m_name not in member_stats:
                member_stats[m_name] = {"name": m_name, "completed": 0, "value": 0}
            member_stats[m_name]["completed"] += 1
            member_stats[m_name]["value"] += (t.value_amount or 0)
        
    task_summary = list(task_counts.values())
    task_summary.sort(key=lambda x: x["completed"], reverse=True)
    
    member_summary = list(member_stats.values())
    member_summary.sort(key=lambda x: x["value"], reverse=True)
    
    return {
        "overview": {
            "total_completed": total_completed,
            "total_pending": total_pending,
            "total_value": total_value
        },
        "task_summary": task_summary,
        "member_summary": member_summary
    }

@app.put("/tasks/{task_id}/revert", response_model=schemas.Task)
def revert_task(task_id: int, background_tasks: BackgroundTasks, payload: ActionPayload = None, db: Session = Depends(get_db)):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.status = "Pending"
    
    action = {"action": "REVERTED", "timestamp": datetime.now().isoformat()}
    if payload:
        if payload.member_id: action["member_id"] = payload.member_id
        if getattr(payload, 'note', None): action["note"] = payload.note
        if getattr(payload, 'image_url', None): action["image_url"] = payload.image_url
        
    history = list(task.action_history) if task.action_history else []
    history.append(action)
    task.action_history = history
    
    db.commit()
    if 'background_tasks' in locals():
        background_tasks.add_task(manager.broadcast, '{"event": "refresh"}')
    db.refresh(task)
    return task

def parse_date_str(date_str: str) -> date:
    try:
        if "-" in date_str:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        else:
            return datetime.strptime(date_str, "%Y%m%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD or YYYYMMDD")

@app.get("/api/external/sum/{date_str}")
def get_external_sum(date_str: str, db: Session = Depends(get_db)):
    target_date = parse_date_str(date_str)
    
    query_pending = db.query(models.Task).filter(
        models.Task.status == "Pending",
        models.Task.due_date <= target_date
    )
    query_done = db.query(models.Task).filter(
        models.Task.status.in_(["Completed", "Skipped"]),
        models.Task.due_date == target_date
    )
    tasks = query_pending.all() + query_done.all()
    
    total_tasks = len(tasks)
    completed_tasks = sum(1 for t in tasks if t.status == "Completed")
    pending_tasks = sum(1 for t in tasks if t.status == "Pending")
    
    members = {m.id: m.name for m in db.query(models.Member).all()}
    by_member = {}
    for m_id, m_name in members.items():
        by_member[m_name] = {"name": m_name, "total": 0, "completed": 0, "pending": 0}
    by_member["⭐ ใครก็ได้ (ANYONE)"] = {"name": "⭐ ใครก็ได้ (ANYONE)", "total": 0, "completed": 0, "pending": 0}
    by_member["ไม่ได้มอบหมาย"] = {"name": "ไม่ได้มอบหมาย", "total": 0, "completed": 0, "pending": 0}
    
    categories = {c.id: c.name for c in db.query(models.Category).all()}
    by_category = {}
    for c_id, c_name in categories.items():
        by_category[c_name] = {"name": c_name, "completed": 0, "pending": 0}
    
    for t in tasks:
        if t.assignment_type == "MEMBER" and t.assigned_member_id:
            m_name = members.get(t.assigned_member_id, "ไม่ระบุสมาชิก")
        elif t.assignment_type == "ANYONE":
            m_name = "⭐ ใครก็ได้ (ANYONE)"
        else:
            m_name = "ไม่ได้มอบหมาย"
            
        if m_name not in by_member:
            by_member[m_name] = {"name": m_name, "total": 0, "completed": 0, "pending": 0}
            
        by_member[m_name]["total"] += 1
        if t.status == "Completed":
            by_member[m_name]["completed"] += 1
        elif t.status == "Pending":
            by_member[m_name]["pending"] += 1
            
        c_name = categories.get(t.category_id, "ไม่ระบุหมวดหมู่")
        if c_name not in by_category:
            by_category[c_name] = {"name": c_name, "completed": 0, "pending": 0}
            
        if t.status == "Completed":
            by_category[c_name]["completed"] += 1
        elif t.status == "Pending":
            by_category[c_name]["pending"] += 1
            
    def sort_member_sum(m):
        name = m["name"]
        is_unassigned = name in ["⭐ ใครก็ได้ (ANYONE)", "ไม่ได้มอบหมาย"]
        return (is_unassigned, -m["total"])
        
    by_member_list = list(by_member.values())
    by_member_list.sort(key=sort_member_sum)
            
    return {
        "date": str(target_date),
        "overview": {
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "pending_tasks": pending_tasks
        },
        "by_member": by_member_list,
        "by_category": list(by_category.values())
    }

@app.get("/api/external/todo/{date_str}")
def get_external_todo(date_str: str, db: Session = Depends(get_db)):
    target_date = parse_date_str(date_str)
    
    query = db.query(models.Task).filter(
        models.Task.status == "Pending",
        models.Task.due_date <= target_date
    )
    tasks = query.all()
    
    total_pending = len(tasks)
    due_today_count = sum(1 for t in tasks if t.due_date == target_date)
    overdue_count = sum(1 for t in tasks if t.due_date < target_date)
    
    members = {m.id: m.name for m in db.query(models.Member).all()}
    categories = {c.id: c.name for c in db.query(models.Category).all()}
    
    tasks_list = []
    by_member = {}
    for m_id, m_name in members.items():
        by_member[m_name] = {"name": m_name, "total": 0, "due_today": 0, "overdue": 0}
    by_member["⭐ ใครก็ได้ (ANYONE)"] = {"name": "⭐ ใครก็ได้ (ANYONE)", "total": 0, "due_today": 0, "overdue": 0}
    by_member["ไม่ได้มอบหมาย"] = {"name": "ไม่ได้มอบหมาย", "total": 0, "due_today": 0, "overdue": 0}
    
    by_category = {}
    for c_id, c_name in categories.items():
        by_category[c_name] = {"name": c_name, "total_pending": 0}
    
    for t in tasks:
        if t.assignment_type == "MEMBER" and t.assigned_member_id:
            m_name = members.get(t.assigned_member_id, "ไม่ระบุสมาชิก")
        elif t.assignment_type == "ANYONE":
            m_name = "⭐ ใครก็ได้ (ANYONE)"
        else:
            m_name = "ไม่ได้มอบหมาย"
            
        c_name = categories.get(t.category_id, "ไม่ระบุหมวดหมู่")
        is_overdue = t.due_date < target_date
        
        tasks_list.append({
            "id": t.id,
            "title": t.title,
            "assignee": m_name,
            "category": c_name,
            "due_date": str(t.due_date),
            "status": t.status,
            "is_overdue": is_overdue,
            "is_recurring": t.is_recurring,
            "is_habit": t.is_habit,
            "time_block": t.time_block,
            "value_amount": t.value_amount
        })
            
        if m_name not in by_member:
            by_member[m_name] = {"name": m_name, "total": 0, "due_today": 0, "overdue": 0}
            
        by_member[m_name]["total"] += 1
        if not is_overdue:
            by_member[m_name]["due_today"] += 1
        else:
            by_member[m_name]["overdue"] += 1
            
        if c_name not in by_category:
            by_category[c_name] = {"name": c_name, "total_pending": 0}
            
        by_category[c_name]["total_pending"] += 1
        
    def sort_member_todo(m):
        name = m["name"]
        is_unassigned = name in ["⭐ ใครก็ได้ (ANYONE)", "ไม่ได้มอบหมาย"]
        return (is_unassigned, -m["total"])
        
    by_member_list = list(by_member.values())
    by_member_list.sort(key=sort_member_todo)
            
    return {
        "date": str(target_date),
        "overview": {
            "total_pending": total_pending,
            "due_today": due_today_count,
            "overdue": overdue_count
        },
        "tasks_list": tasks_list,
        "by_member": by_member_list,
        "by_category": list(by_category.values())
    }

app.mount("/", StaticFiles(directory="static", html=True), name="static")
