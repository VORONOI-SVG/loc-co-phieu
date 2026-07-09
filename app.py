import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime

# Cấu hình giao diện gọn gàng cho điện thoại
st.set_page_config(page_title="Bộ Lọc TradingView Khủng", layout="centered")

st.title("🚀 Bộ Lọc Chiến Lược TradingView [Multi-Tool]")
st.write("Dữ liệu đồng bộ trực tiếp từ thuật toán Pine Script v6")

# Danh sách các mã cổ phiếu phổ biến
symbols = ['FPT', 'SSI', 'VNM', 'HPG', 'VIC', 'VCB', 'TCB', 'MWG', 'DGC', 'STB']

# Giao diện tùy chỉnh bên góc màn hình
st.sidebar.header("⚙️ Cấu hình bộ lọc")
filter_mode = st.sidebar.selectbox("Chế độ lọc chiến lược:", ["Tất cả danh sách", "Tín hiệu chấm xanh (Vortex + ARSI > 80)"])

# --- CÁC HÀM TOÁN HỌC DỊCH TỪ PINE SCRIPT ---
def rma(series, period):
    """Hàm tính RMA giống y hệt ta.rma() của TradingView"""
    return series.ewm(alpha=1/period, min_periods=period, adjust=False).mean()

def calculate_augmented_rsi(df, length=14, smooth_len=14):
    """Dịch chính xác SECTION 2 (Augmented RSI - LuxAlgo) từ Pine Script"""
    src = df['close']
    upper = src.rolling(window=length).max()
    lower = src.rolling(window=length).min()
    rsi_r = upper - lower
    rsi_d = src.diff()
    
    # Logic điều kiện: arsi_upper > arsi_upper[1] ? arsi_r : ...
    upper_diff = upper.diff()
    lower_diff = lower.diff()
    
    arsi_diff = np.where(upper_diff > 0, rsi_r, 
                         np.where(lower_diff < 0, -rsi_r, rsi_d))
    arsi_diff = pd.Series(arsi_diff, index=df.index)
    
    # Tính toán RMA cho tử số và mẫu số
    arsi_num = rma(arsi_diff, length)
    arsi_den = rma(arsi_diff.abs(), length)
    
    arsi = (arsi_num / arsi_den) * 50 + 50
    return arsi

def calculate_vortex_histogram(df):
    """Dịch chính xác SECTION 10 (Vortex Histogram Multi-SMA) từ Pine Script"""
    src = df['close']
    vh_short_sma   = src.rolling(window=6).mean()
    vh_long_sma    = src.rolling(window=27).mean()
    vh_longer_sma  = src.rolling(window=72).mean()
    vh_longest_sma = src.rolling(window=234).mean()
    
    vh_hist      = vh_short_sma - vh_long_sma
    vh_longh     = vh_short_sma - vh_longer_sma
    vh_longesth  = vh_short_sma - vh_longest_sma
    
    # vh_vortex = math.avg(vh_hist / 3, vh_longh / 2, vh_longesth / 4)
    vh_vortex = (vh_hist / 3 + vh_longh / 2 + vh_longesth / 4) / 3
    return vh_vortex

# Nút bấm bắt đầu quét dữ liệu
if st.button("🚀 Bắt đầu quét dữ liệu"):
    with st.spinner("Đang chạy thuật toán quét dữ liệu mượt mà..."):
        results = []
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        for ticker in symbols:
            try:
                # Lấy dữ liệu 2 năm gần nhất để đảm bảo tính đủ SMA 234 phiên
                yahoo_ticker = f"{ticker}.VN"
                df = yf.download(yahoo_ticker, period="2y", end=current_date, progress=False)
                
                if df is None or df.empty or len(df) < 235:
                    continue
                
                # Làm phẳng cột dữ liệu
                df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]
                df.columns = [col.lower() for col in df.columns]
                
                # Tính toán các chỉ báo từ Pine Script của bạn
                df['arsi'] = calculate_augmented_rsi(df)
                df['vh_vortex'] = calculate_vortex_histogram(df)
                
                # Lấy kết quả của phiên đóng cửa gần nhất
                latest = df.iloc[-1]
                
                # Điều kiện kích hoạt Chấm Tròn Tín Hiệu (Combined Signal Dots)
                vh_green_rising = latest['vh_vortex'] >= 0
                arsi_over_80    = latest['arsi'] > 80
                combined_signal = "🟢 MUA" if (vh_green_rising and arsi_over_80) else "⚪ Chờ"
                
                results.append({
                    "Mã CP": ticker,
                    "Giá Đóng (VNĐ)": round(float(latest['close']), 0),
                    "Augmented RSI": round(float(latest['arsi']), 2),
                    "Vortex Histo Wave": round(float(latest['vh_vortex']), 2),
                    "Tín hiệu chấm TV": combined_signal
                })
            except Exception as e:
                continue

        # Xử lý hiển thị kết quả
        if len(results) > 0:
            res_df = pd.DataFrame(results)
            
            if filter_mode == "Tín hiệu chấm xanh (Vortex + ARSI > 80)":
                filtered_df = res_df[res_df['Tín hiệu chấm TV'] == "🟢 MUA"]
                st.subheader("🟢 Danh sách các mã xuất hiện Chấm Tín Hiệu Mua")
                if not filtered_df.empty:
                    st.dataframe(filtered_df, hide_index=True)
                else:
                    st.info("Hiện tại chưa có mã nào kích hoạt chấm xanh mua theo bộ lọc TradingView của bạn.")
            else:
                st.subheader("📋 Bảng tổng hợp các thông số kỹ thuật nâng cao")
                st.dataframe(res_df, hide_index=True)
        else:
            st.error("Không thể quét dữ liệu từ máy chủ. Vui lòng nhấn lại nút Quét.")
