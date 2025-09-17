#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import requests
import time
import logging
import re
from bs4 import BeautifulSoup
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ── ロギング設定 ─────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('boatrace_debug.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# ── 引数解析（修正版）─────────────────────────────────
def parse_arguments():
    p = argparse.ArgumentParser(description='ボートレース結果取得スクリプト')
    p.add_argument('arg1', help='引数1（日付または会場名）')
    p.add_argument('arg2', help='引数2（日付または会場名）')
    return p.parse_args()

# ── レース場コード変換 ─────────────────────────────────
def get_venue_code(name):
    codes = {
        '桐生':'01','戸田':'02','江戸川':'03','平和島':'04',
        '多摩川':'05','浜名湖':'06','蒲郡':'07','常滑':'08',
        '津':'09','三国':'10','琵琶湖':'11','住之江':'12',
        '尼崎':'13','鳴門':'14','丸亀':'15','児島':'16',
        '宮島':'17','徳山':'18','下関':'19','若松':'20',
        '芦屋':'21','福岡':'22','唐津':'23','大村':'24'
    }
    return codes.get(name)

def get_all_venue_names():
    """全ての会場名を取得"""
    return [
        '桐生','戸田','江戸川','平和島',
        '多摩川','浜名湖','蒲郡','常滑',
        '津','三国','琵琶湖','住之江',
        '尼崎','鳴門','丸亀','児島',
        '宮島','徳山','下関','若松',
        '芦屋','福岡','唐津','大村'
    ]

# ── 日付形式の正規化（新機能）────────────────────────────
def normalize_date(date_str):
    """
    日付文字列を yyyymmdd 形式に正規化
    - yyyymmdd (8桁) → そのまま
    - yymmdd (6桁) → 20yymmdd に変換
    
    Returns:
        str: yyyymmdd形式の日付文字列
    """
    # 6桁の場合（yymmdd）
    if re.match(r'^\d{6}$', date_str):
        # 20を先頭に付けて8桁に
        normalized = '20' + date_str
        logging.info(f"日付正規化: {date_str} → {normalized}")
        return normalized
    
    # 8桁の場合（yyyymmdd）
    elif re.match(r'^\d{8}$', date_str):
        return date_str
    
    # それ以外
    else:
        return None

# ── 引数判定（改良版）─────────────────────────────────
def identify_arguments(arg1, arg2):
    """
    2つの引数のうち、どちらが日付でどちらが会場名かを判定
    
    Returns:
        tuple: (venue, date)
    """
    venue_names = get_all_venue_names()
    
    # 日付を正規化
    arg1_normalized = normalize_date(arg1)
    arg2_normalized = normalize_date(arg2)
    
    arg1_is_date = arg1_normalized is not None
    arg2_is_date = arg2_normalized is not None
    
    arg1_is_venue = arg1 in venue_names
    arg2_is_venue = arg2 in venue_names
    
    logging.info(f"引数判定: arg1='{arg1}' (日付: {arg1_is_date}, 会場: {arg1_is_venue})")
    logging.info(f"引数判定: arg2='{arg2}' (日付: {arg2_is_date}, 会場: {arg2_is_venue})")
    
    # 判定ロジック
    if arg1_is_date and arg2_is_venue:
        # パターン1: python script.py 20250603 戸田 または 250603 戸田
        venue = arg2
        date = arg1_normalized
        logging.info("判定結果: 引数1=日付, 引数2=会場名")
        
    elif arg1_is_venue and arg2_is_date:
        # パターン2: python script.py 戸田 20250603 または 戸田 250603
        venue = arg1
        date = arg2_normalized
        logging.info("判定結果: 引数1=会場名, 引数2=日付")
        
    else:
        # エラーパターン
        error_msg = []
        if not (arg1_is_date or arg1_is_venue):
            error_msg.append(f"引数1 '{arg1}' が日付（yyyymmdd/yymmdd）でも会場名でもありません")
        if not (arg2_is_date or arg2_is_venue):
            error_msg.append(f"引数2 '{arg2}' が日付（yyyymmdd/yymmdd）でも会場名でもありません")
        if arg1_is_date and arg2_is_date:
            error_msg.append("両方とも日付です。会場名を指定してください")
        if arg1_is_venue and arg2_is_venue:
            error_msg.append("両方とも会場名です。日付を指定してください")
            
        raise ValueError("\n".join(error_msg) + 
                        f"\n\n利用可能な会場名: {', '.join(venue_names)}" +
                        "\n日付形式: yyyymmdd (例: 20250802) または yymmdd (例: 250802)")
    
    return venue, date

# ── 日付検証 ─────────────────────────────────────────
def validate_date(yyyymmdd):
    """
    yyyymmdd形式の日付を検証
    既に正規化済みの8桁を想定
    """
    try:
        datetime.strptime(yyyymmdd, '%Y%m%d')
        return yyyymmdd
    except ValueError:
        raise ValueError(f"無効な日付: {yyyymmdd}")

# ── 日付フォーマット変換 ─────────────────────────────
def format_date(yyyymmdd):
    """yyyymmdd形式をyyyy/mm/dd形式に変換"""
    try:
        date_obj = datetime.strptime(yyyymmdd, '%Y%m%d')
        return date_obj.strftime('%Y/%m/%d')
    except ValueError:
        return yyyymmdd # 変換失敗時は元の値を返す

# ── セッション作成（リトライ設定）────────────────────
def create_session():
    retry = Retry(total=3, backoff_factor=1,
                  status_forcelist=[429,500,502,503,504],
                  allowed_methods=["GET"])
    sess = requests.Session()
    sess.mount('https://', HTTPAdapter(max_retries=retry))
    return sess

# ── HTML取得 ─────────────────────────────────────────
def fetch_html(session, jcd, hd):
    url = f"https://www.boatrace.jp/owpc/pc/race/resultlist?jcd={jcd}&hd={hd}"
    headers = {'User-Agent':'Mozilla/5.0','Accept-Language':'ja-JP'}
    logging.info(f"Fetching URL: {url}")
    resp = session.get(url, headers=headers, timeout=15)
    resp.encoding = resp.apparent_encoding
    resp.raise_for_status()
    time.sleep(1)
    return resp.text

# ── HTML解析（同着対応版）─────────────────────────────
def parse_html(html):
    soup = BeautifulSoup(html, 'html.parser')
    
    # 1. 勝式・払戻金・結果テーブル
    sec1 = soup.select_one('#section1')
    if not sec1:
        raise ValueError("セクション1が見つかりません")
    
    wrapper1 = sec1.find_next_sibling('div', class_='table1')
    main_tbl = wrapper1.find('table') if wrapper1 else None
    if not main_tbl:
        raise ValueError("勝式・払戻金テーブルが見つかりません")
    
    results = []
    for tbody in main_tbl.select('tbody'):
        cols = tbody.select('td')
        if len(cols) < 5:
            continue
        
        race = cols[0].get_text(strip=True)
        
        # 3連単の処理（同着対応）
        trio_rows = cols[1].select('.numberSet1_row')
        trio_combinations = []
        for row in trio_rows:
            numbers = [s.get_text(strip=True) for s in row.select('.numberSet1_number')]
            if numbers:
                trio_combinations.append('-'.join(numbers))
        trio = ', '.join(trio_combinations) if trio_combinations else "-"
        
        # 3連単払戻金の処理（複数対応）
        tpay_span = cols[2].select_one('.is-payout1')
        if tpay_span:
            # <br>タグで区切られた複数の払戻金を取得
            tpay_html = str(tpay_span)
            # <br>または<br/>で分割
            tpay_parts = re.split(r'<br\s*/?>', tpay_html)
            tpay_values = []
            for part in tpay_parts:
                # HTMLタグを除去して金額を抽出
                clean_part = re.sub(r'<[^>]+>', '', part).strip()
                if clean_part and '¥' in clean_part:
                    tpay_values.append(clean_part)
            tpay = ', '.join(tpay_values) if tpay_values else cols[2].get_text(strip=True)
        else:
            tpay = cols[2].get_text(strip=True)
        
        # 2連単の処理（通常は単一）
        duo = '-'.join(s.get_text(strip=True) for s in cols[3].select('.numberSet1_number'))
        dpay = cols[4].get_text(strip=True)
        
        # 備考欄を取得
        note_from_main = cols[5].get_text(strip=True) if len(cols) > 5 else ""
        
        results.append([race, trio, tpay, duo, dpay, note_from_main])

    # 2. 着順結果テーブル（全着順・決まり手・備考を取得）
    sec2 = soup.select_one('#section2')
    if not sec2:
        logging.warning("セクション2が見つかりません")
        race_details = {}
    else:
        wrapper2 = sec2.find_next_sibling('div', class_='table1')
        order_tbl = wrapper2.find('table') if wrapper2 else None
        
        race_details = {}
        if order_tbl:
            tbodies = order_tbl.select('tbody')
            for tbody in tbodies:
                rows = tbody.select('tr')
                if len(rows) >= 2:
                    # 1行目から情報取得
                    first_row = rows[0]
                    tds = first_row.select('td')
                    
                    # レース番号を取得
                    race_link = tds[0].select_one('a')
                    if race_link:
                        race_text = race_link.get_text(strip=True)
                        
                        # 決まり手と備考を取得
                        kimarite = ""
                        biko = ""
                        
                        # 決まり手は通常8番目のtd
                        if len(tds) > 8:
                            kimarite = tds[8].get_text(strip=True)
                        
                        # 備考は通常9番目のtd
                        if len(tds) > 9:
                            biko_text = tds[9].get_text(strip=True)
                            biko = biko_text if biko_text and biko_text != '\xa0' else "-"
                        
                        # 2行目から全着順を取得
                        second_row = rows[1]
                        order_tds = second_row.select('td')
                        
                        # 各着順の艇番を取得
                        order_list = []
                        for td in order_tds:
                            number_span = td.select_one('.numberSet3_number')
                            if number_span:
                                boat_num = number_span.get_text(strip=True)
                                order_list.append(boat_num)
                        
                        # 全着順を"-"で連結
                        full_order = '-'.join(order_list) if order_list else "-"
                        
                        race_details[race_text] = {
                            'full_order': full_order,
                            'kimarite': kimarite,
                            'biko': biko
                        }

    # 3. コース別勝率テーブル
    sec3 = soup.select_one('#section3')
    if not sec3:
        raise ValueError("セクション3が見つかりません")
    
    wrapper3 = sec3.find_next_sibling('div', class_='table1')
    course_tbl = wrapper3.find('table') if wrapper3 else None
    if not course_tbl:
        raise ValueError("コース別勝率テーブルが見つかりません")

    # ヘッダーからコース名取得
    header_ths = course_tbl.select('thead th')[1:]
    courses = [th.get_text(strip=True) for th in header_ths]

    # データ行
    finish_rows = course_tbl.select('tbody tr')
    rates_by_finish = {}
    
    for tr in finish_rows:
        tds = tr.find_all('td')
        finish = tds[0].get_text(strip=True)
        rates = [td.get_text(strip=True) for td in tds[1:1+len(courses)]]
        rates_by_finish[finish] = rates

    # ピボット
    course_rates = []
    for idx, course in enumerate(courses):
        rate1 = rates_by_finish.get('1着',[None]*len(courses))[idx]
        rate2 = rates_by_finish.get('2着',[None]*len(courses))[idx]
        rate3 = rates_by_finish.get('3着',[None]*len(courses))[idx]
        course_rates.append([course, rate1, rate2, rate3])

    # resultsに全着順、決まり手、備考を追加
    for i, result in enumerate(results):
        race_num = result[0]
        if race_num in race_details:
            result.append(race_details[race_num]['full_order'])
            result.append(race_details[race_num]['kimarite'])
            result.append(race_details[race_num]['biko'])
        else:
            result.append("-")
            result.append("-")
            result.append("-")

    return results, course_rates

# ── Markdown出力（同着対応版）────────────────────────────
def print_markdown(results, course_rates, venue, date):
    """
    Markdownフォーマットで結果を出力
    Args:
        results: レース結果データ（全着順・決まり手・備考含む）
        course_rates: コース別勝率データ
        venue: 会場名
        date: 日付（yyyymmdd形式）
    """
    formatted_date = format_date(date)
    print(f"## 【{venue}】{formatted_date} 勝式・払戻金・結果")
    print("| レース | 3連単着順 | 3連単配当 | 2連単着順 | 2連単配当 | 全着順 | 決まり手 | 備考 |")
    print("|--------|-----------|------------|-----------|------------|---------|----------|------|")
    for r in results:
        # 全着順、決まり手、備考を安全に取得
        full_order = r[6] if len(r) > 6 else "-"
        kimarite = r[7] if len(r) > 7 else "-"
        biko = r[8] if len(r) > 8 else "-"
        print(f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {full_order} | {kimarite} | {biko} |")

    print("\n## コース別勝率分析")
    print("| コース | 1着率 | 2着率 | 3着率 |")
    print("|----------|---------|---------|---------|")
    for c in course_rates:
        print(f"| {c[0]:<6} | {c[1]:>7} | {c[2]:>7} | {c[3]:>7} |")

# ── メイン ─────────────────────────────────────────
def main():
    args = parse_arguments()
    
    try:
        # 引数を自動判定（6桁/8桁両対応）
        venue, date = identify_arguments(args.arg1, args.arg2)
        
        # 会場コードを取得
        jcd = get_venue_code(venue)
        if not jcd:
            raise ValueError(f"無効なレース場名: {venue}")
        
        # 日付を検証（既に8桁に正規化済み）
        hd = validate_date(date)
        
        # 判定結果を表示
        print(f"📍 会場: {venue}")
        print(f"📅 日付: {format_date(date)}")
        print(f"🔄 データ取得中...\n")
        
        # データ取得・解析・出力
        session = create_session()
        html = fetch_html(session, jcd, hd)
        results, course_rates = parse_html(html)
        print_markdown(results, course_rates, venue, date)
        
    except Exception as e:
        logging.error(e)
        print(f"エラー: {e}")
        print("\n使用方法:")
        print("python3 boatrace_results.py 戸田 20250603")
        print("python3 boatrace_results.py 250603 戸田")
        print("python3 boatrace_results.py 戸田 250603")
        print(f"\n利用可能な会場名: {', '.join(get_all_venue_names())}")
        print("日付形式: yyyymmdd (例: 20250802) または yymmdd (例: 250802)")

if __name__ == '__main__':
    main()
