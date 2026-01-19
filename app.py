import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from datetime import datetime, timedelta

# 1. 설정 및 한국 시간(KST) 정의
SHEET_ID = "11MCEC3BwyEXWvcPht_qfB2rnKbcboxcv8ervEQjGg1o"
st.set_page_config(layout="wide", page_title="경호&수진 자산 관제탑", page_icon="🛰️")

def get_kst():
    return datetime.utcnow() + timedelta(hours=9)

now_kst = get_kst()

# 2. 데이터 로드 및 컬럼명 자동 세척 (수량 에러 방지)
@st.cache_data(ttl=60)
def load_data_robust(sheet_name):
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
    try:
        df = pd.read_csv(url)
        # 컬럼명 앞뒤 공백 제거 및 문자열화 (수량 에러 해결 핵심)
        df.columns = [str(col).strip() for col in df.columns]
        df = df.dropna(how='all') 
        return df
    except:
        return pd.DataFrame()

@st.cache_data(ttl=60)
def get_market_data(ticker):
    try:
        data = yf.download(ticker, period="2d", progress=False)
        if not data.empty and len(data) >= 2:
            current = data['Close'].iloc[-1]
            prev = data['Close'].iloc[-2]
            return float(current), float(current - prev)
        return 0.0, 0.0
    except:
        return 0.0, 0.0

# --- 앱 가동 ---
try:
    assets_df = load_data_robust("assets")
    history_df = load_data_robust("history")

    # 3. 최상단 타이틀 (경호님 요청 반영)
    st.title("🛰️ 경호 & 수진 통합 자산 관제탑")
    st.caption(f"기준 시각(KST): {now_kst.strftime('%Y-%m-%d %H:%M:%S')} | 10년 경제적 자유 프로젝트")

    st.divider()

    # 4. 글로벌 시장 지표 (간지 섹션)
    indices = {"S&P 500": "^GSPC", "나스닥": "^IXIC", "코스피": "^KS11", "환율(USD/KRW)": "USDKRW=X", "금(Gold)": "GC=F"}
    m_cols = st.columns(len(indices))
    usd_krw = 1450.0
    for i, (name, ticker) in enumerate(indices.items()):
        p, d = get_market_data(ticker)
        if "환율" in name: usd_krw = p
        m_cols[i].metric(name, f"{p:,.1f}", delta=f"{d:,.1f}")

    st.divider()

    # 5. 실시간 자산 계산 (수량 기반)
    # [방어 코드] 수량 컬럼 존재 확인
    if '수량' not in assets_df.columns:
        st.error(f"⚠️ '수량' 컬럼을 찾을 수 없습니다. 현재 인식된 컬럼: {list(assets_df.columns)}")
        st.stop()
    
    assets_df['수량'] = pd.to_numeric(assets_df['수량'], errors='coerce').fillna(0)
    
    def calc_live_val(row):
        t, q, unit = str(row.get('티커', '-')).strip(), row['수량'], str(row.get('통화', 'KRW')).strip()
        if t == "-" or not t or t == "nan": return q
        p, _ = get_market_data(t)
        return p * q * (usd_krw if unit == "USD" else 1.0)

    assets_df['평가금액'] = assets_df.apply(calc_live_val, axis=1)
    raw_total = assets_df['평가금액'].sum()

    # --- [섹션 1: 지출 입력 및 순자산 계산] ---
    with st.expander("💸 오늘자 지출 입력 및 실시간 순자산 정산", expanded=True):
        st.write("### 1. 지출 내역")
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
        
        st.divider()
        m1, m2, m3 = st.columns(3)
        m1.metric("실시간 자산합계", f"₩{raw_total:,.0f}")
        m2.metric("오늘 총 지출", f"- ₩{total_exp:,.0f}")
        m3.metric("기록될 순자산(A-B)", f"₩{net_total:,.0f}")

        # 저장 기능 (에러 시 복사용 텍스트 제공)
        if st.button("🚀 순자산 데이터 저장"):
            try:
                from streamlit_gsheets import GSheetsConnection
                conn = st.connection("gsheets", type=GSheetsConnection)
                new_row = pd.DataFrame([{"날짜": rec_date.strftime("%Y-%m-%d"), "총자산": int(net_total), "고정지출": v1, "경호용돈": v2, "수진용돈": v3, "생활비": v4, "경조사비": v5, "기타": v6}])
                updated_h = pd.concat([history_df, new_row], ignore_index=True)
                conn.update(worksheet="history", data=updated_h)
                st.success("저장 성공!")
                st.cache_data.clear()
                st.rerun()
            except:
                st.code(f"{rec_date.strftime('%Y-%m-%d')}\t{int(net_total)}\t{v1}\t{v2}\t{v3}\t{v4}\t{v5}\t{v6}")

    st.divider()

    # --- [섹션 2: 시각화 리포트] ---
    col_pie, col_flow = st.columns([1, 1.2])
    
    with col_pie:
        st.subheader("📊 자산 성격별 비중")
        cat_pie = px.pie(assets_df.groupby('카테고리')['평가금액'].sum().reset_index(), 
                         values='평가금액', names='카테고리', hole=0.4)
        st.plotly_chart(cat_pie, use_container_width=True)
        
    with col_flow:
        if not history_df.empty:
            st.subheader("📈 자산 성장 곡선 (만원 단위)")
            history_df['날짜'] = pd.to_datetime(history_df['날짜'])
            history_df = history_df.sort_values('날짜')
            history_df['총자산_만원'] = (pd.to_numeric(history_df['총자산'], errors='coerce').fillna(0) / 10000).round(0)
            
            fig_t = px.line(history_df, x='날짜', y='총자산_만원', markers=True)
            fig_t.update_xaxes(type='date', tickformat="%m/%d")
            fig_t.update_yaxes(ticksuffix="만")
            st.plotly_chart(fig_t, use_container_width=True)

    # --- [섹션 3: 자산 명세서] ---
    st.subheader("📋 실시간 상세 명세")
    assets_df['비중(%)'] = (assets_df['평가금액'] / raw_total * 100).round(1)
    st.dataframe(assets_df[['카테고리', '종목명', '수량', '평가금액', '비중(%)']], use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"오류 발생: {e}")
