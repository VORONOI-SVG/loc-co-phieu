import streamlit as st
import pandas as pd
import numpy as np
import requests
from vnstock import Quote
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import plotly.graph_objects as go
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

# ── QUAN TRỌNG: chỉ áp timeout cho các request HTTP (thư viện requests mà
# vnstock dùng bên dưới), KHÔNG dùng socket.setdefaulttimeout() toàn cục —
# vì cách đó ảnh hưởng luôn tới các socket nội bộ mà Streamlit dùng để giữ
# kết nối WebSocket đẩy cập nhật UI, có thể khiến cả app trông như bị "đơ"
# ngay cả khi backend Python vẫn đang chạy bình thường.
_original_requests_request = requests.Session.request


def _requests_request_with_default_timeout(self, method, url, **kwargs):
    kwargs.setdefault('timeout', 15)
    return _original_requests_request(self, method, url, **kwargs)


requests.Session.request = _requests_request_with_default_timeout

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

skip_input = st.sidebar.text_input(
    "Mã bỏ qua (cách nhau bởi dấu phẩy):",
    value="APG",
    help="Các mã này sẽ được bỏ qua ngay lập tức, không gọi API, để tránh bị kẹt "
         "nếu mã đó đang bị VCI từ chối kết nối."
)
skip_symbols = {s.strip().upper() for s in skip_input.split(",") if s.strip()}

# ── Cấu hình quét ────────────────────────────────────────────────────────
# LƯU Ý: đã thử gọi thẳng API gốc của VCI bằng requests để né giới hạn
# 20 request/phút của vnstock (thư viện "vnai"), nhưng bị chính VCI chặn
# thẳng (403 Forbidden) vì hệ thống chống bot của họ không chấp nhận request
# thiếu các đặc điểm "giống trình duyệt thật" mà vnstock xử lý được. Nên đã
# QUAY LẠI dùng vnstock, và chấp nhận tôn trọng đúng giới hạn 20 request/phút
# thay vì cố né — né không thành công còn dễ bị chặn nặng hơn.
REQUEST_TIMEOUT = 15     # giây, timeout cho mỗi request (áp qua requests.Session ở trên)
HARD_TIMEOUT_SEC = 20    # giây, timeout CỨNG cho mỗi mã (kể cả nếu bị treo thật sự,
                         # không chỉ báo lỗi bình thường) — quá thời gian sẽ tự bỏ qua
MIN_INTERVAL_SEC = 3.2   # ~18.75 request/phút — dưới ngưỡng 20/phút của vnstock,
                         # chừa khoảng đệm an toàn cho các lần gọi khác (vd nút chẩn đoán)
NEEDED_BARS = 300        # đủ cho SMA 234 + tail 60, không cần tải 3 năm dữ liệu


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


def fetch_one_stock_raw(symbol, start_date, end_date):
    """Gọi qua vnstock (Quote). Đã thử gọi thẳng API gốc của VCI bằng requests
    để né giới hạn 20 request/phút của vnstock, nhưng bị chính VCI chặn thẳng
    (403 Forbidden — hệ thống chống bot của họ không chấp nhận request không
    đủ 'giống trình duyệt thật'). Nên quay lại dùng vnstock — thư viện này xử
    lý được phần chống bot đó — và tôn trọng đúng giới hạn 20 request/phút
    thay vì cố né.
    random_agent=True: đổi User-Agent ngẫu nhiên mỗi lần gọi.
    Hàm này chạy trong luồng nền (để enforce timeout cứng), nên KHÔNG được
    đụng tới st.cache_data hay bất kỳ API nào của Streamlit."""
    df = Quote(symbol=symbol, source='VCI', random_agent=True).history(
        start=start_date, end=end_date, interval='1D'
    )
    if df is None or df.empty:
        return None
    df = df.rename(columns={'time': 'date'})
    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date').sort_index()
    if 'close' not in df.columns:
        return None
    return df[['close']].copy()



def get_cache_key(symbol, start_date, end_date):
    return f"stockcache:{symbol}:{start_date}:{end_date}"


def get_cached_stock(symbol, start_date, end_date):
    """Cache TỰ QUẢN LÝ qua st.session_state (không dùng st.cache_data), vì
    st.cache_data có thể gây treo nếu bị gọi từ một luồng không phải luồng
    chính — điều mà cơ chế timeout cứng bên dưới buộc phải làm.
    Chỉ nên gọi hàm này từ LUỒNG CHÍNH của Streamlit."""
    if "stock_cache" not in st.session_state:
        st.session_state["stock_cache"] = {}
    key = get_cache_key(symbol, start_date, end_date)
    entry = st.session_state["stock_cache"].get(key)
    if entry is not None:
        cached_time, df = entry
        if time.time() - cached_time < 1800:  # TTL 30 phút, giống bản cũ
            return df
    return "__MISS__"


def set_cached_stock(symbol, start_date, end_date, df):
    key = get_cache_key(symbol, start_date, end_date)
    st.session_state["stock_cache"][key] = (time.time(), df)


