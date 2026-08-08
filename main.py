import os
import shutil
import uuid
import re
import requests
from fastapi import Request 
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File as FastAPIFile
from fastapi.responses import FileResponse
from sqlmodel import Session, select
from database import create_db_and_tables, get_session
from models import User, UserCreate, UserLogin, File, AuditLog
from auth import hash_password, verify_password, create_access_token, get_current_user

app = FastAPI()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_MAX_SIZE = 10 * 1024 * 1024
DANGEROUS_EXTENSIONS = {".exe", ".sh", ".bat", ".cmd", ".msi", ".com", ".scr", ".php", ".js"}

VT_API_KEY = os.getenv("VT_API_KEY")
# print(f"VT_API_KEY loaded: {VT_API_KEY[:6]}..." if VT_API_KEY else "VT_API_KEY is MISSING/None")
VT_UPLOAD_URL = "https://www.virustotal.com/api/v3/files"
VT_ANALYSIS_URL = "https://www.virustotal.com/api/v3/analyses/{}"


def sanitize_filename(filename: str) -> str:
    filename = os.path.basename(filename)
    filename = re.sub(r'[^A-Za-z0-9._-]', '_', filename)
    return filename

def log_action(session: Session, user_id: int, action: str, request: Request):  # a special FastAPI type that gives you access 
    # to the raw incoming HTTP request, including things like the client's IP address; you get this "for free" 
    # by just adding it as a parameter to any route
    ip_address = request.client.host if request.client else "unknown"
    # pulls the IP address of whoever made the request; the if request.client else "unknown" guards
    # against a rare edge case where this info isn't available
    audit_entry = AuditLog(user_id=user_id, action=action, ip_address=ip_address)
    session.add(audit_entry)
    session.commit()


def submit_to_virustotal(file_path: str) -> str:
    headers = {"x-apikey": VT_API_KEY}
    with open(file_path, "rb") as f:
        files = {"file": f}
        response = requests.post(VT_UPLOAD_URL, headers=headers, files=files)
    response.raise_for_status()
    return response.json()["data"]["id"]


@app.on_event("startup")
def on_startup():
    create_db_and_tables()


@app.get("/")
def read_root():
    return {"message": "Secure File Vault API is running"}


@app.post("/register")
def register(user_data: UserCreate, session: Session = Depends(get_session)):
    existing_user = session.exec(
        select(User).where(User.username == user_data.username)
    ).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already taken")

    new_user = User(
        username=user_data.username,
        email=user_data.email,
        password_hash=hash_password(user_data.password)
    )
    session.add(new_user)
    session.commit()
    session.refresh(new_user)

    return {"message": "User registered successfully", "user_id": new_user.id}


@app.post("/login")
def login(user_data: UserLogin, request: Request, session: Session = Depends(get_session)):
    user = session.exec(
        select(User).where(User.username == user_data.username)
    ).first()

    if not user or not verify_password(user_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    access_token = create_access_token(data={"sub": user.username})
    log_action(session, user.id, "login", request)
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/me")
def read_current_user(current_user: User = Depends(get_current_user)):
    return {"username": current_user.username, "email": current_user.email}


@app.post("/logout")
def logout(request: Request, current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    log_action(session, current_user.id, "logout", request)
    return {"message": f"{current_user.username} logged out. Please discard your token client-side."}


@app.post("/files/upload")
def upload_file(
    request: Request,
    file: UploadFile = FastAPIFile(...),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    safe_filename = sanitize_filename(file.filename)
    file_extension = os.path.splitext(safe_filename)[1].lower()

    if file_extension in DANGEROUS_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type {file_extension} is not allowed")

    contents = file.file.read()
    if len(contents) > ALLOWED_MAX_SIZE:
        raise HTTPException(status_code=413, detail="File too large. Max size is 10MB")

    file_id = uuid.uuid4().hex
    stored_filename = f"{file_id}{file_extension}"
    stored_path = os.path.join(UPLOAD_DIR, stored_filename)

    with open(stored_path, "wb") as buffer:
        buffer.write(contents)

    new_file = File(
        owner_id=current_user.id,
        filename=safe_filename,
        stored_path=stored_path,
        size=len(contents)
    )

    try:
        analysis_id = submit_to_virustotal(stored_path)
        new_file.virustotal_result = f"pending:{analysis_id}"
    except Exception as e:
        print(f"VirusTotal submission failed: {e}")
        new_file.virustotal_result = "scan_failed"

    session.add(new_file)
    session.commit()
    session.refresh(new_file)

    log_action(session, current_user.id, f"upload:{new_file.filename}", request)

    return {"message": "File uploaded successfully", "file_id": new_file.id, "filename": new_file.filename}


@app.get("/files")
def list_files(current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    files = session.exec(
        select(File).where(File.owner_id == current_user.id)
    ).all()
    return files


@app.get("/files/{file_id}/download")
def download_file(file_id: int, request: Request, current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    file_record = session.get(File, file_id)

    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")
    if file_record.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="You do not have permission to access this file")

    log_action(session, current_user.id, f"download:{file_record.filename}", request)

    return FileResponse(path=file_record.stored_path, filename=file_record.filename)


@app.delete("/files/{file_id}")
def delete_file(file_id: int, request: Request, current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    file_record = session.get(File, file_id)

    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")
    if file_record.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="You do not have permission to delete this file")

    filename = file_record.filename

    if os.path.exists(file_record.stored_path):
        os.remove(file_record.stored_path)

    session.delete(file_record)
    session.commit()

    log_action(session, current_user.id, f"delete:{filename}", request)

    return {"message": "File deleted successfully"}


@app.get("/files/{file_id}/scan")
def check_scan_result(file_id: int, current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    file_record = session.get(File, file_id)

    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")
    if file_record.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="You do not have permission to access this file")

    if not file_record.virustotal_result or not file_record.virustotal_result.startswith("pending:"):
        return {"filename": file_record.filename, "scan_result": file_record.virustotal_result}

    analysis_id = file_record.virustotal_result.split("pending:")[1]
    headers = {"x-apikey": VT_API_KEY}
    response = requests.get(VT_ANALYSIS_URL.format(analysis_id), headers=headers)
    response.raise_for_status()
    data = response.json()["data"]["attributes"]

    if data["status"] != "completed":
        return {"filename": file_record.filename, "scan_result": "scanning in progress"}

    stats = data["stats"]
    if stats["malicious"] > 0:
        result = "malicious"
    elif stats["suspicious"] > 0:
        result = "suspicious"
    else:
        result = "clean"

    file_record.virustotal_result = result
    session.add(file_record)
    session.commit()

    return {"filename": file_record.filename, "scan_result": result}