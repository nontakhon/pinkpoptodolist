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

## 📦 4. การอัปเดต Database (Patching Database)

หากคุณทำการโคลนโค้ดเวอร์ชันล่าสุดที่มีการเพิ่มระบบจัดการนิสัย (Habit Master System) และใช้ฐานข้อมูลเดิม (ไม่ได้ลบ `thetask.db` ทิ้ง) คุณจำเป็นต้องรันสคริปต์เพื่อเพิ่มฟิลด์ที่จำเป็นเข้าสู่ Database:

**เปิด Terminal และรันคำสั่งต่อไปนี้:**
```bash
sqlite3 data/thetask.db < patch_is_active.sql
```
*สคริปต์นี้จะทำการเพิ่มคอลัมน์ `is_active` ลงในตาราง `tasks` เพื่อไม่ให้เกิด Error ตอนระบบพยายามดึงข้อมูลสถิติครับ*

## 🐳 5. การใช้งานผ่าน Docker (ทางเลือก)
โปรเจกต์นี้รองรับ Docker และ Docker Compose:
```bash
docker-compose up -d --build
```
ระบบจะรันบน `http://localhost:8000` โดยอัตโนมัติ

*(หมายเหตุ: หากต้องการดูรายละเอียดทางเทคนิคเชิงลึก กรุณาอ่านเพิ่มเติมใน `TECHNICAL_SPEC.md`)*
