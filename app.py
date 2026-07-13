import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime
import plotly.graph_objects as go
import time

# 1. CẤU HÌNH TRANG - Bắt buộc là lệnh Streamlit đầu tiên
st.set_page_config(page_title="Bộ Lọc TradingView Khủng", layout="centered")

st.title("🚀 Bộ Lọc & Biểu Đồ Kỹ Thuật KT2 Multi Pro")
st.write("Đồng bộ hiển thị: Sóng Vortex liên tục (Vortex Oscillator Waves), Longest/Longer/Short Wave, Augmented RSI và ngưỡng quá mua 80 — đúng chuẩn TradingView")

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

    # ── Section 2 (Augmented RSI, © LuxAlgo) — length mặc định 14, smoothing RMA ──
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

    # ── Section 10 (Vortex Histogram) — CHỈ dùng để xét tín hiệu MUA, không vẽ ──
    # (đúng công thức: vh_vortex = avg(hist/3, longh/2, longesth/4), không chia cho giá)
    vh_short_sma   = src.rolling(window=6).mean()
    vh_long_sma    = src.rolling(window=27).mean()
    vh_longer_sma  = src.rolling(window=72).mean()
    vh_longest_sma = src.rolling(window=234).mean()

    vh_hist     = vh_short_sma - vh_long_sma
    vh_longh    = vh_short_sma - vh_longer_sma
    vh_longesth = vh_short_sma - vh_longest_sma

    df['vh_vortex'] = (vh_hist / 3 + vh_longh / 2 + vh_longesth / 4) / 3

    # ── Section 12 (Vortex Oscillator Waves) — công thức thật của "sóng Vortex liên tục"
    # dùng để VẼ đồ thị, đúng như trên TradingView: chia cho close, nhân hệ số scaler=150 ──
    scaler = 150.0
    vo_s   = vh_short_sma
    vo_l   = vh_long_sma
    vo_lr  = vh_longer_sma
    vo_lst = vh_longest_sma

    vo_hist     = ((vo_s - vo_l)   / src) * scaler
    vo_longhist = ((vo_s - vo_lr)  / src) * scaler
    vo_longest  = ((vo_s - vo_lst) / src) * scaler

    vo_f1, vo_f2, vo_f3 = 3, 2, 4
    vo_vortexhist = (vo_hist / vo_f1 + vo_longhist / vo_f2 + vo_longest / vo_f3) / 3
    micro_ema = vo_vortexhist.ewm(span=6, adjust=False).mean()

    df['vo_hist'] = vo_hist
    df['vo_longhist'] = vo_longhist
    df['vo_longest'] = vo_longest
    df['vo_vortexhist'] = vo_vortexhist
    df['micro_ema'] = micro_ema

    return df

@st.cache_data(ttl=1800, show_spinner=False)
def download_batches(tickers_list, current_date):
    """Tải dữ liệu theo từng lô nhỏ, cache trong 30 phút để tránh gọi Yahoo Finance
    quá nhiều lần liên tiếp (nguyên nhân chính gây lỗi Rate Limit / bị chặn IP)."""
    BATCH_SIZE = 15
    batches = [tickers_list[i:i + BATCH_SIZE] for i in range(0, len(tickers_list), BATCH_SIZE)]

    raw_data_list = []
    download_errors = []

    for b_idx, batch in enumerate(batches):
        try:
            part = yf.download(
                batch,
                period="3y",
                end=current_date,
                progress=False,
                auto_adjust=True,
                threads=False,  # giảm tốc độ gọi để tránh bị rate-limit
            )
            if part is not None and not part.empty:
                raw_data_list.append(part)
        except Exception as e:
            download_errors.append(f"Lô {b_idx + 1}: {e}")
        time.sleep(3)  # nghỉ giữa các lô để tránh bị Yahoo chặn (không retry ngay để tránh bị chặn nặng hơn)

    raw_data = pd.concat(raw_data_list, axis=1) if raw_data_list else None
    return raw_data, download_errors, len(batches)


