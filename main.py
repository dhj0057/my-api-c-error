# 📋 main.py · [과제 백엔드] 나만의 멀티모달 API — 사진을 받아 정해 둔 칸(JSON)으로 정리 (Vercel 에 올릴 main.py · POST 한 번에 요청 1번)
# · ★ (직접 작성) 표시가 붙은 곳만 내 주제로 바꾸면 됨 — 화면(app.py)은 고칠 곳 없음
# · 키는 환경 변수 GEMINI_API_KEY · 접근 코드는 APP_ACCESS_CODE (코드 · 저장소에 적지 않음)
import base64
import binascii
import json
import os

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

MODEL_NAME = "gemini-3.5-flash-lite"

# ★ (직접 작성) ① 서비스 이름 · 아이콘 · 한 줄 소개 — 화면이 GET / 로 받아 제목으로 씀
APP_TITLE = "C 오류 화면 해설 도우미"
APP_ICON = "🐞"
APP_DESCRIPTION = "C 컴파일 · 실행 오류가 뜬 화면을 찍으면 오류 메시지 · 위치 · 뜻 · 원인 · 고치는 법을 정리해 줍니다"

# ★ (직접 작성) ② 사진을 보고 할 일 — 역할 · 할 일 · 모를 때
PROMPT = """너는 C 언어를 처음 배우는 대학생을 돕는 'C오류봇' 이야.
사진은 C 코드의 컴파일 오류나 실행 오류가 보이는 화면(터미널 · IDE)이야.
화면에 보이는 첫 번째 오류를 골라 아래 칸을 한국어로 짧게 채워. 오류 메시지는 화면 글자 그대로 옮겨.
화면에서 읽을 수 없거나 판단할 근거가 없는 칸은 지어내지 말고 '확인 불가' 라고 적어.
C 오류 화면이 아니면 모든 칸에 'C 오류 화면이 아님' 이라고 적어.
과제 코드 전체를 대신 써 주지 말고, 고칠 줄만 알려 줘."""

# ★ (직접 작성) ③ 결과로 받을 칸 이름 : 설명 (3~5개)
FIELDS = {
    "오류 메시지": "화면에 보이는 첫 번째 오류 메시지 (화면 글자 그대로)",
    "위치": "파일 이름 · 줄 번호 (예: main.c 5번째 줄)",
    "뜻": "오류 메시지를 쉬운 한국어로 한 문장",
    "원인": "이 오류가 난 까닭 한 문장",
    "고치는 법": "고칠 줄과 고친 모습 한두 문장",
}

SCHEMA = {"type": "object", "properties": {name: {"type": "string", "description": text} for name, text in FIELDS.items()},
          "required": list(FIELDS)}
app = FastAPI(title=APP_TITLE, description=APP_DESCRIPTION)


class PhotoRequest(BaseModel):
    image_b64: str = Field(min_length=1, max_length=4_000_000, description="사진(JPEG)을 base64 로 바꾼 글자")


class Result(BaseModel):
    result: dict[str, str]
    tokens: int | None = None


def check_access(access_code):
    expected = os.environ.get("APP_ACCESS_CODE")
    if expected and access_code != expected:
        raise HTTPException(status_code=401, detail="접근 코드가 틀렸습니다 — 헤더 X-Access-Code 를 확인하세요")


def get_client():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="서버에 GEMINI_API_KEY 가 없습니다 — 환경 변수를 확인하세요")
    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=120_000, retry_options=types.HttpRetryOptions(http_status_codes=[500, 503])),
    )


@app.get("/")
def home():
    """화면이 제목 · 아이콘 · 소개 · 칸 이름을 가져가는 주소 (요청 없음)"""
    return {"name": APP_TITLE, "icon": APP_ICON, "description": APP_DESCRIPTION, "fields": list(FIELDS)}


@app.post("/analyze", response_model=Result)
def analyze(request: PhotoRequest, x_access_code: str | None = Header(default=None)):
    check_access(x_access_code)
    try:
        base64.b64decode(request.image_b64, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=422, detail="base64 글자가 아닙니다")
    client = get_client()
    try:
        reply = client.interactions.create(
            model=MODEL_NAME, store=False,
            input=[{"type": "text", "text": PROMPT}, {"type": "image", "data": request.image_b64, "mime_type": "image/jpeg"}],
            response_format={"type": "text", "mime_type": "application/json", "schema": SCHEMA},
        )
    except Exception as error:
        code = getattr(error, "status_code", None)
        raise HTTPException(status_code=429 if code == 429 else 502, detail=f"Gemini 요청 실패 (상태 번호 {code})")
    try:
        result = json.loads(reply.output_text)
    except json.JSONDecodeError:
        raise HTTPException(status_code=502, detail="답이 JSON 모양이 아닙니다 — 다시 보내 보세요")
    return Result(result={name: str(result.get(name, "")) for name in FIELDS}, tokens=reply.usage.total_tokens)
