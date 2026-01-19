import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from datetime import datetime, timedelta

# 1. 설정 및 한국 시간(KST)
SHEET_ID = "11MCEC3BwyEXWvcPht_qfB2rnKbcboxcv8ervEQjGg1o"
st.set_page_config(layout="wide", page_title="경호&수진 자산 관제탑", page_icon="🛰️")

def get_kst():
    return datetime.utcnow() + timedelta(hours=9)
now_kst = get_kst()

# 2. 초강력 데이터 로드 함수 (이름 대신 위치로 매칭)
@st.cache_data(ttl=60)
def load_data_ultimate(sheet_name):
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&sheet={sheet_name}"
    try:
        df = pd.read_csv(url)
        # 1. 컬럼명 청소
        df.columns = [str(col).strip() for col in df.columns]
        
        # 2. history 탭일 경우 강제 매칭
        if sheet_name == "history" and not df.empty:
            # 첫 번째 컬럼을 무조건 '날짜'로, 두 번째를 '총자산'으로 강제 지정
            new_cols = list(df.columns)
            new_cols[0] = '날짜'
            new_cols[1] = '총자산'
            df.columns = new_cols
            
        return df.dropna(how='all')
    except Exception as e:
        return pd.DataFrame()

@st.cache_data(ttl=60)
def get_market_data(ticker):
    try:
        data = yf.download(ticker, period="2d", progress=False)
        if not data.empty and len(data) >= 2:
            curr = data['Close'].iloc[-1]
            prev = data['Close'].iloc[-2]
            return float(curr), float(curr - prev)
        return 0.0, 0.0
    except: return 0.0, 0.0

# --- 앱 실행 ---
try:
    assets_df = load_data_ultimate("assets")
    history_df = load_data_ultimate("history")

    # 타이틀 및 지표
    st.title("🛰️ 경호 & 수진 통합 자산 관제탑")
    st.caption(f"📍 KST: {now_kst.strftime('%Y-%m-%d %H:%M:%S')} | v3.6 위치 기반 매칭 시스템")

    indices = {"S&P 500": "^GSPC", "나스닥": "^IXIC", "코스피": "^KS11", "환율": "USDKRW=X", "금": "GC=F"}
    m_cols = st.columns(len(indices))
    usd_krw = 1450.0
    for i, (name, ticker) in enumerate(indices.items()):
        p, d = get_market_data(ticker)
        if "환율" in name: usd_krw = p
        m_cols[i].metric(name, f"{p:,.1f}", delta=f"{d:,.1f}")

    st.divider()

    # 실시간 자산 계산
    if '수량' in assets_df.columns:
        assets_df['수량'] = pd.to_numeric(assets_df['수량'], errors='coerce').fillna(0)
        def calc_val(row):
            t, q, unit = str(row.get('티커', '-')).strip(), row['수량'], str(row.get('통화', 'KRW')).strip()
            if t == "-" or not t or t == "nan": return q
            p, _ = get_market_data(t)
            return p * q * (usd_krw if unit == "USD" else 1.0)
        assets_df['평가금액'] = assets_df.apply(calc_val, axis=1)
        raw_total = assets_df['평가금액'].sum()
    else:
        st.error("⚠️ 'assets' 시트 1행에 '수량' 컬럼이 보이지 않습니다.")
        st.stop()

    # 지출 입력 및 정산
    with st.expander("💸 오늘자 지출 입력 및 순자산 기록", expanded=True):
        e_c1, e_c2, e_c3 = st.columns(3)
        v1 = e_c1.number_input("🏠 고정지출", value=0)
        v2 = e_c2.number_input("🤴 경호용돈", value=0)
        v3 = e_c3.number_input("👸 수진용돈", value=0)
        v4 = e_c1.number_input("🍱 생활비", value=0)
        v5 = e_c2.number_input("🤝 경조사비", value=0)
        v6 = e_c3.number_input("❓ 기타", value=0)
        
        total_exp = v1+v2+v3+v4+v5+v6
        net_total = raw_total - total_exp
        rec_date = st.date_input("기록 날짜", now_kst)
        
        m1, m2, m3 = st.columns(3)
        m1.metric("실시간 자산합계", f"₩{raw_total:,.0f}")
        m2.metric("오늘 총 지출", f"- ₩{total_exp:,.0f}")
        m3.metric("최종 순자산", f"₩{net_total:,.0f}")

        if st.button("🚀 데이터 저장"):
            try:
                from streamlit_gsheets import GSheetsConnection
                conn = st.connection("gsheets", type=GSheetsConnection)
                # 시트의 컬럼 순서에 맞춰서 데이터를 생성합니다.
                new_row = pd.DataFrame([[rec_date.strftime("%Y-%m-%d"), int(net_total), v1, v2, v3, v4, v5, v6]], 
                                       columns=history_df.columns[:8])
                updated_h = pd.concat([history_df, new_row], ignore_index=True)
                conn.update(worksheet="history", data=updated_h)
                st.success("저장 완료!")
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.info("💡 수동 입력용:")
                st.code(f"{rec_date.strftime('%Y-%m-%d')}\t{int(net_total)}\t{v1}\t{v2}\t{v3}\t{v4}\t{v5}\t{v6}")

    # 그래프 시각화
    if not history_df.empty:
        st.divider()
        st.subheader("📈 순자산 성장 히스토리")
        # 날짜 형식 강제 변환
        history_df['날짜'] = pd.to_datetime(history_df['날짜'], errors='coerce')
        history_df = history_df.dropna(subset=['날짜']).sort_values('날짜')
        
        history_df['총자산_만원'] = pd.to_numeric(history_df['총자산'], errors='coerce').fillna(0) / 10000
        
        fig_t = px.line(history_df, x='날짜', y='총자산_만원', markers=True, title="자산 성장 곡선 (만원)")
        fig_t.update_yaxes(tickformat=",d", ticksuffix="만")
        st.plotly_chart(fig_t, use_container_width=True)
    else:
        st.info("데이터가 아직 없습니다. 첫 기록을 저장해주세요.")

    # 상세 명세
    st.divider()
    col_p, col_d = st.columns([1, 1.2])
    with col_p:
        st.plotly_chart(px.pie(assets_df.groupby('카테고리')['평가금액'].sum().reset_index(), 
                               values='평가금액', names='카테고리', hole=0.4, title="자산 비중"), use_container_width=True)
    with col_d:
        assets_df['비중(%)'] = (assets_df['평가금액'] / raw_total * 100).round(1)
        st.dataframe(assets_df[['카테고리', '종목명', '수량', '평가금액', '비중(%)']], use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"🚨 시스템 진단 모드: {e}")
    if not history_df.empty:
        st.write("현재 인식된 history 컬럼 목록:", list(history_df.columns))
