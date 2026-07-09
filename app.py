import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime
import plotly.graph_objects as go

# Cấu hình giao diện gọn gàng, tối ưu tuyệt đối cho màn hình điện thoại
st.set_page_config(page_title="Bộ Lọc TradingView Khủng", layout="centered")

st.title("🚀 Bộ Lọc & Biểu Đồ Kỹ Thuật KT2 Multi Pro")
st.write("Đồng bộ hiển thị: Vortex dạng thanh kim đổ bóng mờ, sửa lỗi đường Longest Wave")

# Danh sách 120 mã cổ phiếu
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
    
    # 2. Tính toán HDLine
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
    df['longest_wave'] = src.rolling(window=234).mean()
    
    vh_hist      = vh_short_sma - vh_long_sma
    vh_longh     = vh_short_sma - vh_longer_sma
    vh_longesth  = vh_short_sma - df['longest_wave']
    
    df['vh_vortex'] = (vh_hist / 3 + vh_longh / 2 + vh_longesth / 4) / 3
    
    # Chuẩn hóa Longest Wave về thang đo tương đương Vortex để hiển thị chính xác trên biểu đồ
    df['longest_wave_scaled'] = (df['longest_wave'] - df['longest_wave'].rolling(60).mean()) / df['longest_wave'].rolling(60).std() * 0.3
    
    return df

# Nút bấm bắt đầu quét dữ liệu
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
                        
                        fig = go.Figure()
                        
                        # Tách mây và tính toán mốc màu sắc
                        vortex_vals = chart_data['vh_vortex'].values
                        dates = chart_data.index
                        
                        # 1. TẠO CÁC THANH KIM (THIN BARS) VORTEX ĐỔ MÀU THEO PHIÊN
                        for i in range(len(vortex_vals)):
                            val = vortex_vals[i]
                            prev_val = vortex_vals[i-1] if i > 0 else 0
                            
                            # Xác định màu sắc chuẩn xác của thanh kim
                            if abs(val) < 0.005:
                                bar_color = 'rgba(128, 128, 128, 0.1)'  # Không có lực (Xám rất mờ)
                            elif val > 0:
                                bar_color = '#00c853' if val >= prev_val else '#a5d6a7'  # Xanh đậm / Xanh nhạt
                            else:
                                bar_color = '#d50000' if val <= prev_val else '#ef9a9a'  # Đỏ đậm / Đỏ nhạt
                                
                            # Vẽ từng thanh găm mỏng (Needle Bar)
                            fig.add_trace(go.Scatter(
                                x=[dates[i], dates[i]], y=[0, val],
                                mode='lines',
                                line=dict(color=bar_color, width=1.5),
                                hoverinfo='skip', showlegend=False, yaxis='y1'
                            ))
                        
                        # 2. VẼ VÙNG ĐỔ BÓNG MỜ PHÍA DƯỚI (AREA FILL KHÔNG VIỀN)
                        vortex_p = chart_data['vh_vortex'].clip(lower=0)
                        vortex_n = chart_data['vh_vortex'].clip(upper=0)
                        
                        fig.add_trace(go.Scatter(
                            x=dates, y=vortex_p, mode='lines', line=dict(width=0),
                            fill='tozeroy', fillcolor='rgba(0, 200, 83, 0.08)', showlegend=False, yaxis='y1'
                        ))
                        fig.add_trace(go.Scatter(
                            x=dates, y=vortex_n, mode='lines', line=dict(width=0),
                            fill='tozeroy', fillcolor='rgba(213, 0, 0, 0.08)', showlegend=False, yaxis='y1'
                        ))

                        # 3. VẼ ĐƯỜNG LONGEST WAVE (Màu xanh Cyan sáng bóng dễ nhìn, bám sát vùng trung tâm)
                        fig.add_trace(go.Scatter(
                            x=dates, y=chart_data['longest_wave_scaled'],
                            mode='lines', line=dict(color='#00e5ff', width=1.5, dash='solid'),
                            name='Longest Wave', yaxis='y1'
                        ))
                        
                        # 4. VẼ TRỤC CÂN BẰNG 0
                        fig.add_trace(go.Scatter(
                            x=dates, y=[0]*len(chart_data),
                            mode='lines', line=dict(color='rgba(255,255,255,0.2)', width=1, dash='dash'),
                            showlegend=False, yaxis='y1'
                        ))
                        
                        # 5. VẼ ĐƯỜNG AUGMENTED RSI VÀ HDLINE -> Trục Y phải (0-100)
                        fig.add_trace(go.Scatter(
                            x=dates, y=chart_data['arsi'],
                            mode='lines', line=dict(color='#ff9900', width=2),
                            name='Augmented RSI', yaxis='y2'
                        ))
                        fig.add_trace(go.Scatter(
                            x=dates, y=chart_data['hdline'],
                            mode='lines', line=dict(color='#ea80fc', width=1.5),
                            name='HDLine', yaxis='y2'
                        ))
                        
                        # 6. Chấm tròn tín hiệu mua màu xanh sáng phát sáng dưới đáy
                        sig_x, sig_y = [], []
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
                        
                        # Thiết lập cấu hình đồng bộ chuẩn Darkmode
                        fig.update_layout(
                            title=f"📊 Hệ thống KT2 Multi: **{ticker}**",
                            template="plotly_dark",
                            height=360,
                            margin=dict(l=40, r=40, t=40, b=20),
                            showlegend=False,
                            xaxis=dict(showgrid=False),
                            yaxis=dict(
                                title="Vortex Pulse",
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
