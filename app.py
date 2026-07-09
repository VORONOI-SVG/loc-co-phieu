import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime
import plotly.graph_objects as go

# Cấu hình giao diện gọn gàng, tối ưu tuyệt đối cho màn hình điện thoại
st.set_page_config(page_title="Bộ Lọc TradingView Khủng", layout="centered")

st.title("🚀 Bộ Lọc & Biểu Đồ Chiến Lược KT2 Multi")
st.write("Cấu hình mặc định: Hiện các mã thỏa tín hiệu kèm biểu đồ kỹ thuật tương tự TradingView")

# Danh sách 120 mã cổ phiếu
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

# Nút bấm bắt đầu quét dữ liệu
if st.button("🚀 Bắt đầu quét dữ liệu"):
    with st.spinner(f"Đang phân tích kỹ thuật và dựng biểu đồ {len(symbols)} mã..."):
        matched_stocks = {}
        all_results = []
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
                
                vh_green_rising = vortex_val >= 0
                arsi_over_80    = arsi_val > 80
                combined_signal = "🟢 MUA" if (vh_green_rising and arsi_over_80) else "⚪ Chờ"
                
                res_item = {
                    "Mã CP": ticker,
                    "Giá Đóng (VNĐ)": round(float(latest['close']), 0),
                    "Augmented RSI": round(arsi_val, 2),
                    "Vortex Histo Wave": round(vortex_val, 2),
                    "Tín hiệu": combined_signal
                }
                all_results.append(res_item)
                
                # Lưu lại dữ liệu 60 phiên gần nhất của mã để vẽ chart độc lập
                if filter_mode == "Chỉ hiện mã thỏa điều kiện MUA" and combined_signal == "🟢 MUA":
                    matched_stocks[ticker] = df.tail(60)
                elif filter_mode == "Hiện tất cả danh sách (120 mã)":
                    matched_stocks[ticker] = df.tail(60)
                    
            except:
                continue

        # --- PHẦN HIỂN THỊ KẾT QUẢ ---
        if len(all_results) > 0:
            res_df = pd.DataFrame(all_results)
            
            if filter_mode == "Chỉ hiện mã thỏa điều kiện MUA":
                display_df = res_df[res_df['Tín hiệu'] == "🟢 MUA"]
                st.subheader("🟢 Các mã xuất hiện Chấm Tín Hiệu Mua")
            else:
                display_df = res_df
                st.subheader("📋 Bảng tổng hợp thông số 120 mã")
                
            if not display_df.empty:
                st.dataframe(display_df, hide_index=True)
                st.write("---")
                st.subheader("📈 Chi tiết biểu đồ xu hướng (Giai đoạn hiện tại - 60 phiên gần nhất)")
                
                # Vẽ biểu đồ riêng cho từng mã nằm trong bộ lọc được chọn
                for ticker in display_df["Mã CP"]:
                    if ticker in matched_stocks:
                        chart_data = matched_stocks[ticker]
                        
                        fig = go.Figure()
                        
                        # 1. Vẽ vùng Sóng Vortex (Đổ màu lấp đầy xu hướng)
                        fig.add_trace(go.Scatter(
                            x=chart_data.index, y=chart_data['vh_vortex'],
                            mode='lines', line=dict(width=1, color='rgba(0, 200, 100, 0.4)'),
                            fill='tozeroy', fillcolor='rgba(0, 230, 115, 0.15)',
                            name='Vortex Sóng Dương (Tăng)'
                        ))
                        
                        # 2. Vẽ đường Augmented RSI uốn lượn (Tỷ lệ hóa về thang đo phù hợp với Vortex để nhìn song song)
                        # Để ARSI (thang 0-100) đứng chung với Vortex, ta chuẩn hóa hiển thị trực quan quanh trục 0
                        arsi_scaled = (chart_data['arsi'] - 50) / 10
                        fig.add_trace(go.Scatter(
                            x=chart_data.index, y=arsi_scaled,
                            mode='lines', line=dict(color='#ff9900', width=2),
                            name='Augmented RSI (Scaled)'
                        ))
                        
                        # 3. Vẽ đường tham chiếu biên không (Zero Line)
                        fig.add_trace(go.Scatter(
                            x=chart_data.index, y=[0]*len(chart_data),
                            mode='lines', line=dict(color='white', width=1, dash='dash'),
                            name='Trục Cân Bằng (0)'
                        ))
                        
                        # 4. Đánh dấu các chấm Tròn Tín Hiệu Mua màu xanh dưới đáy đồ thị (nếu phiên đó thỏa mãn)
                        sig_x = []
                        sig_y = []
                        for idx, row in chart_data.iterrows():
                            if row['vh_vortex'] >= 0 and row['arsi'] > 80:
                                sig_x.append(idx)
                                sig_y.append(min(chart_data['vh_vortex'].min(), arsi_scaled.min()) * 1.1)
                                
                        if sig_x:
                            fig.add_trace(go.Scatter(
                                x=sig_x, y=sig_y,
                                mode='markers', marker=dict(color='#00ff66', size=10, symbol='circle'),
                                name='Chấm Xanh Mua'
                            ))
                        
                        # Thiết lập giao diện biểu đồ tối Darkmode sang trọng như TradingView
                        fig.update_layout(
                            title=f"📊 Biểu đồ KT2 Wave: **{ticker}**",
                            template="plotly_dark",
                            height=320,
                            margin=dict(l=20, r=20, t=40, b=20),
                            showlegend=False,
                            xaxis=dict(showgrid=False),
                            yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)')
                        )
                        st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Hiện tại chưa tìm thấy mã nào đạt điều kiện chấm tín hiệu xanh.")
        else:
            st.error("Không lấy được dữ liệu thị trường, vui lòng làm mới hoặc nhấn quét lại.")
