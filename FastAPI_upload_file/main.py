from fastapi import FastAPI, UploadFile, File, BackgroundTasks, Form
from fastapi.responses import JSONResponse
import os, shutil, yaml, boto3, requests
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# 👇 Thêm middleware CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Cho phép tất cả domain (có thể giới hạn lại)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ARTIFACT_DIR = "artifact"
CONFIG_PATH = os.path.join(ARTIFACT_DIR, "config.yaml")

# Đọc file cấu hình YAML
def read_config():
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(f"Config file not found at: {CONFIG_PATH}")

    with open(CONFIG_PATH, "r") as f:
        config = yaml.safe_load(f)

    if config is None:
        raise ValueError("Config file is empty or not valid YAML format")

    return config


# Đẩy file lên AWS S3
def upload_to_s3(file_path: str, filename: str):
    config = read_config()["aws"]
    s3 = boto3.client(
        "s3",
        region_name=config["region"],
        aws_access_key_id=config["access_key"],
        aws_secret_access_key=config["secret_key"]
    )
    s3.upload_file(file_path, config["bucket_name"], filename)
    print(f"✅ Uploaded {filename} successfully!")
# Hàm xử lý chạy ngầm
def background_upload(file_path: str, filename: str, webhook_url: str):
    try:
        upload_to_s3(file_path, filename)
        # Gửi thông báo webhook khi xong
        if webhook_url:
            requests.post(webhook_url, json={"filename": filename, "status": "success"})
    except Exception as e:
        if webhook_url:
            requests.post(webhook_url, json={"filename": filename, "status": "error", "detail": str(e)})

# API nhận file và xử lý ngầm
@app.post("/upload/")
def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    webhook_url: str = Form(default="")
):
    os.makedirs(ARTIFACT_DIR, exist_ok=True)
    file_path = os.path.join(ARTIFACT_DIR, file.filename)

    # Lưu file vào thư mục artifact
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Gửi task chạy ngầm
    background_tasks.add_task(background_upload, file_path, file.filename, webhook_url)

    return JSONResponse(
        content={"message": f"Đã upload file {file.filename}. Task đang xử lý nền."},
        status_code=202
    )
