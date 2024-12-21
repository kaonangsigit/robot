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

def initialize_mt5():
    """
    Inisialisasi MT5
    """
    if not mt5.initialize():
        print("Inisialisasi MT5 gagal!")
        print(f"Error: {mt5.last_error()}")
        return False
    print("MT5 berhasil diinisialisasi")
    return True

def get_available_servers():
    """
    Mendapatkan daftar server yang tersedia
    """
    servers = mt5.servers_get()
    if servers is None:
        print("Tidak dapat mengambil daftar server.")
        return []
    
    print("\nDaftar Server yang Tersedia:")
    for i, server in enumerate(servers):
        print(f"{i + 1}. {server.name}")
    
    return servers

def login_to_mt5():
    """
    Login ke MT5 dengan memilih server
    """
    servers = get_available_servers()
    if not servers:
        return False

    # Meminta pengguna untuk memilih server
    server_index = int(input("\nPilih nomor server untuk login (1-{}): ".format(len(servers)))) - 1
    if server_index < 0 or server_index >= len(servers):
        print("Pilihan server tidak valid.")
        return False

    selected_server = servers[server_index]
    login = int(input("Masukkan nomor akun MT5 Anda: "))  # Ganti dengan input akun
    password = input("Masukkan password akun MT5 Anda: ")  # Ganti dengan input password

    if not mt5.login(login=login, password=password, server=selected_server.name):
        print(f"Login gagal! Error: {mt5.last_error()}")
        mt5.shutdown()
        return False

    print("Login berhasil ke server:", selected_server.name)

    # Tampilkan informasi akun
    account_info = mt5.account_info()
    if account_info is not None:
        print(f"\nInformasi Akun:")
        print(f"Nama: {account_info.name}")
        print(f"Server: {account_info.server}")
        print(f"Balance: ${account_info.balance}")
        print(f"Equity: ${account_info.equity}")
        print(f"Margin Level: {account_info.margin_level}%")

    return True

