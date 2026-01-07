import os
import shutil
import base64
import json
from fastapi import FastAPI, File, UploadFile, Form, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from datetime import datetime, timezone, timedelta
from typing import Optional

app = FastAPI()

# --- 🔐 核心配置 ---
CODE_MAP = {
    "pub1ic": "storage_vivo",
    "yser": "storage_yser",
    # 在这里添加更多暗号
}

BASE_DIR = "uploads"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 🛠️ 辅助函数 ---

def get_target_dir(code: str):
    """根据暗号获取目录"""
    if code not in CODE_MAP:
        raise HTTPException(status_code=403, detail="暗号错误或不存在")
    
    folder_name = CODE_MAP[code]
    target_path = os.path.join(BASE_DIR, folder_name)
    
    if not os.path.exists(target_path):
        os.makedirs(target_path)
    return target_path

def truncate_filename(filename: str, max_length: int = 20) -> str:
    """
    [新增] 文件名截断逻辑
    如果文件名超过 max_length，保留后缀，截断中间
    """
    if len(filename) <= max_length:
        return filename

    # 分离文件名和后缀 (例如: "super_long_name.jpg" -> "super_long_name", ".jpg")
    name, ext = os.path.splitext(filename)
    
    # 计算允许的名字长度
    # 比如 max=20, ext=.jpg(4字符), 那么名字只能有 16字符
    allowed_length = max_length - len(ext)
    
    # 防止后缀太长导致允许长度为负数 (极端情况)
    if allowed_length < 1:
        # 如果连1个字都放不下，就强制截取前20个字符 (可能会破坏后缀，但也只能这样了)
        return filename[:max_length]
    
    # 截取名字部分，并拼接后缀
    return name[:allowed_length] + ext

def get_unique_filename(directory: str, filename: str) -> str:
    """
    核心逻辑：生成唯一文件名
    如果 filename 存在，则变成 filename_1, filename_2 ...
    """
    # 拼接完整路径
    file_path = os.path.join(directory, filename)
    
    # 如果文件不存在，直接返回原名
    if not os.path.exists(file_path):
        return filename
    
    # 如果文件存在，开始尝试重命名
    base, ext = os.path.splitext(filename)
    counter = 1
    
    while True:
        # 构造新名字：原名_序号.后缀
        new_filename = f"{base}_{counter}{ext}"
        new_path = os.path.join(directory, new_filename)
        
        # 检查新名字是否被占用
        if not os.path.exists(new_path):
            return new_filename # 找到可用的名字了！
        
        # 如果还是被占用，序号+1，继续循环
        counter += 1

# ---  Token 生成与解码辅助函数 ---
def generate_token(code: str, filename: str) -> str:
    """生成不包含明文信息的 Base64 Token"""
    try:
        data = json.dumps({"c": code, "f": filename})
        # urlsafe_b64encode 适合放在 URL 中
        token = base64.urlsafe_b64encode(data.encode('utf-8')).decode('utf-8')
        return token
    except Exception:
        return ""

def decode_token(token: str):
    """解析 Token 获取 code 和 filename"""
    try:
        # 解码
        json_str = base64.urlsafe_b64decode(token).decode('utf-8')
        data = json.loads(json_str)
        return data.get("c"), data.get("f")
    except Exception:
        return None, None



# --- 1. 验证接口 ---
@app.get("/verify")
def verify_code(code: str = Query(...)):
    if code in CODE_MAP:
        return {"status": "ok", "msg": "验证通过"}
    else:
        raise HTTPException(status_code=403, detail="暗号错误")

# --- 2. 获取列表 (修改了这里) ---
@app.get("/list_files")
def list_files(code: str = Query(...), keyword: str = Query(None)): # 1. 新增 keyword 参数
    target_dir = get_target_dir(code)
    
    files = []
    if os.path.exists(target_dir):
        # 获取所有文件
        file_list = os.listdir(target_dir)

        # 2. [新增] 核心搜索逻辑：如果有关键词，先进行过滤
        if keyword:
            # lower() 实现忽略大小写搜索
            file_list = [f for f in file_list if keyword.lower() in f.lower()]

        # 按修改时间倒序排列
        file_list.sort(key=lambda x: os.path.getmtime(os.path.join(target_dir, x)), reverse=True)
        # 定义 UTC+8 时区 (北京时间)
        tz_cn = timezone(timedelta(hours=8))
        for filename in file_list:
            file_path = os.path.join(target_dir, filename)
            if os.path.isfile(file_path):
                size_kb = round(os.path.getsize(file_path) / 1024, 2)

                # 1. 获取文件的时间戳
                timestamp = os.path.getmtime(file_path)
                # 2. 强制转为 UTC+8 时区的时间对象
                dt_object = datetime.fromtimestamp(timestamp, tz=tz_cn)
                # 3. 格式化为字符串 (24小时制)
                mtime = dt_object.strftime('%Y-%m-%d %H:%M')
                token = generate_token(code, filename)

                # 如果在服务端，需要使用相对路径；如果在客户端，需要使用完整URL
                share_url = f"http://127.0.0.1:8000/sharedownload/{token}"
                files.append({
                    "name": filename,
                    "size": f"{size_kb} KB",
                    "date": mtime,
                    "url": f"http://127.0.0.1:8000/download/{filename}?code={code}",
                    "share_url": share_url # 分享给别人的链接（加密，无明文码）
                })
    return files

# --- 3. 上传接口 (修改了这里) ---
@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...), 
    code: str = Form(...) 
):

    target_dir = get_target_dir(code)
    short_name = truncate_filename(file.filename, 20)
    unique_name = get_unique_filename(target_dir, short_name)
    
    try:
        file_location = os.path.join(target_dir, unique_name)
        with open(file_location, "wb+") as file_object:
            shutil.copyfileobj(file.file, file_object)
            
        return {"info": "success", "filename": unique_name}
    except Exception as e:
        return {"info": "error", "details": str(e)}
    

# --- 4. 下载接口 ---
@app.get("/download/{filename}")
async def download_file(filename: str, code: str = Query(...)):
    target_dir = get_target_dir(code)
    file_path = os.path.join(target_dir, filename)
    
    if os.path.exists(file_path):
        # 下载时，建议让浏览器显示原名（或者直接用保存名也可以）
        # 这里直接用保存的文件名
        return FileResponse(
            path=file_path, 
            filename=filename, 
            media_type='application/octet-stream'
        )
    return {"error": "File not found"}

@app.get("/sharedownload/{token}")
async def share_download(token: str):
    """无需明文 code，解析 token 后下载"""
    code, filename = decode_token(token)
    
    if not code or not filename:
        return {"error": "无效的链接"}
    
    # 复用鉴权逻辑：如果解析出的 code 不在白名单，get_target_dir 会抛错
    try:
        target_dir = get_target_dir(code)
        file_path = os.path.join(target_dir, filename)
        
        if os.path.exists(file_path):
            return FileResponse(
                path=file_path, 
                filename=filename, 
                media_type='application/octet-stream'
            )
        else:
            return {"error": "文件已被删除或不存在"}
    except HTTPException:
        return {"error": "链接已失效"}

# ---  5. 删除接口 ---
@app.delete("/delete/{filename}")
def delete_file(filename: str, code: str = Query(...)):
    # 1. 鉴权：获取该暗号对应的目录
    target_dir = get_target_dir(code)
    file_path = os.path.join(target_dir, filename)

    # 2. 检查文件是否存在
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")

    # 3. 删除文件
    try:
        os.remove(file_path)
        return {"status": "success", "msg": f"{filename} 已删除"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")
    

    