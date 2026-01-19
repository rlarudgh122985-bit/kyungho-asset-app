import streamlit as st
from streamlit_gsheets import GSheetsConnection
import yfinance as yf
import pandas as pd
import plotly.express as px

# 1. 앱 설정 및 데이터 연결
st.set_page_config(layout="wide", page_title="경호&와이프 자산 관제탑")
conn = st.connection("gsheets", type=GSheetsConnection)

# 2. 데이터 불러오기 (구글 시트에서 실시간으로)
df = conn.read(worksheet="assets")

# 3. 실시간 가격 반영 로직
usd_krw = yf.Ticker("USDKRW=X").history(period="1d")['Close'].iloc[-1]

def get_live_val(row):
    ticker = str(row['티커'])
    qty = float(row['수량'])
    if ticker == "-": return qty # 고정 자금 (공제회 등)
    
    try:
        price = yf.Ticker(ticker).history(period="1d")['Close'].iloc[-1]
        if row['통화'] == "USD":
            return price * qty * usd_krw
        return price * qty
    except:
        return 0

# 평가금액 계산
df['평가금액'] = df.apply(get_live_val, axis=1)
total_val = df['평가금액'].sum()

# 4. 화면 구성 (아이패드 최적화)
st.title(f"🛰️ 경호&와이프 자산 Cockpit (환율: ₩{usd_krw:,.2f})")
st.metric("총 순자산", f"₩{total_val:,.0f}")

# (1) 데이터 관리 구역 (추가/수정/삭제)
with st.expander("🛠️ 자산 관리 (종목 추가 및 수정)"):
    # 직접 편집 가능한 테이블
    edited_df = st.data_editor(df[['카테고리', '종목명', '티커', '수량', '통화']], num_rows="dynamic")
    
    if st.button("💾 변경사항 구글 시트에 저장하기"):
        conn.update(worksheet="assets", data=edited_df)
        st.success("데이터가 안전하게 저장되었습니다!")
        st.rerun()

# (2) 실시간 데이터 분석 뷰
st.divider()
st.subheader("📋 실시간 자산 명세서")
df['비중(%)'] = (df['평가금액'] / total_val * 100).round(1)
st.dataframe(df[['카테고리', '종목명', '수량', '평가금액', '비중(%)']], use_container_width=True, hide_index=True)

# (3) 전략 비중 차트
col1, col2 = st.columns(2)
with col1:
    fig = px.pie(df, values='평가금액', names='카테고리', hole=0.4, title="40:30:30 전략 현황",
                 color_discrete_map={'① 핵심':'#3498db','② 위성':'#e67e22','③ 안전':'#2ecc71'})
    st.plotly_chart(fig, use_container_width=True)
