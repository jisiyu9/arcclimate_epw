"""
直散分離に関するモジュール
"""

import numpy as np
import pandas as pd


def get_separate(msm_target:pd.DataFrame,
                 lat:float,
                 lon:float,
                 ele_target:float,
                 mode_separation:str)->pd.DataFrame:
    """直散分離を行い、水平面全天日射量から法線面直達日射量および水平天空日射量を取得する
    Args:
      msm_target(pd.DataFrame): MSMデータフレーム
      lat(float): 推計対象地点の緯度（10進法）
      lon(float): 推計対象地点の経度（10進法）
      ele_target(float): 推計対象地点の標高（m）
      mode_separation(str): 直散分離手法
    Returns:
      pd.DataFrame: 直散分離後のデータを追加したデータフレーム
    """

    # 時刻データから太陽位置を計算
    msm_target.loc[:,["IN0","h","Sinh","A"]] = get_sun_position(lat,lon,msm_target.index)
    
    # 2種の日射量データについて繰り返し
    for targ in ["est","msm"]:
        if "DSWRF_" + targ in msm_target.columns:
            # Nagata、Watanabe方式では大気透過率Pの収束計算が必要
            if mode_separation == "Nagata" or mode_separation == "Watanabe":
                # Nagata方式でSHを計算
                if mode_separation == "Nagata":
                    method_SH = func_SH_Nagata

                # Watanabe方式でSHを計算
                elif mode_separation == "Watanabe":
                    method_SH = func_SH_Watanabe

                # SHの取得                    
                msm_target["SH_" + targ] = get_SH(msm_target["DSWRF_" + targ].values,
                msm_target.Sinh.values,
                msm_target.IN0.values,
                method_SH)

            # Erbs方式でSHを計算
            elif mode_separation == "Erbs":
                msm_target["SH_" + targ] = get_SH_Erbs(msm_target["DSWRF_" + targ].values,
                msm_target.IN0.values,
                msm_target.Sinh.values)

            # Udagawa方式でDNを計算
            elif mode_separation == "Udagawa":
                msm_target["DN_" + targ] = get_DN_Udagawa(msm_target["DSWRF_" + targ].values,
                msm_target.IN0.values,
                msm_target.Sinh.values)

            # Perez方式でDNを計算    
            elif mode_separation == "Perez":
                msm_target["DN_" + targ] = get_DN_perez(msm_target["DSWRF_" + targ].values,
                msm_target["h"].values,
                msm_target["DT"].values,
                ele_target,
                msm_target["IN0"].values)

            # SHを推計している場合(Nagata,Watanabe,Erbs)
            if "SH_" + targ in msm_target.columns:
                # DNの取得
                msm_target["DN_" + targ] = func_DN(msm_target["DSWRF_" + targ].values,
                msm_target["SH_" + targ].values,
                msm_target.Sinh.values)
                msm_target.loc[msm_target["DN_" + targ] <= 0.0,"DN_" + targ] = 0.0

            # DNを取得している場合(Udagawa,Perez)
            elif "DN_" + targ in msm_target.columns:
                # SHの取得
                msm_target["SH_" + targ] = func_SH(msm_target["DSWRF_" + targ].values,
                msm_target["DN_" + targ].values,
                msm_target["Sinh"].values)
                msm_target.loc[msm_target["SH_" + targ] <= 0.0,"SH_" + targ] = 0.0

            else:
                # DNもSHも無い場合
                pass

        else:
            # 日射量が無い場合
            pass

    return msm_target.drop(["IN0","Sinh"],axis=1)


def get_sun_position(lat:float,
                     lon:float,
                     date:pd.Series)->pd.DataFrame:
    """緯度経度と日時データから太陽位置および大気外法線面日射量の計算を行う

    Args:
      lat(float): 推計対象地点の緯度（10進法）
      lon(float): 推計対象地点の経度（10進法）
      date(pd.Series): 計算対象の時刻データ

    Returns:
      pd.DataFrame: 大気外法線面日射量、太陽高度角および方位角のデータフレーム
                    df[IN0:大気外法線面日射量,
                       h:太陽高度角,
                       Sinh:太陽高度角のサイン,
                       A:太陽方位角]
    """
    
    # 参照時刻の前1時間の太陽高度および方位角を取得する（1/10時間ずつ計算した平均値）
    count=[1.0,0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1]

    J0 = 4.921 #太陽定数[MJ/m²h] 4.921
    dlt0 = np.radians(-23.4393)   #冬至の日赤緯

    df = pd.DataFrame()
    df["date"] = pd.to_datetime(date)
    df["DY"] = df.date.dt.year
    df["year"] = pd.to_datetime(df.DY.astype(str) + '-01-01')
    df["nday"] = (df["date"] - df["year"]).dt.days + 1 # 年間通日+1
    df["Tm"] = df.date.dt.hour #標準時

    df["n"] = df.DY - 1968

    df["d0"] = 3.71 + 0.2596 * df.n - np.floor(( df.n + 3 ) / 4)  #近日点通過日
    df["m"] = 360 * ( df.nday - df.d0 ) / 365.2596       #平均近点離角
    df["eps"] = 12.3901 + 0.0172 * ( df.n + df.m / 360)   #近日点と冬至点の角度
    df["v"] = df.m + 1.914 * np.sin(np.radians(df.m)) + 0.02 * np.sin(np.radians(2*df.m))  #真近点離角
    df["veps"] = np.radians( df.v + df.eps )
    df["Et"] = ( df.m - df.v) - np.degrees(np.arctan( 0.043 * np.sin( 2 * df.veps )/
                                            ( 1 - 0.043 * np.cos( 2 * df.veps)))) #近時差

    df["sindlt"] = np.cos(df.veps) * np.sin(dlt0)  #赤緯の正弦
    df["cosdlt"] = (np.abs(1 - df.sindlt**2))**0.5   #赤緯の余弦

    df["IN0"] = J0 * ( 1 + 0.033 * np.cos(np.radians(df.v))) # IN0 大気外法線面日射量 

    lons = 135 #標準時の地点の経度
    latrad = np.radians( lat ) #緯度

    h = pd.DataFrame() # hの容器
    A = pd.DataFrame() # Aの容器

    for j in count:
        tm = df.Tm - j
        t = 15 * ( tm - 12 ) + ( lon - lons ) + df.Et  #時角
        trad = np.radians(t)
        Sinh = np.sin(latrad) * df.sindlt + np.cos(latrad) * df.cosdlt * np.cos(trad) #太陽高度角の正弦
        Cosh = np.sqrt(1 - Sinh**2)
        SinA = df.cosdlt * np.sin(trad)/Cosh
        CosA = (Sinh*np.sin(latrad)-df.sindlt) / (Cosh * np.cos(latrad))

        h["h_" + str(j)] = np.degrees(np.arcsin(Sinh))
        A["A_" + str(j)] = np.degrees(np.arctan2(SinA, CosA) + np.pi)

    # 太陽高度
    df["h"] = h.mean(axis = 1)
    # 太陽高度角のサイン
    df["Sinh"] = np.sin(np.radians(df["h"]))
    # 太陽方位角
    df["A"] = A.mean(axis = 1)

    return df.set_index("date",drop=True)[["IN0","h","Sinh","A"]]


