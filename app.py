import streamlit as st
import pandas as pd
import ta
import yfinance as yf
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
    with st.spinner("Đang kết nối cổng dữ liệu Yahoo Finance quốc tế..."):
        results = []
        
        # Tự động lấy ngày hôm nay (Năm hiện tại 2026)
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        for ticker in symbols:
            try:
                # Yahoo Finance yêu cầu mã chứng khoán VN phải có đuôi .VN
                yahoo_ticker = f"{ticker}.VN"
                
                # Tải dữ liệu từ đầu năm 2026 đến nay
                df = yf.download(yahoo_ticker, start="2026-01-01", end=current_date, progress=False)
                
                # Kiểm tra dữ liệu hợp lệ
                if df is None or df.empty or len(df) < 20:
                    continue
                
                # Làm sạch dữ liệu (Yahoo Finance trả về định dạng đặc biệt, cần đưa về Series phẳng)
                df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]
                df.columns = [col.lower() for col in df.columns]
                
                # Tính toán RSI và MA20
                df['rsi'] = ta.momentum.rsi(df['close'], window=14)
                df['ma20'] = ta.trend.sma_indicator(df['close'], window=20)
                
                # Lấy phiên gần nhất
                latest = df.iloc[-1]
                
                # Lấy giá trị chính xác dạng số (float)
                price_val = float(latest['close'])
                rsi_val = float(latest['rsi']) if not pd.isna(latest['rsi']) else 0
                ma20_val = float(latest['ma20']) if not pd.isna(latest['ma20']) else 0
                
                results.append({
                    "Mã CP": ticker,
                    "Giá Đóng": round(price_val, 0),
                    "RSI": round(rsi_val, 2),
                    "MA20": round(ma20_val, 0)
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
            st.error("Không kết nối được cổng dữ liệu quốc tế. Bạn vui lòng thử lại sau giây lát nhé.")
