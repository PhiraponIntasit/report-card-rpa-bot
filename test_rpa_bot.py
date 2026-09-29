"""เทสต์ตรรกะเกรดและการตรวจข้อมูล — รันด้วย: python test_rpa_bot.py (หรือ pytest)"""
import pandas as pd
from rpa_bot import score_to_grade, calculate_gpa, validate_student


def row(**overrides):
    base = {"student_id": "1", "first_name": "ก", "last_name": "ข",
            "math": 80, "science": 80, "english": 80, "thai": 80, "social": 80,
            "parent_email": "p@example.com"}
    base.update(overrides)
    return pd.Series(base)


def test_grade_boundaries():
    cases = {100: "4.0", 80: "4.0", 79: "3.5", 75: "3.5", 70: "3.0", 65: "2.5",
             60: "2.0", 55: "1.5", 50: "1.0", 49: "0.0", 0: "0.0"}
    for score, grade in cases.items():
        assert score_to_grade(score) == grade, (score, score_to_grade(score))


def test_gpa():
    assert calculate_gpa(row()) == 4.0
    assert calculate_gpa(row(math=49)) == 3.2


def test_validate():
    assert validate_student(row()) == []
    assert validate_student(row(math="abc"))          # ตัวอักษรต้องไม่ทำให้ crash
    assert validate_student(row(math=101))
    assert validate_student(row(english=float("nan")))
    assert validate_student(row(parent_email="a@"))
    assert validate_student(row(parent_email="no-at-sign.com"))


if __name__ == "__main__":
    test_grade_boundaries(); test_gpa(); test_validate()
    print("all tests passed")