def is_connection_error(err_msg: str) -> bool:
    """Nhận diện lỗi kết nối/timeout (khả năng do VCI giới hạn tốc độ tạm thời)
    để đưa vào hàng đợi thử lại, thay vì các lỗi khác (vd: mã không tồn tại)."""
    keywords = ["ConnectionError", "RetryError", "Timeout", "timed out", "Connection"]
    return any(k.lower() in err_msg.lower() for k in keywords)


if st.button("🔍 Chẩn đoán: thử tải riêng 1 mã (APH) qua vnstock"):
    import traceback
    test_symbol = "APH"
    vn_now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))
    end_date = (vn_now + timedelta(days=1)).strftime('%Y-%m-%d')
    start_date = (vn_now - timedelta(days=int(NEEDED_BARS * 1.6))).strftime('%Y-%m-%d')
    st.write(f"Đang gọi vnstock (Quote) cho mã `{test_symbol}` (start='{start_date}', end='{end_date}') ...")
    t0 = time.monotonic()
    try:
        df_test = fetch_one_stock_raw(test_symbol, start_date, end_date)
        elapsed = time.monotonic() - t0
        st.success(f"✅ Thành công sau {elapsed:.1f} giây. Số dòng dữ liệu: {len(df_test) if df_test is not None else 0}")
        if df_test is not None:
            st.dataframe(df_test.tail(5))
    except Exception as e:
        elapsed = time.monotonic() - t0
        st.error(f"❌ Lỗi sau {elapsed:.1f} giây: {e}")
        with st.expander("Xem traceback đầy đủ"):
            st.code(traceback.format_exc())