def get_SH(TH:np.ndarray,
           Sinh:np.ndarray,           
           IN0:np.ndarray,
           method_SH)->pd.Series:
    """天空日射量SHの収束計算のループ

    Args:
      TH(ndarray[float]): 水平面全天日射量(MJ/m2)
      Sinh(ndarray[float]): 太陽高度角のサイン(-)
      IN0(ndarray[float]): 大気外法線面日射量(MJ/m2)
      method_SH(def): 天空日射量の推計式

    Returns:
      SH(ndarray[float]): 水平面天空日射量(MJ/m2)
    """
    # アウトプット用のリストを作成
    SH = []
    
    dataL = len(TH)
    
    for i in range(dataL):
        if Sinh[i] <= 0.0:
            sh = 0.0
        
        elif np.isnan(TH[i]):
            sh = np.nan

        else:
            sh = max(0.0,
                     get_SH_core(TH[i],
                                 Sinh[i],
                                 IN0[i],
                                 method_SH))
                     
        SH.append(sh)

    return np.array(SH)
                     

def get_SH_core(TH:float,
                Sinh:float,
                IN0:float,
                method_SH)->float:
    """天空日射量SHの収束計算のコア
       収束した大気透過率Pにおける天空日射量を取得する

    Args:
      TH(float): 水平面全天日射量(MJ/m2)
      Sinh(float): 太陽高度角のサイン(-)
      IN0(float): 大気外法線面日射量(MJ/m2)
      function_SH: 天空日射量の推計式

    Returns:
      SH(float): 水平面天空日射量(MJ/m2)
    """
    
    LIMIT1 = 1e-5 # THとTH0の差がこの値以下になったらPを返す
    LIMIT2 = 1e-10 # a(下限値)とb(上限値)の差がこの値以下になったら収束しないものとみなしてnp.nanを返す
    
    # Pの最小値 下限値を設定するか要検討
    P_min = 0.0
    # Pの最大値 上限値を設定するか要検討
    P_max = 0.85
    
    a = 0.0 # 大気透過率の範囲は0～1
    b = 1.2 # 太陽高度が小さい条件でPが1を超えることがある

    #2分法で収束計算(中間値の定理を満たしていない)
    while True:
        P = (a + b)/2
        SH = method_SH(P,IN0,Sinh)
        TH0 = func_TH(P,IN0,Sinh,SH)

        if abs(TH0 - TH) <= LIMIT1: # 目標の誤差まで収束した場合
            # P_maxを上限とする
            if P >= P_max:
                SH = method_SH(P_max,IN0,Sinh)

            return min(SH,TH)
        
        elif a >= P_max: # 下限値がP_maxより大きい
            return min(method_SH(P_max,IN0,Sinh),TH)
        
        elif b <= P_min: # 上限値がP_minより小さい
            return min(method_SH(P_min,IN0,Sinh),TH)
        
        elif P <= LIMIT2*10: # PがLIMIT2の10倍以下（限りなく0に近い）
            return min(method_SH(0.0,IN0,Sinh),TH)

        elif abs(a-b) <= LIMIT2: # 収束していない
            return np.nan

        elif TH0 < TH:
            a = P

        else:
            b = P

    return np.nan


def func_TH(P:float,
            IN0:float,
            Sinh:float,
            SH:float)->float:
    """水平面全天日射量の式
    Args:
      P(float): 大気透過率(-)      
      IN0(float): 大気外法線面日射量(MJ/m2)
      Sinh(float): 太陽高度角のサイン(-)
      SH(float): 水平面天空日射量(MJ/m2)

    Returns:
      TH(float)): 水平面全天日射量(MJ/m2)
    """
    return IN0 * P**(1/Sinh) * Sinh + SH


"""
SHの予測 Nagataモデル  
"""
def func_SH_Nagata(P:float,
                   IN0:float,
                   Sinh:float)->float:
    """天空日射量の推計式 Nagataモデル
    Args:
      P(float): 大気透過率(-)      
      IN0(float): 大気外法線面日射量(MJ/m2)
      Sinh(float): 太陽高度角のサイン(-)

    Returns:
      TH(float)): 水平面全天日射量(MJ/m2)
    """
    return IN0 * Sinh * (1.0 - P ** (1/Sinh)) * (
        0.66 - 0.32 * Sinh) * (0.5 + (0.4 - 0.3 * P) * Sinh)


