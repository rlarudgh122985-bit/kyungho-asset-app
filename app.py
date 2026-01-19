import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from datetime import datetime, timedelta

# 1. 설정 및 한국 시간(KST) 동기화
SHEET_ID = "11MCEC3BwyEXWvcPht_qfB2rnKbcboxcv8ervEQjGg1o"
st.set_page_config(layout="wide", page_title="경호&수진 자산 관제탑")

def get_kst():
    # 서버 시간(UTC)에 9시간을 더해 한국 시간으로 고정
    return datetime.utcnow() + timedelta(hours=9)

now_kst = get_kst()

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

# --- 데이터 준비 및 실시간 계산 ---
try:
    assets_df = load_data_direct("assets")
    history_df = load_data_direct("history")
    usd_krw = get_live_price("USDKRW=X")
    if usd_krw <= 100: usd_krw = 1450.0

    # 실시간 자산 총합 (지출 차감 전)
    assets_df['평가금액'] = assets_df.apply(lambda r: get_live_price(r['티커']) * r['수량'] * (usd_krw if r['통화']=="USD" else 1.0) if r['티커'] != "-" else r['수량'], axis=1)
    raw_total = assets_df['평가금액'].sum()

    st.header(f"🛰️ 경호&수진 통합 관제탑 (v2.9 Full-Auto)")

    # --- [상단: 실시간 자산 비중 & 명세] ---
    col_pie, col_table = st.columns([1, 1.2])
    with col_pie:
        # 핵심/위성/안전 3대 자산 원형 그래프
        cat_summary = assets_df.groupby('카테고리')['평가금액'].sum().reset_index()
        fig_pie = px.pie(cat_summary, values='평가금액', names='카테고리', 
                         hole=0.4, title="3대 자산 성격별 비중 (실시간)",
                         color_discrete_map={'① 핵심':'#1f77b4','② 위성':'#ff7f0e','③ 안전':'#2ca02c'})
        st.plotly_chart(fig_pie, use_container_width=True)
    with col_table:
        assets_df['비중(%)'] = (assets_df['평가금액'] / raw_total * 100).round(1)
        st.write(f"**📍 한국 시각:** {now_kst.strftime('%Y-%m-%d %H:%M:%S')}")
        st.dataframe(assets_df[['카테고리', '종목명', '수량', '평가금액', '비중(%)']], use_container_width=True, hide_index=True)

    st.divider()

    # --- [중단: 지출 입력 및 순자산 기록실] ---
    with st.expander("💸 수동 지출 기록 (입력 시 실시간 자산에서 차감 후 저장)", expanded=False):
        c1, c2, c3 = st.columns(3)
        v1 = c1.number_input("🏠 고정지출", value=0)
        v2 = c2.number_input("🤴 경호용돈", value=0)
        v3 = c3.number_input("👸 수진용돈", value=0)
        v4 = c1.number_input("🍱 생활비", value=0)
        v5 = c2.number_input("🤝 경조사비", value=0)
        v6 = c3.number_input("❓ 기타", value=0)
        
        total_expense = v1 + v2 + v3 + v4 + v5 + v6
        net_total = raw_total - total_expense
        rec_date = st.date_input("기록 날짜", now_kst)
        
        m1, m2, m3 = st.columns(3)
        m1.metric("실시간 자산합계", f"₩{raw_total:,.0f}")
        m2.metric("오늘 총 지출", f"- ₩{total_expense:,.0f}")
        m3.metric("최종 순자산(기록용)", f"₩{net_total:,.0f}")

        if st.button("🚀 순자산 데이터 저장"):
            try:
                from streamlit_gsheets import GSheetsConnection
                conn = st.connection("gsheets", type=GSheetsConnection)
                new_row = pd.DataFrame([{"날짜": rec_date.strftime("%Y-%m-%d"), "총자산": int(net_total), "고정지출": v1, "경호용돈": v2, "수진용돈": v3, "생활비": v4, "경조사비": v5, "기타": v6}])
                updated_h = pd.concat([history_df, new_row], ignore_index=True)
                conn.update(worksheet="history", data=updated_h)
                st.success("성공적으로 저장되었습니다!")
                st.cache_data.clear()
                st.rerun()
            except:
                st.error("저장 실패! 아래 내용을 복사해서 시트 하단에 붙여넣으세요.")
                st.code(f"{rec_date.strftime('%Y-%m-%d')}\t{int(net_total)}\t{v1}\t{v2}\t{v3}\t{v4}\t{v5}\t{v6}")

    # --- [하단: 자산 성장 추이 - 만원 단위 & 입력일 기준] ---
    if not history_df.empty:
        st.subheader("📈 자산 성장 히스토리 (단위: 만원)")
        history_df['날짜'] = pd.to_datetime(history_df['날짜'])
        history_df = history_df.sort_values('날짜')
        history_df['총자산_만원'] = (history_df['총자산'] / 10000).astype(int)
        
        # 1) 순자산 성장 곡선 (입력 날짜가 X축)
        fig_t = px.line(history_df, x='날짜', y='총자산_만원', markers=True, 
                        title="기록일 기준 순자산 성장 (만원)",
                        labels={'총자산_만원': '순자산(만원)', '날짜': '기록일'})
        fig_t.update_xaxes(type='date', tickformat="%m/%d")
        # Y축 범위를 데이터에 맞춰 자동 조절하되 '만원' 단위 명시
        fig_t.update_yaxes(ticksuffix="만")
        st.plotly_chart(fig_t, use_container_width=True)

        # 2) 월별 지출 상세
        spend_items = ['고정지출', '경호용돈', '수진용돈', '생활비', '경조사비', '기타']
        fig_s = px.bar(history_df, x='날짜', y=[i for i in spend_items if i in history_df.columns], title="월별 지출 구성", barmode='stack')
        st.plotly_chart(fig_s, use_container_width=True)

except Exception as e:
    st.error(f"앱 가동 오류: {e}")
