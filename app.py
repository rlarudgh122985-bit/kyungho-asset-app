import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px

# 1. 앱 설정
st.set_page_config(layout="wide", page_title="경호 자산 관제탑")

# 2. 구글 시트 연결 (직통 방식)
# Secrets에서 주소를 가져와 CSV 다운로드 주소로 변환합니다.
try:
    raw_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
    # 주소에서 핵심 ID만 추출하여 CSV 내보내기 주소로 변환
    if "/d/" in raw_url:
        sheet_id = raw_url.split("/d/")[1].split("/")[0]
        # 'assets'라는 이름의 탭(gid)을 찾아야 하므로 주소를 정교하게 만듭니다.
        # 만약 탭 이름이 assets라면 gid를 확인해야 하지만, 일단 첫번째 시트로 시도합니다.
        csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
    else:
        st.error("구글 시트 주소가 올바르지 않습니다.")
        st.stop()

    # 데이터 읽기 (이 방식은 로그인 없이 링크만 있으면 바로 읽어옵니다)
    df = pd.read_csv(csv_url)
    
    # 만약 시트의 컬럼명이 한글이라면 공백 제거
    df.columns = df.columns.str.strip()
    
except Exception as e:
    st.error(f"데이터를 불러오지 못했습니다. 공유 설정을 확인해주세요! 에러: {e}")
    st.stop()

# 3. 실시간 가격 반영 (야후 파이낸스)
usd_krw = yf.Ticker("USDKRW=X").history(period="1d")['Close'].iloc[-1]

def get_live_val(row):
    ticker = str(row['티커']).strip()
    qty = float(row['수량'])
    if ticker == "-" or ticker == "nan": return qty
    
    try:
        data = yf.Ticker(ticker).history(period="1d")
        if not data.empty:
            price = data['Close'].iloc[-1]
            if row['통화'] == "USD":
                return price * qty * usd_krw
            return price * qty
        return 0
    except:
        return 0

# 평가금액 계산
df['평가금액'] = df.apply(get_live_val, axis=1)
total_val = df['평가금액'].sum()

# 4. 화면 출력
st.header(f"🛰️ 경호&와이프 자산 관제탑 (환율: ₩{usd_krw:,.2f})")
st.metric("총 순자산", f"₩{total_val:,.0f}")

st.divider()
st.subheader("📋 실시간 자산 데이터")
df['비중(%)'] = (df['평가금액'] / total_val * 100).round(1)
st.dataframe(df[['카테고리', '종목명', '수량', '평가금액', '비중(%)']], use_container_width=True, hide_index=True)

# 차트 시각화
fig = px.pie(df, values='평가금액', names='카테고리', hole=0.4, 
             color_discrete_map={'① 핵심':'#3498db','② 위성':'#e67e22','③ 안전':'#2ecc71'})
st.plotly_chart(fig, use_container_width=True)
