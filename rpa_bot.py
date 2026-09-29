"""
RPA Bot: ระบบอัตโนมัติสร้างและจัดส่งใบรายงานผลการเรียนทางอีเมล
วิชา: Robotic Process Automation
ผู้จัดทำ: พีรพล อินทะสิทธิ์, พีรณัฐ เมฆฉาย
"""

import pandas as pd
import smtplib
import logging
import os
import re
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from dotenv import load_dotenv

# โหลดค่าลับ (อีเมล / App Password) จากไฟล์ .env — ไฟล์นี้ไม่ถูกอัปโหลดขึ้น GitHub
load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
pdfmetrics.registerFont(TTFont("THSarabun", os.path.join(BASE_DIR, "fonts", "THSarabunNew.ttf")))
pdfmetrics.registerFont(TTFont("THSarabun-Bold", os.path.join(BASE_DIR, "fonts", "THSarabunNew-Bold.ttf")))

# ========== CONFIG ==========
CONFIG = {
    # path อิงจากโฟลเดอร์ของสคริปต์ จึงรันจากโฟลเดอร์ไหนก็ได้
    "input_path":    os.path.join(BASE_DIR, "students.csv"),   # ไฟล์ข้อมูลนักเรียน
    "output_folder": os.path.join(BASE_DIR, "report_cards"),   # โฟลเดอร์เก็บ PDF
    "summary_path":  os.path.join(BASE_DIR, "summary.csv"),    # ไฟล์สรุปผล
    "log_file":      os.path.join(BASE_DIR, "bot_log.log"),    # ไฟล์ log

    # ตั้งค่า Email (SMTP)
    # ค่าทั้งหมดอ่านจากไฟล์ .env (ดูตัวอย่างใน .env.example)
    "smtp_host":     os.getenv("SMTP_HOST", "smtp.gmail.com"),
    "smtp_port":     int(os.getenv("SMTP_PORT", "587")),
    "email_sender":  os.getenv("EMAIL_SENDER", ""),      # อีเมลผู้ส่ง
    "email_password":os.getenv("EMAIL_PASSWORD", ""),    # Gmail App Password
    "send_email":    os.getenv("SEND_EMAIL", "false").lower() == "true",  # true เมื่อพร้อมส่งจริง

    # ข้อมูลโรงเรียน
    "school_name":   "โรงเรียนตัวอย่าง",
    "semester":      "ภาคเรียนที่ 1/2568",
    "pass_score":    50,                   # คะแนนผ่านขั้นต่ำ
}

SUBJECTS = {
    "math":    "คณิตศาสตร์",
    "science": "วิทยาศาสตร์",
    "english": "ภาษาอังกฤษ",
    "thai":    "ภาษาไทย",
    "social":  "สังคมศึกษา",
}

