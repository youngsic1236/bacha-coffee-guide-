# -*- coding: utf-8 -*-
"""
==========================================================================
 세력 매집 흔적 스크리너 (KOSPI / KOSDAQ 전 종목)
 - "거래량은 폭증했는데 주가는 거의 안 움직인" 종목을 찾아냅니다.
   (큰 손이 가격을 띄우지 않고 조용히 물량을 모을 때 나타나는 전형적인 흔적)
==========================================================================

[1] 설치 방법 (터미널 / 명령 프롬프트 / 아나콘다 프롬프트에서 1회만 실행)

    pip install finance-datareader pandas tqdm

    * tqdm 은 진행률 막대를 보여주는 라이브러리입니다. (없어도 동작은 합니다)
    * 파이썬 3.9 이상을 권장합니다.

[2] 실행 방법

    python accumulation_screener.py

    * 전 종목(약 2,500개)의 일봉을 내려받기 때문에 1~5분 정도 걸립니다.
    * 결과는 화면에 출력되고, 같은 폴더에 CSV 파일로도 저장됩니다.
    * 장중에 실행하면 '당일 거래량'이 아직 다 쌓이지 않은 값이므로,
      장 마감(15:30) 이후에 실행하는 것을 권장합니다.

[3] 스크리닝 조건 (두 조건을 '동시에' 충족)

    조건 1 (거래량 폭증) : 당일 거래량 >= 직전 20거래일 평균 거래량 x 3배
    조건 2 (주가 변동 제한): -3% <= 당일 등락률(전일 종가 대비) <= +3%

[4] 자동 제외 대상

    관리종목, 우선주, ETF, ETN, SPAC(스팩), 거래정지 종목, 코넥스 종목

※ 이 프로그램은 학습/참고용입니다. 투자 판단과 그 결과의 책임은 본인에게 있습니다.
"""

import time
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

import pandas as pd
import FinanceDataReader as fdr

warnings.filterwarnings("ignore")

# tqdm(진행률 막대)이 설치되어 있지 않아도 프로그램이 돌아가도록 처리
try:
    from tqdm import tqdm
except ImportError:  # tqdm 이 없으면 그냥 원래 반복자를 그대로 돌려줌
    def tqdm(iterable, **kwargs):
        return iterable


# ==========================================================================
# 설정값 (원하는 대로 숫자만 바꿔서 사용하세요)
# ==========================================================================
VOLUME_AVG_DAYS = 20        # 평균 거래량을 계산할 기간 (직전 20거래일 = 약 한 달)
VOLUME_MULTIPLE = 3.0       # 조건 1: 당일 거래량이 평균의 몇 배 이상인지 (3.0 = 300%)
PRICE_CHANGE_MIN = -3.0     # 조건 2: 당일 등락률 하한 (%)
PRICE_CHANGE_MAX = 3.0      # 조건 2: 당일 등락률 상한 (%)
MIN_AVG_VOLUME = 0          # (선택) 20일 평균 거래량이 너무 적은 '잡주' 제외용. 예: 10000
MAX_WORKERS = 8             # 동시에 데이터를 내려받을 개수 (너무 크면 서버가 차단할 수 있음)
PREFILTER_BY_TODAY_CHANGE = True  # True 면 '오늘 등락률'로 먼저 걸러서 다운로드 수를 줄임(속도 향상)
SAVE_CSV = True             # 결과를 CSV 파일로 저장할지 여부


# ==========================================================================
# 1단계: 스크리닝 대상 종목 목록 만들기 (불필요한 종목 필터링)
# ==========================================================================
def get_admin_codes():
    """관리종목 코드 목록을 가져옵니다. (KRX KIND 사이트)"""
    try:
        admin = fdr.StockListing("KRX-ADMINISTRATIVE")
        # 엑셀/HTML 에서 읽으면 앞자리 0 이 사라질 수 있으므로 6자리로 맞춰 줌
        return set(admin["Symbol"].astype(str).str.zfill(6))
    except Exception as e:
        print(f"  [경고] 관리종목 목록을 가져오지 못했습니다 ({e}).")
        print("         -> 소속부(Dept) 정보로만 관리종목을 걸러냅니다.")
        return set()


