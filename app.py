import streamlit as st
import pandas as pd
from vnstock import Market
# Thay đổi thư viện tính toán ở đây để tránh lỗi hệ thống
import ta

# Cấu hình giao diện gọn gàng cho điện thoại
st.set_page_config(page_title="Bộ Lọc Cổ Phiếu", layout="centered")

st.title("📊 Bộ Lọc Cổ Phiếu Việt Nam")
st.write("Ứng dụng chạy trên mọi thiết bị (PC / Điện thoại)")

# Danh sách các mã cổ phiếu phổ biến
symbols = ['FPT', 'SSI', 'VNM', 'HPG', 'VIC', 'VCB', 'TCB', 'MWG', 'DGC', 'STB']

# Giao diện tùy chỉnh bên góc màn hình
st.sidebar.header("⚙️ Cấu hình bộ lọc")
filter_type = st.sidebar.selectbox("Chọn chỉ báo muốn lọc:", ["RSI (Quá bán / Quá mua)", "Đường xu hướng MA20"])

# Nút bấm bắt đầu quét dữ liệu
if st.button("🚀 Bắt đầu quét dữ liệu"):
    with st.spinner("Đang kết nối dữ liệu sàn chứng khoán..."):
        market = Market()
        results = []
        
        for ticker in symbols:
            try:
                # Tải dữ liệu lịch sử
                df = market.equity.ohlcv(symbol=ticker, start='2026-01-01', end='2026-07-09')
                if df.empty:
                    continue
                
                # Tính RSI và MA20 bằng thư viện 'ta' mới để không bị lỗi build wheel
                df['RSI'] = ta.momentum.rsi(df['close'], window=14)
                df['MA20'] = ta.trend.sma_indicator(df['close'], window=20)
                
                # Lấy dòng dữ liệu mới nhất (ngày hôm nay)
                latest = df.iloc[-1]
                
                results.append({
                    "Mã CP": ticker,
                    "Giá Đóng": latest['close'],
                    "RSI": round(latest['RSI'], 2) if not pd.isna(latest['RSI']) else 0,
                    "MA20": round(latest['MA20'], 2) if not pd.isna(latest['MA20']) else 0
                })
            except:
                continue

        if len(results) > 0:
            res_df = pd.DataFrame(results)
            st.subheader("📋 Kết quả lọc")
            
            if filter_type == "RSI (Quá bán / Quá mua)":
                st.write("**⚠️ Vùng Quá mua (RSI > 70) - Giá đang cao:**")
                st.dataframe(res_df[res_df['RSI'] > 70])
                
                st.write("**💎 Vùng Quá bán (RSI < 30) - Giá đang rẻ:**")
                st.dataframe(res_df[res_df['RSI'] < 30])
                
            elif filter_type == "Đường xu hướng MA20":
                st.write("**📈 Cổ phiếu nằm TRÊN đường MA20 (Xu hướng tăng):**")
                st.dataframe(res_df[res_df['Giá Đóng'] > res_df['MA20']])
        else:
            st.error("Không lấy được dữ liệu, vui lòng thử lại sau.")
