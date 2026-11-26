import uvicorn
from app.main import app

if __name__ == "__main__":
    # استفاده از سرور داخلی بدون نیاز به تنظیمات پیچیده
    uvicorn.run(app, host="127.0.0.1", port=8080)