import streamlit as st
from streamlit_gsheets import GSheetsConnection
import yfinance as yf
import pandas as pd
import plotly.express as px
from datetime import datetime

# 1. 페이지 설정
st.set_page_config(layout="wide", page_title="경호 자산 관제탑")

# 2. 구글 시트 연결
conn = st.connection("gsheets", type=GSheetsConnection)

# 3. 데이터 불러오기
assets_df = conn.read(worksheet="assets")
history_df = conn.read(worksheet="history")

# 4. 실시간 가격 반영 및 총자산 계산
@st.cache_data(ttl=300)
def get_price(ticker):
    if ticker == "-" or pd.isna(ticker): return 1.0
    try:
        p = yf.download(ticker, period="1d", progress=False)['Close'].iloc[-1]
        return float(p)
    except: return 0.0

usd_krw = get_price("USDKRW=X")
if usd_krw <= 1.0: usd_krw = 1450.0 # 환율 에러 방지

# 실시간 총자산 계산 (경호님이 원하신 기능)
def calc_total():
    temp_df = assets_df.copy()
    temp_df['평가금액'] = temp_df.apply(lambda r: get_price(str(r['티커']).strip()) * r['수량'] * (usd_krw if r['통화']=="USD" else 1.0) if str(r['티커']).strip() != "-" else r['수량'], axis=1)
    return temp_df['평가금액'].sum(), temp_df

current_total, final_assets = calc_total()

# --- 화면 구성 ---
st.header(f"🛰️ 경호&와이프 자산 관제탑")

col1, col2, col3 = st.columns(3)
col1.metric("현재 총 자산", f"₩{current_total:,.0f}")
col2.metric("실시간 환율", f"₩{usd_krw:,.2f}")
col3.write(f"**마지막 업데이트:** {datetime.now().strftime('%H:%M:%S')}")

st.divider()

# --- 자동 기록 섹션 ---
with st.expander("📝 이번 달 기록장 (자동 계산)", expanded=True):
    col_a, col_b = st.columns(2)
    record_date = col_a.date_input("기록 기준일", datetime.now())
    monthly_spend = col_b.number_input("이번 달 지출액(원)", value=0, step=10000)
    
    if st.button("🚀 현재 자산 실시간 데이터로 기록하기"):
        # 새로운 기록 데이터 생성
        new_record = pd.DataFrame([{
            "날짜": record_date.strftime("%Y-%m-%d"),
            "총자산": int(current_total),
            "지출": monthly_spend
        }])
        # 기존 기록에 합치기
        updated_history = pd.concat([history_df, new_record], ignore_index=True)
        # 구글 시트에 업데이트
        conn.update(worksheet="history", data=updated_history)
        st.success(f"✅ {record_date} 자산 ₩{current_total:,.0f} 기록 완료!")
        st.rerun()

# --- 자산 추이 그래프 ---
if history_df is not None and not history_df.empty:
    st.subheader("📈 자산 및 지출 히스토리")
    history_df['날짜'] = pd.to_datetime(history_df['날짜'])
    fig = px.line(history_df.sort_values('날짜'), x='날짜', y='총자산', markers=True, title="자산 성장 곡선")
    st.plotly_chart(fig, use_container_width=True)

# --- 자산 명세서 ---
st.subheader("📋 실시간 상세 명세")
final_assets['비중(%)'] = (final_assets['평가금액'] / current_total * 100).round(1)
st.dataframe(final_assets[['카테고리', '종목명', '수량', '평가금액', '비중(%)']], use_container_width=True, hide_index=True)
