"""
입력값 오류를 한글로 바꿔주기

FastAPI는 기본으로 "String should have at least 2 characters" 같은
영어를 돌려줌. 사용자가 볼 화면에 영어가 뜨면 안 되니 여기서 번역함
"""

from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from config import FIELD_LABELS
from korean import josa




async def korean_validation_error(request, exc: RequestValidationError):
    err = exc.errors()[0]          # 여러 개여도 첫 번째만 보여줌
    # loc 는 ("body", "username") 형태라 마지막이 칸 이름
    raw_field = str(err["loc"][-1])
    label = FIELD_LABELS.get(raw_field, raw_field)
    kind = err.get("type", "")
    ctx = err.get("ctx", {}) or {}

    if kind == "missing":
        msg = f"{josa(label, '을', '를')} 입력해주세요"
    elif kind == "string_too_short":
        msg = f"{josa(label, '은', '는')} {ctx.get('min_length')}자 이상이어야 합니다"
    elif kind == "string_too_long":
        msg = f"{josa(label, '은', '는')} {ctx.get('max_length')}자 이하여야 합니다"
    elif kind == "string_pattern_mismatch":
        if raw_field == "email":
            msg = "이메일 형식이 올바르지 않습니다"
        elif raw_field == "phone":
            msg = "휴대폰 번호는 숫자와 하이픈만 쓸 수 있습니다"
        else:
            msg = f"{label} 형식이 올바르지 않습니다"
    elif kind in ("greater_than_equal", "greater_than"):
        msg = f"{josa(label, '은', '는')} {ctx.get('ge', ctx.get('gt'))} 이상이어야 합니다"
    elif kind in ("less_than_equal", "less_than"):
        msg = f"{josa(label, '은', '는')} {ctx.get('le', ctx.get('lt'))} 이하여야 합니다"
    elif kind in ("int_parsing", "int_type", "float_parsing"):
        msg = f"{josa(label, '은', '는')} 숫자로 입력해주세요"
    elif kind == "json_invalid":
        msg = "요청 형식이 올바르지 않습니다"
    else:
        msg = f"{josa(label, '을', '를')} 다시 확인해주세요"

    # 화면 코드가 기대하는 형태 그대로 (detail 에 문자열 하나)
    return JSONResponse(status_code=422, content={"detail": msg})
