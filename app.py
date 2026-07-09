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

    # 3. Tính toán các đường sóng Vortex
    vh_short_sma   = src.rolling(window=6).mean()
    vh_long_sma    = src.rolling(window=27).mean()
    vh_longer_sma  = src.rolling(window=72).mean()
    raw_longest_wave = src.rolling(window=234).mean()
    
    vh_hist      = vh_short_sma - vh_long_sma
    vh_longh     = vh_short_sma - vh_longer_sma
    vh_longesth  = vh_short_sma - raw_longest_wave
    
    df['vh_vortex'] = (vh_hist / 3 + vh_longh / 2 + vh_longesth / 4) / 3
    
    # CẢI TIẾN QUAN TRỌNG: Chuẩn hóa Longest Wave về dạng chỉ báo Oscilator (biên độ dao động)
    # Bằng cách lấy khoảng cách phần trăm giữa giá và SMA234, nhân hệ số để khớp biên độ với Vortex
    df['longest_wave'] = ((src - raw_longest_wave) / raw_longest_wave) * 2000
    
    return df
