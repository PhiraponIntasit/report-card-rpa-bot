# Report Card RPA Bot

An RPA (Robotic Process Automation) bot that automatically generates student report cards as Thai-language PDFs and emails them to parents.

บอท RPA ที่สร้างใบรายงานผลการเรียนเป็นไฟล์ PDF ภาษาไทย และส่งอีเมลถึงผู้ปกครองโดยอัตโนมัติ — โปรเจกต์วิชา Robotic Process Automation

![Sample report card](docs/sample_report_card.png)

## Features

- **Read data** — loads student scores from a CSV file
- **Validate** — checks for missing fields, out-of-range scores (0–100) and invalid email addresses; bad rows are skipped and logged instead of crashing the run
- **Grade** — converts scores to the Thai 8-level grade scale (0.0–4.0) and calculates GPA
- **Generate PDF** — builds a formatted A4 report card with Thai font (TH Sarabun New), failing subjects highlighted in red
- **Email** — sends each PDF to the parent via SMTP (Gmail)
- **Log & summarize** — writes a run log (`bot_log.log`) and a per-student result file (`summary.csv`)

## Workflow

```
students.csv → Validate → Calculate grades & GPA → Generate PDF → Send email → summary.csv + log
```

## Tech Stack

Python · pandas · ReportLab · smtplib · python-dotenv

## Getting Started

Requires **Python 3.9+**.

**1. Install dependencies**
```bash
pip install -r requirements.txt
```

**2. Configure email (optional)**

Copy `.env.example` to `.env` and fill in your details. For Gmail, use an [App Password](https://support.google.com/accounts/answer/185833), not your normal password.
```
EMAIL_SENDER=your_email@gmail.com
EMAIL_PASSWORD=your_gmail_app_password
SEND_EMAIL=true
```
With `SEND_EMAIL=false` (default), the bot only generates PDFs — useful for testing.

**3. Run**
```bash
python rpa_bot.py
```
PDFs are saved in `report_cards/`, and results in `summary.csv` (with `email_status`: `sent` / `skipped`). The script can be run from any folder — all paths are relative to `rpa_bot.py`.

Example console output:
```
[3/5] ประมวลผล: 6700003
  📄 สร้าง PDF: .../report_cards/6700003_report_card.pdf
  📧 [SKIP] ส่ง Email ถึง parent3@example.com (ปิดใน config)
[4/5] ประมวลผล: 6700004
  ⚠️  ข้อมูลไม่ผ่าน: ขาดคะแนน ภาษาอังกฤษ
📊 สรุปผล → .../summary.csv
   สำเร็จ : 3
   ล้มเหลว: 2
```

**4. Run tests**
```bash
python test_rpa_bot.py
```

## Input Format

`students.csv` (UTF-8) must have these columns:

| column | description |
|---|---|
| `student_id`, `first_name`, `last_name` | required |
| `math`, `science`, `english`, `thai`, `social` | numeric score 0–100 (must match keys in `SUBJECTS`) |
| `parent_email` | recipient address |

A row with a missing/non-numeric/out-of-range score or an invalid email is skipped and recorded as `error` in `summary.csv`. If sending an email fails (e.g. wrong App Password), that student is also marked `error` with the reason.

## Grading Scale

| Score | Grade | Label |
|---|---|---|
| 80–100 | 4.0 | ดีเยี่ยม |
| 75–79 | 3.5 | ดี |
| 70–74 | 3.0 | ดี |
| 65–69 | 2.5 | พอใช้ |
| 60–64 | 2.0 | พอใช้ |
| 55–59 | 1.5 | ผ่าน |
| 50–54 | 1.0 | ผ่าน |
| 0–49 | 0.0 | ไม่ผ่าน |

GPA = average of subject grades (equal weight).

## Sample Data & Output

`students.csv` contains fictional sample data, including two intentionally invalid rows to demonstrate validation:

| student_id | name | GPA | status | reason |
|---|---|---|---|---|
| 6700001 | สมชาย ใจดี | 3.70 | ✅ success | |
| 6700002 | สมหญิง รักเรียน | 4.00 | ✅ success | |
| 6700003 | มานะ อดทน | 1.70 | ✅ success | |
| 6700004 | ปิติ ยิ้มแย้ม | – | ❌ error | missing English score |
| 6700005 | ชูใจ สดใส | – | ❌ error | invalid email format |

A full sample PDF is in [`docs/sample_report_card.pdf`](docs/sample_report_card.pdf).

## Project Structure

```
├── rpa_bot.py          # main bot script
├── test_rpa_bot.py     # tests for grading & validation
├── students.csv        # input data (sample)
├── requirements.txt
├── .env.example        # email config template
├── fonts/              # TH Sarabun New (Thai font)
└── docs/               # sample output
```

## Customization

Edit `CONFIG` and `SUBJECTS` at the top of `rpa_bot.py` to change the school name, semester, passing score or subject list.

## Scheduling (optional)

To run the bot automatically (e.g. at the end of each semester), use **Windows Task Scheduler** → *Create Basic Task* → action *Start a program*: `python` with argument `C:/path/to/rpa_bot.py`. On macOS/Linux use `cron`.

## Limitations & Future Work

- Input is CSV only (Excel `.xlsx` could be supported via `pandas.read_excel`)
- Subjects have equal weight — no credit-hour weighting
- One SMTP connection per email; fine for a class, slow for thousands of students

## Authors

- พีรพล อินทะสิทธิ์ (Phirapon Intasit)
- พีรณัฐ เมฆฉาย (Peeranut Mekchay)

## Credits

TH Sarabun New font by SIPA (Software Industry Promotion Agency), free to use and redistribute.
