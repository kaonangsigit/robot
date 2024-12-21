import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime
import time
import numpy as np
import os
import json
import telebot
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from telebot.handler_backends import State, StatesGroup
from telebot.storage import StateMemoryStorage

class ForexGoldAnalyzer:
    def __init__(self):
        self.forex_pairs = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "NZDUSD"]
        self.gold_symbols = ["XAUUSD", "GOLD"]
        self.gold = None
        self.timeframes = {
            "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15,
            "M30": mt5.TIMEFRAME_M30,
            "H1": mt5.TIMEFRAME_H1,
            "H4": mt5.TIMEFRAME_H4,
            "D1": mt5.TIMEFRAME_D1
        }
        
        # Inisialisasi trade history
        self.trade_history = []
        
        # Setup notifikasi Telegram
        self.notifications = {
            'telegram': {
                'enabled': True,
                'token': '7826750724:AAH388qrr5H0o4aH8wDJh2d4HLT9kuPS3Mo',
                'chat_id': '734315039',
                'bot': None
            }
        }
        
        # Inisialisasi bot Telegram
        if self.notifications['telegram']['enabled']:
            self.initialize_telegram_bot()

    def initialize_telegram_bot(self):
        try:
            bot = telebot.TeleBot(self.notifications['telegram']['token'])
            self.notifications['telegram']['bot'] = bot
            print("✅ Bot Telegram berhasil diinisialisasi")
        except Exception as e:
            print(f"❌ Error inisialisasi bot Telegram: {e}")
            self.notifications['telegram']['enabled'] = False

    def send_telegram(self, message):
        try:
            if not self.notifications['telegram']['enabled']:
                return
                
            bot = self.notifications['telegram']['bot']
            chat_id = self.notifications['telegram']['chat_id']
            
            bot.send_message(chat_id, message)
            print("✅ Pesan Telegram terkirim")
            
        except Exception as e:
            print(f"❌ Error mengirim pesan Telegram: {e}")

    def test_telegram_connection(self):
        try:
            test_message = """
🤖 Bot Trading berhasil terhubung!

⚡️ Status: Active
📊 Mode: Auto Trading
⏰ Time: {}
            """.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            
            self.send_telegram(test_message)
            return True
        except Exception as e:
            print(f"❌ Error test koneksi Telegram: {e}")
            return False

    def display_trade_history(self):
        try:
            if not self.trade_history:
                print("\nBelum ada history trading")
                return

            print("\n=== TRADING HISTORY ===")
            for trade in self.trade_history:
                print(f"\nTrade pada {trade['datetime']}")
                print(f"Symbol: {trade['symbol']}")
                print(f"Type: {trade['type']}")
                print(f"Lot: {trade['lot_size']}")
                print(f"Entry: {trade['entry']}")
                print(f"SL: {trade['sl']}")
                print(f"TP1: {trade['tp1']}")
                print(f"TP2: {trade['tp2']}")
                
        except Exception as e:
            print(f"❌ Error menampilkan trade history: {e}")

def main():
    # Inisialisasi analyzer
    analyzer = ForexGoldAnalyzer()
    
    # Test koneksi Telegram
    print("\nMenguji koneksi Telegram...")
    if analyzer.test_telegram_connection():
        print("✅ Koneksi Telegram berhasil!")
    else:
        print("❌ Koneksi Telegram gagal!")

if __name__ == "__main__":
    main()