# ========== LOGGER ==========
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(CONFIG["log_file"], encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


# ========== STEP 1: อ่านข้อมูล CSV ==========
def read_student_data(path: str) -> pd.DataFrame:
    log.info(f"📂 อ่านข้อมูลจาก: {path}")
    df = pd.read_csv(path)
    log.info(f"✅ พบข้อมูลนักเรียน {len(df)} คน")
    return df


# ========== STEP 2: ตรวจสอบข้อมูล ==========
EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")

def validate_student(row: pd.Series) -> list[str]:
    errors = []
    required = ["student_id", "first_name", "last_name", "parent_email"]
    for field in required:
        if pd.isna(row.get(field)) or str(row.get(field)).strip() == "":
            errors.append(f"ขาดข้อมูล '{field}'")

    for subj in SUBJECTS:
        val = row.get(subj)
        if pd.isna(val):
            errors.append(f"ขาดคะแนน {SUBJECTS[subj]}")
            continue
        try:
            ok = 0 <= float(val) <= 100
        except ValueError:
            ok = False
        if not ok:
            errors.append(f"คะแนน {SUBJECTS[subj]} ไม่ถูกต้อง ({val})")

    if not EMAIL_RE.fullmatch(str(row.get("parent_email", "")).strip()):
        errors.append("รูปแบบ email ไม่ถูกต้อง")

    return errors


# ========== STEP 3: คำนวณเกรด ==========
def score_to_grade(score: float) -> str:
    if score >= 80: return "4.0"
    if score >= 75: return "3.5"
    if score >= 70: return "3.0"
    if score >= 65: return "2.5"
    if score >= 60: return "2.0"
    if score >= 55: return "1.5"
    if score >= 50: return "1.0"
    return "0.0"

def score_to_label(score: float) -> str:
    if score >= 80: return "ดีเยี่ยม"
    if score >= 70: return "ดี"
    if score >= 60: return "พอใช้"
    if score >= 50: return "ผ่าน"
    return "ไม่ผ่าน"

def calculate_gpa(row: pd.Series) -> float:
    grades = [float(score_to_grade(float(row[s]))) for s in SUBJECTS]
    return round(sum(grades) / len(grades), 2)


# ========== STEP 4: สร้าง PDF Report Card ==========
def generate_report_card(row: pd.Series, output_folder: str) -> str:
    os.makedirs(output_folder, exist_ok=True)
    filename = os.path.join(output_folder, f"{row['student_id']}_report_card.pdf")

    doc = SimpleDocTemplate(
        filename,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=1.5*cm,
        bottomMargin=1.5*cm,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "title", parent=styles["Normal"],
        fontSize=18, fontName="THSarabun-Bold",
        alignment=TA_CENTER, spaceAfter=4,
        textColor=colors.HexColor("#1a3a5c"),
    )
    subtitle_style = ParagraphStyle(
        "subtitle", parent=styles["Normal"],
        fontSize=11, fontName="THSarabun",
        alignment=TA_CENTER, spaceAfter=2,
        textColor=colors.HexColor("#444444"),
    )
    info_style = ParagraphStyle(
        "info", parent=styles["Normal"],
        fontSize=11, fontName="THSarabun",
        alignment=TA_LEFT,
    )
    center_style = ParagraphStyle(
        "center", parent=styles["Normal"],
        fontSize=12, fontName="THSarabun-Bold",
        alignment=TA_CENTER,
    )

    story = []

    # Header
    story.append(Paragraph(CONFIG["school_name"], title_style))
    story.append(Paragraph("ใบรายงานผลการเรียน (Report Card)", subtitle_style))
    story.append(Paragraph(CONFIG["semester"], subtitle_style))
    story.append(HRFlowable(width="100%", thickness=2,
                             color=colors.HexColor("#1a3a5c"), spaceAfter=12))

    # Student Info
    full_name = f"{row['first_name']} {row['last_name']}"
    info_data = [
        ["รหัสนักเรียน:", row["student_id"], "ชื่อ-นามสกุล:", full_name],
        ["วันที่ออกเอกสาร:", datetime.now().strftime("%d/%m/%Y"), "อีเมลผู้ปกครอง:", row["parent_email"]],
    ]
    info_table = Table(info_data, colWidths=[3.5*cm, 5*cm, 3.5*cm, 6*cm])
    info_table.setStyle(TableStyle([
        ("FONTNAME",    (0,0), (-1,-1), "THSarabun"),
        ("FONTSIZE",    (0,0), (-1,-1), 10),
        ("FONTNAME",    (0,0), (0,-1), "THSarabun-Bold"),
        ("FONTNAME",    (2,0), (2,-1), "THSarabun-Bold"),
        ("VALIGN",      (0,0), (-1,-1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0,0), (-1,-1), [colors.HexColor("#f0f4f8"), colors.white]),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("TOPPADDING",    (0,0), (-1,-1), 6),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 14))

    # Scores Table
    story.append(Paragraph("ผลการเรียนรายวิชา", ParagraphStyle(
        "sec", parent=styles["Normal"], fontSize=13, fontName="THSarabun-Bold",
        textColor=colors.HexColor("#1a3a5c"), spaceAfter=6,
    )))

    score_rows = [["วิชา", "คะแนน (เต็ม 100)", "เกรด", "ผลการประเมิน"]]
    for col, label in SUBJECTS.items():
        score = float(row[col])
        grade = score_to_grade(score)
        result = score_to_label(score)
        score_rows.append([label, f"{score:.0f}", grade, result])

    gpa = calculate_gpa(row)
    score_rows.append(["รวมเฉลี่ย (GPA)", "", f"{gpa:.2f}", ""])

    score_table = Table(score_rows, colWidths=[5.5*cm, 4*cm, 3*cm, 4.5*cm])
    score_style = TableStyle([
        # Header row
        ("BACKGROUND",   (0,0), (-1,0), colors.HexColor("#1a3a5c")),
        ("TEXTCOLOR",    (0,0), (-1,0), colors.white),
        ("FONTNAME",     (0,0), (-1,0), "THSarabun-Bold"),
        ("FONTSIZE",     (0,0), (-1,-1), 10),
        ("FONTNAME",     (0,1), (-1,-1), "THSarabun"),
        ("ALIGN",        (1,0), (-1,-1), "CENTER"),
        ("VALIGN",       (0,0), (-1,-1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0,1), (-1,-2), [colors.white, colors.HexColor("#f0f4f8")]),
        ("GRID",         (0,0), (-1,-1), 0.5, colors.HexColor("#cccccc")),
        ("TOPPADDING",   (0,0), (-1,-1), 7),
        ("BOTTOMPADDING",(0,0), (-1,-1), 7),
        # GPA row
        ("BACKGROUND",   (0,-1), (-1,-1), colors.HexColor("#e8f0fe")),
        ("FONTNAME",     (0,-1), (-1,-1), "THSarabun-Bold"),
        ("SPAN",         (0,-1), (1,-1)),
    ])

    # สีแดงถ้าไม่ผ่าน
    for i, (col, _) in enumerate(SUBJECTS.items(), start=1):
        if float(row[col]) < CONFIG["pass_score"]:
            score_style.add("TEXTCOLOR", (3,i), (3,i), colors.HexColor("#c0392b"))
            score_style.add("FONTNAME",  (3,i), (3,i), "THSarabun-Bold")

    score_table.setStyle(score_style)
    story.append(score_table)
    story.append(Spacer(1, 20))

    # Summary box
    passed = all(float(row[s]) >= CONFIG["pass_score"] for s in SUBJECTS)
    status_text = " ผ่านทุกวิชา" if passed else " มีวิชาที่ไม่ผ่าน"
    status_color = colors.HexColor("#27ae60") if passed else colors.HexColor("#c0392b")

    summary_data = [[f"GPA รวม: {gpa:.2f}   |   สถานะ: {status_text}"]]
    summary_table = Table(summary_data, colWidths=[17*cm])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), colors.HexColor("#f8f9fa")),
        ("TEXTCOLOR",     (0,0), (-1,-1), status_color),
        ("FONTNAME",      (0,0), (-1,-1), "THSarabun-Bold"),
        ("FONTSIZE",      (0,0), (-1,-1), 12),
        ("ALIGN",         (0,0), (-1,-1), "CENTER"),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",    (0,0), (-1,-1), 10),
        ("BOTTOMPADDING", (0,0), (-1,-1), 10),
        ("BOX",           (0,0), (-1,-1), 1.5, status_color),
        ("ROUNDEDCORNERS",(0,0), (-1,-1), [4,4,4,4]),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 30))

    # Signature
    sig_data = [["", ""],
                ["_________ครูประจำชั้น___________", "___________ผู้อำนวยการ___________"],
                ["ครูประจำชั้น", "ผู้อำนวยการโรงเรียน"]]
    sig_table = Table(sig_data, colWidths=[8.5*cm, 8.5*cm])
    sig_table.setStyle(TableStyle([
        ("ALIGN",    (0,0), (-1,-1), "CENTER"),
        ("FONTNAME", (0,0), (-1,-1), "THSarabun"),
        ("FONTSIZE", (0,0), (-1,-1), 10),
        ("TOPPADDING",    (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
    ]))
    story.append(sig_table)

    doc.build(story)
    log.info(f"  📄 สร้าง PDF: {filename}")
    return filename


# ========== STEP 5: ส่ง Email ==========
# คืนค่า "sent" / "skipped" — ถ้าส่งไม่สำเร็จจะ raise ให้ main() บันทึกเป็น error
def send_email(row: pd.Series, pdf_path: str) -> str:
    if not CONFIG["send_email"]:
        log.info(f"  📧 [SKIP] ส่ง Email ถึง {row['parent_email']} (ปิดใน config)")
        return "skipped"
    if not CONFIG["email_sender"] or not CONFIG["email_password"]:
        raise RuntimeError("ยังไม่ได้ตั้งค่า EMAIL_SENDER / EMAIL_PASSWORD ในไฟล์ .env")

    full_name = f"{row['first_name']} {row['last_name']}"
    msg = MIMEMultipart()
    msg["From"]    = CONFIG["email_sender"]
    msg["To"]      = row["parent_email"]
    msg["Subject"] = f"ผลการเรียน {full_name} — {CONFIG['semester']}"

    body = f"""
เรียน ผู้ปกครองของ {full_name}

    ทางโรงเรียนขอส่งใบรายงานผลการเรียนของนักเรียน {full_name}
    ประจำ{CONFIG['semester']} ตามเอกสารแนบ

    หากมีข้อสงสัยกรุณาติดต่อครูประจำชั้น

ขอแสดงความนับถือ
{CONFIG['school_name']}
    """
    msg.attach(MIMEText(body, "plain", "utf-8"))

    with open(pdf_path, "rb") as f:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition",
                        f"attachment; filename={os.path.basename(pdf_path)}")
        msg.attach(part)

    with smtplib.SMTP(CONFIG["smtp_host"], CONFIG["smtp_port"]) as server:
        server.starttls()
        server.login(CONFIG["email_sender"], CONFIG["email_password"])
        server.send_message(msg)
    log.info(f"  ✉️  ส่ง Email สำเร็จ → {row['parent_email']}")
    return "sent"


# ========== STEP 6: บันทึก Log ผลลัพธ์ ==========
def save_summary_log(results: list[dict]):
    summary_path = CONFIG["summary_path"]
    df = pd.DataFrame(results)
    df.to_csv(summary_path, index=False, encoding="utf-8-sig")
    log.info(f"\n📊 สรุปผล → {summary_path}")
    log.info(f"   สำเร็จ : {sum(1 for r in results if r['status'] == 'success')}")
    log.info(f"   ล้มเหลว: {sum(1 for r in results if r['status'] == 'error')}")


# ========== MAIN PROCESS ==========
def main():
    log.info("=" * 50)
    log.info("🤖 RPA Bot เริ่มทำงาน")
    log.info("=" * 50)

    df = read_student_data(CONFIG["input_path"])
    results = []

    for idx, row in df.iterrows():
        student_id = row.get("student_id", f"row_{idx}")
        log.info(f"\n[{idx+1}/{len(df)}] ประมวลผล: {student_id}")

        # Validate
        errors = validate_student(row)
        if errors:
            log.warning(f"  ⚠️  ข้อมูลไม่ผ่าน: {', '.join(errors)}")
            results.append({"student_id": student_id, "status": "error",
                            "reason": "; ".join(errors)})
            continue

        try:
            # Generate PDF
            pdf_path = generate_report_card(row, CONFIG["output_folder"])

            # Send Email
            email_status = send_email(row, pdf_path)

            results.append({"student_id": student_id,
                            "name": f"{row['first_name']} {row['last_name']}",
                            "gpa": calculate_gpa(row),
                            "pdf": pdf_path,
                            "email": row["parent_email"],
                            "email_status": email_status,
                            "status": "success", "reason": ""})

        except Exception as e:
            log.error(f"  ❌ Error: {e}")
            results.append({"student_id": student_id, "status": "error", "reason": str(e)})

    save_summary_log(results)
    log.info("\n✅ Bot ทำงานเสร็จสิ้น")


if __name__ == "__main__":
    main()