import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# 1. 설정
SHEET_ID = "11MCEC3BwyEXWvcPht_qfB2rnKbcboxcv8ervEQjGg1o"
st.set_page_config(layout="wide", page_title="경호&수진 자산 관제탑")

# 2. 데이터 로드 함수 (읽기 전용 직통 주소)
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

# --- 메인 실행 ---
try:
    assets_df = load_data_direct("assets")
    history_df = load_data_direct("history")
    
    usd_krw = get_live_price("USDKRW=X")
    if usd_krw <= 100: usd_krw = 1450.0

    # 실시간 자산 계산
    assets_df['평가금액'] = assets_df.apply(lambda r: get_live_price(r['티커']) * r['수량'] * (usd_krw if r['통화']=="USD" else 1.0) if r['티커'] != "-" else r['수량'], axis=1)
    current_total = assets_df['평가금액'].sum()

    st.header(f"🛰️ 경호&수진 통합 자산 관제탑 (v2.3)")
    
    # 상단 요약
    c1, c2, c3 = st.columns(3)
    c1.metric("현재 총 자산", f"₩{current_total:,.0f}")
    c2.metric("실시간 환율", f"₩{usd_krw:,.2f}")
    c3.success(f"관제탑 가동 중 ({datetime.now().strftime('%H:%M')})")

    st.divider()

    # --- [심플 지출 입력 섹션] ---
    with st.expander("💸 핵심 6종 지출 기록실", expanded=True):
        col_d, col_t = st.columns(2)
        rec_date = col_d.date_input("기록 기준일", datetime.now())
        col_t.info(f"기록될 총자산: ₩{current_total:,.0f}")
        
        st.write("### 💰 이번 달 지출 내역")
        
        # 3개 열로 배치 (아이패드 최적화)
        r1_c1, r1_c2, r1_c3 = st.columns(3)
        v1 = r1_c1.number_input("🏠 고정지출", value=0, step=10000)
        v2 = r1_c2.number_input("🤴 경호용돈", value=0, step=10000)
        v3 = r1_c3.number_input("👸 수진용돈", value=0, step=10000)
        
        r2_c1, r2_c2, r2_c3 = st.columns(3)
        v4 = r2_c1.number_input("🍱 생활비", value=0, step=10000)
        v5 = r2_c2.number_input("🤝 경조사비", value=0, step=10000)
        v6 = r2_c3.number_input("❓ 기타", value=0, step=10000)
        
        total_s = v1+v2+v3+v4+v5+v6
        st.write(f"📊 **이번 달 지출 합계:** ₩{total_s:,.0f}")
        
        if st.button("🚀 기록 저장 (History 탭)"):
            try:
                conn = st.connection("gsheets", type=GSheetsConnection)
                new_row = pd.DataFrame([{
                    "날짜": rec_date.strftime("%Y-%m-%d"),
                    "총자산": int(current_total),
                    "고정지출": v1, "경호용돈": v2, "수진용돈": v3, 
                    "생활비": v4, "경조사비": v5, "기타": v6
                }])
                updated_h = pd.concat([history_df, new_row], ignore_index=True)
                conn.update(worksheet="history", data=updated_h)
                st.success("기록 성공! 그래프를 업데이트합니다.")
                st.cache_data.clear()
                st.rerun()
            except:
                st.error("⚠️ 앱 저장 실패 (구글 보안 정책)")
                st.info("💡 아래 내용을 복사해서 시트 history 탭 맨 아래에 붙여넣으세요!")
                st.code(f"{rec_date.strftime('%Y-%m-%d')}\t{int(current_total)}\t{v1}\t{v2}\t{v3}\t{v4}\t{v5}\t{v6}")

    # --- 시각화 그래프 ---
    if not history_df.empty:
        st.subheader("📈 자산 및 지출 분석")
        history_df['날짜'] = pd.to_datetime(history_df['날짜'])
        
        # 지출 항목별 누적 막대 그래프
        spend_items = ['고정지출', '경호용돈', '수진용돈', '생활비', '경조사비', '기타']
        valid_items = [i for i in spend_items if i in history_df.columns]
        
        fig_s = px.bar(history_df, x='날짜', y=valid_items, title="월별 지출 구성 (6대 항목)", barmode='stack')
        st.plotly_chart(fig_s, use_container_width=True)

        fig_t = px.line(history_df, x='날짜', y='총자산', markers=True, title="우리 집 자산 성장 곡선")
        st.plotly_chart(fig_t, use_container_width=True)

    # --- 자산 명세서 ---
    st.divider()
    st.subheader("📋 실시간 자산 명세")
    st.dataframe(assets_df[['카테고리', '종목명', '수량', '평가금액']], use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"오류: {e}")
