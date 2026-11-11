# 📋 main.py · 과제 — 나만의 AI API
# ============================================================
# 13주차 오늘의 과제 · 나만의 AI API (main.py)
# ------------------------------------------------------------
# · 키는 서버 환경 변수 GEMINI_API_KEY 로만 읽음 (Vercel → Settings → Environment Variables)
# · 접근 코드는 환경 변수 APP_ACCESS_CODE — 부르는 쪽은 헤더 X-Access-Code 에 같은 값을 넣음
#   ★ 이 파일 · GitHub 저장소에 키와 접근 코드를 절대 적지 않음
# · POST /ask 한 번에 Gemini 요청 1번 (무료 한도 분당 15회)
# ============================================================
import os
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

MODEL_NAME = "gemini-3.5-flash-lite"

# ① API 이름 · 한 줄 소개
APP_TITLE = "C 오류 해설 API"
APP_DESCRIPTION = "C 언어를 처음 배우는 대학생에게 컴파일 오류 · 실행 오류의 뜻과 고치는 법을 알려 주는 AI API"

# ② 시스템 프롬프트 — 설계표 여섯 칸 (이름 · 역할 / 말투 / 할 일 / 하지 않을 일 / 모를 때 / 개인정보)
#    ※ {tone} 외에는 중괄호를 쓰지 않음 (format 이 오류를 냄)
SYSTEM_PROMPT = """너는 'C오류봇'이야. C 언어를 처음 배우는 대학생에게 컴파일 오류와 실행 오류를 풀이해 주는 도우미야.
규칙 1. {tone} 말투로 4문장 이내로 답한다.
규칙 2. 오류 메시지의 뜻 · 흔한 원인 · 고치는 방법을 순서대로 알려 준다.
규칙 3. C 언어 · 프로그래밍과 관련 없는 질문에는 '저는 C 오류 도우미라서 그 질문에는 답하기 어려워요.' 라고 답한다. 과제 코드를 통째로 대신 써 주지 않는다.
규칙 4. 코드 일부만 보고는 원인을 알 수 없으면 지어내지 말고, 오류 메시지 전체와 해당 줄을 함께 보내 달라고 안내한다.
규칙 5. 이름 · 학번 · 전화번호 같은 개인정보를 묻지 않는다."""

# ③ 예시 질문 3개 (GET /examples 가 돌려줌)
EXAMPLE_QUESTIONS = [
    "segmentation fault 가 뭐야?",
    "expected ';' before 'return' 오류는 왜 나와?",
    "scanf 에서 & 를 빼면 왜 안 돼?",
]

app = FastAPI(title=APP_TITLE, description=APP_DESCRIPTION)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=300, description="질문")
    tone: str = Field(default="친근한 존댓말", max_length=20, description="답의 말투")


class AskReply(BaseModel):
    question: str
    answer: str
    tokens: int | None = None


def check_access(access_code):
    """APP_ACCESS_CODE 가 정해져 있으면, 헤더의 접근 코드가 같아야만 통과"""
    expected = os.environ.get("APP_ACCESS_CODE")
    if expected and access_code != expected:
        raise HTTPException(status_code=401, detail="접근 코드가 틀렸습니다 — 헤더 X-Access-Code 를 확인하세요")


def get_client():
    """키는 서버의 환경 변수 GEMINI_API_KEY 에서 읽음"""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="서버에 GEMINI_API_KEY 가 없습니다 — 환경 변수를 확인하세요")
    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=60_000, retry_options=types.HttpRetryOptions(http_status_codes=[500, 503])),
    )


@app.get("/")
def home():
    return {"name": APP_TITLE, "description": APP_DESCRIPTION, "how_to_use": "POST /ask 에 {\"question\": \"…\"} 를 보내세요. 자세한 사용법은 /docs"}


@app.get("/examples")
def examples():
    return {"examples": EXAMPLE_QUESTIONS}


@app.post("/ask", response_model=AskReply)
def ask(request: AskRequest, x_access_code: str | None = Header(default=None)):
    check_access(x_access_code)
    client = get_client()
    try:
        reply = client.interactions.create(
            model=MODEL_NAME, store=False,
            system_instruction=SYSTEM_PROMPT.format(tone=request.tone),
            input=request.question,
        )
    except Exception as error:
        code = getattr(error, "status_code", None)
        if code == 429:
            raise HTTPException(status_code=429, detail="Gemini 무료 한도를 넘었습니다 — 1분 뒤 다시 요청하세요")
        raise HTTPException(status_code=502, detail=f"Gemini 요청 실패 (상태 번호 {code})")
    return AskReply(question=request.question, answer=reply.output_text, tokens=reply.usage.total_tokens)
