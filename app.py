import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime

# Cấu hình giao diện gọn gàng, tối ưu tuyệt đối cho màn hình điện thoại
st.set_page_config(page_title="Bộ Lọc TradingView Khủng", layout="centered")

st.title("🚀 Bộ Lọc Chiến Lược TradingView [Multi-Tool]")
st.write("Cấu hình mặc định: Chỉ hiển thị các mã thỏa mãn tín hiệu MUA")

# Mở rộng danh sách lên đúng 120 mã cổ phiếu tốt và thanh khoản cao nhất thị trường Việt Nam
symbols = [
    # 1. Nhóm Ngân hàng (22 mã)
    'OCB', 'VCB', 'TCB', 'STB', 'MBB', 'ACB', 'BID', 'CTG', 'VPB', 'HDB', 
    'VIB', 'LPB', 'SHB', 'TPB', 'MSB', 'BAB', 'EIB', 'NAB', 'SSB', 'BVB', 'ABB', 'PGB',
    # 2. Nhóm Chứng khoán (16 mã)
    'SSI', 'VND', 'VCI', 'HCM', 'FTS', 'BSI', 'MBS', 'SHS', 'AGR', 'CTS', 
    'VIX', 'ORS', 'BVS', 'TVSI', 'VDS', 'TCI',
    # 3. Nhóm Thép & Nguyên vật liệu (8 mã)
    'HPG', 'HSG', 'NKG', 'VGS', 'SMC', 'TLH', 'POM', 'TVN',
    # 4. Nhóm Bất động sản & Khu công nghiệp (24 mã)
    'VIC', 'VHM', 'VRE', 'NVL', 'PDR', 'DIG', 'CEO', 'DXG', 'KDH', 'NLG', 
    'KBC', 'IDC', 'SZC', 'VGC', 'VPI', 'DXS', 'HQC', 'IJC', 'LDG', 'SCR', 'TCH', 'ITA', 'LHG', 'TIP',
    # 5. Nhóm Công nghệ, Bán lẻ & Hàng tiêu dùng (15 mã)
    'FPT', 'MWG', 'FRT', 'DGW', 'PNJ', 'VNM', 'MSN', 'SAB', 'MCH', 'VTP', 'PET', 'CMG', 'ELA', 'KDC', 'VOC',
    # 6. Nhóm Dầu khí, Năng lượng & Điện (12 mã)
    'GAS', 'PVD', 'PVS', 'POW', 'PC1', 'HDG', 'GEG', 'PVT', 'BSR', 'OIL', 'NT2', 'QTP',
    # 7. Nhóm Hóa chất, Phân bón & Cao su (11 mã)
    'DGC', 'DPM', 'DCM', 'CSV', 'BFC', 'GVR', 'PHR', 'DPR', 'DRI', 'DDV', 'LAS',
    # 8. Nhóm Đầu tư công, Xây dựng & Hạ tầng (6 mã)
    'HHV', 'LCG', 'VJ_G', 'C4G', 'FCN', 'VCG',
    # 9. Nhóm Thủy sản, Nông nghiệp & Dệt may (6 mã)
    'ANV', 'VHC', 'DBC', 'PAN', 'TNG', 'MSH'
]

# Thanh điều hướng ẩn gọn trong Sidebar (Nếu muốn xem lại tất cả mã, có thể bấm chọn)
filter_mode = st.sidebar.selectbox("Chế độ hiển thị:", ["Chỉ hiện mã thỏa điều kiện MUA", "Hiện tất cả danh sách (120 mã)"])

# --- CÁC HÀM TOÁN HỌC DỊCH TỪ PINE SCRIPT ---
def rma(series, period):
    return series.ewm(alpha=1/period, min_periods=period, adjust=False).mean()

def calculate_augmented_rsi(df, length=14):
    src = df['close']
    upper = src.rolling(window=length).max()
    lower = src.rolling(window=length).min()
    rsi_r = upper - lower
    rsi_d = src.diff()
    
    upper_diff = upper.diff()
    lower_diff = lower.diff()
    
    rsi_diff_np = np.where(upper_diff > 0, rsi_r, np.where(lower_diff < 0, -rsi_r, rsi_d))
    arsi_diff = pd.Series(rsi_diff_np, index=df.index)
    
    arsi_num = rma(arsi_diff, length)
    arsi_den = rma(arsi_diff.abs(), length)
    
    return (arsi_num / arsi_den.replace(0, np.nan)) * 50 + 50

def calculate_vortex_histogram(df):
    src = df['close']
    vh_short_sma   = src.rolling(window=6).mean()
    vh_long_sma    = src.rolling(window=27).mean()
    vh_longer_sma  = src.rolling(window=72).mean()
    vh_longest_sma = src.rolling(window=234).mean()
    
    vh_hist      = vh_short_sma - vh_long_sma
    vh_longh     = vh_short_sma - vh_longer_sma
    vh_longesth  = vh_short_sma - vh_longest_sma
    
    return (vh_hist / 3 + vh_longh / 2 + vh_longesth / 4) / 3

# Nút bấm bắt đầu quét dữ liệu đặt ngay đầu trang
if st.button("🚀 Bắt đầu quét dữ liệu"):
    with st.spinner(f"Đang phân tích kỹ thuật {len(symbols)} mã cổ phiếu..."):
        results = []
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        for ticker in symbols:
            try:
                yahoo_ticker = f"{ticker}.VN"
                df = yf.download(yahoo_ticker, period="3y", end=current_date, progress=False)
                
                if df is None or df.empty or len(df) < 240:
                    continue
                
                df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]
                df.columns = [col.lower() for col in df.columns]
                
                df['arsi'] = calculate_augmented_rsi(df)
                df['vh_vortex'] = calculate_vortex_histogram(df)
                
                latest = df.iloc[-1]
                arsi_val = float(latest['arsi']) if not pd.isna(latest['arsi']) else 0
                vortex_val = float(latest['vh_vortex']) if not pd.isna(latest['vh_vortex']) else 0
                
                # Logic xác định tín hiệu chấm xanh từ Pine Script của bạn
                vh_green_rising = vortex_val >= 0
                arsi_over_80    = arsi_val > 80
                combined_signal = "🟢 MUA" if (vh_green_rising and arsi_over_80) else "⚪ Chờ"
                
                results.append({
                    "Mã CP": ticker,
                    "Giá Đóng (VNĐ)": round(float(latest['close']), 0),
                    "Augmented RSI": round(arsi_val, 2),
                    "Vortex Histo Wave": round(vortex_val, 2),
                    "Tín hiệu": combined_signal
                })
            except:
                continue

        # Xử lý hiển thị kết quả lọc thông minh
        if len(results) > 0:
            res_df = pd.DataFrame(results)
            
            if filter_mode == "Chỉ hiện mã thỏa điều kiện MUA":
                filtered_df = res_df[res_df['Tín hiệu'] == "🟢 MUA"]
                st.subheader("🟢 Danh sách các mã xuất hiện Chấm Tín Hiệu Mua")
                if not filtered_df.empty:
                    st.dataframe(filtered_df, hide_index=True)
                else:
                    st.info("Hiện tại không có mã nào kích hoạt chấm xanh mua trong 120 mã.")
            else:
                st.subheader(f"📋 Bảng tổng hợp thông số ({len(results)} mã thành công)")
                st.dataframe(res_df, hide_index=True)
        else:
            st.error("Không thể lấy dữ liệu từ Yahoo Finance. Vui lòng bấm thử lại.")
