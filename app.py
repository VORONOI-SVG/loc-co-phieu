import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime

# Cấu hình giao diện gọn gàng cho điện thoại
st.set_page_config(page_title="Bộ Lọc TradingView Khủng", layout="centered")

st.title("🚀 Bộ Lọc Chiến Lược TradingView [Multi-Tool]")
st.write("Dữ liệu đồng bộ trực tiếp từ thuật toán Pine Script v6")

# Danh sách mở rộng toàn bộ các mã cổ phiếu lớn và phổ biến trên thị trường (đã thêm OCB)
# Danh sách 80 mã cổ phiếu hàng đầu, thanh khoản cao và có chỉ số tốt trên thị trường
symbols = [
    # 1. Nhóm Ngân hàng (20 mã - Đầu ngành và có chỉ số tài chính, tăng trưởng tốt)
    'OCB', 'VCB', 'TCB', 'STB', 'MBB', 'ACB', 'BID', 'CTG', 'VPB', 'HDB', 
    'VIB', 'LPB', 'SHB', 'TPB', 'MSB', 'BAB', 'EIB', 'NAB', 'SSB', 'BVB',
    
    # 2. Nhóm Chứng khoán (12 mã - Độ nhạy sóng cao, hưởng lợi thanh khoản)
    'SSI', 'VND', 'VCI', 'HCM', 'FTS', 'BSI', 'MBS', 'SHS', 'AGR', 'CTS', 
    'VIX', 'ORS',
    
    # 3. Nhóm Thép & Nguyên vật liệu (6 mã - Đầu ngành sản xuất)
    'HPG', 'HSG', 'NKG', 'VGS', 'SMC', 'TLH',
    
    # 4. Nhóm Bất động sản & Khu công nghiệp (15 mã - Quỹ đất và tài chính ổn định)
    'VIC', 'VHM', 'VRE', 'NVL', 'PDR', 'DIG', 'CEO', 'DXG', 'KDH', 'NLG', 
    'KBC', 'IDC', 'SZC', 'VGC', 'VPI',
    
    # 5. Nhóm Công nghệ, Bán lẻ & Hàng tiêu dùng (10 mã - Chỉ số cơ bản cực tốt)
    'FPT', 'MWG', 'FRT', 'DGW', 'PNJ', 'VNM', 'MSN', 'SAB', 'MCH', 'VTP',
    
    # 6. Nhóm Dầu khí & Năng lượng (7 mã - Hưởng lợi vĩ mô và hạ tầng)
    'GAS', 'PVD', 'PVS', 'POW', 'PC1', 'HDG', 'GEG',
    
    # 7. Nhóm Hóa chất & Phân bón (5 mã - Dòng tiền duy trì đều đặn)
    'DGC', 'DPM', 'DCM', 'CSV', 'BFC',
    
    # 8. Nhóm Thủy sản & Nông nghiệp & Đầu tư công (5 mã - Tiềm năng xuất khẩu và hạ tầng)
    'ANV', 'VHC', 'DBC', 'HHV', 'LCG'
]

# Giao diện tùy chỉnh bên góc màn hình
st.sidebar.header("⚙️ Cấu hình bộ lọc")
filter_mode = st.sidebar.selectbox("Chế độ lọc chiến lược:", ["Tất cả danh sách", "Tín hiệu chấm xanh (Vortex + ARSI > 80)"])

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
    
    # Tránh chia cho 0
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

# Nút bấm bắt đầu quét dữ liệu
if st.button("🚀 Bắt đầu quét dữ liệu"):
    with st.spinner(f"Đang quét toàn bộ {len(symbols)} mã trên thị trường..."):
        results = []
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        for ticker in symbols:
            try:
                yahoo_ticker = f"{ticker}.VN"
                # Tải dữ liệu dài hơn (3 năm) để làm mượt SMA dài hạn
                df = yf.download(yahoo_ticker, period="3y", end=current_date, progress=False)
                
                if df is None or df.empty or len(df) < 240:
                    continue
                
                # Làm phẳng hoàn toàn cột dữ liệu của Yahoo Finance thành 1 tầng duy nhất
                df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]
                df.columns = [col.lower() for col in df.columns]
                
                # Tính toán chỉ báo
                df['arsi'] = calculate_augmented_rsi(df)
                df['vh_vortex'] = calculate_vortex_histogram(df)
                
                latest = df.iloc[-1]
                
                # Lấy giá trị float thuần túy
                arsi_val = float(latest['arsi']) if not pd.isna(latest['arsi']) else 0
                vortex_val = float(latest['vh_vortex']) if not pd.isna(latest['vh_vortex']) else 0
                
                # Điều kiện kích hoạt chấm xanh
                vh_green_rising = vortex_val >= 0
                arsi_over_80    = arsi_val > 80
                combined_signal = "🟢 MUA" if (vh_green_rising and arsi_over_80) else "⚪ Chờ"
                
                results.append({
                    "Mã CP": ticker,
                    "Giá Đóng (VNĐ)": round(float(latest['close']), 0),
                    "Augmented RSI": round(arsi_val, 2),
                    "Vortex Histo Wave": round(vortex_val, 2),
                    "Tín hiệu chấm TV": combined_signal
                })
            except:
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
                    st.info("Hiện tại chưa có mã nào kích hoạt chấm xanh mua. Bạn thử chuyển qua chế độ 'Tất cả danh sách' để xem thông số nhé.")
            else:
                st.subheader(f"📋 Bảng tổng hợp thông số kỹ thuật ({len(results)} mã thành công)")
                st.dataframe(res_df, hide_index=True)
        else:
            st.error("Không thể quét dữ liệu từ máy chủ. Vui lòng nhấn lại nút Quét.")
