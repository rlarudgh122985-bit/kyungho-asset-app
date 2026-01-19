import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# 1. 설정 구간
SHEET_ID = "11MCEC3BwyEXWvcPht_qfB2rnKbcboxcv8ervEQjGg1o"
st.set_page_config(layout="wide", page_title="경호 자산 관제탑")

# 2. 데이터 로드 함수 (302 에러 우회 직통 방식)
@st.cache_data(ttl=60)
def load_data_direct(sheet_name):
    # 구글 시트를 CSV로 직접 내보내는 주소 (가장 안정적)
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
    try:
        df = pd.read_csv(url)
        df.columns = [col.strip() for col in df.columns] # 공백 제거
        return df
    except Exception as e:
        st.error(f"'{sheet_name}' 탭을 읽어오지 못했습니다: {e}")
        return pd.DataFrame()

# 3. 실시간 가격 로직
@st.cache_data(ttl=60)
def get_live_price(ticker):
    ticker = str(ticker).strip()
    if ticker == "-" or ticker == "nan" or not ticker: return 1.0
    try:
        data = yf.download(ticker, period="1d", progress=False)
        return float(data['Close'].iloc[-1]) if not data.empty else 0.0
    except: return 0.0

# --- 앱 실행 ---
try:
    assets_df = load_data_direct("assets")
    history_df = load_data_direct("history")

    if not assets_df.empty:
        # 환율 및 자산 계산
        usd_krw = get_live_price("USDKRW=X")
        if usd_krw <= 100: usd_krw = 1450.0

        def calc_val(row):
            t, q, unit = str(row['티커']).strip(), float(row['수량']), str(row['통화']).strip()
            if t == "-": return q
            p = get_live_price(t)
            return p * q * (usd_krw if unit == "USD" else 1.0)

        assets_df['평가금액'] = assets_df.apply(calc_val, axis=1)
        current_total = assets_df['평가금액'].sum()

        # --- 화면 구성 ---
        st.header(f"🛰️ 경호&와이프 자산 관제탑 (v1.9 Stable)")
        
        # 사이드바
        if st.sidebar.button("🔄 즉시 새로고침"):
            st.cache_data.clear()
            st.rerun()

        # 상단 요약
        c1, c2, c3 = st.columns(3)
        c1.metric("현재 총 자산", f"₩{current_total:,.0f}")
        c2.metric("실시간 환율", f"₩{usd_krw:,.2f}")
        c3.write(f"⏱️ {datetime.now().strftime('%H:%M:%S')} 업데이트")

        st.divider()

        # (1) 히스토리 그래프
        if not history_df.empty:
            st.subheader("📈 자산 성장 히스토리")
            history_df['날짜'] = pd.to_datetime(history_df['날짜'])
            history_df = history_df.sort_values('날짜')
            fig = px.line(history_df, x='날짜', y='총자산', markers=True, title="순자산 변화")
            st.plotly_chart(fig, use_container_width=True)

        # (2) 자산 기록 (History 저장)
        with st.expander("📝 현재 자산 기록하기"):
            st.info(f"계산된 총액: ₩{current_total:,.0f}")
            h_date = st.date_input("기준일", datetime.now())
            h_spend = st.number_input("이번 달 지출", value=0)
            
            if st.button("🚀 데이터 저장 실행"):
                try:
                    conn = st.connection("gsheets", type=GSheetsConnection)
                    new_row = pd.DataFrame([{"날짜": h_date.strftime("%Y-%m-%d"), "총자산": int(current_total), "지출": h_spend}])
                    updated_h = pd.concat([history_df, new_row], ignore_index=True)
                    conn.update(worksheet="history", data=updated_h)
                    st.success("기록 완료! 앱을 새로고침합니다.")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"저장 중 오류가 발생했습니다. 구글 시트 공유 권한(편집자)을 확인하세요: {e}")

        # (3) 상세 명세
        st.subheader("📋 자산 명세")
        assets_df['비중(%)'] = (assets_df['평가금액'] / current_total * 100).round(1)
        st.dataframe(assets_df[['카테고리', '종목명', '수량', '평가금액', '비중(%)']], use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"앱 가동 실패: {e}")
