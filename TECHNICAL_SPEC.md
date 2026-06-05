# 💻 เอกสารข้อมูลทางเทคนิค (Technical Specification) - pinkpop

เอกสารอธิบายสถาปัตยกรรมและรายละเอียดทางเทคนิคเชิงลึกของแอปพลิเคชัน pinkpop

## 1. 🏗 สถาปัตยกรรมระบบ (System Architecture)

pinkpop ใช้สถาปัตยกรรมแบบ Monolith ที่แยกส่วน Backend และ Frontend ออกจากกันอย่างชัดเจน โดยให้ Backend ทำหน้าที่เป็น API Provider และใช้ Frontend (Static HTML/JS) ดึงข้อมูลผ่าน REST API และรับสัญญาณอัปเดตผ่าน WebSocket

### 1.1 Tech Stack
- **Backend Framework:** FastAPI (Python 3.9+)
- **Database ORM:** SQLAlchemy
- **Database Engine:** SQLite (รองรับการทำ Database Migration/Patching ด้วยสคริปต์)
- **Frontend Framework:** Alpine.js (สำหรับทำ Reactive UI ภายในไฟล์ HTML ปกติ โดยไม่ต้องใช้ Node.js/Webpack)
- **CSS Framework:** Tailwind CSS (โหลดผ่าน CDN เพื่อความเบาและคล่องตัว)
- **Task Scheduler:** APScheduler (รันแบบ Background Task เพื่อประมวลผลงานรายวันและนิสัยอัตโนมัติ)
- **Real-time Engine:** FastAPI WebSockets
- **Containerization:** Docker & Docker Compose

## 2. 🗄 โครงสร้างฐานข้อมูล (Database Schema)

ไฟล์หลักอยู่ที่ `app/models.py` โดยมี Table ที่สำคัญดังนี้:

1. **Member (สมาชิก):** เก็บข้อมูลผู้ใช้, อวาตาร์ และสถานะกระเป๋าเงิน (Wallet)
2. **Category (หมวดหมู่):** เก็บสีและไอคอนสำหรับจัดประเภทงาน มีฟิลด์รองรับกฏพิเศษเช่น `rule_type` (เช่น ROUND_ROBIN หรือ RANDOM)
3. **Task (งาน/นิสัย):** เป็นแกนหลักของระบบ โดยรองรับทั้งงานปกติและ *งานต้นแบบ (Templates)* 
   - `status`: งานปกติจะมีสถานะ (Pending, Completed, Missed, etc.) ในขณะที่งานต้นแบบจะมีสถานะเป็น `"Template"`
   - `is_habit`: Boolean บ่งบอกว่าเป็นนิสัยหรือไม่
   - `is_active`: (อัปเดตใหม่) สำหรับระงับ/เปิดใช้งาน Template ชั่วคราว โดยไม่กระทบสถิติย้อนหลัง
   - `cron_expression` / `recurrence_interval_days`: ระบุเงื่อนไขการเกิดซ้ำ
4. **ActionHistory (ประวัติการกระทำ):** เก็บ Log พฤติกรรม (การกดเสร็จงาน, ข้ามงาน) และเก็บ `image_url` สำหรับรูปภาพหลักฐานอัปโหลด

## 3. 🔄 ระบบ Real-time Synchronization (WebSockets)

เพื่อให้ทุกอุปกรณ์ที่ล็อกอินอยู่ (ทั้งฝั่ง User และ Admin) เห็นข้อมูลตรงกันทันทีที่ใครบางคนกดยืนยันงาน ระบบใช้ WebSockets ทำหน้าที่ **"Signal Broadcaster"**:
- ทันทีที่มีการเรียกใช้ API ที่เปลี่ยนแปลงข้อมูล (POST/PUT/DELETE) Backend จะเรียกใช้ `manager.broadcast('{"event": "refresh"}')` ใน Background Task
- เมื่อ Frontend (Alpine.js) ได้รับข้อความ `refresh` ตัว UI จะแอบดึงข้อมูล `loadAllTasks()` และ `loadDashboard()` ใหม่อย่างเงียบๆ ทำให้ผู้ใช้เห็นสถานะเปลี่ยนแปลงโดยไม่ต้องกดรีเฟรชหน้าจอ

## 4. ⏰ ระบบสร้างงานอัตโนมัติ (Cron & Task Spawner)

ตัวแอปมีการตั้งเวลาอัตโนมัติ 2 ส่วน (อยู่ที่ `app/main.py`):
1. **BackgroundScheduler:** จะรันทุกๆ คืนเวลา `00:00` เพื่อเปลี่ยนสถานะงานที่หมดเวลา (Overdue/Missed) และหักแต้ม (Penalty) ถ้ามี รวมถึงทริกเกอร์ให้ฟังก์ชันสร้างงานรายวันทำงาน
2. **spawn_recurring_tasks():** ฟังก์ชันหลักที่จะกวาดหา `Task` ที่มี `status="Template"` และ `is_active=True` 
   - ระบบจะเปรียบเทียบ `cron_expression` และ `interval_days` กับวันปัจจุบัน หากตรงเงื่อนไข ระบบจะดึงเทมเพลตมาสร้างเป็น Task ชิ้นใหม่ (Clone) ที่มีสถานะเป็น `"Pending"` และกำหนด Due Date เป็นวันปัจจุบัน
   - รองรับระบบ "จ่ายงานอัตโนมัติแบบวนรอบ (Round-Robin)" หรือ "สุ่ม (Random)" ตามกฎของ `Category`

## 5. 📸 ระบบอัปโหลดและจัดการรูปภาพ (File Uploads)

- ระบบรับรูปภาพผ่านฟอร์ม `multipart/form-data` และใช้ `uuid4` ในการสุ่มชื่อไฟล์เพื่อป้องกันการซ้ำซ้อน
- ภาพจะถูกเซฟไว้ในโฟลเดอร์ `/data/uploads/` และถูกเสิร์ฟด้วย `StaticFiles` ของ FastAPI (เข้าถึงได้ผ่าน URL `/data/uploads/xxxx.jpg`)
- ในอนาคตสามารถใช้ Nginx มาครอบ `/data/uploads` หรือทำ CDN ได้หากรูปภาพมีจำนวนเยอะขึ้น

## 6. 🛡 แนวทางการสเกลและข้อควรระวัง
- **SQLite Concurrency:** ปัจจุบันระบบใช้ SQLite ซึ่งเพียงพอต่อการใช้งานระดับบ้าน/ออฟฟิศขนาดเล็ก หากต้องการขยาย (Scale) รองรับผู้ใช้หลักหลายพันคน ควรเปลี่ยน `DATABASE_URL` ใน `database.py` ไปใช้ PostgreSQL แทน
- **Memory Optimization:** รูปภาพอัปโหลดไม่ได้ผ่านการบีบอัดในโค้ดปัจจุบัน ควรเพิ่มการปรับ Resize รูปภาพฝั่ง Frontend (ด้วย Canvas) ก่อนส่งขึ้น Server หรือใช้ไลบรารีอย่าง `Pillow` ปรับลดขนาดก่อนเซฟลงดิสก์ เพื่อประหยัดพื้นที่จัดเก็บ