"""
SHの予測 Watanabeモデル  
"""
def func_SH_Watanabe(P:float,
                   IN0:float,
                   Sinh:float)->float:
    """天空日射量の推計式 Watanabeモデル
    Args:
      P(float): 大気透過率(-)      
      IN0(float): 大気外法線面日射量(MJ/m2)
      Sinh(float): 太陽高度角のサイン(-)

    Returns:
      TH(float)): 水平面全天日射量(MJ/m2)
    """
    
    if P >= 1.0: # Watanabe式の場合Pが1以上の時エラーとなる
        P = 1.0
        
    Q = (0.8672 + 0.7505 * Sinh) * (
        P**(0.421*1/Sinh)) * ((1-P ** (1/Sinh))**2.277)
    return IN0 * Sinh *( Q / ( 1 + Q ))


"""
SHからDNを計算する
"""
def func_DN(TH:float,
            SH:float,
            Sinh:float)->float:
    """法線面直達日射量の式
    Args:
      TH(float): 水平面全天日射量(MJ/m2)
      SH(float): 水平面天空日射量(MJ/m2)
      Sinh(float): 太陽高度角のサイン(-)

    Returns:
      DN(float)): 法線面直達日射量(MJ/m2)
    """
    return ( TH - SH ) / Sinh


"""
SHの予測 Erbsモデル  
"""
def get_SH_Erbs(TH:np.ndarray,
                IN0:np.ndarray,
                Sinh:np.ndarray)->np.ndarray:
    """天空日射量の計算ループ Erbsモデル

    Args:
      TH(ndarray[float]): 水平面全天日射量(MJ/m2)
      IN0(ndarray[float]): 大気外法線面日射量(MJ/m2)
      Sinh(ndarray[float]): 太陽高度角のサイン(-)

    Returns:
      SH(ndarray[float]): 水平面天空日射量(MJ/m2)
    """
    
    # アウトプット用のリストを作成
    SH = []
    
    dataL = len(TH)
    
    for i in range(dataL):

        if np.isnan(TH[i]):
            sh = np.nan

        elif TH[i] <= 0.0:
            sh = 0.0
        
        else:
            KT = min(1.0, # KTが1.0を超えるときは1.0
                     func_KT(TH[i],
                             IN0[i],
                             Sinh[i]))
            
            if KT <= 0.22:
                # SHの計算1次式（KTが0.22以下）
                sh = func_SH_Erbs_1d_022(TH[i],KT)
                
            elif 0.22 < KT <= 0.80:
                # SHの計算4次式（KTが0.22を超えて0.80以下）
                sh = func_SH_Erbs_4d(TH[i],KT)
                
            else:
                # SHの計算1次式（KTが0.80を超える）
                sh = func_SH_Erbs_1d_080(TH[i])
        
        SH.append(sh)

    return np.array(SH)


def func_SH_Erbs_1d_022(TH:float,
                        KT:float)->float:
    """天空日射量の推計式 Erbsモデル 1次式（KTが0.22以下）
    Args:
      TH(float): 水平面全天日射量(MJ/m2)
      KT(float): 晴天指数(-)

    Returns:
      SH(float)): 水平面天空日射量(MJ/m2)
    """
    return TH * (1.0 - 0.09 * KT)


def func_SH_Erbs_4d(TH:float,
                    KT:float)->float:
    """天空日射量の推計式 Erbsモデル 4次式（KTが0.22を超えて0.80以下）
    Args:
      TH(float): 水平面全天日射量(MJ/m2)
      KT(float): 晴天指数(-)

    Returns:
      SH(float)): 水平面天空日射量(MJ/m2)
    """
    return TH * (0.9511 - 0.1604*KT + 4.388*KT**2 - 16.638*KT**3 + 12.336*KT**4)


def func_SH_Erbs_1d_080(TH:float)->float:
    """天空日射量の推計式 Erbsモデル 1次式（KTが0.80を超える）
    Args:
      TH(float): 水平面全天日射量(MJ/m2)

    Returns:
      SH(float)): 水平面天空日射量(MJ/m2)
    """
    return 0.165 * TH


def func_KT(TH:float,
            IN0:float,
            Sinh:float)->float:
    """晴天指数の計算式

    Args:
      TH(float): 水平面全天日射量(MJ/m2)
      IN0(float): 大気外法線面日射量(MJ/m2)
      Sinh(float): 太陽高度角のサイン(-)

    Returns:
      KT(float): 晴天指数(-)
    """
    return TH / (IN0 * Sinh)


"""
DNの予測 Udagawa モデル  
"""
def get_DN_Udagawa(TH:np.ndarray,
                   IN0:np.ndarray,
                   Sinh:np.ndarray)->np.ndarray:
    """直達日射量の計算ループ Udagawaモデル

    Args:
      TH(ndarray[float]): 水平面全天日射量(MJ/m2)
      IN0(ndarray[float]): 大気外法線面日射量(MJ/m2)
      Sinh(ndarray[float]): 太陽高度角のサイン(-)

    Returns:
      DN(ndarray[float]): 法線面直達日射量(MJ/m2)
    """
    
    # アウトプット用のリストを作成
    DN = []
    
    dataL = len(TH)
    
    for i in range(dataL):
        if np.isnan(TH[i]):
            dn = np.nan

        # 水平面全天日射量が0.0の場合、法線面直達日射量を0.0
        elif TH[i] <= 0.0:
            dn = 0.0
        
        else:
            # KC:1次式と3次式の接続点であり、太陽高度の関数
            KC = (0.5163 + 0.333*Sinh[i] + 0.00803*Sinh[i]**2) * IN0[i] * Sinh[i]
            
            # KT:晴天指数 [–] (正規化した全天日射)の算出 1.0が最大
            KT = min(1.0,
                     func_KT(TH[i],
                             IN0[i],
                             Sinh[i]))
            
            # KCがKTを上回る場合=>3次式
            if KT < KC:
                # DNの計算(3次式)
                dn = max(0.0,
                         func_DN_Udagawa_3d(IN0[i],
                                            Sinh[i],
                                            KT))
            else:
                # DNの計算(1次式)
                dn = max(0.0,
                         func_DN_Udagawa_1d(IN0[i],
                                            KT))

        DN.append(dn)

    return np.array(DN)


