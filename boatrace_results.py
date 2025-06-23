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

# ── 引数判定（新機能）─────────────────────────────────
def identify_arguments(arg1, arg2):
    """
    2つの引数のうち、どちらが日付でどちらが会場名かを判定
    
    Returns:
        tuple: (venue, date)
    """
    venue_names = get_all_venue_names()
    
    # 日付パターン（yyyymmdd）
    date_pattern = r'^\d{8}$'
    
    arg1_is_date = bool(re.match(date_pattern, arg1))
    arg2_is_date = bool(re.match(date_pattern, arg2))
    
    arg1_is_venue = arg1 in venue_names
    arg2_is_venue = arg2 in venue_names
    
    logging.info(f"引数判定: arg1='{arg1}' (日付: {arg1_is_date}, 会場: {arg1_is_venue})")
    logging.info(f"引数判定: arg2='{arg2}' (日付: {arg2_is_date}, 会場: {arg2_is_venue})")
    
    # 判定ロジック
    if arg1_is_date and arg2_is_venue:
        # パターン1: python script.py 20250603 戸田
        venue = arg2
        date = arg1
        logging.info("判定結果: 引数1=日付, 引数2=会場名")
        
    elif arg1_is_venue and arg2_is_date:
        # パターン2: python script.py 戸田 20250603
        venue = arg1
        date = arg2
        logging.info("判定結果: 引数1=会場名, 引数2=日付")
        
    else:
        # エラーパターン
        error_msg = []
        if not (arg1_is_date or arg1_is_venue):
            error_msg.append(f"引数1 '{arg1}' が日付（yyyymmdd）でも会場名でもありません")
        if not (arg2_is_date or arg2_is_venue):
            error_msg.append(f"引数2 '{arg2}' が日付（yyyymmdd）でも会場名でもありません")
        if arg1_is_date and arg2_is_date:
            error_msg.append("両方とも日付です。会場名を指定してください")
        if arg1_is_venue and arg2_is_venue:
            error_msg.append("両方とも会場名です。日付を指定してください")
            
        raise ValueError("\n".join(error_msg) + f"\n\n利用可能な会場名: {', '.join(venue_names)}")
    
    return venue, date

# ── 日付検証 ─────────────────────────────────────────
def validate_date(yyyymmdd):
    try:
        datetime.strptime(yyyymmdd, '%Y%m%d')
        return yyyymmdd
    except ValueError:
        raise ValueError("日付は yyyymmdd 形式で入力してください")

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

# ── HTML解析 ─────────────────────────────────────────
def parse_html(html):
    soup = BeautifulSoup(html, 'html.parser')
    
    # 勝式・払戻金・結果テーブル
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
        trio = '-'.join(s.get_text(strip=True) for s in cols[1].select('.numberSet1_number'))
        tpay = cols[2].get_text(strip=True)
        duo = '-'.join(s.get_text(strip=True) for s in cols[3].select('.numberSet1_number'))
        dpay = cols[4].get_text(strip=True)
        results.append([race, trio, tpay, duo, dpay])

    # コース別勝率テーブル
    sec3 = soup.select_one('#section3')
    if not sec3:
        raise ValueError("セクション3が見つかりません")
    
    wrapper3 = sec3.find_next_sibling('div', class_='table1')
    course_tbl = wrapper3.find('table') if wrapper3 else None
    if not course_tbl:
        raise ValueError("コース別勝率テーブルが見つかりません")

    # ヘッダーからコース名取得 (1コース～6コース)
    header_ths = course_tbl.select('thead th')[1:] # 先頭は「着順」
    courses = [th.get_text(strip=True) for th in header_ths]

    # データ行: 各着順ごとに6コース分の率を取得
    finish_rows = course_tbl.select('tbody tr')
    rates_by_finish = {}
    
    for tr in finish_rows:
        tds = tr.find_all('td')
        finish = tds[0].get_text(strip=True) # "1着" etc
        rates = [td.get_text(strip=True) for td in tds[1:1+len(courses)]]
        rates_by_finish[finish] = rates

    # ピボット: コースごとに1着率,2着率,3着率 をまとめる
    course_rates = []
    for idx, course in enumerate(courses):
        # finishRows keys: e.g. ["1着","2着",...]
        rate1 = rates_by_finish.get('1着',[None]*len(courses))[idx]
        rate2 = rates_by_finish.get('2着',[None]*len(courses))[idx]
        rate3 = rates_by_finish.get('3着',[None]*len(courses))[idx]
        course_rates.append([course, rate1, rate2, rate3])

    return results, course_rates

# ── Markdown出力 ────────────────────────────────────
def print_markdown(results, course_rates, venue, date):
    """
    Markdownフォーマットで結果を出力
    Args:
        results: レース結果データ
        course_rates: コース別勝率データ
        venue: 会場名
        date: 日付（yyyymmdd形式）
    """
    formatted_date = format_date(date)
    print(f"## 【{venue}】{formatted_date} 勝式・払戻金・結果")
    print("| レース | 3連単着順 | 3連単配当 | 2連単着順 | 2連単配当 |")
    print("|--------|-----------|------------|-----------|------------|")
    for r in results:
        print(f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} |")

    print("\n## コース別勝率分析")
    print("| コース | 1着率 | 2着率 | 3着率 |")
    print("|----------|---------|---------|---------|")
    for c in course_rates:
        print(f"| {c[0]:<6} | {c[1]:>7} | {c[2]:>7} | {c[3]:>7} |")

# ── メイン ─────────────────────────────────────────
def main():
    args = parse_arguments()
    
    try:
        # 引数を自動判定
        venue, date = identify_arguments(args.arg1, args.arg2)
        
        # 会場コードを取得
        jcd = get_venue_code(venue)
        if not jcd:
            raise ValueError(f"無効なレース場名: {venue}")
        
        # 日付を検証
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
        print("python boatrace_results.py 戸田 20250603")
        print("python boatrace_results.py 20250603 戸田")
        print(f"\n利用可能な会場名: {', '.join(get_all_venue_names())}")

if __name__ == '__main__':
    main()
