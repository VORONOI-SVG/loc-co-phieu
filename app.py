import streamlit as st
import pandas as pd
# Nhập thẳng hàm lấy dữ liệu ohlcv của vnstock3 để chạy nhanh hơn
from vnstock.data.equity import ohlcv
import ta
from datetime import datetime

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
        results = []
        
        # Tự động lấy ngày hôm nay để đảm bảo dữ liệu luôn mới nhất
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        for ticker in symbols:
            try:
                # Dùng hàm ohlcv trực tiếp, đổi nguồn sang 'dnse' hoặc 'tcbs' để tăng tỉ lệ thành công
                df = ohlcv(symbol=ticker, start='2026-01-01', end=current_date, source='dnse')
                
                # Kiểm tra nếu dữ liệu rỗng
                if df is None or df.empty or 'close' not in df.columns:
                    # Thử lại với nguồn tcbs nếu nguồn dnse bị nghẽn
                    df = ohlcv(symbol=ticker, start='2026-01-01', end=current_date, source='tcbs')
                    if df is None or df.empty or 'close' not in df.columns:
                        continue
                
                # Tính RSI và MA20
                df['RSI'] = ta.momentum.rsi(df['close'], window=14)
                df['MA20'] = ta.trend.sma_indicator(df['close'], window=20)
                
                # Lấy dòng dữ liệu mới nhất
                latest = df.iloc[-1]
                
                results.append({
                    "Mã CP": ticker,
                    "Giá Đóng": latest['close'],
                    "RSI": round(latest['RSI'], 2) if not pd.isna(latest['RSI']) else 0,
                    "MA20": round(latest['MA20'], 2) if not pd.isna(latest['MA20']) else 0
                })
            except Exception as e:
                continue

        # Hiển thị kết quả ra màn hình
        if len(results) > 0:
            res_df = pd.DataFrame(results)
            st.subheader("📋 Kết quả lọc toàn bộ danh sách")
            st.dataframe(res_df) 
            
            st.divider() 
            
            if filter_type == "RSI (Quá bán / Quá mua)":
                st.write("**⚠️ Vùng Quá mua (RSI > 70) - Giá đang cao:**")
                qua_mua = res_df[res_df['RSI'] > 70]
                if not qua_mua.empty:
                    st.dataframe(qua_mua)
                else:
                    st.info("Hiện tại không có mã nào trong danh sách bị quá mua.")
                
                st.write("**💎 Vùng Quá bán (RSI < 30) - Giá đang rẻ:**")
                qua_ban = res_df[res_df['RSI'] < 30]
                if not qua_ban.empty:
                    st.dataframe(qua_ban)
                else:
                    st.info("Hiện tại không có mã nào trong danh sách bị quá bán.")
                
            elif filter_type == "Đường xu hướng MA20":
                st.write("**📈 Cổ phiếu nằm TRÊN đường MA20 (Xu hướng tăng):**")
                xu_huong_tang = res_df[res_df['Giá Đóng'] > res_df['MA20']]
                if not xu_huong_tang.empty:
                    st.dataframe(xu_huong_tang)
                else:
                    st.info("Không có cổ phiếu nào nằm trên đường MA20.")
        else:
            st.error("Hệ thống không quét được dữ liệu. Vui lòng bấm thử lại nút 'Bắt đầu quét dữ liệu' sau vài giây để kích hoạt lại cổng kết nối.")
