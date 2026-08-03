import streamlit as st
import pandas as pd
import numpy as np
import socket
from vnstock import Quote
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import plotly.graph_objects as go
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── QUAN TRỌNG: đặt timeout ở tầng socket của hệ điều hành ──────────────────
# vnstock (dùng requests bên dưới) không tự đặt timeout cho request mạng,
# nên nếu server không phản hồi, kết nối có thể treo VÔ THỜI HẠN và không
# cách nào huỷ được từ phía Python (kể cả dùng future.result(timeout=...)).
# socket.setdefaulttimeout ép TẤT CẢ socket mới tạo trong tiến trình này
# (bao gồm cả bên trong vnstock/requests/urllib3) phải timeout sau N giây.
socket.setdefaulttimeout(15)

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

# ── Cấu hình quét đồng thời có kiểm soát tốc độ ─────────────────────────────
MAX_WORKERS = 5          # số luồng tải song song
REQUEST_TIMEOUT = 15     # giây, timeout cứng cho MỖI request — tránh treo cả app vì 1 mã lỗi mạng
MIN_INTERVAL_SEC = 3.0   # khoảng cách tối thiểu giữa các lần "cấp phép gọi API" -> ~20 req/phút
NEEDED_BARS = 300        # đủ cho SMA 234 + tail 60, không cần tải 3 năm dữ liệu


class RateLimiter:
    """Token-bucket đơn giản, dùng chung giữa các luồng để không vượt quá
    giới hạn ~20 request/phút của vnstock bản miễn phí, kể cả khi chạy song song.
    QUAN TRỌNG: chỉ giữ lock để ĐỌC/GHI last_call, KHÔNG sleep trong lúc giữ lock —
    nếu không, mọi luồng khác sẽ bị chặn cứng theo, triệt tiêu hết lợi ích chạy song song
    và làm tăng nguy cơ nghẽn dây chuyền khi có 1 luồng gặp sự cố."""
    def __init__(self, min_interval):
        self.min_interval = min_interval
        self.lock = threading.Lock()
        self.last_call = 0.0

    def wait(self):
        with self.lock:
            now = time.monotonic()
            wait_time = self.last_call + self.min_interval - now
            self.last_call = max(now, self.last_call) + (self.min_interval if wait_time > 0 else 0)
        if wait_time > 0:
            time.sleep(wait_time)


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

    vh_short_sma   = src.rolling(window=6).mean()
    vh_long_sma    = src.rolling(window=27).mean()
    vh_longer_sma  = src.rolling(window=72).mean()
    vh_longest_sma = src.rolling(window=234).mean()

    vh_hist     = vh_short_sma - vh_long_sma
    vh_longh    = vh_short_sma - vh_longer_sma
    vh_longesth = vh_short_sma - vh_longest_sma

    df['vh_vortex'] = (vh_hist / 3 + vh_longh / 2 + vh_longesth / 4) / 3

    scaler = 150.0
    vo_s, vo_l, vo_lr, vo_lst = vh_short_sma, vh_long_sma, vh_longer_sma, vh_longest_sma

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
def fetch_one_stock(symbol, start_date, end_date):
    """Cache TỪNG mã riêng lẻ (thay vì cả batch) để bấm quét lại không phải
    tải lại toàn bộ 150 mã nếu đã có mã nào đó còn hạn cache."""
    df = Quote(symbol=symbol, source='VCI').history(start=start_date, end=end_date, interval='1D')
    if df is None or df.empty:
        return None
    df = df.rename(columns={'time': 'date'})
    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date').sort_index()
    if 'close' not in df.columns:
        return None
    return df[['close']].copy()


def fetch_with_timeout(symbol, start_date, end_date, limiter):
    """Gọi fetch_one_stock. Việc treo mạng vô thời hạn đã được chặn ở tầng
    socket.setdefaulttimeout() phía trên, nên ở đây chỉ cần bắt Exception thường."""
    limiter.wait()
    try:
        return symbol, fetch_one_stock(symbol, start_date, end_date), None
    except Exception as e:
        return symbol, None, str(e)


