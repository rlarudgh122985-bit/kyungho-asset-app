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

# 2. 초강력 데이터 로드 함수 (공백 및 특수문자 완벽 제거)
@st.cache_data(ttl=60)
def load_data_ultimate(sheet_name):
    # gviz/tq 방식이 export 방식보다 시트 이름 인식에 더 강합니다.
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
    try:
        df = pd.read_csv(url)
        # 컬럼명의 모든 공백과 특수문자 제거 후 표준화
        df.columns = [str(col).strip() for col in df.columns]
        
        if sheet_name == "history" and not df.empty:
            # 글자가 틀려도 위치(0번, 1번 열)로 강제 매칭
            df.columns = ['날짜', '총자산'] + list(df.columns[2:])
        return df.dropna(how='all')
    except:
        # history 실패 시 History로 재시도
        if sheet_name == "history":
            try:
                url_alt = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=History"
                df = pd.read_csv(url_alt)
                df.columns = ['날짜', '총자산'] + list(df.columns[2:])
                return df
            except: return pd.DataFrame()
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
    assets_df = load_data_ultimate("assets")
    history_df = load_data_ultimate("history")

    st.title("🛰️ 경호 & 수진 통합 자산 관제탑")
    st.caption(f"📍 KST: {now_kst.strftime('%Y-%m-%d %H:%M:%S')} | v3.8 2,000만원 단위 최적화")

    # 시장 지표 표시
    indices = {"S&P 500": "^GSPC", "나스닥": "^IXIC", "코스피": "^KS11", "환율": "USDKRW=X", "금": "GC=F"}
    m_cols = st.columns(len(indices))
    usd_krw = 1450.0
    for i, (name, ticker) in enumerate(indices.items()):
        p, d = get_market_data(ticker)
        if "환율" in name: usd_krw = p
        m_cols[i].metric(name, f"{p:,.1f}", delta=f"{d:,.1f}")

    st.divider()

    # 실시간 자산 계산
    assets_df['수량'] = pd.to_numeric(assets_df['수량'], errors='coerce').fillna(0)
    def calc_val(row):
        t, q, unit = str(row.get('티커', '-')).strip(), row['수량'], str(row.get('통화', 'KRW')).strip()
        if t == "-" or not t or t == "nan": return q
        p, _ = get_market_data(t)
        return p * q * (usd_krw if unit == "USD" else 1.0)
    assets_df['평가금액'] = assets_df.apply(calc_val, axis=1)
    raw_total = assets_df['평가금액'].sum()

    # 지출 입력 섹션
    with st.expander("💸 오늘자 지출 및 순자산 정산", expanded=True):
        e1, e2, e3 = st.columns(3)
        v1, v2, v3 = e1.number_input("🏠 고정지출", 0), e2.number_input("🤴 경호용돈", 0), e3.number_input("👸 수진용돈", 0)
        v4, v5, v6 = e1.number_input("🍱 생활비", 0), e2.number_input("🤝 경조사비", 0), e3.number_input("❓ 기타", 0)
        
        total_exp = v1+v2+v3+v4+v5+v6
        net_total = raw_total - total_exp
        rec_date = st.date_input("기록 날짜", now_kst)
        
        m1, m2, m3 = st.columns(3)
        m1.metric("실시간 자산합계", f"₩{raw_total:,.0f}")
        m2.metric("오늘 지출차감", f"- ₩{total_exp:,.0f}")
        m3.metric("최종 순자산", f"₩{net_total:,.0f}")

        if st.button("🚀 데이터 저장 (History)"):
            try:
                from streamlit_gsheets import GSheetsConnection
                conn = st.connection("gsheets", type=GSheetsConnection)
                new_row = pd.DataFrame([[rec_date.strftime("%Y-%m-%d"), int(net_total), v1, v2, v3, v4, v5, v6]], columns=history_df.columns[:8])
                conn.update(worksheet="history", data=pd.concat([history_df, new_row], ignore_index=True))
                st.success("저장 완료!"); st.cache_data.clear(); st.rerun()
            except:
                st.info("수동 입력용 코드:"); st.code(f"{rec_date.strftime('%Y-%m-%d')}\t{int(net_total)}\t{v1}\t{v2}\t{v3}\t{v4}\t{v5}\t{v6}")

    # --- [그래프 핵심 수정: Y축 2,000만원 단위 & 히스토리 복구] ---
    st.divider()
    st.subheader("📈 자산 성장 히스토리 (오늘 기준)")

    # 1. 히스토리 정제 (날짜 파싱 실패 시 대비)
    if not history_df.empty:
        history_df['날짜'] = pd.to_datetime(history_df['날짜'], errors='coerce')
        history_df = history_df.dropna(subset=['날짜'])
    
    # 2. 오늘 실시간 데이터 합치기
    today_row = pd.DataFrame({'날짜': [pd.to_datetime(rec_date)], '총자산': [net_total]})
    plot_df = pd.concat([history_df[['날짜', '총자산']], today_row], ignore_index=True)
    plot_df = plot_df.drop_duplicates(subset=['날짜'], keep='last').sort_values('날짜')
    plot_df['총자산_만원'] = plot_df['총자산'] / 10000

    # 3. 그래프 생성
    fig_t = px.line(plot_df, x='날짜', y='총자산_만원', markers=True, 
                    title=f"자산 성장 곡선 (시작일: {plot_df['날짜'].min().strftime('%Y-%m-%d')})")
    
    # [핵심 요청사항] Y축 범례 단위를 2,000만원으로 설정
    # dtick=2000 (만원 단위이므로 2000만 원 의미)
    fig_t.update_yaxes(
        dtick=2000, 
        tickformat=",d", 
        ticksuffix="만",
        title="순자산 (단위: 만원)"
    )
    
    # X축: 오늘부터 시작하는 느낌을 주도록 범위 설정 (최근 6개월 혹은 전체)
    fig_t.update_xaxes(
        type='date',
        tickformat="%m/%d",
        range=[plot_df['날짜'].max() - timedelta(days=90), plot_df['날짜'].max() + timedelta(days=2)] # 최근 90일 강조
    )
    st.plotly_chart(fig_t, use_container_width=True)

    # 상세 명세
    st.divider()
    col_p, col_d = st.columns([1, 1.2])
    with col_p:
        st.plotly_chart(px.pie(assets_df.groupby('카테고리')['평가금액'].sum().reset_index(), 
                               values='평가금액', names='카테고리', hole=0.4, title="실시간 비중"), use_container_width=True)
    with col_d:
        assets_df['비중(%)'] = (assets_df['평가금액'] / raw_total * 100).round(1)
        st.dataframe(assets_df[['카테고리', '종목명', '수량', '평가금액', '비중(%)']], use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"🚨 시스템 진단: {e}")
