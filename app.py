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

# 2. 데이터 로드 및 유연한 컬럼 매칭 함수
@st.cache_data(ttl=60)
def load_data_flexible(sheet_name):
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&sheet={sheet_name}"
    try:
        df = pd.read_csv(url)
        # 컬럼명 세척 (공백 제거)
        df.columns = [str(col).strip() for col in df.columns]
        
        # [핵심] '날짜'라는 이름이 정확하지 않아도 찾아내는 로직
        if sheet_name == "history":
            date_col = next((c for c in df.columns if '날' in c or 'Date' in c.capitalize()), None)
            if date_col and date_col != '날짜':
                df = df.rename(columns={date_col: '날짜'})
            
            asset_col = next((c for c in df.columns if '자산' in c or 'Total' in c.capitalize()), None)
            if asset_col and asset_col != '총자산':
                df = df.rename(columns={asset_col: '총자산'})
        
        return df.dropna(how='all') 
    except:
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

# --- 앱 가동 ---
try:
    assets_df = load_data_flexible("assets")
    history_df = load_data_flexible("history")

    # 3. 타이틀 및 글로벌 지표 (간지 유지)
    st.title("🛰️ 경호 & 수진 통합 자산 관제탑")
    st.caption(f"📍 한국 표준시: {now_kst.strftime('%Y-%m-%d %H:%M:%S')} | 데이터 매칭 강화 버전")

    indices = {"S&P 500": "^GSPC", "나스닥": "^IXIC", "코스피": "^KS11", "환율": "USDKRW=X", "금": "GC=F"}
    m_cols = st.columns(len(indices))
    usd_krw = 1450.0
    for i, (name, ticker) in enumerate(indices.items()):
        p, d = get_market_data(ticker)
        if "환율" in name: usd_krw = p
        m_cols[i].metric(name, f"{p:,.1f}", delta=f"{d:,.1f}")

    st.divider()

    # 4. 실시간 자산 계산
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
        st.error("⚠️ 'assets' 시트의 첫 줄에 '수량'이라는 글자가 있는지 확인해주세요.")
        st.stop()

    # 5. 지출 입력 및 순자산 정산
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
        m3.metric("기록될 순자산", f"₩{net_total:,.0f}")

        if st.button("🚀 데이터 저장 시도"):
            try:
                from streamlit_gsheets import GSheetsConnection
                conn = st.connection("gsheets", type=GSheetsConnection)
                new_row = pd.DataFrame([{"날짜": rec_date.strftime("%Y-%m-%d"), "총자산": int(net_total), "고정지출": v1, "경호용돈": v2, "수진용돈": v3, "생활비": v4, "경조사비": v5, "기타": v6}])
                updated_h = pd.concat([history_df, new_row], ignore_index=True)
                conn.update(worksheet="history", data=updated_h)
                st.success("저장 완료!")
                st.cache_data.clear()
                st.rerun()
            except:
                st.info("💡 수동 입력용 코드:")
                st.code(f"{rec_date.strftime('%Y-%m-%d')}\t{int(net_total)}\t{v1}\t{v2}\t{v3}\t{v4}\t{v5}\t{v6}")

    # 6. 시각화 (날짜 오류 방어)
    if not history_df.empty and '날짜' in history_df.columns:
        st.divider()
        st.subheader("📈 순자산 성장 히스토리")
        history_df['날짜'] = pd.to_datetime(history_df['날짜'], errors='coerce')
        history_df = history_df.dropna(subset=['날짜']).sort_values('날짜')
        
        history_df['총자산_만원'] = (pd.to_numeric(history_df['총자산'], errors='coerce').fillna(0) / 10000)
        
        fig_t = px.line(history_df, x='날짜', y='총자산_만원', markers=True, title="자산 성장 곡선 (만원)")
        fig_t.update_yaxes(tickformat=",d", ticksuffix="만")
        st.plotly_chart(fig_t, use_container_width=True)
    elif history_df.empty:
        st.info("💡 'history' 탭에 아직 기록된 데이터가 없습니다. 첫 기록을 저장해보세요!")
    else:
        st.warning("⚠️ 'history' 탭에서 '날짜' 컬럼을 찾을 수 없어 그래프를 그릴 수 없습니다.")

    # 7. 상세 명세 및 비중
    st.divider()
    col_p, col_d = st.columns([1, 1.2])
    with col_p:
        st.plotly_chart(px.pie(assets_df.groupby('카테고리')['평가금액'].sum().reset_index(), 
                               values='평가금액', names='카테고리', hole=0.4, title="자산 비중"), use_container_width=True)
    with col_d:
        assets_df['비중(%)'] = (assets_df['평가금액'] / raw_total * 100).round(1)
        st.dataframe(assets_df[['카테고리', '종목명', '수량', '평가금액', '비중(%)']], use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"🚨 예상치 못한 오류: {e}")
