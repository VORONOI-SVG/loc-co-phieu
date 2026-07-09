import streamlit as st
import pandas as pd
import ta
import requests

# Cấu hình giao diện gọn gàng cho điện thoại
st.set_page_config(page_title="Bộ Lọc Cổ Phiếu", layout="centered")

st.title("📊 Bộ Lọc Cổ Phiếu Việt Nam")
st.write("Ứng dụng chạy trên mọi thiết bị (PC / Điện thoại)")

# Danh sách các mã cổ phiếu phổ biến
symbols = ['FPT', 'SSI', 'VNM', 'HPG', 'VIC', 'VCB', 'TCB', 'MWG', 'DGC', 'STB']

# Giao diện tùy chỉnh bên góc màn hình
st.sidebar.header("⚙️ Cấu hình bộ lọc")
filter_type = st.sidebar.selectbox("Chọn chỉ báo muốn lọc:", ["RSI (Quá bán / Quá mua)", "Đường xu hướng MA20"])

# Nút bấm bắt đầu quét dữ liệu
if st.button("🚀 Bắt đầu quét dữ liệu"):
    with st.spinner("Đang kết nối thẳng tới nguồn dữ liệu sàn chứng khoán..."):
        results = []
        
        for ticker in symbols:
            try:
                # Nguồn API công khai dự phòng, chấp nhận mọi kết nối từ Cloud
                url = f"https://s.cafef.vn/Ajax/PageNew/Data/TradeHistory.ashx?symbol={ticker}&page=1&size=50"
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
                
                response = requests.get(url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    data = response.json().get('Data', [])
                    if not data:
                        continue
                        
                    # Chuyển đổi dữ liệu thô thành bảng số liệu
                    df = pd.DataFrame(data)
                    
                    # Trích xuất giá đóng cửa (Cafef dùng cột 'Price' hoặc 'GiaDongCua')
                    # Đảm bảo ép kiểu dữ liệu về dạng số để tính toán
                    df['close'] = pd.to_numeric(df['Price'], errors='coerce')
                    
                    # Đảo chuỗi thời gian từ cũ đến mới để chỉ báo kỹ thuật tính đúng
                    df = df.iloc[::-1].reset_index(drop=True)
                    
                    # Kiểm tra số lượng dòng dữ liệu hợp lệ
                    if len(df) < 20:
                        continue
                        
                    # Tính toán RSI và MA20
                    df['RSI'] = ta.momentum.rsi(df['close'], window=14)
                    df['MA20'] = ta.trend.sma_indicator(df['close'], window=20)
                    
                    # Lấy phiên mới nhất
                    latest = df.iloc[-1]
                    
                    results.append({
                        "Mã CP": ticker,
                        "Giá Đóng": latest['close'] * 1000 if latest['close'] < 200 else latest['close'], # Chuẩn hóa đơn vị giá VNĐ
                        "RSI": round(latest['RSI'], 2) if not pd.isna(latest['RSI']) else 0,
                        "MA20": round(latest['MA20'] * 1000 if latest['MA20'] < 200 else latest['MA20'], 2) if not pd.isna(latest['MA20']) else 0
                    })
            except:
                continue

        # Hiển thị kết quả ra màn hình
        if len(results) > 0:
            res_df = pd.DataFrame(results)
            st.subheader("📋 Kết quả lọc toàn bộ danh sách")
            st.dataframe(res_df) 
            
            st.divider() 
            
            if filter_type == "RSI (Quá bán / Quá mua)":
                st.write("**⚠️ Vùng Quá mua (RSI > 70) - Giá đang cao:**")
                qua_mua = res_df[res_df['RSI'] > 70]
                if not qua_mua.empty:
                    st.dataframe(qua_mua)
                else:
                    st.info("Hiện tại không có mã nào trong danh sách bị quá mua.")
                
                st.write("**💎 Vùng Quá bán (RSI < 30) - Giá đang rẻ:**")
                qua_ban = res_df[res_df['RSI'] < 30]
                if not qua_ban.empty:
                    st.dataframe(qua_ban)
                else:
                    st.info("Hiện tại không có mã nào trong danh sách bị quá bán.")
                
            elif filter_type == "Đường xu hướng MA20":
                st.write("**📈 Cổ phiếu nằm TRÊN đường MA20 (Xu hướng tăng):**")
                xu_huong_tang = res_df[res_df['Giá Đóng'] > res_df['MA20']]
                if not xu_huong_tang.empty:
                    st.dataframe(xu_huong_tang)
                else:
                    st.info("Không có cổ phiếu nào nằm trên đường MA20.")
        else:
            st.error("Nguồn dữ liệu bận hoặc bị nghẽn mạng. Bạn vui lòng bấm thử lại nút quét dữ liệu nhé.")
