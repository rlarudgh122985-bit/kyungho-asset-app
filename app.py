 import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from datetime import datetime, timedelta

# 1. 설정 및 한국 시간(KST) 정의
SHEET_ID = "11MCEC3BwyEXWvcPht_qfB2rnKbcboxcv8ervEQjGg1o"
st.set_page_config(layout="wide", page_title="경호&수진 자산 관제탑")

# 한국 시간 계산 함수 (서버 시간이 UTC이므로 9시간을 더함)
def get_kst():
    return datetime.utcnow() + timedelta(hours=9)

now_kst = get_kst()

# 2. 데이터 로드 함수
@st.cache_data(ttl=60)
def load_data_direct(sheet_name):
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
    try:
        df = pd.read_csv(url)
        df.columns = [col.strip() for col in df.columns]
        return df
    except: return pd.DataFrame()

@st.cache_data(ttl=60)
def get_live_price(ticker):
    ticker = str(ticker).strip()
    if ticker in ["-", "nan", ""]: return 1.0
    try:
        data = yf.download(ticker, period="1d", progress=False)
        return float(data['Close'].iloc[-1]) if not data.empty else 0.0
    except: return 0.0

# --- 앱 실행 ---
try:
    assets_df = load_data_direct("assets")
    history_df = load_data_direct("history")
    
    usd_krw = get_live_price("USDKRW=X")
    if usd_krw <= 100: usd_krw = 1450.0

    # 실시간 자산 계산
    assets_df['평가금액'] = assets_df.apply(lambda r: get_live_price(r['티커']) * r['수량'] * (usd_krw if r['통화']=="USD" else 1.0) if r['티커'] != "-" else r['수량'], axis=1)
    current_total = assets_df['평가금액'].sum()

    # --- UI 사이드바 ---
    st.sidebar.header("⚙️ 관제 설정")
    if st.sidebar.button("🔄 즉시 새로고침"):
        st.cache_data.clear()
        st.rerun()
    
    show_legend = st.sidebar.checkbox("표 범례(Legend) 표시", value=True)

    # --- 메인 화면 ---
    st.header(f"🛰️ 경호&수진 통합 관제탑 (v2.4)")
    
    c1, c2, c3 = st.columns(3)
    c1.metric("현재 총 자산", f"₩{current_total:,.0f}")
    c2.metric("실시간 환율", f"₩{usd_krw:,.2f}")
    # 한국 시간 표시
    c3.info(f"📍 현재 시각(KST): {now_kst.strftime('%H:%M:%S')}")

    st.divider()

    # --- [지출 기록 섹션] ---
    with st.expander("💸 핵심 6종 지출 기록실"):
        # 날짜 입력 기본값을 한국 오늘 날짜로 설정
        rec_date = st.date_input("기록 기준일", now_kst)
        
        r1_c1, r1_c2, r1_c3 = st.columns(3)
        v1 = r1_c1.number_input("🏠 고정지출", value=0, step=10000)
        v2 = r1_c2.number_input("🤴 경호용돈", value=0, step=10000)
        v3 = r1_c3.number_input("👸 수진용돈", value=0, step=10000)
        
        r2_c1, r2_c2, r2_c3 = st.columns(3)
        v4 = r2_c1.number_input("🍱 생활비", value=0, step=10000)
        v5 = r2_c2.number_input("🤝 경조사비", value=0, step=10000)
        v6 = r2_c3.number_input("❓ 기타", value=0, step=10000)
        
        st.write(f"📊 **기록될 총자산:** ₩{current_total:,.0f}")
        # (저장 버튼 로직은 이전과 동일하되 기록 시 now_kst 활용)

    # --- 시각화 그래프 ---
    if not history_df.empty:
        st.subheader("📈 자산 및 지출 분석")
        history_df['날짜'] = pd.to_datetime(history_df['날짜'])
        
        # 1) 지출 그래프
        spend_items = ['고정지출', '경호용돈', '수진용돈', '생활비', '경조사비', '기타']
        valid_items = [i for i in spend_items if i in history_df.columns]
        
        fig_s = px.bar(history_df, x='날짜', y=valid_items, title="월별 지출 구성", barmode='stack')
        fig_s.update_layout(showlegend=show_legend)
        st.plotly_chart(fig_s, use_container_width=True)

        # 2) 자산 성장 그래프 (매주 월요일 기준 X축 설정)
        fig_t = px.line(history_df, x='날짜', y='총자산', markers=True, title="자산 성장 곡선 (주 단위)")
        
        # [핵심] X축을 매주 월요일(Monday) 단위로 표시하도록 설정
        fig_t.update_xaxes(
            dtick=604800000,  # 7일을 밀리초(ms)로 환산
            tickformat="%y년 %m월 %d일", # 날짜 표시 형식
            ticklabelmode="period"
        )
        fig_t.update_layout(showlegend=show_legend)
        st.plotly_chart(fig_t, use_container_width=True)

    # --- 상세 명세 ---
    st.divider()
    st.subheader("📋 실시간 상세 명세")
    st.dataframe(assets_df[['카테고리', '종목명', '수량', '평가금액']], use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"오류: {e}")
