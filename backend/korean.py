"""
한글 다루기 도구

검색·추천에서 씀. 한글 한 글자는 첫소리·가운뎃소리·끝소리 세 조각으로
이뤄져 있어서, 그걸 풀어내면 오타나 초성으로도 낱말을 찾을 수 있음
"""



# ---------------------------------------------------------------
# 한글 다루기 도구 (검색·추천에서 씀)
#
# CHO/JUNG/JONG = 한글 한 글자를 이루는 세 조각.
# "강" = ㄱ(첫소리) + ㅏ(가운뎃소리) + ㅇ(끝소리)
# ---------------------------------------------------------------
CHO = list("ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ")           # 첫소리 19개


JUNG = list("ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ")      # 가운뎃소리 21개


JONG = list(" ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ")  # 끝소리 28개




def to_jamo(text: str) -> str:
    """한글을 자모로 풀어씀. "강" → "ㄱㅏㅇ"
    오타 보정에 씀. 글자로 비교하면 "애어"와 "에어"가 하나도 안 겹치지만
    자모로 풀면 대부분 겹쳐서 비슷하다는 걸 알 수 있음"""
    out = []
    for ch in text:
        code = ord(ch)
        # 0xAC00(가) ~ 0xD7A3(힣) 이 완성된 한글 글자의 범위
        if 0xAC00 <= code <= 0xD7A3:
            i = code - 0xAC00
            out.append(CHO[i // 588])          # 588 = 21 * 28
            out.append(JUNG[(i % 588) // 28])
            jong = JONG[i % 28]
            if jong != " ":
                out.append(jong)               # 받침이 있을 때만
        else:
            out.append(ch)                     # 한글이 아니면 그대로
    return "".join(out)




def to_chosung(text: str) -> str:
    """첫소리만 뽑아냄. "에어프라이어" → "ㅇㅇㅍㄹㅇㅇ" """
    out = []
    for ch in text:
        code = ord(ch)
        if 0xAC00 <= code <= 0xD7A3:
            out.append(CHO[(code - 0xAC00) // 588])
        else:
            out.append(ch)
    return "".join(out)




def is_chosung_only(text: str) -> bool:
    """자음 낱자만으로 이뤄졌는지. "ㅇㅇㅍ" 같은 줄임 입력을 가려냄"""
    return bool(text) and all("\u3131" <= ch <= "\u314e" for ch in text)




def has_batchim(word: str) -> bool:
    """마지막 글자에 받침이 있는지. 조사를 고르는 데 씀"""
    if not word:
        return False
    code = ord(word[-1])
    if not (0xAC00 <= code <= 0xD7A3):
        return False
    return (code - 0xAC00) % 28 != 0




def josa(word: str, with_batchim: str, without: str) -> str:
    """받침에 맞는 조사를 붙여줌. 아이디+를 / 닉네임+을"""
    return word + (with_batchim if has_batchim(word) else without)
