import csv, io, json, os
from datetime import datetime, timedelta
from typing import Annotated

import jwt
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import StreamingResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from models import Token, OutputRecord
from graph import graph

app = FastAPI(title="Profile Enricher")

# --- JWT config ---
SECRET = os.getenv("JWT_SECRET", "dev-secret")
ALGORITHM = "HS256"
FAKE_USER = {"username": "admin", "password": "password"}

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def create_token(data: dict) -> str:
    payload = {**data, "exp": datetime.utcnow() + timedelta(hours=1)}
    return jwt.encode(payload, SECRET, algorithm=ALGORITHM)

async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    try:
        jwt.decode(token, SECRET, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# --- Auth endpoint ---
@app.post("/token", response_model=Token)
async def login(form: OAuth2PasswordRequestForm = Depends()):
    if form.username != FAKE_USER["username"] or form.password != FAKE_USER["password"]:
        raise HTTPException(status_code=401, detail="Bad credentials")
    return Token(access_token=create_token({"sub": form.username}))

# --- Processing endpoint ---
@app.post("/process/csv", dependencies=[Depends(get_current_user)])
async def process_csv(file: UploadFile = File(...)):
    content = await file.read()
    reader = csv.DictReader(io.StringIO(content.decode()))
    records = [dict(row) for row in reader]
    
    result = graph.invoke({
        "records": records,
        "processed": [],
        "failed": []
    })
    
    all_records = result["processed"] + result["failed"]
    
    # Stream CSV back
    output = io.StringIO()
    fields = OutputRecord.model_fields.keys()
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(all_records)
    output.seek(0)
    
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=enriched.csv"}
    )

@app.post("/process/json", dependencies=[Depends(get_current_user)])
async def process_json(file: UploadFile = File(...)):
    content = await file.read()
    records = json.loads(content.decode())
    
    result = graph.invoke({
        "records": records,
        "processed": [],
        "failed": []
    })
    
    all_records = result["processed"] + result["failed"]
    
    return StreamingResponse(
        io.BytesIO(json.dumps(all_records, indent=2).encode()),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=enriched.json"}
    )