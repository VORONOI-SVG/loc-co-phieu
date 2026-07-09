import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime
import plotly.graph_objects as go

# Cấu hình giao diện gọn gàng, tối ưu tuyệt đối cho màn hình điện thoại
st.set_page_config(page_title="Bộ Lọc TradingView Khủng", layout="centered")

st.title("🚀 Bộ Lọc & Biểu Đồ Kỹ Thuật KT2 Multi Pro")
st.write("Đồng bộ hiển thị: Cột Histogram thanh mảnh liên tục, đường Longest Wave và HDLine")

# Danh sách 120 mã cổ phiếu tốt và thanh khoản cao trên thị trường Việt Nam
symbols = [
    'OCB', 'VCB', 'TCB', 'STB', 'MBB', 'ACB', 'BID', 'CTG', 'VPB', 'HDB', 
    'VIB', 'LPB', 'SHB', 'TPB', 'MSB', 'BAB', 'EIB', 'NAB', 'SSB', 'BVB', 'ABB', 'PGB',
    'SSI', 'VND', 'VCI', 'HCM', 'FTS', 'BSI', 'MBS', 'SHS', 'AGR', 'CTS', 
    'VIX', 'ORS', 'BVS', 'TVSI', 'VDS', 'TCI',
    'HPG', 'HSG', 'NKG', 'VGS', 'SMC', 'TLH', 'POM', 'TVN',
    'VIC', 'VHM', 'VRE', 'NVL', 'PDR', 'DIG', 'CEO', 'DXG', 'KDH', 'NLG', 
    'KBC', 'IDC', 'SZC', 'VGC', 'VPI', 'DXS', 'HQC', 'IJC', 'LDG', 'SCR', 'TCH', 'ITA', 'LHG', 'TIP',
    'FPT', 'MWG', 'FRT', 'DGW', 'PNJ', 'VNM', 'MSN', 'SAB', 'MCH', 'VTP', 'PET', 'CMG', 'ELA', 'KDC', 'VOC',
    'GAS', 'PVD', 'PVS', 'POW', 'PC1', 'HDG', 'GEG', 'PVT', 'BSR', 'OIL', 'NT2', 'QTP',
    'DGC', 'DPM', 'DCM', 'CSV', 'BFC', 'GVR', 'PHR', 'DPR', 'DRI', 'DDV', 'LAS',
    'HHV', 'LCG', 'VJ_G', 'C4G', 'FCN', 'VCG',
    'ANV', 'VHC', 'DBC', 'PAN', 'TNG', 'MSH'
]

# Thanh điều hướng ẩn gọn trong Sidebar cho Mobile
filter_mode = st.sidebar.selectbox("Chế độ hiển thị:", ["Chỉ hiện mã thỏa điều kiện MUA", "Hiện tất cả danh sách (120 mã)"])

# --- CÁC HÀM TOÁN HỌC DỊCH TỪ PINE SCRIPT ---
def rma(series, period):
    return series.ewm(alpha=1/period, min_periods=period, adjust=False).mean()

def calculate_indicators(df, length=14):
    src = df['close']
    
    # 1. Tính toán Augmented RSI
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
    df['arsi'] = (arsi_num / arsi_den.replace(0, np.nan)) * 50 + 50
    
    # 2. Tính toán HDLine (Giữ đỉnh khi ARSI > 80)
    hdline = []
    current_hd = 80.0
    for arsi_val in df['arsi']:
        if pd.isna(arsi_val):
            hdline.append(80.0)
        elif arsi_val > 80:
            current_hd = arsi_val
            hdline.append(current_hd)
        else:
            current_hd = 80.0
            hdline.append(current_hd)
    df['hdline'] = hdline

    # 3. Tính toán các đường sóng Vortex và Longest Wave
    vh_short_sma   = src.rolling(window=6).mean()
    vh_long_sma    = src.rolling(window=27).mean()
    vh_longer_sma  = src.rolling(window=72).mean()
    raw_longest_wave = src.rolling(window=234).mean()
    
    vh_hist      = vh_short_sma - vh_long_sma
    vh_longh     = vh_short_sma - vh_longer_sma
    vh_longesth  = vh_short_sma - raw_longest_wave
    
    df['vh_vortex'] = (vh_hist / 3 + vh_longh / 2 + vh_longesth / 4) / 3
    
    # Chuẩn hóa Longest Wave thành dạng Oscillator đồng biên độ với Vortex Histogram
    df['longest_wave'] = ((src - raw_longest_wave) / raw_longest_wave) * 2000
    
    return df