if st.button("🚀 Bắt đầu quét dữ liệu"):
    with st.spinner("Đang kết nối API Yahoo Finance và xử lý dữ liệu (dữ liệu được cache 30 phút để tránh bị chặn)..."):
        matched_stocks = {}
        all_results = []
        current_date = datetime.now().strftime('%Y-%m-%d')

        # Tạo danh sách mã có kèm hậu tố .VN
        tickers_list = tuple(f"{s}.VN" for s in symbols)

        raw_data, download_errors, n_batches = download_batches(tickers_list, current_date)

        if download_errors:
            with st.expander(f"⚠️ Chi tiết lỗi khi tải dữ liệu ({len(download_errors)}/{n_batches} lô lỗi — bấm để xem)"):
                for err in download_errors:
                    st.write(err)
                st.info("Nếu thấy nhiều lỗi 'Rate limited', Yahoo Finance đang tạm chặn IP của Streamlit Cloud. "
                        "Kết quả đã được cache 30 phút — hãy đợi một lúc rồi bấm quét lại thay vì bấm liên tục.")

        try:
            if raw_data is not None and not raw_data.empty:
                for ticker in symbols:
                    try:
                        yahoo_code = f"{ticker}.VN"
                        df = pd.DataFrame(index=raw_data.index)
                        
                        # Trích xuất dữ liệu đa tầng linh hoạt (chống lỗi định dạng cột của yfinance)
                        if isinstance(raw_data.columns, pd.MultiIndex):
                            if yahoo_code in raw_data.columns.levels[0]:
                                df['close'] = raw_data[(yahoo_code, 'Close')]
                            elif yahoo_code in raw_data.columns.levels[1]:
                                df['close'] = raw_data[('Close', yahoo_code)]
                            else:
                                continue
                        else:
                            # Trường hợp yfinance chỉ trả về 1 mã do các mã khác bị lọc sạch
                            if 'Close' in raw_data.columns:
                                df['close'] = raw_data['Close']
                            else:
                                continue
                                
                        df = df.dropna(subset=['close']).copy()
                        if len(df) < 240:
                            continue
                            
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
            st.error(f"Lỗi xử lý dữ liệu sau khi tải: {e}")

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
                        x = chart_data.index

                        # ── Section 12: Longest / Longer / Short Wave (area, đúng công thức TradingView) ──
                        fig.add_trace(go.Scatter(
                            x=x, y=(chart_data['vo_longest'] * 5).values.flatten(),
                            mode='lines', line=dict(width=1, color='#008080'),
                            fill='tozeroy', fillcolor='rgba(0, 128, 128, 0.20)',
                            name='Longest Wave', yaxis='y1'))
                        fig.add_trace(go.Scatter(
                            x=x, y=(chart_data['vo_longhist'] * 5).values.flatten(),
                            mode='lines', line=dict(width=1, color='#808000'),
                            fill='tozeroy', fillcolor='rgba(128, 128, 0, 0.20)',
                            name='Longer Wave', yaxis='y1'))
                        fig.add_trace(go.Scatter(
                            x=x, y=(chart_data['vo_hist'] * 5).values.flatten(),
                            mode='lines', line=dict(width=1, color='#FF00FF'),
                            fill='tozeroy', fillcolor='rgba(255, 0, 255, 0.20)',
                            name='Short Wave', yaxis='y1'))

                        # ── Vortex Main: sóng Vortex liên tục, xanh khi >=0, đỏ khi <0 (đúng Section 12) ──
                        vortex_main = (chart_data['vo_vortexhist'] * 5).values.flatten()
                        vortex_main_pos = np.where(vortex_main >= 0, vortex_main, np.nan)
                        vortex_main_neg = np.where(vortex_main < 0, vortex_main, np.nan)
                        fig.add_trace(go.Scatter(
                            x=x, y=vortex_main_pos, mode='lines', line=dict(width=1, color='#2e7d32'),
                            fill='tozeroy', fillcolor='rgba(0, 150, 0, 0.35)',
                            name='Vortex Main (Tăng)', yaxis='y1'))
                        fig.add_trace(go.Scatter(
                            x=x, y=vortex_main_neg, mode='lines', line=dict(width=1, color='#c62828'),
                            fill='tozeroy', fillcolor='rgba(200, 0, 0, 0.35)',
                            name='Vortex Main (Giảm)', yaxis='y1'))

                        # ── Micro EMA (đường trắng mảnh phủ lên Vortex Main) ──
                        fig.add_trace(go.Scatter(
                            x=x, y=(chart_data['micro_ema'] * 5).values.flatten(),
                            mode='lines', line=dict(color='#eeeeee', width=1),
                            name='Micro EMA', yaxis='y1'))

                        # ── Augmented RSI + ngưỡng quá mua 80 (hline tĩnh, đúng Pine, không phải HDLine giả) ──
                        fig.add_trace(go.Scatter(
                            x=x, y=chart_data['arsi'].values.flatten(),
                            mode='lines', line=dict(color='#ff8f00', width=2),
                            name='Augmented RSI', yaxis='y2'))
                        fig.add_trace(go.Scatter(
                            x=[x[0], x[-1]], y=[80, 80],
                            mode='lines', line=dict(color='#089981', width=1, dash='dot'),
                            name='ARSI Overbought (80)', yaxis='y2'))

                        # ── Chấm tín hiệu MUA (Section 11: vh_vortex >= 0 và arsi > 80) ──
                        sig_x = [idx for idx, row in chart_data.iterrows()
                                 if float(row['vh_vortex']) >= 0 and float(row['arsi']) > 80]
                        if sig_x:
                            y_floor = np.nanmin(vortex_main) if len(vortex_main) else 0
                            fig.add_trace(go.Scatter(
                                x=sig_x, y=[y_floor] * len(sig_x),
                                mode='markers', marker=dict(color='#00FF00', size=8, symbol='circle'),
                                name='Chấm Mua', yaxis='y1'))

                        fig.update_layout(
                            title=dict(text=f"📊 <b>{ticker}</b>", font=dict(size=22, color='#000000')),
                            template="plotly_white", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                            height=380, margin=dict(l=40, r=40, t=60, b=20), showlegend=True,
                            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, font=dict(size=9)),
                            xaxis=dict(showgrid=False),
                            yaxis=dict(title="Vortex Waves", side="left", showgrid=True, gridcolor='rgba(0,0,0,0.05)'),
                            yaxis2=dict(title="Augmented RSI", side="right", overlaying="y", range=[0, 110], showgrid=False)
                        )
                        st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Hiện tại chưa tìm thấy mã nào thỏa mãn chấm tín hiệu xanh.")
        else:
            st.error("Không lấy được dữ liệu thị trường từ hệ thống Yahoo Finance, vui lòng thử nhấn quét lại.")
