import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime
import plotly.graph_objects as go

# 1. CẤU HÌNH TRANG - Bắt buộc là lệnh Streamlit đầu tiên
st.set_page_config(page_title="Bộ Lọc TradingView Khủng", layout="centered")

st.title("🚀 Bộ Lọc & Biểu Đồ Kỹ Thuật KT2 Multi Pro")
st.write("Đồng bộ hiển thị: Sóng Vortex liên tục, đường Longest Wave và HDLine chuẩn TradingView")

# Danh sách 150 mã cổ phiếu tiêu chuẩn Việt Nam
symbols = [
    'OCB', 'VCB', 'TCB', 'STB', 'MBB', 'ACB', 'BID', 'CTG', 'VPB', 'HDB', 
    'VIB', 'LPB', 'SHB', 'TPB', 'MSB', 'BAB', 'EIB', 'NAB', 'SSB', 'BVB', 
    'ABB', 'PGB', 'KLB', 'SGB', 'VAB', 'SSI', 'VND', 'VCI', 'HCM', 'FTS', 
    'BSI', 'MBS', 'SHS', 'AGR', 'CTS', 'VIX', 'ORS', 'BVS', 'TVSI', 'VDS', 
    'TCI', 'PSI', 'APG', 'SBS', 'WSS', 'HPG', 'HSG', 'NKG', 'VGS', 'SMC', 
    'TLH', 'POM', 'TVN', 'KKC', 'VNS', 'VIC', 'VHM', 'VRE', 'NVL', 'PDR', 
    'DIG', 'CEO', 'DXG', 'KDH', 'NLG', 'VPI', 'DXS', 'HQC', 'IJC', 'LDG', 
    'SCR', 'TCH', 'ITA', 'HDG', 'CRE', 'KHG', 'NHA', 'AGG', 'QCG', 'NTL', 
    'KBC', 'IDC', 'SZC', 'VGC', 'LHG', 'TIP', 'PHR', 'DPR', 'D2D', 'SIP', 
    'FPT', 'MWG', 'FRT', 'DGW', 'PNJ', 'VNM', 'MSN', 'SAB', 'MCH', 'VTP', 
    'PET', 'CMG', 'ELA', 'KDC', 'VOC', 'HAX', 'GAS', 'PVD', 'PVS', 'POW', 
    'PC1', 'GEG', 'PVT', 'BSR', 'OIL', 'NT2', 'QTP', 'TV2', 'HND', 'VSH', 
    'SAM', 'DGC', 'DPM', 'DCM', 'CSV', 'BFC', 'GVR', 'DRI', 'DDV', 'LAS', 
    'APH', 'HHV', 'LCG', 'VJC', 'C4G', 'FCN', 'VCG', 'CII', 'HT1', 'BCC', 
    'KSB', 'ANV', 'VHC', 'DBC', 'PAN', 'TNG', 'MSH', 'FMC', 'CMX', 'IDI', 
    'BAF', 'HNG'
]

symbols = sorted(list(set(symbols)))

filter_mode = st.sidebar.selectbox("Chế độ hiển thị:", ["Chỉ hiện mã thỏa điều kiện MUA", "Hiện tất cả danh sách (150 mã)"])

def rma(series, period):
    return series.ewm(alpha=1/period, min_periods=period, adjust=False).mean()

def calculate_indicators(df, length=14):
    src = pd.Series(df['close'].values.flatten(), index=df.index)
    
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

    vh_short_sma   = src.rolling(window=6).mean()
    vh_long_sma    = src.rolling(window=27).mean()
    vh_longer_sma  = src.rolling(window=72).mean()
    raw_longest_wave = src.rolling(window=234).mean()
    
    vh_hist      = vh_short_sma - vh_long_sma
    vh_longh     = vh_short_sma - vh_longer_sma
    vh_longesth  = vh_short_sma - raw_longest_wave
    
    df['vh_vortex'] = (vh_hist / 3 + vh_longh / 2 + vh_longesth / 4) / 3
    df['longest_wave'] = ((src - raw_longest_wave) / raw_longest_wave) * 2000
    
    return df