# Nút bấm bắt đầu quét dữ liệu đặt ngay đầu trang
if st.button("🚀 Bắt đầu quét dữ liệu"):
    with st.spinner(f"Đang phân tích kỹ thuật nâng cao {len(symbols)} mã..."):
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
                
                df = calculate_indicators(df)
                
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
                
                if filter_mode == "Chỉ hiện mã thỏa điều kiện MUA" and combined_signal == "🟢 MUA":
                    matched_stocks[ticker] = df.tail(60)
                elif filter_mode == "Hiện tất cả danh sách (120 mã)":
                    matched_stocks[ticker] = df.tail(60)
                    
            except:
                continue

        # --- PHẦN HIỂN THỊ KẾT QUẢ KÈM BIỂU ĐỒ ---
        if len(all_results) > 0:
            res_df = pd.DataFrame(all_results)
            
            if filter_mode == "Chỉ hiện mã thỏa điều kiện MUA":
                display_df = res_df[res_df['Tín hiệu'] == "🟢 MUA"]
                st.subheader("🟢 Các mã xuất hiện Chấm Tín Hiệu Mua")
            else:
                display_df = res_df
                st.subheader("📋 Bảng tổng hợp thông số")
                
            if not display_df.empty:
                st.dataframe(display_df, hide_index=True)
                st.write("---")
                st.subheader("📊 Chi tiết biểu đồ xung lực dòng tiền")
                
                for ticker in display_df["Mã CP"]:
                    if ticker in matched_stocks:
                        chart_data = matched_stocks[ticker].copy()
                        
                        # Thuật toán phân tách màu sắc liên tục không đứt quãng
                        colors = []
                        vortex_vals = chart_data['vh_vortex'].values
                        
                        for i in range(len(vortex_vals)):
                            val = vortex_vals[i]
                            prev_val = vortex_vals[i-1] if i > 0 else 0
                            
                            if val >= 0:
                                if val >= prev_val:
                                    colors.append('#00c853') # Xanh lá đậm (Xu hướng tăng mạnh)
                                else:
                                    colors.append('#a5d6a7') # Xanh lá nhạt (Xu hướng tăng yếu đi)
                            else:
                                if val <= prev_val:
                                    colors.append('#d50000') # Đỏ đậm (Xu hướng giảm mạnh)
                                else:
                                    colors.append('#ef9a9a') # Đỏ nhạt (Xu hướng giảm hồi phục)
                        
                        fig = go.Figure()
                        
                        # 1. Vẽ VORTEX HISTOGRAM dạng thanh mảnh liên tục giống TradingView
                        # Thêm `width=0.5` hoặc dùng milliseconds để ép cột nhỏ lại theo mong muốn
                        fig.add_trace(go.Bar(
                            x=chart_data.index, y=chart_data['vh_vortex'],
                            marker_color=colors,
                            marker_line_width=0, # Xóa viền đen quanh cột để mượt hơn
                            width=1000 * 60 * 60 * 16, # Thu nhỏ chiều rộng cột (tính theo mili-giây đối với mốc thời gian)
                            name='Vortex Histogram', yaxis='y1'
                        ))
                        
                        # 2. Vẽ đường LONGEST WAVE uốn lượn ổn định -> Trục Y trái (Chung trục Vortex)
                        fig.add_trace(go.Scatter(
                            x=chart_data.index, y=chart_data['longest_wave'],
                            mode='lines', line=dict(color='#00e5ff', width=2, dash='solid'),
                            name='Longest Wave', yaxis='y1'
                        ))
                        
                        # 3. Vẽ đường AUGMENTED RSI màu cam -> Trục Y phải
                        fig.add_trace(go.Scatter(
                            x=chart_data.index, y=chart_data['arsi'],
                            mode='lines', line=dict(color='#ff9900', width=2),
                            name='Augmented RSI', yaxis='y2'
                        ))
                        
                        # 4. Vẽ đường HDLINE màu hồng/tím nhạt -> Trục Y phải
                        fig.add_trace(go.Scatter(
                            x=chart_data.index, y=chart_data['hdline'],
                            mode='lines', line=dict(color='#e040fb', width=1.5),
                            name='HDLine', yaxis='y2'
                        ))
                        
                        # 5. Chấm tròn tín hiệu mua màu xanh sáng dưới đáy đồ thị
                        sig_x = []
                        sig_y = []
                        for idx, row in chart_data.iterrows():
                            if row['vh_vortex'] >= 0 and row['arsi'] > 80:
                                sig_x.append(idx)
                                sig_y.append(10)
                                
                        if sig_x:
                            fig.add_trace(go.Scatter(
                                x=sig_x, y=sig_y,
                                mode='markers', marker=dict(color='#00ff66', size=9, symbol='circle'),
                                name='Chấm Mua', yaxis='y2'
                            ))
                        
                        # Thiết lập cấu hình hệ thống Đa trục cân bằng đồng bộ TradingView
                        fig.update_layout(
                            title=f"📊 Hệ thống KT2 Multi: **{ticker}**",
                            template="plotly_dark",
                            height=360,
                            margin=dict(l=40, r=40, t=40, b=20),
                            showlegend=False,
                            barmode='overlay',
                            xaxis=dict(showgrid=False),
                            yaxis=dict(
                                title="Vortex & Longest Wave",
                                side="left",
                                showgrid=True,
                                gridcolor='rgba(255,255,255,0.03)'
                            ),
                            yaxis2=dict(
                                title="ARSI / HDLine",
                                side="right",
                                overlaying="y",
                                range=[0, 110],
                                showgrid=False
                            )
                        )
                        st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Hiện tại chưa tìm thấy mã nào bùng nổ thỏa mãn chấm tín hiệu xanh.")
        else:
            st.error("Không lấy được dữ liệu thị trường, vui lòng nhấn quét lại.")