def func_DN_Udagawa_3d(IN0:float,
                       Sinh:float,
                       KT:float)->float:
    """直達日射量の推計式 Udagawaモデル 3次式

    Args:
      IN0(float): 大気外法線面日射量(MJ/m2)
      Sinh(float): 太陽高度角のサイン(-)
      KT(float): 晴天指数(-)

    Returns:
      DN(float): 法線面直達日射量(MJ/m2)
    """
    return IN0*(2.277-1.258*Sinh+0.2396*Sinh**2)*KT**3


def func_DN_Udagawa_1d(IN0:float,
                       KT:float)->float:
    """直達日射量の推計式 Udagawaモデル 1次式

    Args:
      IN0(float): 大気外法線面日射量(MJ/m2)
      KT(float): 晴天指数(-)

    Returns:
      DN(float): 法線面直達日射量(MJ/m2)
    """
    return IN0*(-0.43 + 1.43 * KT)


def func_SH(TH:float,
            DN:float,
            Sinh:float)->float:
    """法線面直達日射量の式
    Args:
      TH(float): 水平面全天日射量(MJ/m2)
      DN(float)): 法線面直達日射量(MJ/m2)
      Sinh(float): 太陽高度角のサイン(-)

    Returns:
      SH(float): 水平面天空日射量(MJ/m2)
    """
    return TH - (DN*Sinh)


