import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import time

# 1. 앱 설정
st.set_page_config(layout="wide", page_title="경호 자산 관제탑")

# 2. 구글 시트 데이터 로드 (캐시 적용 - 10분 동안 유지)
@st.cache_data(ttl=600)
def get_google_data(url):
    try:
        if "/d/" in url:
            sheet_id = url.split("/d/")[1].split("/")[0]
            csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
            df = pd.read_csv(csv_url)
            df.columns = df.columns.str.strip()
            return df
    except Exception as e:
        st.error(f"시트 로드 실패: {e}")
        return None

# 3. 실시간 가격 가져오기 (에러 방어 로직 추가)
@st.cache_data(ttl=300) # 가격은 5분마다 갱신
def fetch_price(ticker):
    if ticker == "-" or ticker == "nan" or not isinstance(ticker, str):
        return 1.0
    try:
        # 야후 파이낸스 요청 (에러 나면 루프 돌지 않게 단발성으로)
        data = yf.download(ticker, period="1d", interval="1m", progress=False)
        if not data.empty:
            return float(data['Close'].iloc[-1])
        return 0.0
    except Exception:
        # Rate Limit 걸리면 0을 반환해서 앱이 멈추지 않게 함
        return 0.0

# 4. 실행 로직
try:
    raw_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
    df = get_google_data(raw_url)
    
    if df is not None:
        # 환율 가져오기 (실패 시 기본값 1400원 설정)
        usd_krw = fetch_price("USDKRW=X")
        if usd_krw == 0: usd_krw = 1450.0 # 야후 차단 시 임시 환율
        
        # 전체 자산 평가
        processed = []
        for _, row in df.iterrows():
            ticker = str(row['티커']).strip()
            qty = float(row['수량'])
            unit = str(row['통화']).strip()
            
            # 실시간 가격 시도
            live_p = fetch_price(ticker)
            
            # 평가금액 계산
            if ticker == "-": # 고정 자금
                eval_krw = qty
            elif live_p > 0: # 실시간 성공
                eval_krw = live_p * qty * (usd_krw if unit == "USD" else 1.0)
            else: # 실시간 실패 시 (안내 메시지용)
                eval_krw = 0 # 일단 0으로 표기
            
            processed.append([row['카테고리'], row['종목명'], qty, live_p, eval_krw])
        
        res_df = pd.DataFrame(processed, columns=["카테고리", "종목명", "수량", "현재가", "평가금액"])
        total_val = res_df["평가금액"].sum()
        
        # 화면 출력
        st.header(f"🛰️ 경호&와이프 자산 관제탑")
        c1, c2 = st.columns(2)
        c1.metric("총 순자산", f"₩{total_val:,.0f}")
        c2.metric("실시간 환율(적용)", f"₩{usd_krw:,.2f}")
        
        if any(res_df["현재가"] == 0):
            st.warning("⚠️ 야후 파이낸스 접속량이 많아 일부 가격을 불러오지 못했습니다. 잠시 후 새로고침하세요.")

        st.dataframe(res_df, use_container_width=True, hide_index=True)
        
        # 차트
        fig = px.pie(res_df, values='평가금액', names='카테고리', hole=0.4,
                     color_discrete_map={'① 핵심':'#3498db','② 위성':'#e67e22','③ 안전':'#2ecc71'})
        st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.error(f"설정 확인 필요: {e}")