def get_target_stocks():
    """
    KOSPI + KOSDAQ 전체 종목 중, 스크리닝 대상이 되는 '보통주'만 남깁니다.
    반환: DataFrame (Code, Name, Market, Close, ChagesRatio, Volume ...)
    """
    print("[1/3] 전체 종목 목록을 불러오는 중...")
    listing = fdr.StockListing("KRX")  # KOSPI, KOSDAQ, KONEX 전체 (ETF/ETN 은 원래 미포함)
    total = len(listing)

    df = listing.copy()
    df["Code"] = df["Code"].astype(str).str.zfill(6)
    df["Name"] = df["Name"].astype(str)
    df["Dept"] = df["Dept"].fillna("").astype(str)

    # (1) 코넥스 제외 -> KOSPI, KOSDAQ 만 남김 (KOSDAQ GLOBAL 포함)
    df = df[df["Market"].isin(["KOSPI", "KOSDAQ", "KOSDAQ GLOBAL"])]

    # (2) 우선주 제외
    #     - 보통주 종목코드는 끝자리가 '0' 입니다. (예: 삼성전자 005930)
    #     - 우선주는 끝자리가 5, 7, 9, K, L ... (예: 삼성전자우 005935)
    #     - 이름이 '우', '우B', '우C', '(전환)' 으로 끝나는 경우도 함께 제외
    df = df[df["Code"].str[-1] == "0"]
    df = df[~df["Name"].str.contains(r"(우|우B|우C|\(전환\))$", regex=True)]

    # (3) SPAC(스팩) 제외 - 종목명에 '스팩' 또는 'SPAC' 이 들어감
    df = df[~df["Name"].str.contains("스팩|SPAC", case=False, regex=True)]

    # (4) ETF / ETN 제외
    #     - KRX 주식 목록에는 원래 ETF/ETN 이 없지만, 혹시 모를 경우를 대비해
    #       대표적인 운용사 브랜드/키워드가 들어간 종목명을 한 번 더 걸러냅니다.
    etf_etn_keywords = (
        "ETN|ETF|KODEX|TIGER|KBSTAR|RISE|ARIRANG|HANARO|KOSEF|ACE|SOL|PLUS|"
        "TIMEFOLIO|KIWOOM|WOORI|FOCUS|TREX|마이티|파워|히어로즈|BNK|에셋플러스"
    )
    is_etf_like = df["Name"].str.match(rf"^({etf_etn_keywords})\b", case=False)
    df = df[~is_etf_like]

    # (5) 관리종목 제외
    #     - 소속부(Dept)에 '관리' 가 표시된 종목 + KIND 관리종목 지정 목록
    admin_codes = get_admin_codes()
    df = df[~df["Dept"].str.contains("관리")]
    df = df[~df["Code"].isin(admin_codes)]

    # (6) 거래정지 종목 제외 (오늘 거래량이 0 인 종목)
    df = df[pd.to_numeric(df["Volume"], errors="coerce").fillna(0) > 0]

    df = df.reset_index(drop=True)
    print(f"      전체 {total:,}개 -> 필터링 후 대상 {len(df):,}개 "
          f"(관리종목 {len(admin_codes)}개 목록 반영)")
    return df


# ==========================================================================
# 2단계: 종목별 일봉 데이터를 받아서 조건 검사
# ==========================================================================
def check_stock(code, name, start_date):
    """
    한 종목의 최근 일봉을 받아 두 조건을 검사합니다.
    조건을 만족하면 결과 dict 를, 아니면 None 을 반환합니다.
    """
    # 네트워크 오류 대비: 최대 3번까지 재시도
    ohlcv = None
    for attempt in range(3):
        try:
            ohlcv = fdr.DataReader(code, start_date)
            break
        except Exception:
            time.sleep(1 + attempt)
    if ohlcv is None or ohlcv.empty:
        return None

    # 거래량 0 인 날(거래정지일)은 계산에서 제외
    ohlcv = ohlcv[ohlcv["Volume"] > 0]

    # 오늘 1일 + 직전 20일 = 최소 21거래일이 있어야 계산 가능 (신규 상장주 등은 제외)
    if len(ohlcv) < VOLUME_AVG_DAYS + 1:
        return None

    today = ohlcv.iloc[-1]                          # 가장 최근 거래일(=당일)
    prev_close = ohlcv["Close"].iloc[-2]            # 전일 종가
    past = ohlcv.iloc[-(VOLUME_AVG_DAYS + 1):-1]    # 당일을 '제외한' 직전 20거래일

    today_volume = float(today["Volume"])
    avg_volume = float(past["Volume"].mean())
    if avg_volume <= 0 or avg_volume < MIN_AVG_VOLUME or prev_close <= 0:
        return None

    volume_ratio = today_volume / avg_volume                       # 거래량 배수
    change_pct = (today["Close"] - prev_close) / prev_close * 100  # 당일 등락률(%)

    # ---- 핵심 조건 검사 (두 조건 동시 충족) ----
    cond1 = volume_ratio >= VOLUME_MULTIPLE                         # 조건 1: 거래량 폭증
    cond2 = PRICE_CHANGE_MIN <= change_pct <= PRICE_CHANGE_MAX     # 조건 2: 주가 변동 제한

    if cond1 and cond2:
        return {
            "종목코드": code,
            "종목명": name,
            "기준일": ohlcv.index[-1].strftime("%Y-%m-%d"),
            "현재가": int(today["Close"]),
            "당일등락률": round(change_pct, 2),
            "당일거래량": int(today_volume),
            "20일평균거래량": int(round(avg_volume)),
            "거래량배수": round(volume_ratio, 2),
        }
    return None


