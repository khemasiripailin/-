# Tutor & Market Tracker — Apps Script + Google Sheets Version 🧡

เว็บ Streamlit สำหรับจดเวลาสอนพิเศษ + To-do จ่ายตลาด โดยเก็บข้อมูลลง Google Sheets ผ่าน Google Apps Script

เวอร์ชันนี้ **ไม่ต้องใช้ Google Cloud Service Account JSON** และ **ไม่ต้องใส่ payment method ใน Google Cloud**

## ไฟล์สำคัญ

- `app.py` — หน้าเว็บ Streamlit
- `db.py` — backend ที่ยิงข้อมูลไป Apps Script
- `apps_script_code.gs` — โค้ดที่ต้องวางใน Google Apps Script
- `.streamlit/secrets.toml.example` — ตัวอย่าง secret สำหรับ local และ Streamlit Cloud

## วิธีตั้งค่า Google Sheet + Apps Script

### 1) สร้าง Google Sheet

สร้าง Google Sheet เปล่า 1 ไฟล์ แล้ว copy Sheet ID จาก URL เช่น

```text
https://docs.google.com/spreadsheets/d/1AbCDeFGxxxxxxx/edit#gid=0
```

Sheet ID คือ

```text
1AbCDeFGxxxxxxx
```

### 2) เปิด Apps Script

ใน Google Sheet ให้กด:

```text
Extensions > Apps Script
```

ลบโค้ดเดิม แล้ววางโค้ดจากไฟล์ `apps_script_code.gs` ทั้งหมด

แก้ 2 บรรทัดบนสุด:

```javascript
const SPREADSHEET_ID = "ใส่ Google Sheet ID";
const API_TOKEN = "ตั้งรหัสลับยาว ๆ เอง เช่น my-secret-123456";
```

กด Save

### 3) Deploy Apps Script เป็น Web app

กด:

```text
Deploy > New deployment > Select type: Web app
```

ตั้งค่า:

```text
Execute as: Me
Who has access: Anyone
```

กด Deploy แล้วกด Authorize ตามขั้นตอนของ Google

หลัง deploy ให้ copy **Web app URL** ที่ลงท้ายด้วย `/exec`

### 4) ตั้งค่า Streamlit secrets ในเครื่อง

copy ไฟล์ตัวอย่าง:

```powershell
copy .streamlit\secrets.toml.example .streamlit\secrets.toml
notepad .streamlit\secrets.toml
```

แก้เป็น:

```toml
[apps_script]
web_app_url = "https://script.google.com/macros/s/xxxxxxxxxxxx/exec"
api_token = "รหัสเดียวกับ API_TOKEN ใน Apps Script"
```

### 5) รันแอป

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m streamlit run app.py
```

## Deploy ขึ้น Streamlit Community Cloud

1. Push โปรเจกต์ขึ้น GitHub
2. อย่า push `.streamlit/secrets.toml`
3. ใน Streamlit Cloud ไปที่ App settings > Secrets
4. วางค่าเดียวกับใน `secrets.toml`
5. Deploy โดย main file เป็น `app.py`

## โครงข้อมูลใน Google Sheets

แอปจะสร้าง tab ให้อัตโนมัติ:

- `teaching_sessions`
- `shopping_runs`
- `shopping_items`

