import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from datetime import datetime, timedelta

# 1. 설정 및 한국 시간(KST) 정의
SHEET_ID = "11MCEC3BwyEXWvcPht_qfB2rnKbcboxcv8ervEQjGg1o"
st.set_page_config(layout="wide", page_title="경호&수진 자산 관제탑")

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
    show_legend = st.sidebar.checkbox("범례(Legend) 표시", value=True)

    # --- 메인 화면 ---
    st.header(f"🛰️ 경호&수진 통합 관제탑 (v2.5)")
    
    c1, c2, c3 = st.columns(3)
    c1.metric("현재 총 자산", f"₩{current_total:,.0f}")
    c2.metric("실시간 환율", f"₩{usd_krw:,.2f}")
    c3.info(f"📍 현재 시각(KST): {now_kst.strftime('%H:%M:%S')}")

    st.divider()

    # --- [상단 시각화: 포트폴리오 비율] ---
    st.subheader("📊 자산 포트폴리오 구성 (실시간)")
    col_pie, col_table = st.columns([1, 1])
    
    with col_pie:
        # 카테고리별 합계 계산
        cat_summary = assets_df.groupby('카테고리')['평가금액'].sum().reset_index()
        fig_pie = px.pie(cat_summary, values='평가금액', names='카테고리', 
                         hole=0.4, title="핵심/위성/안전 비중",
                         color_discrete_map={'① 핵심':'#1f77b4','② 위성':'#ff7f0e','③ 안전':'#2ca02c'})
        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_table:
        # 비중 표 표시
        assets_df['비중(%)'] = (assets_df['평가금액'] / current_total * 100).round(1)
        st.write("**실시간 자산 명세서**")
        st.dataframe(assets_df[['카테고리', '종목명', '수량', '평가금액', '비중(%)']], use_container_width=True, hide_index=True)

    st.divider()

    # --- [하단 시각화: 추이 분석] ---
    if not history_df.empty:
        st.subheader("📈 자산 성장 및 지출 분석")
        history_df['날짜'] = pd.to_datetime(history_df['날짜'])
        
        # 1) 자산 성장 그래프 (Y축 만원 단위 변환)
        history_df['총자산_만원'] = history_df['총자산'] / 10000
        fig_t = px.line(history_df, x='날짜', y='총자산_만원', markers=True, title="순자산 성장 곡선 (주 단위)")
        
        # X축 설정 (월요일 기준)
        fig_t.update_xaxes(dtick=604800000, tickformat="%y년 %m월 %d일")
        # Y축 라벨 설정
        fig_t.update_yaxes(title="자산액 (단위: 만원)")
        fig_t.update_layout(showlegend=show_legend)
        st.plotly_chart(fig_t, use_container_width=True)

        # 2) 지출 그래프
        spend_items = ['고정지출', '경호용돈', '수진용돈', '생활비', '경조사비', '기타']
        valid_items = [i for i in spend_items if i in history_df.columns]
        fig_s = px.bar(history_df, x='날짜', y=valid_items, title="월별 지출 구성", barmode='stack')
        fig_s.update_layout(showlegend=show_legend)
        st.plotly_chart(fig_s, use_container_width=True)

    # --- 지출 기록 섹션 (하단으로 이동) ---
    with st.expander("💸 이번 달 지출 데이터 기록하기"):
        rec_date = st.date_input("기록 기준일", now_kst)
        r1, r2, r3 = st.columns(3)
        v1 = r1.number_input("🏠 고정지출", value=0)
        v2 = r2.number_input("🤴 경호용돈", value=0)
        v3 = r3.number_input("👸 수진용돈", value=0)
        v4 = r1.number_input("🍱 생활비", value=0)
        v5 = r2.number_input("🤝 경조사비", value=0)
        v6 = r3.number_input("❓ 기타", value=0)
        # (저장 로직은 v2.3과 동일)

except Exception as e:
    st.error(f"오류: {e}")