def get_CM():
    """Pertzの係数CMをndarrayとして取得する
    Args:
        
    Returns:
        CM(ndarray[float]):Pertzの係数CM
    """ 
    # pythonは0オリジンのため全て-1
    CM = [0.385230, 0.385230, 0.385230, 0.462880, 0.317440,#1_1 => 0_0
          0.338390, 0.338390, 0.221270, 0.316730, 0.503650,
          0.235680, 0.235680, 0.241280, 0.157830, 0.269440,
          0.830130, 0.830130, 0.171970, 0.841070, 0.457370,
          0.548010, 0.548010, 0.478000, 0.966880, 1.036370,
          0.548010, 0.548010, 1.000000, 3.012370, 1.976540,
          0.582690, 0.582690, 0.229720, 0.892710, 0.569950,
          0.131280, 0.131280, 0.385460, 0.511070, 0.127940,#1_2 => 0_1
          0.223710, 0.223710, 0.193560, 0.304560, 0.193940,
          0.229970, 0.229970, 0.275020, 0.312730, 0.244610,
          0.090100, 0.184580, 0.260500, 0.687480, 0.579440,
          0.131530, 0.131530, 0.370190, 1.380350, 1.052270,
          1.116250, 1.116250, 0.928030, 3.525490, 2.316920,
          0.090100, 0.237000, 0.300040, 0.812470, 0.664970,
          0.587510, 0.130000, 0.400000, 0.537210, 0.832490,#1_3 => 0_2
          0.306210, 0.129830, 0.204460, 0.500000, 0.681640,
          0.224020, 0.260620, 0.334080, 0.501040, 0.350470,
          0.421540, 0.753970, 0.750660, 3.706840, 0.983790,
          0.706680, 0.373530, 1.245670, 0.864860, 1.992630,
          4.864400, 0.117390, 0.265180, 0.359180, 3.310820,
          0.392080, 0.493290, 0.651560, 1.932780, 0.898730,
          0.126970, 0.126970, 0.126970, 0.126970, 0.126970,#1_4 => 0_3
          0.810820, 0.810820, 0.810820, 0.810820, 0.810820,
          3.241680, 2.500000, 2.291440, 2.291440, 2.291440,
          4.000000, 3.000000, 2.000000, 0.975430, 1.965570,
          12.494170, 12.494170, 8.000000, 5.083520, 8.792390,
          21.744240, 21.744240, 21.744240, 21.744240, 21.744240,
          3.241680, 12.494170, 1.620760, 1.375250, 2.331620,
          0.126970, 0.126970, 0.126970, 0.126970, 0.126970,#1_5 => 0_4
          0.810820, 0.810820, 0.810820, 0.810820, 0.810820,
          3.241680, 2.500000, 2.291440, 2.291440, 2.291440,
          4.000000, 3.000000, 2.000000, 0.975430, 1.965570,
          12.494170, 12.494170, 8.000000, 5.083520, 8.792390,
          21.744240, 21.744240, 21.744240, 21.744240, 21.744240,
          3.241680, 12.494170, 1.620760, 1.375250, 2.331620,
          0.126970, 0.126970, 0.126970, 0.126970, 0.126970,#1_6 => 0_5
          0.810820, 0.810820, 0.810820, 0.810820, 0.810820,
          3.241680, 2.500000, 2.291440, 2.291440, 2.291440,
          4.000000, 3.000000, 2.000000, 0.975430, 1.965570,
          12.494170, 12.494170, 8.000000, 5.083520, 8.792390,
          21.744240, 21.744240, 21.744240, 21.744240, 21.744240,
          3.241680, 12.494170, 1.620760, 1.375250, 2.331620,
          0.337440, 0.337440, 0.969110, 1.097190, 1.116080,#2_1 => 1_0
          0.337440, 0.337440, 0.969110, 1.116030, 0.623900,
          0.337440, 0.337440, 1.530590, 1.024420, 0.908480,
          0.584040, 0.584040, 0.847250, 0.914940, 1.289300,
          0.337440, 0.337440, 0.310240, 1.435020, 1.852830,
          0.337440, 0.337440, 1.015010, 1.097190, 2.117230,
          0.337440, 0.337440, 0.969110, 1.145730, 1.476400,
          0.300000, 0.300000, 0.700000, 1.100000, 0.796940,#2_2 => 1_1
          0.219870, 0.219870, 0.526530, 0.809610, 0.649300,
          0.386650, 0.386650, 0.119320, 0.576120, 0.685460,
          0.746730, 0.399830, 0.470970, 0.986530, 0.785370,
          0.575420, 0.936700, 1.649200, 1.495840, 1.335590,
          1.319670, 4.002570, 1.276390, 2.644550, 2.518670,
          0.665190, 0.678910, 1.012360, 1.199940, 0.986580,
          0.378870, 0.974060, 0.500000, 0.491880, 0.665290,#2_3 => 1_2
          0.105210, 0.263470, 0.407040, 0.553460, 0.582590,
          0.312900, 0.345240, 1.144180, 0.854790, 0.612280,
          0.119070, 0.365120, 0.560520, 0.793720, 0.802600,
          0.781610, 0.837390, 1.270420, 1.537980, 1.292950,
          1.152290, 1.152290, 1.492080, 1.245370, 2.177100,
          0.424660, 0.529550, 0.966910, 1.033460, 0.958730,
          0.310590, 0.714410, 0.252450, 0.500000, 0.607600,#2_4 => 1_3
          0.975190, 0.363420, 0.500000, 0.400000, 0.502800,
          0.175580, 0.196250, 0.476360, 1.072470, 0.490510,
          0.719280, 0.698620, 0.657770, 1.190840, 0.681110,
          0.426240, 1.464840, 0.678550, 1.157730, 0.978430,
          2.501120, 1.789130, 1.387090, 2.394180, 2.394180,
          0.491640, 0.677610, 0.685610, 1.082400, 0.735410,
          0.597000, 0.500000, 0.300000, 0.310050, 0.413510,#2_5 => 1_4
          0.314790, 0.336310, 0.400000, 0.400000, 0.442460,
          0.166510, 0.460440, 0.552570, 1.000000, 0.461610,
          0.401020, 0.559110, 0.403630, 1.016710, 0.671490,
          0.400360, 0.750830, 0.842640, 1.802600, 1.023830,
          3.315300, 1.510380, 2.443650, 1.638820, 2.133990,
          0.530790, 0.745850, 0.693050, 1.458040, 0.804500,
          0.597000, 0.500000, 0.300000, 0.310050, 0.800920,#2_6 => 1_5
          0.314790, 0.336310, 0.400000, 0.400000, 0.237040,
          0.166510, 0.460440, 0.552570, 1.000000, 0.581990,
          0.401020, 0.559110, 0.403630, 1.016710, 0.898570,
          0.400360, 0.750830, 0.842640, 1.802600, 3.400390,
          3.315300, 1.510380, 2.443650, 1.638820, 2.508780,
          0.204340, 1.157740, 2.003080, 2.622080, 1.409380,
          1.242210, 1.242210, 1.242210, 1.242210, 1.242210,#3_1 => 2_0
          0.056980, 0.056980, 0.656990, 0.656990, 0.925160,
          0.089090, 0.089090, 1.040430, 1.232480, 1.205300,
          1.053850, 1.053850, 1.399690, 1.084640, 1.233340,
          1.151540, 1.151540, 1.118290, 1.531640, 1.411840,
          1.494980, 1.494980, 1.700000, 1.800810, 1.671600,
          1.018450, 1.018450, 1.153600, 1.321890, 1.294670,
          0.700000, 0.700000, 1.023460, 0.700000, 0.945830,#3_2 => 2_1
          0.886300, 0.886300, 1.333620, 0.800000, 1.066620,
          0.902180, 0.902180, 0.954330, 1.126690, 1.097310,
          1.095300, 1.075060, 1.176490, 1.139470, 1.096110,
          1.201660, 1.201660, 1.438200, 1.256280, 1.198060,
          1.525850, 1.525850, 1.869160, 1.985410, 1.911590,
          1.288220, 1.082810, 1.286370, 1.166170, 1.119330,
          0.600000, 1.029910, 0.859890, 0.550000, 0.813600,#3_3 => 2_2
          0.604450, 1.029910, 0.859890, 0.656700, 0.928840,
          0.455850, 0.750580, 0.804930, 0.823000, 0.911000,
          0.526580, 0.932310, 0.908620, 0.983520, 0.988090,
          1.036110, 1.100690, 0.848380, 1.035270, 1.042380,
          1.048440, 1.652720, 0.900000, 2.350410, 1.082950,
          0.817410, 0.976160, 0.861300, 0.974780, 1.004580,
          0.782110, 0.564280, 0.600000, 0.600000, 0.665740,#3_4 => 2_3
          0.894480, 0.680730, 0.541990, 0.800000, 0.669140,
          0.487460, 0.818950, 0.841830, 0.872540, 0.709040,
          0.709310, 0.872780, 0.908480, 0.953290, 0.844350,
          0.863920, 0.947770, 0.876220, 1.078750, 0.936910,
          1.280350, 0.866720, 0.769790, 1.078750, 0.975130,
          0.725420, 0.869970, 0.868810, 0.951190, 0.829220,
          0.791750, 0.654040, 0.483170, 0.409000, 0.597180,#3_5 => 2_4
          0.566140, 0.948990, 0.971820, 0.653570, 0.718550,
          0.648710, 0.637730, 0.870510, 0.860600, 0.694300,
          0.637630, 0.767610, 0.925670, 0.990310, 0.847670,
          0.736380, 0.946060, 1.117590, 1.029340, 0.947020,
          1.180970, 0.850000, 1.050000, 0.950000, 0.888580,
          0.700560, 0.801440, 0.961970, 0.906140, 0.823880,
          0.500000, 0.500000, 0.586770, 0.470550, 0.629790,#3_6 => 2_5
          0.500000, 0.500000, 1.056220, 1.260140, 0.658140,
          0.500000, 0.500000, 0.631830, 0.842620, 0.582780,
          0.554710, 0.734730, 0.985820, 0.915640, 0.898260,
          0.712510, 1.205990, 0.909510, 1.078260, 0.885610,
          1.899260, 1.559710, 1.000000, 1.150000, 1.120390,
          0.653880, 0.793120, 0.903320, 0.944070, 0.796130,
          1.000000, 1.000000, 1.050000, 1.170380, 1.178090,#4_1 => 3_0
          0.960580, 0.960580, 1.059530, 1.179030, 1.131690,
          0.871470, 0.871470, 0.995860, 1.141910, 1.114600,
          1.201590, 1.201590, 0.993610, 1.109380, 1.126320,
          1.065010, 1.065010, 0.828660, 0.939970, 1.017930,
          1.065010, 1.065010, 0.623690, 1.119620, 1.132260,
          1.071570, 1.071570, 0.958070, 1.114130, 1.127110,
          0.950000, 0.973390, 0.852520, 1.092200, 1.096590,#4_2 => 3_1
          0.804120, 0.913870, 0.980990, 1.094580, 1.042420,
          0.737540, 0.935970, 0.999940, 1.056490, 1.050060,
          1.032980, 1.034540, 0.968460, 1.032080, 1.015780,
          0.900000, 0.977210, 0.945960, 1.008840, 0.969960,
          0.600000, 0.750000, 0.750000, 0.844710, 0.899100,
          0.926800, 0.965030, 0.968520, 1.044910, 1.032310,
          0.850000, 1.029710, 0.961100, 1.055670, 1.009700,#4_3 => 3_2
          0.818530, 0.960010, 0.996450, 1.081970, 1.036470,
          0.765380, 0.953500, 0.948260, 1.052110, 1.000140,
          0.775610, 0.909610, 0.927800, 0.987800, 0.952100,
          1.000990, 0.881880, 0.875950, 0.949100, 0.893690,
          0.902370, 0.875960, 0.807990, 0.942410, 0.917920,
          0.856580, 0.928270, 0.946820, 1.032260, 0.972990,
          0.750000, 0.857930, 0.983800, 1.056540, 0.980240,#4_4 => 3_3
          0.750000, 0.987010, 1.013730, 1.133780, 1.038250,
          0.800000, 0.947380, 1.012380, 1.091270, 0.999840,
          0.800000, 0.914550, 0.908570, 0.999190, 0.915230,
          0.778540, 0.800590, 0.799070, 0.902180, 0.851560,
          0.680190, 0.317410, 0.507680, 0.388910, 0.646710,
          0.794920, 0.912780, 0.960830, 1.057110, 0.947950,
          0.750000, 0.833890, 0.867530, 1.059890, 0.932840,#4_5 => 3_4
          0.979700, 0.971470, 0.995510, 1.068490, 1.030150,
          0.858850, 0.987920, 1.043220, 1.108700, 1.044900,
          0.802400, 0.955110, 0.911660, 1.045070, 0.944470,
          0.884890, 0.766210, 0.885390, 0.859070, 0.818190,
          0.615680, 0.700000, 0.850000, 0.624620, 0.669300,
          0.835570, 0.946150, 0.977090, 1.049350, 0.979970,
          0.689220, 0.809600, 0.900000, 0.789500, 0.853990,#4_6 => 3_5
          0.854660, 0.852840, 0.938200, 0.923110, 0.955010,
          0.938600, 0.932980, 1.010390, 1.043950, 1.041640,
          0.843620, 0.981300, 0.951590, 0.946100, 0.966330,
          0.694740, 0.814690, 0.572650, 0.400000, 0.726830,
          0.211370, 0.671780, 0.416340, 0.297290, 0.498050,
          0.843540, 0.882330, 0.911760, 0.898420, 0.960210,
          1.054880, 1.075210, 1.068460, 1.153370, 1.069220,#5_1 => 4_0
          1.000000, 1.062220, 1.013470, 1.088170, 1.046200,
          0.885090, 0.993530, 0.942590, 1.054990, 1.012740,
          0.920000, 0.950000, 0.978720, 1.020280, 0.984440,
          0.850000, 0.908500, 0.839940, 0.985570, 0.962180,
          0.800000, 0.800000, 0.810080, 0.950000, 0.961550,
          1.038590, 1.063200, 1.034440, 1.112780, 1.037800,
          1.017610, 1.028360, 1.058960, 1.133180, 1.045620,#5_2 => 4_1
          0.920000, 0.998970, 1.033590, 1.089030, 1.022060,
          0.912370, 0.949930, 0.979770, 1.020420, 0.981770,
          0.847160, 0.935300, 0.930540, 0.955050, 0.946560,
          0.880260, 0.867110, 0.874130, 0.972650, 0.883420,
          0.627150, 0.627150, 0.700000, 0.774070, 0.845130,
          0.973700, 1.006240, 1.026190, 1.071960, 1.017240,
          1.028710, 1.017570, 1.025900, 1.081790, 1.024240,#5_3 => 4_2
          0.924980, 0.985500, 1.014100, 1.092210, 0.999610,
          0.828570, 0.934920, 0.994950, 1.024590, 0.949710,
          0.900810, 0.901330, 0.928830, 0.979570, 0.913100,
          0.761030, 0.845150, 0.805360, 0.936790, 0.853460,
          0.626400, 0.546750, 0.730500, 0.850000, 0.689050,
          0.957630, 0.985480, 0.991790, 1.050220, 0.987900,
          0.992730, 0.993880, 1.017150, 1.059120, 1.017450,#5_4 => 4_3
          0.975610, 0.987160, 1.026820, 1.075440, 1.007250,
          0.871090, 0.933190, 0.974690, 0.979840, 0.952730,
          0.828750, 0.868090, 0.834920, 0.905510, 0.871530,
          0.781540, 0.782470, 0.767910, 0.764140, 0.795890,
          0.743460, 0.693390, 0.514870, 0.630150, 0.715660,
          0.934760, 0.957870, 0.959640, 0.972510, 0.981640,
          0.965840, 0.941240, 0.987100, 1.022540, 1.011160,#5_5 => 4_4
          0.988630, 0.994770, 0.976590, 0.950000, 1.034840,
          0.958200, 1.018080, 0.974480, 0.920000, 0.989870,
          0.811720, 0.869090, 0.812020, 0.850000, 0.821050,
          0.682030, 0.679480, 0.632450, 0.746580, 0.738550,
          0.668290, 0.445860, 0.500000, 0.678920, 0.696510,
          0.926940, 0.953350, 0.959050, 0.876210, 0.991490,
          0.948940, 0.997760, 0.850000, 0.826520, 0.998470,#5_6 => 4_5
          1.017860, 0.970000, 0.850000, 0.700000, 0.988560,
          1.000000, 0.950000, 0.850000, 0.606240, 0.947260,
          1.000000, 0.746140, 0.751740, 0.598390, 0.725230,
          0.922210, 0.500000, 0.376800, 0.517110, 0.548630,
          0.500000, 0.450000, 0.429970, 0.404490, 0.539940,
          0.960430, 0.881630, 0.775640, 0.596350, 0.937680,
          1.030000, 1.040000, 1.000000, 1.000000, 1.049510,#6_1 => 5_0
          1.050000, 0.990000, 0.990000, 0.950000, 0.996530,
          1.050000, 0.990000, 0.990000, 0.820000, 0.971940,
          1.050000, 0.790000, 0.880000, 0.820000, 0.951840,
          1.000000, 0.530000, 0.440000, 0.710000, 0.928730,
          0.540000, 0.470000, 0.500000, 0.550000, 0.773950,
          1.038270, 0.920180, 0.910930, 0.821140, 1.034560,
          1.041020, 0.997520, 0.961600, 1.000000, 1.035780,#6_2 => 5_1
          0.948030, 0.980000, 0.900000, 0.950360, 0.977460,
          0.950000, 0.977250, 0.869270, 0.800000, 0.951680,
          0.951870, 0.850000, 0.748770, 0.700000, 0.883850,
          0.900000, 0.823190, 0.727450, 0.600000, 0.839870,
          0.850000, 0.805020, 0.692310, 0.500000, 0.788410,
          1.010090, 0.895270, 0.773030, 0.816280, 1.011680,
          1.022450, 1.004600, 0.983650, 1.000000, 1.032940,#6_3 => 5_2
          0.943960, 0.999240, 0.983920, 0.905990, 0.978150,
          0.936240, 0.946480, 0.850000, 0.850000, 0.930320,
          0.816420, 0.885000, 0.644950, 0.817650, 0.865310,
          0.742960, 0.765690, 0.561520, 0.700000, 0.827140,
          0.643870, 0.596710, 0.474460, 0.600000, 0.651200,
          0.971740, 0.940560, 0.714880, 0.864380, 1.001650,
          0.995260, 0.977010, 1.000000, 1.000000, 1.035250,#6_4 => 5_3
          0.939810, 0.975250, 0.939980, 0.950000, 0.982550,
          0.876870, 0.879440, 0.850000, 0.900000, 0.917810,
          0.873480, 0.873450, 0.751470, 0.850000, 0.863040,
          0.761470, 0.702360, 0.638770, 0.750000, 0.783120,
          0.734080, 0.650000, 0.600000, 0.650000, 0.715660,
          0.942160, 0.919100, 0.770340, 0.731170, 0.995180,
          0.952560, 0.916780, 0.920000, 0.900000, 1.005880,#6_5 => 5_4
          0.928620, 0.994420, 0.900000, 0.900000, 0.983720,
          0.913070, 0.850000, 0.850000, 0.800000, 0.924280,
          0.868090, 0.807170, 0.823550, 0.600000, 0.844520,
          0.769570, 0.719870, 0.650000, 0.550000, 0.733500,
          0.580250, 0.650000, 0.600000, 0.500000, 0.628850,
          0.904770, 0.852650, 0.708370, 0.493730, 0.949030,
          0.911970, 0.800000, 0.800000, 0.800000, 0.956320,#6_6 => 5_5
          0.912620, 0.682610, 0.750000, 0.700000, 0.950110,
          0.653450, 0.659330, 0.700000, 0.600000, 0.856110,
          0.648440, 0.600000, 0.641120, 0.500000, 0.695780,
          0.570000, 0.550000, 0.598800, 0.40000 , 0.560150,
          0.475230, 0.500000, 0.518640, 0.339970, 0.520230,
          0.743440, 0.592190, 0.603060, 0.316930, 0.794390 ]

    return np.array(CM, dtype=float).reshape((6,6,7,5))