if st.button("🚀 Bắt đầu quét dữ liệu"):
    with st.spinner("Đang tải dữ liệu hàng loạt từ Yahoo Finance (Tốc độ cao)..."):
        matched_stocks = {}
        all_results = []
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        # Gom toàn bộ mã thành chuỗi cách nhau bởi dấu cách để tải 1 lần duy nhất
        tickers_string = " ".join([f"{s}.VN" for s in symbols])
        
        try:
            # Tải đồng thời tất cả các mã để tránh bị block IP trên Cloud
            raw_data = yf.download(tickers_string, period="3y", end=current_date, group_by='ticker', progress=False)
            
            if raw_data is not None and not raw_data.empty:
                for ticker in symbols:
                    try:
                        yahoo_code = f"{ticker}.VN"
                        
                        # Kiểm tra xem mã đó có dữ liệu trong bảng tổng hợp không
                        if yahoo_code in raw_data.columns.levels[0]:
                            df = raw_data[yahoo_code].dropna(subset=['Close']).copy()
                        else:
                            continue
                            
                        if len(df) < 240:
                            continue
                            
                        # Chuẩn hóa tên cột về chữ thường
                        df.columns = [str(col).lower() for col in df.columns]
                        
                        df = calculate_indicators(df)
                        
                        latest = df.iloc[-1]
                        arsi_val = float(latest['arsi']) if not pd.isna(latest['arsi']) else 0.0
                        vortex_val = float(latest['vh_vortex']) if not pd.isna(latest['vh_vortex']) else 0.0
                        close_val = float(latest['close']) if not pd.isna(latest['close']) else 0.0
                        
                        vh_green_rising = vortex_val >= 0
                        arsi_over_80    = arsi_val > 80
                        combined_signal = "🟢 MUA" if (vh_green_rising and arsi_over_80) else "⚪ Chờ"
                        
                        res_item = {
                            "Mã CP": ticker,
                            "Giá Đóng (VNĐ)": round(close_val, 0),
                            "Augmented RSI": round(arsi_val, 2),
                            "Vortex Histo Wave": round(vortex_val, 2),
                            "Tín hiệu": combined_signal
                        }
                        all_results.append(res_item)
                        
                        if "150 mã" in filter_mode:
                            matched_stocks[ticker] = df.tail(60)
                        elif filter_mode == "Chỉ hiện mã thỏa điều kiện MUA" and combined_signal == "🟢 MUA":
                            matched_stocks[ticker] = df.tail(60)
                    except:
                        continue
        except Exception as e:
            st.error(f"Lỗi hệ thống khi kết nối API: {str(e)}")

        # --- HIỂN THỊ KẾT QUẢ KÈM ĐỒ THỊ ---
        if len(all_results) > 0:
            res_df = pd.DataFrame(all_results)
            
            if "Chỉ hiện mã thỏa điều kiện MUA" in filter_mode:
                display_df = res_df[res_df['Tín hiệu'] == "🟢 MUA"]
                st.subheader("🟢 Các mã xuất hiện Chấm Tín Hiệu Mua")
            else:
                display_df = res_df
                st.subheader(f"📋 Bảng tổng hợp thông số ({len(all_results)} mã)")
                
            if not display_df.empty:
                st.dataframe(display_df, hide_index=True)
                st.write("---")
                st.subheader("📊 Chi tiết biểu đồ xung lực dòng tiền")
                
                for ticker in display_df["Mã CP"]:
                    if ticker in matched_stocks:
                        chart_data = matched_stocks[ticker].copy()
                        fig = go.Figure()
                        
                        vortex_p = chart_data['vh_vortex'].clip(lower=0).values.flatten()
                        vortex_n = chart_data['vh_vortex'].clip(upper=0).values.flatten()
                        
                        fig.add_trace(go.Scatter(x=chart_data.index, y=vortex_p, mode='lines', line=dict(width=0), fill='tozeroy', fillcolor='rgba(0, 180, 50, 0.08)', yaxis='y1'))
                        fig.add_trace(go.Scatter(x=chart_data.index, y=vortex_n, mode='lines', line=dict(width=0), fill='tozeroy', fillcolor='rgba(230, 30, 30, 0.08)', yaxis='y1'))
                        
                        vortex_vals = chart_data['vh_vortex'].values.flatten()
                        for i in range(len(vortex_vals)):
                            val = vortex_vals[i]
                            prev_val = vortex_vals[i-1] if i > 0 else 0
                            idx = chart_data.index[i]
                            col = '#00aa3c' if val >= prev_val else '#81c784' if val >= 0 else '#b71c1c' if val <= prev_val else '#e57373'
                            fig.add_trace(go.Scatter(x=[idx, idx], y=[0, val], mode='lines', line=dict(color=col, width=1.5), hoverinfo='skip', showlegend=False, yaxis='y1'))
                        
                        fig.add_trace(go.Scatter(x=chart_data.index, y=chart_data['longest_wave'].values.flatten(), mode='lines', line=dict(color='#00b8d4', width=2), name='Longest Wave', yaxis='y1'))
                        fig.add_trace(go.Scatter(x=chart_data.index, y=chart_data['arsi'].values.flatten(), mode='lines', line=dict(color='#ff8f00', width=2), name='Augmented RSI', yaxis='y2'))
                        fig.add_trace(go.Scatter(x=chart_data.index, y=chart_data['hdline'].values.flatten(), mode='lines', line=dict(color='#c51162', width=1.5), name='HDLine', yaxis='y2'))
                        
                        sig_x = [idx for idx, row in chart_data.iterrows() if float(row['vh_vortex']) >= 0 and float(row['arsi']) > 80]
                        if sig_x:
                            fig.add_trace(go.Scatter(x=sig_x, y=[10]*len(sig_x), mode='markers', marker=dict(color='#00e676', size=9), name='Chấm Mua', yaxis='y2'))
                        
                        fig.update_layout(
                            title=dict(text=f"📊 <b>{ticker}</b>", font=dict(size=22, color='#000000')),
                            template="plotly_white", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                            height=360, margin=dict(l=40, r=40, t=60, b=20), showlegend=False,
                            xaxis=dict(showgrid=False),
                            yaxis=dict(title="Vortex Pulse", side="left", showgrid=True, gridcolor='rgba(0,0,0,0.05)'),
                            yaxis2=dict(title="ARSI / HDLine", side="right", overlaying="y", range=[0, 110], showgrid=False)
                        )
                        st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Hiện tại chưa tìm thấy mã nào thỏa mãn chấm tín hiệu xanh.")
        else:
            st.error("Không lấy được dữ liệu thị trường từ hệ thống Yahoo Finance, vui lòng nhấn quét lại.")