class ForexGoldAnalyzer:
    def __init__(self):
        self.forex_pairs = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "NZDUSD"]
        self.gold_symbols = ["XAUUSD", "GOLD"]  # Coba beberapa kemungkinan simbol Gold
        self.gold = None
        self.timeframes = {
            "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15,
            "M30": mt5.TIMEFRAME_M30,
            "H1": mt5.TIMEFRAME_H1,
            "H4": mt5.TIMEFRAME_H4,
            "D1": mt5.TIMEFRAME_D1
        }
        self.trade_history = []
        
        # Menambahkan indikator baru
        self.indicators = {
            'ema_fast': 8,
            'ema_medium': 21,
            'ema_slow': 50,
            'rsi_period': 14,
            'macd_fast': 12,
            'macd_slow': 26,
            'macd_signal': 9,
            'atr_period': 14
        }
        
        # Tambahan parameter untuk manajemen risiko
        self.risk_params = {
            'max_daily_trades': 5,      # Maksimum trade per hari
            'max_open_trades': 3,       # Maksimum posisi terbuka
            'max_daily_loss': 3,        # Maksimum loss harian (%)
            'required_win_rate': 60,    # Minimum win rate untuk lanjut trading (%)
            'correlation_threshold': 0.7 # Batas korelasi antar pair
        }
        
        # Tracking performa
        self.performance = {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'daily_profit_loss': 0,
            'win_rate': 0,
            'daily_trades': 0
        }
        
        # Tambahan parameter untuk filter pasar
        self.market_filters = {
            'min_volatility': 0.1,      # Minimum volatilitas untuk trading
            'max_spread': 20,           # Maximum spread yang diizinkan (dalam pips)
            'trading_hours': {
                'start': '07:00',       # Jam mulai trading (GMT+0)
                'end': '21:00'          # Jam selesai trading (GMT+0)
            },
            'excluded_days': [5, 6]     # Tidak trading di hari Sabtu (5) dan Minggu (6)
        }
        
        # Parameter untuk trailing stop
        self.trailing_params = {
            'enabled': True,
            'activation_profit': 0.5,    # Aktifkan trailing stop setelah 0.5% profit
            'trailing_distance': 20      # Jarak trailing stop dalam pips
        }
        
        # Setup notifikasi yang lebih lengkap
        self.notifications = {
            'telegram': {
                'enabled': True,
                'token': '7826750724:AAH388qrr5H0o4aH8wDJh2d4HLT9kuPS3Mo',  # Token bot Anda
                'chat_id': '734315039',  # Chat ID Anda
                'bot': None
            },
            'email': {
                'enabled': True,
                'smtp_server': 'smtp.gmail.com',
                'smtp_port': 587,
                'sender_email': 'your_email@gmail.com',     # Ganti dengan email Anda
                'sender_password': 'your_app_password',     # Ganti dengan app password Gmail
                'recipient_email': 'recipient@gmail.com'    # Ganti dengan email penerima
            }
        }
        
        # Inisialisasi bot Telegram jika diaktifkan
        if self.notifications['telegram']['enabled']:
            self.initialize_telegram_bot()

    def initialize_telegram_bot(self):
        """
        Inisialisasi bot Telegram dengan handler pesan
        """
        try:
            bot = telebot.TeleBot(self.notifications['telegram']['token'])
            self.notifications['telegram']['bot'] = bot

            # Handler untuk command /start
            @bot.message_handler(commands=['start'])
            def send_welcome(message):
                chat_id = message.chat.id
                welcome_text = f"""
🤖 Selamat datang di Bot Trading!

Chat ID Anda adalah: {chat_id}

Perintah yang tersedia:
/start - Memulai bot
/status - Cek status trading
/balance - Cek balance
/positions - Cek posisi terbuka
/help - Bantuan
                """
                bot.reply_to(message, welcome_text)
                print(f"✅ User baru terdeteksi! Chat ID: {chat_id}")
                self.notifications['telegram']['chat_id'] = str(chat_id)

            # Handler untuk command /status
            @bot.message_handler(commands=['status'])
            def send_status(message):
                status_text = """
📊 Status Trading Bot:
✅ Bot Aktif
📈 Mode: Auto Trading
⏰ Update Terakhir: {}
                """.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                bot.reply_to(message, status_text)

            # Handler untuk command /help
            @bot.message_handler(commands=['help'])
            def send_help(message):
                help_text = """
📚 Bantuan Bot Trading:

Perintah yang tersedia:
/start - Memulai bot
/status - Cek status trading
/balance - Cek balance
/positions - Cek posisi terbuka
/help - Menampilkan bantuan ini

Bot akan mengirim notifikasi otomatis untuk:
- Signal trading baru
- Eksekusi order
- Update trailing stop
- Penutupan posisi
- Error yang terjadi
- Laporan harian
                """
                bot.reply_to(message, help_text)

            # Handler untuk pesan teks biasa
            @bot.message_handler(func=lambda message: True)
            def echo_all(message):
                bot.reply_to(message, "Gunakan perintah /help untuk melihat perintah yang tersedia.")

            print("�� Bot Telegram berhasil diinisialisasi")
            
            # Mulai bot dalam thread terpisah
            import threading
            bot_thread = threading.Thread(target=bot.polling, kwargs={'none_stop': True})
            bot_thread.daemon = True
            bot_thread.start()
            
        except Exception as e:
            print(f"❌ Error inisialisasi bot Telegram: {e}")
            self.notifications['telegram']['enabled'] = False

    def test_telegram_connection(self):
        """
        Test koneksi Telegram
        """
        try:
            if not self.notifications['telegram']['enabled']:
                return False
                
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

    def send_telegram(self, message):
        """
        Kirim pesan melalui Telegram
        """
        try:
            if not self.notifications['telegram']['enabled']:
                return
                
            bot = self.notifications['telegram']['bot']
            chat_id = self.notifications['telegram']['chat_id']
            
            bot.send_message(chat_id, message)
            print("✅ Pesan Telegram terkirim")
            
        except Exception as e:
            print(f"❌ Error mengirim pesan Telegram: {e}")

    def send_email(self, subject, message):
        """
        Kirim email notifikasi
        """
        try:
            if not self.notifications['email']['enabled']:
                return
                
            email_config = self.notifications['email']
            
            # Setup email
            msg = MIMEMultipart()
            msg['From'] = email_config['sender_email']
            msg['To'] = email_config['recipient_email']
            msg['Subject'] = subject
            
            # Tambah body email
            msg.attach(MIMEText(message, 'plain'))
            
            # Buat koneksi SMTP
            server = smtplib.SMTP(email_config['smtp_server'], email_config['smtp_port'])
            server.starttls()
            
            # Login ke email
            server.login(email_config['sender_email'], email_config['sender_password'])
            
            # Kirim email
            server.send_message(msg)
            server.quit()
            
            print("✅ Email terkirim")
            
        except Exception as e:
            print(f"❌ Error mengirim email: {e}")

    def send_notification(self, message, type='info'):
        """
        Kirim notifikasi ke semua channel yang aktif
        """
        try:
            # Format pesan berdasarkan tipe
            if type == 'trade':
                subject = "🔔 Signal Trading Baru"
            elif type == 'alert':
                subject = "⚠️ Trading Alert"
            elif type == 'error':
                subject = "❌ Trading Error"
            else:
                subject = "ℹ️ Trading Info"
                
            # Kirim ke Telegram
            if self.notifications['telegram']['enabled']:
                self.send_telegram(f"{subject}\n\n{message}")
                
            # Kirim ke Email
            if self.notifications['email']['enabled']:
                self.send_email(subject, message)
                
        except Exception as e:
            print(f"Error sending notification: {e}")

    def notify_trade_execution(self, trade_info):
        """
        Kirim notifikasi untuk eksekusi trading
        """
        message = f"""
🔵 TRADE EXECUTION
Symbol: {trade_info['symbol']}
Type: {trade_info['type']}
Entry: {trade_info['entry']}
Stop Loss: {trade_info['sl']}
Take Profit 1: {trade_info['tp1']}
Take Profit 2: {trade_info['tp2']}
Lot Size: {trade_info['lot_size']}
        """
        self.send_notification(message, type='trade')

    def find_gold_symbol(self):
        for symbol in self.gold_symbols:
            if mt5.symbol_info(symbol) is not None:
                self.gold = symbol
                print(f"Simbol Gold ditemukan: {symbol}")
                return True
        print("Simbol Gold tidak ditemukan!")
        return False

    def get_price_data(self, symbol, timeframe, num_bars=100):
        """
        Mengambil data harga dari MT5
        """
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, num_bars)
        return pd.DataFrame(rates)

    def calculate_indicators(self, df):
        """
        Menghitung indikator teknikal yang lebih lengkap
        """
        # EMA
        df['EMA_fast'] = df['close'].ewm(span=self.indicators['ema_fast']).mean()
        df['EMA_medium'] = df['close'].ewm(span=self.indicators['ema_medium']).mean()
        df['EMA_slow'] = df['close'].ewm(span=self.indicators['ema_slow']).mean()
        
        # RSI
        df['RSI'] = self.calculate_rsi(df['close'], self.indicators['rsi_period'])
        
        # MACD
        exp1 = df['close'].ewm(span=self.indicators['macd_fast']).mean()
        exp2 = df['close'].ewm(span=self.indicators['macd_slow']).mean()
        df['MACD'] = exp1 - exp2
        df['Signal'] = df['MACD'].ewm(span=self.indicators['macd_signal']).mean()
        
        # ATR untuk manajemen risiko
        df['ATR'] = self.calculate_atr(df, self.indicators['atr_period'])
        
        return df

    def calculate_rsi(self, prices, period=14):
        """
        Menghitung RSI
        """
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def calculate_atr(self, df, period):
        """
        Menghitung Average True Range
        """
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()

    def analyze_signals(self, df):
        """
        Menganalisis sinyal trading berdasarkan kombinasi indikator
        """
        signals = []
        current = df.iloc[-1]
        prev = df.iloc[-2]

        # Trend Analysis
        trend = "BULLISH" if current['EMA_fast'] > current['EMA_slow'] else "BEARISH"
        
        # MACD Signal
        macd_signal = "BUY" if current['MACD'] > current['Signal'] and prev['MACD'] <= prev['Signal'] else \
                     "SELL" if current['MACD'] < current['Signal'] and prev['MACD'] >= prev['Signal'] else "NEUTRAL"
        
        # RSI Conditions
        rsi_signal = "BUY" if current['RSI'] < 30 else \
                    "SELL" if current['RSI'] > 70 else "NEUTRAL"

        # EMA Cross
        ema_signal = "BUY" if current['EMA_fast'] > current['EMA_medium'] and prev['EMA_fast'] <= prev['EMA_medium'] else \
                    "SELL" if current['EMA_fast'] < current['EMA_medium'] and prev['EMA_fast'] >= prev['EMA_medium'] else "NEUTRAL"

        # Menghitung kekuatan sinyal
        signal_strength = 0
        if trend == "BULLISH":
            signal_strength += 1
        else:
            signal_strength -= 1
            
        if macd_signal == "BUY":
            signal_strength += 2
        elif macd_signal == "SELL":
            signal_strength -= 2
            
        if rsi_signal == "BUY":
            signal_strength += 1
        elif rsi_signal == "SELL":
            signal_strength -= 1
            
        if ema_signal == "BUY":
            signal_strength += 1
        elif ema_signal == "SELL":
            signal_strength -= 1

        return {
            'strength': signal_strength,
            'trend': trend,
            'macd': macd_signal,
            'rsi': rsi_signal,
            'ema': ema_signal,
            'atr': current['ATR']
        }

    def calculate_entry_points(self, analysis, direction):
        """
        Menghitung entry, stop loss, dan take profit berdasarkan ATR
        """
        symbol_info = mt5.symbol_info(symbol)
        point = symbol_info.point
        
        current_price = mt5.symbol_info_tick(symbol).ask if direction == "BUY" else mt5.symbol_info_tick(symbol).bid
        atr = analysis['atr']
        
        # Risk management berdasarkan ATR
        sl_distance = atr * 1.5
        tp1_distance = atr * 2  # Risk:Reward 1:1.33
        tp2_distance = atr * 3  # Risk:Reward 1:2
        
        if direction in ["BUY", "STRONG_BUY"]:
            entry = current_price
            sl = entry - sl_distance
            tp1 = entry + tp1_distance
            tp2 = entry + tp2_distance
        else:
            entry = current_price
            sl = entry + sl_distance
            tp1 = entry - tp1_distance
            tp2 = entry - tp2_distance
            
        return {
            'entry': entry,
            'stop_loss': sl,
            'take_profit1': tp1,
            'take_profit2': tp2,
            'risk_pips': abs(entry - sl) / point
        }

    def display_analysis(self):
        """
        Menampilkan analisis untuk pasangan forex dan gold
        """
        print("\n=== ANALISIS PASAR ===")
        
        # Analisis untuk setiap pasangan forex
        for pair in self.forex_pairs:
            print(f"\nAnalisis untuk {pair}:")
            df = self.get_price_data(pair, self.timeframes['H1'])
            df = self.calculate_indicators(df)

            # Tampilkan indikator
            print(f"MA50: {df['MA50'].iloc[-1]}")
            print(f"RSI: {df['RSI'].iloc[-1]}")

            # Logika trading berdasarkan indikator
            if df['RSI'].iloc[-1] > 70:
                print("Sinyal: Jual (Overbought)")
            elif df['RSI'].iloc[-1] < 30:
                print("Sinyal: Beli (Oversold)")
            else:
                print("Sinyal: Tunggu")

        # Analisis untuk Gold
        if self.gold:
            print(f"\nAnalisis untuk {self.gold}:")
            df_gold = self.get_price_data(self.gold, self.timeframes['H1'])
            df_gold = self.calculate_indicators(df_gold)

            # Tampilkan indikator
            print(f"MA50: {df_gold['MA50'].iloc[-1]}")
            print(f"RSI: {df_gold['RSI'].iloc[-1]}")

            # Logika trading berdasarkan indikator
            if df_gold['RSI'].iloc[-1] > 70:
                print("Sinyal: Jual (Overbought)")
            elif df_gold['RSI'].iloc[-1] < 30:
                print("Sinyal: Beli (Oversold)")
            else:
                print("Sinyal: Tunggu")

    def execute_trade(self, symbol, trade_type, lot_size, entry_price, sl, tp1, tp2):
        """
        Eksekusi trade otomatis ke MT5
        """
        try:
            point = mt5.symbol_info(symbol).point
            deviation = 20

            if trade_type in ["STRONG_BUY", "BUY"]:
                trade_type = mt5.ORDER_TYPE_BUY
                price = mt5.symbol_info_tick(symbol).ask
            else:
                trade_type = mt5.ORDER_TYPE_SELL
                price = mt5.symbol_info_tick(symbol).bid

            # Request untuk posisi pertama (dengan TP1)
            request1 = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": lot_size / 2,
                "type": trade_type,
                "price": price,
                "sl": sl,
                "tp": tp1,
                "deviation": deviation,
                "magic": 234000,
                "comment": "python script trade",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }

            # Request untuk posisi kedua (dengan TP2)
            request2 = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": lot_size / 2,
                "type": trade_type,
                "price": price,
                "sl": sl,
                "tp": tp2,
                "deviation": deviation,
                "magic": 234000,
                "comment": "python script trade",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }

            # Eksekusi trades
            result1 = mt5.order_send(request1)
            result2 = mt5.order_send(request2)

            if result1.retcode == mt5.TRADE_RETCODE_DONE and result2.retcode == mt5.TRADE_RETCODE_DONE:
                print(f"🎯 Trades executed successfully for {symbol}")
                print(f"Order 1 (TP1) ticket: {result1.order}")
                print(f"Order 2 (TP2) ticket: {result2.order}")

                # Simpan trade history
                self.trade_history.append({
                    'datetime': datetime.now(),
                    'symbol': symbol,
                    'type': 'BUY' if trade_type == mt5.ORDER_TYPE_BUY else 'SELL',
                    'lot_size': lot_size,
                    'entry': price,
                    'sl': sl,
                    'tp1': tp1,
                    'tp2': tp2,
                    'ticket1': result1.order,
                    'ticket2': result2.order
                })
                return True
            else:
                print(f"❌ Error executing trades for {symbol}")
                print(f"Error code 1: {result1.retcode}")
                print(f"Error code 2: {result2.retcode}")
                return False

        except Exception as e:
            print(f"❌ Error in execute_trade: {e}")
            return False

    def check_existing_positions(self, symbol):
        positions = mt5.positions_get(symbol=symbol)
        return len(positions) > 0

    def close_all_positions(self, symbol):
        positions = mt5.positions_get(symbol=symbol)
        if positions:
            for position in positions:
                close_request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": symbol,
                    "volume": position.volume,
                    "type": mt5.ORDER_TYPE_SELL if position.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY,
                    "position": position.ticket,
                    "price": mt5.symbol_info_tick(symbol).bid if position.type == mt5.ORDER_TYPE_BUY else mt5.symbol_info_tick(symbol).ask,
                    "deviation": 20,
                    "magic": 234000,
                    "comment": "python script close",
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": mt5.ORDER_FILLING_IOC,
                }
                result = mt5.order_send(close_request)
                if result.retcode != mt5.TRADE_RETCODE_DONE:
                    print(f"❌ Error closing position {position.ticket}")
                else:
                    print(f"✅ Position {position.ticket} closed successfully")

    def manage_trades(self, symbol, signals, overall_strength):
        try:
            if self.check_existing_positions(symbol):
                print(f"⚠️ Already have open position for {symbol}")
                return

            if abs(overall_strength) >= 3:
                latest = signals[0]['analysis']
                direction = "STRONG_BUY" if overall_strength > 0 else "STRONG_SELL"
                entry_points = self.calculate_entry_points(latest, direction)

                account_info = mt5.account_info()
                if account_info is None:
                    print("Error: Couldn't get account info")
                    return

                balance = account_info.balance
                risk_amount = balance * 0.01  # 1% risk

                if symbol == self.gold:
                    lot_size = round(risk_amount / (abs(entry_points['entry'] - entry_points['stop_loss']) * 100), 2)
                else:
                    lot_size = round(risk_amount / (entry_points['risk_pips'] * 10), 2)

                if lot_size < 0.01:
                    lot_size = 0.01

                success = self.execute_trade(
                    symbol=symbol,
                    trade_type=direction,
                    lot_size=lot_size,
                    entry_price=entry_points['entry'],
                    sl=entry_points['stop_loss'],
                    tp1=entry_points['take_profit1'],
                    tp2=entry_points['take_profit2']
                )

                if success:
                    print(f"✅ Trade executed for {symbol}")
                    print(f"Lot Size: {lot_size}")
                    print(f"Entry: {entry_points['entry']}")
                    print(f"Stop Loss: {entry_points['stop_loss']}")
                    print(f"Take Profit 1: {entry_points['take_profit1']}")
                    print(f"Take Profit 2: {entry_points['take_profit2']}")

    def display_trade_history(self):
        """
        Menampilkan history trading
        """
        try:
            if not hasattr(self, 'trade_history'):
                self.trade_history = []  # Inisialisasi trade_history jika belum ada
                
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
                print(f"TP1: {trade['tp1']} (Ticket: {trade['ticket1']})")
                print(f"TP2: {trade['tp2']} (Ticket: {trade['ticket2']})")
                
                # Kirim notifikasi ke Telegram
                if self.notifications['telegram']['enabled']:
                    trade_message = f"""
🔄 TRADE HISTORY
📊 Symbol: {trade['symbol']}
📈 Type: {trade['type']}
💰 Lot Size: {trade['lot_size']}
⚡️ Entry: {trade['entry']}
🛑 Stop Loss: {trade['sl']}
✅ Take Profit 1: {trade['tp1']}
✅ Take Profit 2: {trade['tp2']}
🎫 Tickets: {trade['ticket1']}, {trade['ticket2']}
⏰ Time: {trade['datetime']}
                    """
                    self.send_telegram(trade_message)
                    
        except Exception as e:
            error_msg = f"❌ Error menampilkan trade history: {e}"
            print(error_msg)
            if self.notifications['telegram']['enabled']:
                self.send_telegram(error_msg)

    def check_market_conditions(self):
        """
        Mengecek kondisi pasar sebelum trading
        """
        try:
            # Cek waktu pasar
            current_time = datetime.now()
            if current_time.weekday() >= 5:  # Weekend
                return False, "Pasar tutup (Weekend)"
                
            # Cek volatilitas
            for pair in self.forex_pairs:
                df = self.get_price_data(pair, mt5.TIMEFRAME_H1, 24)
                atr = self.calculate_atr(df, 24)
                if atr.iloc[-1] < atr.mean() * 0.5:
                    return False, f"Volatilitas {pair} terlalu rendah"
                    
            # Cek news impact
            if self.check_high_impact_news():
                return False, "Ada berita ekonomi penting"
                
            return True, "Kondisi pasar normal"
            
        except Exception as e:
            return False, f"Error checking market conditions: {e}"

    def check_high_impact_news(self):
        """
        Cek berita ekonomi dengan impact tinggi
        """
        # Implementasi cek kalender ekonomi
        # Bisa menggunakan API dari forexfactory atau investing.com
        pass

    def calculate_correlation(self):
        """
        Menghitung korelasi antar pair
        """
        prices = {}
        for pair in self.forex_pairs:
            df = self.get_price_data(pair, mt5.TIMEFRAME_H1, 100)
            prices[pair] = df['close']
            
        corr_matrix = pd.DataFrame(prices).corr()
        return corr_matrix

    def update_performance_metrics(self, trade_result):
        """
        Update metrik performa trading
        """
        self.performance['total_trades'] += 1
        self.performance['daily_trades'] += 1
        
        if trade_result['profit'] > 0:
            self.performance['winning_trades'] += 1
        else:
            self.performance['losing_trades'] += 1
            
        self.performance['daily_profit_loss'] += trade_result['profit']
        self.performance['win_rate'] = (self.performance['winning_trades'] / 
                                      self.performance['total_trades'] * 100)

    def check_trading_limits(self):
        """
        Cek batasan trading
        """
        if self.performance['daily_trades'] >= self.risk_params['max_daily_trades']:
            return False, "Mencapai batas maksimum trade harian"
            
        if self.performance['daily_profit_loss'] <= -self.risk_params['max_daily_loss']:
            return False, "Mencapai batas maksimum loss harian"
            
        if self.performance['total_trades'] > 20 and \
           self.performance['win_rate'] < self.risk_params['required_win_rate']:
            return False, "Win rate di bawah minimum yang dibutuhkan"
            
        return True, "Trading masih dalam batas yang diizinkan"

    def check_trading_session(self):
        """
        Cek apakah saat ini adalah waktu trading yang baik
        """
        current_time = datetime.now()
        current_hour = current_time.strftime('%H:%M')
        
        if current_time.weekday() in self.market_filters['excluded_days']:
            return False, "Di luar hari trading"
            
        if not (self.market_filters['trading_hours']['start'] <= current_hour <= 
                self.market_filters['trading_hours']['end']):
            return False, "Di luar jam trading"
            
        return True, "Dalam sesi trading aktif"

    def check_spread(self, symbol):
        """
        Cek spread untuk pair tertentu
        """
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            return False, "Tidak dapat mendapatkan informasi symbol"
            
        spread_points = symbol_info.spread
        spread_pips = spread_points / 10  # Convert to pips
        
        if spread_pips > self.market_filters['max_spread']:
            return False, f"Spread terlalu tinggi: {spread_pips} pips"
            
        return True, "Spread normal"

    def manage_trailing_stop(self, position):
        """
        Mengatur trailing stop untuk posisi yang profit
        """
        try:
            if not self.trailing_params['enabled']:
                return
                
            current_price = mt5.symbol_info_tick(position.symbol).bid \
                           if position.type == mt5.ORDER_TYPE_BUY else \
                           mt5.symbol_info_tick(position.symbol).ask
                           
            profit_pips = (current_price - position.price_open) / mt5.symbol_info(position.symbol).point \
                         if position.type == mt5.ORDER_TYPE_BUY else \
                         (position.price_open - current_price) / mt5.symbol_info(position.symbol).point
                         
            if profit_pips >= self.trailing_params['activation_profit']:
                new_sl = current_price - (self.trailing_params['trailing_distance'] * mt5.symbol_info(position.symbol).point) \
                        if position.type == mt5.ORDER_TYPE_BUY else \
                        current_price + (self.trailing_params['trailing_distance'] * mt5.symbol_info(position.symbol).point)
                        
                if position.sl != new_sl:
                    request = {
                        "action": mt5.TRADE_ACTION_SLTP,
                        "position": position.ticket,
                        "symbol": position.symbol,
                        "sl": new_sl,
                        "tp": position.tp
                    }
                    result = mt5.order_send(request)
                    if result.retcode != mt5.TRADE_RETCODE_DONE:
                        print(f"Error updating trailing stop: {result.comment}")
                    else:
                        print(f"Trailing stop updated for {position.symbol}")
                        
        except Exception as e:
            print(f"Error in trailing stop management: {e}")

    def generate_report(self):
        """
        Membuat laporan trading harian
        """
        report = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'total_trades': self.performance['total_trades'],
            'win_rate': self.performance['win_rate'],
            'profit_loss': self.performance['daily_profit_loss'],
            'best_pair': self.get_best_performing_pair(),
            'worst_pair': self.get_worst_performing_pair()
        }
        
        return report

    def save_trading_data(self):
        """
        Menyimpan data trading ke file
        """
        try:
            data = {
                'trades': self.trade_history,
                'performance': self.performance,
                'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            filename = f"trading_data_{datetime.now().strftime('%Y%m%d')}.json"
            with open(filename, 'w') as f:
                json.dump(data, f)
                
        except Exception as e:
            print(f"Error saving trading data: {e}")

    def run_auto_trading(self):
        """
        Menjalankan auto trading dengan fitur tambahan
        """
        try:
            print("\n=== MEMULAI AUTO TRADING ===")
            
            # Cek sesi trading
            session_ok, session_message = self.check_trading_session()
            if not session_ok:
                print(f"⚠️ {session_message}")
                return
            
            # Update trailing stops untuk posisi yang ada
            positions = mt5.positions_get()
            if positions:
                for position in positions:
                    self.manage_trailing_stop(position)
            
            # Lanjutkan dengan analisis dan trading normal
            # ... (kode existing) ...
            
            # Simpan data dan generate report
            self.save_trading_data()
            report = self.generate_report()
            self.send_notification(f"Daily Report:\n{json.dumps(report, indent=2)}")
            
        except Exception as e:
            error_msg = f"❌ Error dalam auto trading: {e}"
            print(error_msg)
            self.send_notification(error_msg, type='error')

    def display_performance_metrics(self):
        """
        Tampilkan metrik performa trading
        """
        print("\n=== PERFORMANCE METRICS ===")
        print(f"Total Trades: {self.performance['total_trades']}")
        print(f"Win Rate: {self.performance['win_rate']:.2f}%")
        print(f"Daily P/L: {self.performance['daily_profit_loss']:.2f}%")
        print(f"Daily Trades: {self.performance['daily_trades']}")

    def setup_telegram_bot(self):
        """
        Setup bot Telegram dan dapatkan chat_id
        """
        try:
            # Inisialisasi bot
            bot = telebot.TeleBot(self.notifications['telegram']['token'])
            
            # Handler untuk pesan /start
            @bot.message_handler(commands=['start'])
            def send_welcome(message):
                chat_id = message.chat.id
                welcome_text = f"""
🤖 Selamat datang di Bot Trading!

Chat ID Anda adalah: {chat_id}

Silakan copy Chat ID tersebut ke konfigurasi robot trading Anda.
                """
                bot.reply_to(message, welcome_text)
                print(f"✅ Chat ID ditemukan: {chat_id}")
            
            print("✅ Bot siap! Silakan buka Telegram dan kirim pesan /start ke @TredingBYKSP_bot")
            # Jalankan bot
            bot.polling(none_stop=True)
            
        except Exception as e:
            print(f"❌ Error setup bot: {e}")

def main():
    if not initialize_mt5():
        return

    if not mt5.terminal_info().connected:
        if not login_to_mt5():
            return

    analyzer = ForexGoldAnalyzer()
    if not analyzer.find_gold_symbol():
        print("Warning: Analisis Gold akan dilewati")

    update_interval = 300  # 5 menit

    try:
        while True:
            analyzer.run_auto_trading()  # Menjalankan auto trading
            analyzer.display_trade_history()
            print(f"\nUpdate berikutnya dalam {update_interval//60} menit...")
            time.sleep(update_interval)

    except KeyboardInterrupt:
        print("\nProgram dihentikan oleh user")
    finally:
        mt5.shutdown()

if __name__ == "__main__":
    analyzer = ForexGoldAnalyzer()
    
    # Test koneksi Telegram
    print("\nMenguji koneksi Telegram...")
    if analyzer.test_telegram_connection():
        print("✅ Koneksi Telegram berhasil!")
        
        # Mulai auto trading
        print("\nMemulai auto trading...")
        analyzer.run_auto_trading()
    else:
        print("❌ Koneksi Telegram gagal!")