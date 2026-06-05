# 🚀 คู่มือการรันระบบ (Setup & Run Manual) - pinkpop

คู่มือนี้สำหรับนักพัฒนาหรือผู้ดูแลระบบในการติดตั้งและเปิดใช้งานเซิร์ฟเวอร์ของแอป **pinkpop**

## 📌 ความต้องการของระบบ (Prerequisites)
- Python 3.9 หรือสูงกว่า
- Pip (Python Package Installer)

## 🛠 1. การติดตั้ง (Installation)

เปิด Terminal และรันคำสั่งตามลำดับดังนี้:

1. **โคลนโปรเจกต์ (ถ้ายังไม่มี):**
   ```bash
   git clone https://github.com/nontakhon/pinkpoptodolist.git
   cd pinkpoptodolist
   ```

2. **สร้าง Virtual Environment:**
   ```bash
   python3 -m venv venv
   ```

3. **เปิดใช้งาน Virtual Environment:**
   - **สำหรับ Mac/Linux:**
     ```bash
     source venv/bin/activate
     ```
   - **สำหรับ Windows:**
     ```cmd
     venv\Scripts\activate
     ```

4. **ติดตั้ง Packages ที่จำเป็น:**
   ```bash
   pip install -r requirements.txt
   ```
   *(หมายเหตุ: หากไม่มีไฟล์ requirements.txt สามารถรัน `pip install fastapi uvicorn sqlalchemy pydantic apscheduler websockets`)*

## ▶️ 2. การเปิดเซิร์ฟเวอร์ (Running the Application)

ก่อนรันเซิร์ฟเวอร์ ต้องแน่ใจว่าได้เปิดใช้งาน Virtual Environment (มีวงเล็บ `(venv)` ขึ้นหน้าบรรทัดคำสั่ง) แล้ว:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

- `--host 0.0.0.0`: ทำให้เครื่องอื่นในเครือข่ายวง LAN เดียวกันสามารถเข้าถึงได้
- `--port 8000`: กำหนดพอร์ตในการเข้าถึง
- `--reload`: ระบบจะรีเฟรชตัวเองอัตโนมัติหากมีการแก้ไขไฟล์โค้ด (เหมาะสำหรับโหมด Development)

## 🌐 3. การเข้าใช้งาน (Accessing the App)

เมื่อเซิร์ฟเวอร์รันสำเร็จ จะปรากฏข้อความ `Application startup complete.`
- **หน้าผู้ใช้งานทั่วไป:** เปิดเบราว์เซอร์ไปที่ `http://localhost:8000/`
- **หน้าผู้ดูแลระบบ:** เปิดเบราว์เซอร์ไปที่ `http://localhost:8000/admin.html`
- **หน้า API Docs (Swagger):** เปิดเบราว์เซอร์ไปที่ `http://localhost:8000/docs`

## ⚙️ 4. สถาปัตยกรรม (Architecture Notes)
- **Database:** ใช้ SQLite ไฟล์ `tasks.db` จะถูกสร้างขึ้นอัตโนมัติในโฟลเดอร์โปรเจกต์เมื่อเริ่มรัน
- **Real-time Sync:** ใช้เทคโนโลยี WebSocket ของ FastAPI ในการ Broadcast สถานะ `{"event": "refresh"}` ไปยังทุกเครื่องลูกข่าย เพื่อให้อัปเดต UI เบื้องหลังทันทีที่มีการเปลี่ยนแปลง
- **Cron Jobs:** ใช้ `APScheduler` (BackgroundScheduler) ทำงานในแอปพลิเคชัน เพื่อเจนงานรายวันตาม Schedule/Habit ที่ตั้งค่าไว้แบบอัตโนมัติ
