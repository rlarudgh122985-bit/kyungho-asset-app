import streamlit as st
from streamlit_gsheets import GSheetsConnection
import yfinance as yf
import pandas as pd
import plotly.express as px
from datetime import datetime

# 1. 페이지 설정 및 연결
st.set_page_config(layout="wide", page_title="경호&와이프 자산 관제탑")
conn = st.connection("gsheets", type=GSheetsConnection)

# 2. 데이터 불러오기 (탭 이름으로 직접 접근)
@st.cache_data(ttl=60)
def get_data():
    # 첫 번째 시트(assets)와 두 번째 시트(history)를 이름으로 읽어옵니다.
    assets = conn.read(worksheet="assets", ttl=60)
    try:
        history = conn.read(worksheet="history", ttl=60)
    except:
        history = pd.DataFrame(columns=["날짜", "총자산", "지출"])
    return assets, history

assets_df, history_df = get_data()

# 3. 실시간 가격 및 환율 계산
@st.cache_data(ttl=60)
def fetch_price(ticker):
    ticker = str(ticker).strip()
    if ticker == "-" or ticker == "nan": return 1.0
    try:
        data = yf.download(ticker, period="1d", progress=False)
        return float(data['Close'].iloc[-1]) if not data.empty else 0.0
    except: return 0.0

usd_krw = fetch_price("USDKRW=X")
if usd_krw <= 100: usd_krw = 1450.0 # 환율 에러 시 기본값

# 실시간 총자산 계산
def calculate_assets(df):
    df['평가금액'] = df.apply(lambda r: fetch_price(r['티커']) * r['수량'] * (usd_krw if r['통화']=="USD" else 1.0) if str(r['티커']).strip() != "-" else r['수량'], axis=1)
    return df['평가금액'].sum(), df

current_total, final_assets_df = calculate_assets(assets_df)

# --- 화면 구성 ---
st.header(f"🛰️ 경호&와이프 자산 관제탑 (v1.8)")

# 사이드바: 새로고침 버튼
if st.sidebar.button("🔄 시세 즉시 새로고침"):
    st.cache_data.clear()
    st.rerun()

# 상단 요약 대시보드
c1, c2, c3 = st.columns(3)
c1.metric("현재 실시간 총자산", f"₩{current_total:,.0f}")
c2.metric("현재 적용 환율", f"₩{usd_krw:,.2f}")
c3.write(f"⏱️ **조회 시간:** {datetime.now().strftime('%H:%M:%S')}")

st.divider()

# --- 자산 추이 그래프 ---
if not history_df.empty:
    st.subheader("📈 자산 성장 및 지출 기록")
    history_df['날짜'] = pd.to_datetime(history_df['날짜'])
    history_df = history_df.sort_values('날짜')
    
    # 자산 성장 선 그래프
    fig_line = px.line(history_df, x='날짜', y='총자산', markers=True, title="우리 집 자산 성장 곡선")
    st.plotly_chart(fig_line, use_container_width=True)
    
    # 지출 막대 그래프
    fig_bar = px.bar(history_df, x='날짜', y='지출', title="월별 지출 추이", color_discrete_sequence=['#FF4B4B'])
    st.plotly_chart(fig_bar, use_container_width=True)

# --- 자동 기록 기능 (경호님 요청!) ---
with st.expander("📝 이번 달 데이터 기록실 (History 저장)", expanded=True):
    col_a, col_b = st.columns(2)
    record_date = col_a.date_input("기록 기준일", datetime.now())
    monthly_spend = col_b.number_input("이번 달 총 지출(원)", value=0, step=10000)
    
    st.write(f"👉 **저장될 내용:** {record_date} | 자산: ₩{current_total:,.0f} | 지출: ₩{monthly_spend:,.0f}")
    
    if st.button("🚀 위 데이터를 History 탭에 저장하기"):
        # 새로운 기록 생성
        new_row = pd.DataFrame([{
            "날짜": record_date.strftime("%Y-%m-%d"),
            "총자산": int(current_total),
            "지출": monthly_spend
        }])
        # 기존 데이터와 합치기
        updated_history = pd.concat([history_df, new_row], ignore_index=True)
        # 구글 시트 history 탭에 업데이트
        conn.update(worksheet="history", data=updated_history)
        st.success("✅ 구글 시트에 안전하게 기록되었습니다!")
        st.cache_data.clear()
        st.rerun()

# --- 상세 자산 리스트 ---
st.divider()
st.subheader("📋 실시간 자산 명세서")
final_assets_df['비중(%)'] = (final_assets_df['평가금액'] / current_total * 100).round(1)
st.dataframe(final_assets_df[['카테고리', '종목명', '티커', '수량', '평가금액', '비중(%)']], 
             use_container_width=True, hide_index=True)
