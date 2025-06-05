from fastapi import FastAPI, HTTPException, Query, Depends, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import pandas as pd
import os
import gcsfs


fs = gcsfs.GCSFileSystem(project='questionbankclassifier')
subjects_df = pd.read_csv('gs://ib_question_bank/QuestionBank/QuestionBankSubjects.csv')
selected_subject = subjects_df['Subject'].unique().tolist()[0]  # Default to first subject
questions_df = pd.read_csv('gs://ib_question_bank/QuestionBank/'+subjects_df.loc[0, 'DataFile'])

app = FastAPI()

# CORS for local development/frontend testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



# --- MODELS ---

class QuestionOut(BaseModel):
    questionId: str
    imageFilename: str
    year: int
    month: str
    subject: str
    paperType: str
    timezone: str
    level: str
    questionNumber: int
    markschemeAnswer: Optional[str]
    syllabus: str
    imageUrl: str

class ReportIn(BaseModel):
    userId: Optional[str]
    reason: str

# In-memory stores for bookmarks, done, reports (use DB in prod!)
USER_BOOKMARKS = {}
USER_DONE = {}
REPORTS = []

# --- ENDPOINTS ---

@app.get("/api/subjects")
async def list_subjects():
    return subjects_df.to_dict(orient='records')

@app.get("/static/{path:path}")
async def static_files(path: str):
    #serve static files from the gcsfs path
    fs = gcsfs.GCSFileSystem(project='questionbankclassifier')
    file_path = f"gs://ib_question_bank/QuestionBank/questions/{path}"
    if fs.exists(file_path):
        with fs.open(file_path, 'rb') as f:
            content = f.read()
        return Response(content=content, media_type="image/png")

# set subject
@app.post("/api/subjects/{subject}")
async def set_subject(subject: str):
    selected_subject = subjects_df['Subject'].unique().tolist()[subject]  # Default to first subject
    questions_df = pd.read_csv('gs://ib_question_bank/QuestionBank/'+subjects_df.loc[subject, 'DataFile'])


# Filter/list questions (with pagination)
@app.get("/api/questions", response_model=dict)
def list_questions(
    unit: Optional[str] = Query(None, alias="unit"),
    paperType: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
    subject: Optional[str] = Query(None),
    page: int = 1,
    pageSize: int = 10
):
    df = questions_df.copy()
    if unit:
        df = df[df['Syllabus'] == unit]
    if paperType:
        df = df[df['Paper Type'] == paperType]
    if year:
        df = df[df['Year'] == year]
    if subject:
        df = df[df['Subject'] == subject]

    total = len(df)
    df = df.iloc[(page-1)*pageSize: page*pageSize]
    questions = []
    for _, row in df.iterrows():
        questions.append({
            "questionId": row["QuestionID"],
            "imageFilename": row["Image Filename"],
            "year": int(row["Year"]),
            "month": row["Month"],
            "subject": row["Subject"],
            "paperType": row["Paper Type"],
            "timezone": row["Timezone"],
            "level": row["Level"],
            "questionNumber": int(row["Question Number"]),
            "syllabus": row["Syllabus"],
            "markschemeAnswer": row.get("Markscheme Answer"),
            "imageUrl": f"/static/{row['Image Filename']}"
        })
    return {"results": questions, "total": total, "page": page, "pageSize": pageSize}

# Get question detail
@app.get("/api/questions/{question_id}", response_model=QuestionOut)
def get_question(question_id: str):
    df = questions_df[questions_df["QuestionID"] == question_id]
    if df.empty:
        raise HTTPException(status_code=404, detail="Question not found")
    row = df.iloc[0]
    return QuestionOut(
        questionId=row["QuestionID"],
        imageFilename=row["Image Filename"],
        year=int(row["Year"]),
        month=row["Month"],
        subject=row["Subject"],
        paperType=row["Paper Type"],
        timezone=row["Timezone"],
        level=row["Level"],
        questionNumber=int(row["Question Number"]),
        syllabus=row["Syllabus"],
        markschemeAnswer=row.get("Markscheme Answer"),
        imageUrl=f"/static/{row['Image Filename']}"
    )

# Bookmark endpoints
@app.get("/api/users/{user_id}/bookmarks")
def list_bookmarks(user_id: str):
    return USER_BOOKMARKS.get(user_id, [])

@app.post("/api/users/{user_id}/bookmarks")
def add_bookmark(user_id: str, data: dict):
    qid = data["questionId"]
    USER_BOOKMARKS.setdefault(user_id, set()).add(qid)
    return {"success": True}

@app.delete("/api/users/{user_id}/bookmarks/{qid}")
def remove_bookmark(user_id: str, qid: str):
    USER_BOOKMARKS.setdefault(user_id, set()).discard(qid)
    return {"success": True}

# Done endpoints
@app.get("/api/users/{user_id}/done")
def list_done(user_id: str):
    return USER_DONE.get(user_id, [])

@app.post("/api/users/{user_id}/done")
def add_done(user_id: str, data: dict):
    qid = data["questionId"]
    USER_DONE.setdefault(user_id, set()).add(qid)
    return {"success": True}

@app.delete("/api/users/{user_id}/done/{qid}")
def remove_done(user_id: str, qid: str):
    USER_DONE.setdefault(user_id, set()).discard(qid)
    return {"success": True}

# Report endpoint
@app.post("/api/questions/{question_id}/report")
def report_question(question_id: str, report: ReportIn):
    REPORTS.append({"questionId": question_id, "userId": report.userId, "reason": report.reason})
    return {"success": True}

@app.get("/api/questions/units")
def get_units(subject: Optional[str] = None):
    df = questions_df
    if subject:
        df = df[df['Subject'] == subject]
    return sorted(df['Syllabus'].unique().tolist())

@app.get("/api/questions/paperTypes")
def get_paper_types(subject: Optional[str] = None):
    df = questions_df
    if subject:
        df = df[df['Subject'] == subject]
    return sorted(df['Paper Type'].unique().tolist())

@app.get("/api/questions/years")
def get_years(subject: Optional[str] = None):
    df = questions_df
    if subject:
        df = df[df['Subject'] == subject]
    return sorted(df['Year'].unique().tolist())
