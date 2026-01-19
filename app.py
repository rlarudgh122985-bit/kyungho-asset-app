import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from datetime import datetime, timedelta

# 1. 설정 및 한국 시간(KST) 정의
SHEET_ID = "11MCEC3BwyEXWvcPht_qfB2rnKbcboxcv8ervEQjGg1o"
st.set_page_config(layout="wide", page_title="경호&수진 자산 관제탑", page_icon="📈")

def get_kst():
    return datetime.utcnow() + timedelta(hours=9)

now_kst = get_kst()

# 2. 데이터 로드 및 정제 (에러 방지 강화)
@st.cache_data(ttl=60)
def load_data_direct(sheet_name):
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
    try:
        df = pd.read_csv(url)
        df.columns = [col.strip() for col in df.columns]
        # 날짜가 비어있는 행 제거
        df = df.dropna(subset=['날짜'])
        return df
    except:
        return pd.DataFrame()

# 지표 및 가격 로드 함수
@st.cache_data(ttl=60)
def get_market_data(ticker):
    try:
        data = yf.download(ticker, period="2d", progress=False)
        if len(data) >= 2:
            current = data['Close'].iloc[-1]
            prev = data['Close'].iloc[-2]
            delta = current - prev
            return float(current), float(delta)
        elif len(data) == 1:
            return float(data['Close'].iloc[-1]), 0.0
        return 0.0, 0.0
    except:
        return 0.0, 0.0

# --- 시장 지표 수집 ---
indices = {
    "S&P 500": "^GSPC",
    "나스닥": "^IXIC",
    "코스피": "^KS11",
    "환율(USD/KRW)": "USDKRW=X",
    "금(Gold)": "GC=F"
}

# --- 앱 가동 ---
try:
    assets_df = load_data_direct("assets")
    history_df = load_data_direct("history")
    
    # 3. 상단 글로벌 마켓 지표 (간지 포인트)
    st.markdown(f"### 🌏 Global Market Overview <small>(KST {now_kst.strftime('%H:%M:%S')})</small>", unsafe_allow_html=True)
    m_cols = st.columns(len(indices))
    
    usd_krw = 1450.0 # 기본값
    for i, (name, ticker) in enumerate(indices.items()):
        price, delta = get_market_data(ticker)
        if name == "환율(USD/KRW)": usd_krw = price
        
        # 지표별 포맷팅
        if "환율" in name or "금" in name:
            fmt = f"₩{price:,.1f}" if "환율" in name else f"${price:,.1f}"
        else:
            fmt = f"{price:,.2f}"
            
        m_cols[i].metric(name, fmt, delta=f"{delta:,.2f}")

    st.divider()

    # 4. 자산 계산 로직
    # [에러 방지] 비어있는 값을 미리 0으로 채움
    assets_df['수량'] = pd.to_numeric(assets_df['수량'], errors='coerce').fillna(0)
    
    def calc_live_val(row):
        t = str(row['티커']).strip()
        q = row['수량']
        unit = str(row['통화']).strip()
        if t == "-" or not t: return q
        p, _ = get_market_data(t)
        return p * q * (usd_krw if unit == "USD" else 1.0)

    assets_df['평가금액'] = assets_df.apply(calc_live_val, axis=1)
    current_total = assets_df['평가금액'].sum()

    # --- 실시간 자산 요약 ---
    st.subheader("💰 실시간 자산 현황")
    c1, c2 = st.columns([1, 1.2])
    
    with c1:
        cat_summary = assets_df.groupby('카테고리')['평가금액'].sum().reset_index()
        fig_pie = px.pie(cat_summary, values='평가금액', names='카테고리', hole=0.4, 
                         color_discrete_sequence=px.colors.qualitative.Pastel)
        fig_pie.update_layout(margin=dict(t=0, b=0, l=0, r=0))
        st.plotly_chart(fig_pie, use_container_width=True)
        
    with c2:
        assets_df['비중(%)'] = (assets_df['평가금액'] / current_total * 100).round(1)
        st.metric("현재 순자산 합계", f"₩{current_total:,.0f}")
        st.dataframe(assets_df[['카테고리', '종목명', '수량', '평가금액', '비중(%)']], use_container_width=True, hide_index=True)

    st.divider()

    # --- [섹션 2: 자산 성장 추이] ---
    if not history_df.empty:
        st.subheader("📈 순자산 성장 히스토리")
        # [에러 방지] 모든 숫자 컬럼을 안전하게 변환
        num_cols = ['총자산', '고정지출', '경호용돈', '수진용돈', '생활비', '경조사비', '기타']
        for col in num_cols:
            if col in history_df.columns:
                history_df[col] = pd.to_numeric(history_df[col], errors='coerce').fillna(0)
        
        history_df['날짜'] = pd.to_datetime(history_df['날짜'])
        history_df = history_df.sort_values('날짜')
        history_df['총자산_만원'] = (history_df['총자산'] / 10000).round(0)
        
        fig_t = px.line(history_df, x='날짜', y='총자산_만원', markers=True, title="기록일 기준 순자산 성장 (만원)")
        fig_t.update_xaxes(type='date', tickformat="%m/%d")
        fig_t.update_yaxes(ticksuffix="만")
        st.plotly_chart(fig_t, use_container_width=True)

        # 지출 구성
        spend_items = ['고정지출', '경호용돈', '수진용돈', '생활비', '경조사비', '기타']
        fig_s = px.bar(history_df, x='날짜', y=[i for i in spend_items if i in history_df.columns], title="월별 지출 구성", barmode='stack')
        st.plotly_chart(fig_s, use_container_width=True)

except Exception as e:
    st.error(f"앱 가동 오류: {e}")
    st.info("구글 시트의 데이터 형식을 확인해주세요. (숫자 칸에 문자가 있는지 등)")