if st.button("🚀 Bắt đầu quét dữ liệu"):
    if skip_symbols:
        st.caption(f"⏭️ Sẽ bỏ qua: {', '.join(sorted(skip_symbols))}")
    scan_symbols = [s for s in symbols if s not in skip_symbols]
    st.info(f"⏳ Đang quét tuần tự {len(scan_symbols)} mã (giãn cách {MIN_INTERVAL_SEC}s/mã theo giới hạn "
            f"tốc độ của vnstock miễn phí, ước tính {len(scan_symbols)*MIN_INTERVAL_SEC/60:.0f} phút, "
            f"chưa kể thời gian thử lại nếu có mã bị lỗi kết nối). Mỗi mã có timeout cứng "
            f"{HARD_TIMEOUT_SEC}s — quá thời gian sẽ tự bỏ qua, không đợi vô thời hạn nữa. "
            f"Kết quả sẽ hiện dần bên dưới.")

    vn_now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))
    end_date = (vn_now + timedelta(days=1)).strftime('%Y-%m-%d')
    # Chỉ tải đủ số phiên cần thiết (SMA 234 + tail 60) thay vì 3 năm => request nhẹ và nhanh hơn
    start_date = (vn_now - timedelta(days=int(NEEDED_BARS * 1.6))).strftime('%Y-%m-%d')

    progress_bar = st.progress(0, text="Chuẩn bị tải dữ liệu...")
    table_placeholder = st.empty()
    charts_header_placeholder = st.empty()

    all_results = []
    matched_stocks = {}
    fetch_errors = []
    connection_error_symbols = []  # mã lỗi kết nối -> sẽ thử lại ở cuối

    total = len(scan_symbols)

    # Dùng vài luồng dự phòng (không phải chạy song song thật sự — ta vẫn submit
    # tuần tự từng mã một). Lý do cần hơn 1 luồng: nếu vnstock/vnai tự chờ nội bộ
    # khi bị rate-limit (có thể tới 50-60s) và ta đã bỏ cuộc chờ sau HARD_TIMEOUT_SEC,
    # luồng đó vẫn bận cho tới khi xong — nếu chỉ có 1 luồng, mã tiếp theo sẽ phải
    # xếp hàng chờ luồng cũ giải phóng, gây cảm giác "đơ" y hệt bị treo thật.
    hard_timeout_executor = ThreadPoolExecutor(max_workers=4)

    def fetch_with_hard_timeout(symbol, start_date, end_date):
        cached = get_cached_stock(symbol, start_date, end_date)  # đọc cache ở LUỒNG CHÍNH
        if cached != "__MISS__":
            return cached
        # Chỉ hàm THUẦN (không đụng st.cache_data) mới chạy trong luồng nền
        fut = hard_timeout_executor.submit(fetch_one_stock_raw, symbol, start_date, end_date)
        df = fut.result(timeout=HARD_TIMEOUT_SEC)
        set_cached_stock(symbol, start_date, end_date, df)  # ghi cache ở LUỒNG CHÍNH
        return df

    def is_rate_limit_error(err_msg: str) -> bool:
        keywords = ["RateLimitExceeded", "GIỚI HẠN API", "rate limit", "20/20"]
        return any(k.lower() in err_msg.lower() for k in keywords)

    def process_symbol(symbol, done_count, total_for_progress):
        """Tải + tính chỉ báo cho 1 mã. Trả về True nếu nên đưa vào hàng đợi thử lại."""
        t0 = time.monotonic()
        try:
            df = fetch_with_hard_timeout(symbol, start_date, end_date)
            err = None
        except FutureTimeoutError:
            df, err = None, f"Timeout cứng sau {HARD_TIMEOUT_SEC}s — bỏ qua"
        except Exception as e:
            df, err = None, str(e)

        if err and is_rate_limit_error(err):
            # Đã chạm giới hạn 20 request/phút của vnstock (gói Khách/Guest).
            # Nghỉ hẳn 65 giây để khung 1 phút được reset, thay vì chỉ giãn
            # cách bình thường rồi lại dính tiếp ngay lập tức.
            progress_bar.progress(
                min(done_count / total_for_progress, 1.0),
                text=f"⏸️ Đã chạm giới hạn 20 request/phút của vnstock. Nghỉ 65 giây cho reset "
                     f"(mã {symbol})..."
            )
            time.sleep(65)
        else:
            elapsed = time.monotonic() - t0
            remaining_wait = MIN_INTERVAL_SEC - elapsed
            if remaining_wait > 0:
                time.sleep(remaining_wait)

        progress_bar.progress(
            min(done_count / total_for_progress, 1.0),
            text=f"Đã xử lý {done_count}/{total_for_progress} lượt gọi (gần nhất: {symbol})..."
        )

        if err:
            fetch_errors.append(f"{symbol}: {err}")
            return is_connection_error(err) or is_rate_limit_error(err)
        if df is None or df.dropna(subset=['close']).shape[0] < 240:
            return False

        try:
            df2 = df.dropna(subset=['close']).copy()
            df2 = calculate_indicators(df2)

            latest = df2.iloc[-1]
            arsi_val = float(latest['arsi']) if not pd.isna(latest['arsi']) else 0.0
            vortex_val = float(latest['vh_vortex']) if not pd.isna(latest['vh_vortex']) else 0.0
            close_val = float(latest['close']) if not pd.isna(latest['close']) else 0.0

            vh_green_rising = vortex_val >= 0
            arsi_over_80 = arsi_val > 80
            combined_signal = "🟢 MUA" if (vh_green_rising and arsi_over_80) else "⚪ Chờ"

            res_item = {
                "Mã CP": symbol,
                "Ngày dữ liệu": df2.index[-1].strftime('%d/%m/%Y'),
                "Giá Đóng (VNĐ)": round(close_val, 0),
                "Augmented RSI": round(arsi_val, 2),
                "Vortex Histo Wave": round(vortex_val, 2),
                "Tín hiệu": combined_signal
            }
            all_results.append(res_item)

            if "150 mã" in filter_mode:
                matched_stocks[symbol] = df2.tail(60)
            elif filter_mode == "Chỉ hiện mã thỏa điều kiện MUA" and combined_signal == "🟢 MUA":
                matched_stocks[symbol] = df2.tail(60)

            if done_count % 5 == 0 or done_count == total_for_progress:
                res_df_live = pd.DataFrame(all_results)
                if "Chỉ hiện mã thỏa điều kiện MUA" in filter_mode:
                    display_live = res_df_live[res_df_live['Tín hiệu'] == "🟢 MUA"]
                else:
                    display_live = res_df_live
                if not display_live.empty:
                    table_placeholder.dataframe(display_live, hide_index=True)
        except Exception:
            pass
        return False

    # ── Lượt 1: quét toàn bộ danh sách ──────────────────────────────────────
    step = 0
    for symbol in scan_symbols:
        step += 1
        should_retry = process_symbol(symbol, step, total)
        if should_retry:
            connection_error_symbols.append(symbol)

    # ── Lượt 2: nghỉ một chút rồi thử lại các mã bị lỗi kết nối ─────────────
    # (lỗi ConnectionError từ VCI thường chỉ là chặn/giới hạn tạm thời, nên
    # nghỉ ~20 giây cho hạ nhiệt trước khi thử lại thường sẽ thành công hơn)
    if connection_error_symbols:
        st.warning(f"⏸️ Có {len(connection_error_symbols)} mã bị lỗi kết nối ở lượt 1 "
                   f"({', '.join(connection_error_symbols[:10])}{'...' if len(connection_error_symbols) > 10 else ''}). "
                   f"Đang nghỉ 20 giây rồi thử lại...")
        time.sleep(20)
        retry_total = total + len(connection_error_symbols)
        for symbol in connection_error_symbols:
            step += 1
            process_symbol(symbol, step, retry_total)

    progress_bar.empty()
    hard_timeout_executor.shutdown(wait=False)  # không đợi các luồng bị bỏ cuộc (nếu có) thoát hẳn

    if fetch_errors:
        with st.expander(f"⚠️ Chi tiết lỗi khi tải dữ liệu ({len(fetch_errors)}/{len(scan_symbols)} mã lỗi — bấm để xem)"):
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