def run_screener():
    targets = get_target_stocks()

    # (속도 향상) 종목 목록에 이미 '오늘 등락률'이 들어 있으므로,
    # 조건 2 를 명백히 벗어난 종목은 일봉을 내려받지 않고 미리 건너뜁니다.
    # (최종 판정은 아래에서 일봉 데이터로 다시 정확하게 계산합니다)
    if PREFILTER_BY_TODAY_CHANGE and "ChagesRatio" in targets.columns:
        ratio = pd.to_numeric(targets["ChagesRatio"], errors="coerce")
        margin = 0.5  # 반올림 차이 등을 고려한 여유분
        keep = ratio.between(PRICE_CHANGE_MIN - margin, PRICE_CHANGE_MAX + margin) | ratio.isna()
        targets = targets[keep].reset_index(drop=True)
        print(f"      등락률 1차 필터 후 일봉 조회 대상 {len(targets):,}개")

    # 20거래일 + 여유분(공휴일, 거래정지 등)을 위해 약 60일 전부터 데이터 조회
    start_date = (datetime.today() - timedelta(days=60)).strftime("%Y-%m-%d")

    print(f"[2/3] 종목별 일봉 데이터 수집 및 조건 검사 중... (동시 {MAX_WORKERS}개)")
    results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [
            executor.submit(check_stock, row.Code, row.Name, start_date)
            for row in targets.itertuples()
        ]
        for future in tqdm(as_completed(futures), total=len(futures), ncols=80):
            res = future.result()
            if res is not None:
                results.append(res)

    # ----------------------------------------------------------------------
    # 3단계: 결과 정리 (거래량 배수 내림차순 정렬)
    # ----------------------------------------------------------------------
    print("[3/3] 결과 정리 중...")
    columns = ["종목코드", "종목명", "현재가", "당일등락률", "당일거래량", "20일평균거래량", "거래량배수"]
    if not results:
        print("\n조건을 만족하는 종목이 없습니다.")
        return pd.DataFrame(columns=columns)

    result_df = pd.DataFrame(results)

    # 대부분 종목은 같은 날짜가 '당일'이지만, 일부 종목의 데이터가 늦게 갱신된 경우를
    # 대비해 가장 최근 기준일의 종목만 남깁니다.
    latest_day = result_df["기준일"].max()
    result_df = result_df[result_df["기준일"] == latest_day]

    result_df = (
        result_df[columns]
        .sort_values("거래량배수", ascending=False)  # 거래량 배수 높은 순 (Descending)
        .reset_index(drop=True)
    )
    result_df.index = result_df.index + 1  # 순위를 1부터 표시

    print(f"\n기준일: {latest_day}  |  조건 만족 종목: {len(result_df)}개")
    print(f"(거래량 {VOLUME_MULTIPLE:g}배 이상 & 등락률 {PRICE_CHANGE_MIN:+g}% ~ {PRICE_CHANGE_MAX:+g}%)\n")

    if SAVE_CSV:
        filename = f"매집흔적_스크리닝_{latest_day}.csv"
        # utf-8-sig: 엑셀에서 열어도 한글이 깨지지 않음
        result_df.to_csv(filename, index_label="순위", encoding="utf-8-sig")
        print(f"결과가 '{filename}' 파일로 저장되었습니다.\n")

    return result_df


# ==========================================================================
# 프로그램 시작점
# ==========================================================================
if __name__ == "__main__":
    # 화면에서 표가 잘리지 않고 한눈에 보이도록 출력 옵션 설정
    pd.set_option("display.max_rows", 200)
    pd.set_option("display.width", 200)
    pd.set_option("display.unicode.east_asian_width", True)  # 한글 정렬 맞춤

    start = time.time()
    df = run_screener()
    if not df.empty:
        # 보기 좋게 천 단위 콤마 등 서식 적용
        print(df.to_string(formatters={
            "현재가": "{:,}".format,
            "당일등락률": "{:+.2f}%".format,
            "당일거래량": "{:,}".format,
            "20일평균거래량": "{:,}".format,
            "거래량배수": "{:.2f}배".format,
        }))
    print(f"\n총 소요 시간: {time.time() - start:.1f}초")