if st.button("🚀 Bắt đầu quét dữ liệu"):
    st.info(f"⏳ Đang quét {len(symbols)} mã song song (tối đa {MAX_WORKERS} luồng cùng lúc, "
            f"mỗi mã timeout {REQUEST_TIMEOUT}s để không bị treo cả app). Kết quả sẽ hiện dần bên dưới.")

    vn_now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))
    end_date = (vn_now + timedelta(days=1)).strftime('%Y-%m-%d')
    # Chỉ tải đủ số phiên cần thiết (SMA 234 + tail 60) thay vì 3 năm => request nhẹ và nhanh hơn
    start_date = (vn_now - timedelta(days=int(NEEDED_BARS * 1.6))).strftime('%Y-%m-%d')

    progress_bar = st.progress(0, text="Chuẩn bị tải dữ liệu...")
    status_area = st.empty()
    table_placeholder = st.empty()
    charts_header_placeholder = st.empty()

    all_results = []
    matched_stocks = {}
    fetch_errors = []

    limiter = RateLimiter(MIN_INTERVAL_SEC)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:

        future_map = {
            pool.submit(fetch_with_timeout, sym, start_date, end_date, limiter): sym
            for sym in symbols
        }

        done_count = 0
        total = len(symbols)

        for fut in as_completed(future_map):
            sym = future_map[fut]
            done_count += 1
            try:
                symbol, df, err = fut.result()
            except Exception as e:
                symbol, df, err = sym, None, str(e)

            progress_bar.progress(done_count / total, text=f"Đã xử lý {done_count}/{total} mã (gần nhất: {symbol})...")

            if err:
                fetch_errors.append(f"{symbol}: {err}")
                continue
            if df is None or df.dropna(subset=['close']).shape[0] < 240:
                continue

            try:
                df = df.dropna(subset=['close']).copy()
                df = calculate_indicators(df)

                latest = df.iloc[-1]
                arsi_val = float(latest['arsi']) if not pd.isna(latest['arsi']) else 0.0
                vortex_val = float(latest['vh_vortex']) if not pd.isna(latest['vh_vortex']) else 0.0
                close_val = float(latest['close']) if not pd.isna(latest['close']) else 0.0

                vh_green_rising = vortex_val >= 0
                arsi_over_80 = arsi_val > 80
                combined_signal = "🟢 MUA" if (vh_green_rising and arsi_over_80) else "⚪ Chờ"

                res_item = {
                    "Mã CP": symbol,
                    "Ngày dữ liệu": df.index[-1].strftime('%d/%m/%Y'),
                    "Giá Đóng (VNĐ)": round(close_val, 0),
                    "Augmented RSI": round(arsi_val, 2),
                    "Vortex Histo Wave": round(vortex_val, 2),
                    "Tín hiệu": combined_signal
                }
                all_results.append(res_item)

                if "150 mã" in filter_mode:
                    matched_stocks[symbol] = df.tail(60)
                elif filter_mode == "Chỉ hiện mã thỏa điều kiện MUA" and combined_signal == "🟢 MUA":
                    matched_stocks[symbol] = df.tail(60)

                # Cập nhật bảng kết quả định kỳ (mỗi 5 mã) thay vì MỖI mã một lần —
                # gửi cập nhật UI quá dồn dập qua WebSocket có thể làm nghẽn kết nối
                # trên các phiên mạng yếu/không ổn định.
                if done_count % 5 == 0 or done_count == total:
                    res_df_live = pd.DataFrame(all_results)
                    if "Chỉ hiện mã thỏa điều kiện MUA" in filter_mode:
                        display_live = res_df_live[res_df_live['Tín hiệu'] == "🟢 MUA"]
                    else:
                        display_live = res_df_live
                    if not display_live.empty:
                        table_placeholder.dataframe(display_live, hide_index=True)

            except Exception:
                continue

    progress_bar.empty()
    status_area.empty()

    if fetch_errors:
        with st.expander(f"⚠️ Chi tiết lỗi khi tải dữ liệu ({len(fetch_errors)}/{len(symbols)} mã lỗi — bấm để xem)"):
            for err in fetch_errors:
                st.write(err)

    # --- HIỂN THỊ KẾT QUẢ CUỐI CÙNG KÈM ĐỒ THỊ ---
    if len(all_results) > 0:
        res_df = pd.DataFrame(all_results)

        if "Chỉ hiện mã thỏa điều kiện MUA" in filter_mode:
            display_df = res_df[res_df['Tín hiệu'] == "🟢 MUA"]
            charts_header_placeholder.subheader("🟢 Các mã xuất hiện Chấm Tín Hiệu Mua")
        else:
            display_df = res_df
            charts_header_placeholder.subheader(f"📋 Bảng tổng hợp thông số ({len(all_results)} mã)")

        if not display_df.empty:
            table_placeholder.dataframe(display_df, hide_index=True)
            st.write("---")
            st.subheader("📊 Chi tiết biểu đồ xung lực dòng tiền")

            for ticker in display_df["Mã CP"]:
                if ticker in matched_stocks:
                    chart_data = matched_stocks[ticker].copy()
                    fig = go.Figure()
                    x = chart_data.index

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

                    fig.add_trace(go.Scatter(
                        x=x, y=(chart_data['micro_ema'] * 5).values.flatten(),
                        mode='lines', line=dict(color='#eeeeee', width=1),
                        name='Micro EMA', yaxis='y1'))

                    fig.add_trace(go.Scatter(
                        x=x, y=chart_data['arsi'].values.flatten(),
                        mode='lines', line=dict(color='#ff8f00', width=2),
                        name='Augmented RSI', yaxis='y2'))
                    fig.add_trace(go.Scatter(
                        x=[x[0], x[-1]], y=[80, 80],
                        mode='lines', line=dict(color='#089981', width=1, dash='dot'),
                        name='ARSI Overbought (80)', yaxis='y2'))

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
        st.error("Không lấy được dữ liệu thị trường từ vnstock, vui lòng thử nhấn quét lại sau ít phút.")