def W_to_MJ(W):
    """単位換算　W/m2 => MJ/m2・h 
    Args:
        W(float):日射量等(W/m2)

    Returns:
        MJ(float):日射量等(MJ/m2・h)
    """
    return W * 3600 * 10**-6


def MJ_to_W(MJ):
    """単位換算　MJ/m2・h => W/m2
    Args:
        MJ(float):日射量等(MJ/m2・h)

    Returns:
        W(float):日射量等(W/m2)
    """
    return MJ / (3600 * 10**-6)


def get_DN_perez_core(G_mj:np.ndarray,
                      h_deg:np.ndarray,
                      TD:float,
                      ALT:float,
                      IN0:float)->float:
    """直達日射量の推計(Pertz方式)
    Args:
        G_mj(ndarray[float,float,float]):水平面全天日射量(MJ/m2・h)のndarray
                                   計算対象時刻の1時間前、対象時刻、対象時刻の1時間後のデータ
        h_deg(ndarray[float,float,float]):太陽高度(DEGREES)のndarray
                                   計算対象時刻の1時間前、対象時刻、対象時刻の1時間後のデータ
        TD(float):計算対象時刻の露点温度(℃)
        ALT(float):標高(m)
        IN0(float):大気外法線面日射量(MJ/m2・h)
        
    Returns:
        DIRMAX(float):法線面直達日射量(MJ/m2・h)
    """ 
    
    CM = get_CM()
    # 係数選択のための閾値
    KTBIN = np.array([0.24, 0.4, 0.56, 0.7, 0.8])
    ZBIN = np.array([25.0, 40.0, 55.0, 70.0, 80.0])
    DKTBIN = np.array([0.015, 0.035, 0.07, 0.15, 0.3])
    WBIN = np.array([1.0, 2.0, 3.0])
    
    # 度数法と弧度法の換算 degrees(1 radians)
    #RTOD = 57.295779513082316 
    
    # Perez式はW/m2で計算するため換算
    G = MJ_to_W(G_mj) # MJ/m2・h => W/m2

    # 計算対象時刻の水平面全天日射量が1W/m2以下の時は、DIRMAXを0とする
    if G[1] < 1.0 or np.isnan(G[1]): # G[1] 当該時刻の水平面全天日射量
        return 0.0
    
    if h_deg[1] <= 0.0: # h_deg[1] 当該時刻の太陽高度
        return 0.0
    
    h_deg[h_deg < 0.0] = np.nan

    # 赤坂の方法で求めた太陽位置から算出した法線面直達日射量を使用
    IO = MJ_to_W(IN0) 
    # Pertzの方法 1367.0 * (1.0 + 0.033 * np.cos(0.0172142 * float(DOY)))
    
    # 太陽高度[DEG]を天頂高度[DEG]へ変換
    ZENITH = 90 - h_deg 
    
    # 1時間前、対象時刻、1時間後のデータを計算
    cz = np.cos(np.radians(ZENITH))
    
    CZ = np.where(cz <= 6.5*(10**-2), 6.5*(10**-2), cz)
    IOCZ = IO * CZ
    KT = G / IOCZ

    # エアマスの計算
    AM = 1.0 / (CZ + 0.15 * np.power((93.9 - ZENITH), -1.253))
    AM[AM >= 15.25] = 15.25

    KTPAM = AM * np.exp(-0.0001184 * ALT)
    KT1 = KT / (1.031 * np.exp(-1.4 / (0.9 + 9.4 / KTPAM)) + 0.1)    
    KT1[cz < 0.0] = np.nan
    
    # 前の時刻のデータがない場合
    if np.isnan(G[0]) or np.isnan(ZENITH[0]): #G[0] 1時間前のG,Z[0] 1時間前のZ
        KT1[0] = np.nan
    # 後の時刻のデータがない場合
    if np.isnan(G[2]) or np.isnan(ZENITH[2]):
        KT1[2] = np.nan
    
    # 対象時刻の天頂高度のコサインが0未満の場合
    if CZ[1] < 0.0:
        return 0.0
    
    if KT[1] <= 0.6:
        A = 0.512 - (1.56 * KT[1]) +(2.286 * (KT[1]**2.0)) - (2.22 * (KT[1]**3.0))
        B = 0.37 + (0.962 * KT[1])
        C = -0.28 + (0.932 * KT[1]) - (2.048 * (KT[1]**2.0))
    
    else:
        A = -5.743 + (21.77 * KT[1]) - (27.49 * (KT[1]**2.0)) + (11.56 * (KT[1]**3.0))
        B = 41.40 - (118.5 * KT[1]) + (66.05 * (KT[1]**2.0)) + (31.9 * (KT[1]**3.0))
        C = -47.01 + (184.2 * KT[1]) - (222.0 * (KT[1]**2.0)) + (73.81 * (KT[1]**3.0))
        
    KNC = 0.866 - (0.122 * AM[1]) + (0.0121 * (AM[1]**2.0)) \
          - (0.000653 * (AM[1]**3.0)) + (0.000014 * (AM[1]**4.0))
    
    BMAX = IO * (KNC - (A + B * np.exp(C * AM[1])))
    
    if np.isnan(KT1[0]) and np.isnan(KT1[2]):
        K = 6 #7 pythonは0オリジンのため-1
    
    else:
        if np.isnan(KT1[0]) or ZENITH[0] >= 85.0:
            DKT1 = np.abs(KT1[2] - KT1[1])
        
        elif np.isnan(KT1[2]) or ZENITH[2] >= 85.0:
            DKT1 = np.abs(KT1[1] - KT1[0])
        
        else:
            DKT1 = 0.5*(np.abs(KT1[1] - KT1[0]) + np.abs(KT1[2] - KT1[1]))
        
        K = np.digitize(DKT1, DKTBIN)
        
    I = np.digitize(KT1[1], KTBIN)
    
    J = np.digitize(ZENITH[1], ZBIN)
    
    if np.isnan(TD):
        L = 4 #5 pythonは0オリジンのため-1
        
    else:
        W = np.exp( -0.075 + 0.07 *TD)
        L = np.digitize(W, WBIN)
        
    DIRMAX = BMAX * CM[I,J,K,L]
    
    if DIRMAX < 0.0:
        DIRMAX = 0.0
        
    return W_to_MJ(DIRMAX) # W/m2 => MJ/m2・h


def get_DN_perez(TH,h,TD,ALT,IN0):

    # アウトプット用のリストを作成
    DN = []
    
    dataL = len(TH)
#     dataL = 3
    
    for i in range(dataL):
        if i == 0:
            G = np.array([np.nan,TH[i],TH[i+1]])
            H = np.array([np.nan,h[i],h[i+1]])
            
        elif i == dataL-1:
            G = np.array([TH[i-1],TH[i],np.nan])
            H = np.array([h[i-1],h[i],np.nan])
        
        else:
            G = np.array([TH[i-1],TH[i],TH[i+1]])
            H = np.array([h[i-1],h[i],h[i+1]])

        # 水平面全天日射量が存在しない場合にはnanを返す
        if np.isnan(TH[i]):
            DN.append(np.nan)

        else:
            dn = get_DN_perez_core(G,
                                H,
                                TD[i],
                                ALT,
                                IN0[i])
            DN.append(dn)

    return np.array(DN)

