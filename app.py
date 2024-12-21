import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta
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
from pywinauto.application import Application
import pywinauto.keyboard as keyboard
import threading

class ForexGoldAnalyzer:
    def __init__(self):
        # Konfigurasi MT5
        self.mt5_config = {
            'login': ,  
            'password': '',  
            'server': '',  
            'path': r'C:\Program Files\MetaTrader 5\terminal64.exe'
        }
        
        # Status login
        self.login_status = {
            'is_logged_in': False,
            'login_attempts': 0,
            'last_login': None
        }
        
        # Status bot
        self.bot_status = {
            'is_running': False,
            'start_time': None,
            'total_signals': 0,
            'is_polling': False
        }
        
        # Temporary storage untuk proses login
        self.temp_credentials = {}
        
        # Setup notifikasi Telegram
        self.notifications = {
            'telegram': {
                'enabled': True,
                'token': 'YOUR_BOT_TOKEN',
                'chat_id': 'YOUR_CHAT_ID',
                'bot': None
            }
        }
        
        # Trading pairs
        self.forex_pairs = ['EURUSD', 'GBPUSD', 'USDJPY', 'XAUUSD']
        
        # Risk parameters
        self.risk_params = {
            'risk_percent': 1.0,
            'max_daily_loss': 5.0,
            'max_trades': 5,
            'max_drawdown': 2.0  # dalam persen
        }
        
        # Trading pairs dengan spread maksimum yang disesuaikan
        self.trading_pairs = {
            'forex': {
                'EURUSD': {'max_spread': 20},
                'GBPUSD': {'max_spread': 20},
                'USDJPY': {'max_spread': 20},
                'AUDUSD': {'max_spread': 25},
                'USDCAD': {'max_spread': 25}
            },
            'metals': {
                'GOLD': {'max_spread': 100},
                'GOLD.a': {'max_spread': 100},
                'GLD': {'max_spread': 100},
                'XAUUSD': {'max_spread': 100}
            },
            'crypto': {
                'BTCUSD': {'max_spread': 8200},
                'ETHUSD': {'max_spread': 5000},
                'LTCUSD': {'max_spread': 5000},
                'XRPUSD': {'max_spread': 5000}
            }
        }
        
        # Risk settings per instrument type
        self.risk_settings = {
            'forex': {
                'sl_pips': 30,
                'tp_pips': 60,
                'risk_percent': 1.0
            },
            'metals': {
                'sl_pips': 100,
                'tp_pips': 200,
                'risk_percent': 1.0
            },
            'crypto': {
                'sl_percent': 2.0,
                'tp_percent': 4.0,
                'risk_percent': 1.0
            }
        }
        
        # Konfigurasi pairs yang akan dianalisa
        self.trading_pairs = {
            'forex': ['EURUSD', 'GBPUSD', 'USDJPY'],
            'metals': ['GOLD', 'GOLD.a', 'GLD','XAUUSD'],  # Variasi simbol Gold untuk berbagai broker
            'crypto': ['BTCUSD', 'ETHUSD', 'LTCUSD', 'XRPUSD']
        }
        
        # Pengaturan analisa per instrument
        self.analysis_settings = {
            'forex': {
                'timeframes': [mt5.TIMEFRAME_M5, mt5.TIMEFRAME_M15, mt5.TIMEFRAME_H1],
                'ma_periods': {'fast': 20, 'slow': 50},
                'rsi_period': 14,
                'bb_period': 20,
                'macd_settings': {'fast': 12, 'slow': 26, 'signal': 9}
            },
            'metals': {
                'timeframes': [mt5.TIMEFRAME_M15, mt5.TIMEFRAME_H1, mt5.TIMEFRAME_H4],
                'ma_periods': {'fast': 20, 'slow': 50},
                'rsi_period': 14,
                'bb_period': 20,
                'macd_settings': {'fast': 12, 'slow': 26, 'signal': 9}
            },
            'crypto': {
                'timeframes': [mt5.TIMEFRAME_H1, mt5.TIMEFRAME_H4, mt5.TIMEFRAME_D1],
                'ma_periods': {'fast': 10, 'slow': 30},
                'rsi_period': 14,
                'bb_period': 20,
                'macd_settings': {'fast': 12, 'slow': 26, 'signal': 9}
            }
        }
        
        # Initialize Telegram bot
        if self.notifications['telegram']['enabled']:
            self.initialize_telegram_bot()

        # Market filters
        self.market_filters = {
            'trading_hours': {
                'start': datetime.strptime('09:00', '%H:%M').time(),
                'end': datetime.strptime('17:00', '%H:%M').time()
            },
            'max_spread': 3.0
        }

        # Trailing parameters
        self.trailing_params = {
            'enabled': True,
            'start_pips': 20,
            'step_pips': 10,
            'min_step': 5
        }

        # Inisialisasi MT5 saat startup
        self.initialize_mt5()

    def initialize_telegram_bot(self):
        """
        Inisialisasi bot Telegram
        """
        try:
            bot = telebot.TeleBot(self.notifications['telegram']['token'])
            self.notifications['telegram']['bot'] = bot
            self.setup_telegram_commands()
            return True
        except Exception as e:
            print(f"❌ Error initializing Telegram bot: {e}")
            return False

    def test_telegram_connection(self):
        """
        Test koneksi Telegram
        """
        try:
            bot = self.notifications['telegram']['bot']
            if bot.get_me():
                return True
            return False
        except Exception as e:
            print(f"❌ Telegram connection error: {e}")
            return False

    def send_telegram(self, message):
        """
        Kirim pesan ke Telegram
        """
        try:
            if self.notifications['telegram']['enabled']:
                bot = self.notifications['telegram']['bot']
                bot.send_message(
                    self.notifications['telegram']['chat_id'],
                    message
                )
                return True
            return False
        except Exception as e:
            print(f"❌ Error sending Telegram message: {e}")
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

    def get_price_data(self, symbol, timeframe, bars=100):
        """
        Mengambil data harga dari MT5
        """
        try:
            rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            return df
        except Exception as e:
            print(f"❌ Error mengambil data harga: {e}")
            return None

    def calculate_indicators(self, df):
        """
        Menghitung indikator teknikal
        """
        try:
            # EMA
            df['EMA_fast'] = df['close'].ewm(span=self.indicators['ema_fast']).mean()
            df['EMA_medium'] = df['close'].ewm(span=self.indicators['ema_medium']).mean()
            df['EMA_slow'] = df['close'].ewm(span=self.indicators['ema_slow']).mean()
            
            # RSI
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=self.indicators['rsi_period']).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=self.indicators['rsi_period']).mean()
            rs = gain / loss
            df['RSI'] = 100 - (100 / (1 + rs))
            
            # MACD
            exp1 = df['close'].ewm(span=self.indicators['macd_fast']).mean()
            exp2 = df['close'].ewm(span=self.indicators['macd_slow']).mean()
            df['MACD'] = exp1 - exp2
            df['Signal'] = df['MACD'].ewm(span=self.indicators['macd_signal']).mean()
            
            # ATR
            high_low = df['high'] - df['low']
            high_close = abs(df['high'] - df['close'].shift())
            low_close = abs(df['low'] - df['close'].shift())
            ranges = pd.concat([high_low, high_close, low_close], axis=1)
            true_range = ranges.max(axis=1)
            df['ATR'] = true_range.rolling(window=self.indicators['atr_period']).mean()
            
            return df
        except Exception as e:
            print(f"❌ Error menghitung indikator: {e}")
            return None

    def analyze_signals(self, df):
        """
        Menganalisis sinyal trading
        """
        try:
            current = df.iloc[-1]
            prev = df.iloc[-2]
            
            signals = {
                'ema': 'NEUTRAL',
                'rsi': 'NEUTRAL',
                'macd': 'NEUTRAL',
                'strength': 0
            }
            
            # EMA Signal
            if current['EMA_fast'] > current['EMA_slow'] and prev['EMA_fast'] <= prev['EMA_slow']:
                signals['ema'] = 'BUY'
                signals['strength'] += 1
            elif current['EMA_fast'] < current['EMA_slow'] and prev['EMA_fast'] >= prev['EMA_slow']:
                signals['ema'] = 'SELL'
                signals['strength'] -= 1
                
            # RSI Signal
            if current['RSI'] < 30:
                signals['rsi'] = 'BUY'
                signals['strength'] += 1
            elif current['RSI'] > 70:
                signals['rsi'] = 'SELL'
                signals['strength'] -= 1
                
            # MACD Signal
            if current['MACD'] > current['Signal'] and prev['MACD'] <= prev['Signal']:
                signals['macd'] = 'BUY'
                signals['strength'] += 2
            elif current['MACD'] < current['Signal'] and prev['MACD'] >= prev['Signal']:
                signals['macd'] = 'SELL'
                signals['strength'] -= 2
                
            return signals
            
        except Exception as e:
            print(f"❌ Error menganalisis sinyal: {e}")
            return None

    def calculate_position_size(self, symbol, stop_loss_pips):
        """
        Hitung ukuran posisi dengan risk 1% dari modal
        """
        try:
            account_info = mt5.account_info()
            if account_info is None:
                return 0.01  # Default minimal lot
            
            # Risk 1% dari balance
            risk_amount = account_info.balance * 0.01  # 1% risk per trade
            
            # Hitung nilai per pip
            symbol_info = mt5.symbol_info(symbol)
            pip_value = symbol_info.trade_tick_value * (10 if symbol_info.digits == 3 else 1)
            
            # Hitung lot size berdasarkan risk
            lot_size = risk_amount / (stop_loss_pips * pip_value)
            
            # Round dan batasi lot size
            lot_size = round(lot_size, 2)
            lot_size = max(0.01, min(lot_size, symbol_info.volume_max))
            
            return lot_size
            
        except Exception as e:
            print(f"❌ Error calculating position size: {e}")
            return 0.01

    def execute_trade(self, signal):
        """
        Eksekusi trading dengan risk management ketat
        """
        try:
            symbol = signal['symbol']  # Perbaikan dari signal['action']
            action = signal['action']
            
            # Cek jumlah posisi terbuka
            positions = mt5.positions_get()
            if len(positions) >= self.risk_params['max_trades']:
                self.send_telegram("⚠️ Maksimum jumlah trade tercapai")
                return False
            
            # Cek total floating loss
            total_loss = 0
            for pos in positions:
                if pos.profit < 0:
                    total_loss += abs(pos.profit)
            
            # Cek jika total kerugian sudah mencapai 1% dari modal
            account_info = mt5.account_info()
            max_loss = account_info.balance * 0.01  # 1% dari modal
            
            if total_loss >= max_loss:
                self.send_telegram(f"""
⚠️ Trading dihentikan!
Total kerugian telah mencapai batas 1% dari modal
Loss: ${total_loss:.2f}
Max Loss: ${max_loss:.2f}
                """)
                self.bot_status['is_running'] = False
                return False
            
            # Setup order dengan SL yang ketat
            symbol_info = mt5.symbol_info(symbol)
            point = symbol_info.point
            
            if action == 'BUY':
                order_type = mt5.ORDER_TYPE_BUY
                price = mt5.symbol_info_tick(symbol).ask
                sl = price - (30 * point)  # 30 pips SL
                tp = price + (60 * point)  # 60 pips TP (1:2 risk:reward)
            else:
                order_type = mt5.ORDER_TYPE_SELL
                price = mt5.symbol_info_tick(symbol).bid
                sl = price + (30 * point)
                tp = price - (60 * point)
            
            # Hitung position size berdasarkan 1% risk
            volume = self.calculate_position_size(symbol, 30)  # 30 pips SL
            
            # Kirim detail order ke Telegram
            order_details = f"""
🔄 MEMBUKA POSISI

Symbol: {symbol}
Type: {action}
Volume: {volume}
Entry: {price:.5f}
SL: {sl:.5f}
TP: {tp:.5f}
Risk: 1% (${max_loss:.2f})
            """
            self.send_telegram(order_details)
            
            # Buat request
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": order_type,
                "price": price,
                "sl": sl,
                "tp": tp,
                "deviation": 10,
                "magic": 234000,
                "comment": "risk_1_percent",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            # Kirim order
            result = mt5.order_send(request)
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                self.send_telegram(f"❌ Order gagal: {result.comment}")
                return False
            
            # Kirim konfirmasi order berhasil
            success_msg = f"""
✅ ORDER BERHASIL!

Symbol: {symbol}
Type: {action}
Volume: {volume}
Entry: {price:.5f}
SL: {sl:.5f}
TP: {tp:.5f}
            """
            self.send_telegram(success_msg)
            return True
            
        except Exception as e:
            error_msg = f"❌ Error executing trade: {e}"
            print(error_msg)
            self.send_telegram(error_msg)
            return False

    def check_market_conditions(self, symbol):
        """
        Cek kondisi market sebelum trading
        """
        try:
            # Cek waktu trading
            now = datetime.now()
            if now.weekday() in self.market_filters['excluded_days']:
                return False, "Weekend trading tidak diizinkan"
                
            current_hour = now.strftime('%H:%M')
            if not (self.market_filters['trading_hours']['start'] <= 
                   current_hour <= 
                   self.market_filters['trading_hours']['end']):
                return False, "Di luar jam trading"
                
            # Cek spread
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info.spread > self.market_filters['max_spread']:
                return False, f"Spread terlalu tinggi ({symbol_info.spread} pips)"
                
            # Cek volatilitas
            df = self.get_price_data(symbol, mt5.TIMEFRAME_H1, 24)
            volatility = (df['high'].max() - df['low'].min()) / df['low'].min() * 100
            if volatility < self.market_filters['min_volatility']:
                return False, "Volatilitas terlalu rendah"
                
            return True, "Market conditions OK"
            
        except Exception as e:
            return False, f"Error checking market conditions: {e}"

    def manage_trailing_stop(self, position):
        """
        Update trailing stop untuk posisi yang profit
        """
        try:
            if not self.trailing_params['enabled']:
                return
                
            symbol_info = mt5.symbol_info(position.symbol)
            point = symbol_info.point
            
            # Hitung profit dalam pips
            if position.type == mt5.ORDER_TYPE_BUY:
                profit_pips = (mt5.symbol_info_tick(position.symbol).bid - position.price_open) / point
            else:
                profit_pips = (position.price_open - mt5.symbol_info_tick(position.symbol).ask) / point
                
            # Update trailing stop jika profit melebihi activation_pips
            if profit_pips > self.trailing_params['activation_pips']:
                new_sl = None
                if position.type == mt5.ORDER_TYPE_BUY:
                    new_sl = mt5.symbol_info_tick(position.symbol).bid - (self.trailing_params['trailing_distance'] * point)
                    if new_sl > position.sl and new_sl > position.price_open:
                        self.modify_position(position.ticket, new_sl)
                else:
                    new_sl = mt5.symbol_info_tick(position.symbol).ask + (self.trailing_params['trailing_distance'] * point)
                    if new_sl < position.sl and new_sl < position.price_open:
                        self.modify_position(position.ticket, new_sl)
                        
        except Exception as e:
            print(f"❌ Error managing trailing stop: {e}")

    def generate_report(self):
        """
        Generate laporan performa trading
        """
        try:
            if self.performance['total_trades'] > 0:
                self.performance['win_rate'] = (self.performance['winning_trades'] / 
                                              self.performance['total_trades'] * 100)
                
            report = f"""
📊 TRADING PERFORMANCE REPORT
📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Total Trades: {self.performance['total_trades']}
Win Rate: {self.performance['win_rate']:.2f}%
Profit Factor: {abs(self.performance['total_profit']/self.performance['total_loss']) if self.performance['total_loss'] != 0 else 'N/A'}

🟢 Winning Trades: {self.performance['winning_trades']}
🔴 Losing Trades: {self.performance['losing_trades']}

💰 Total Profit: ${self.performance['total_profit']:.2f}
📉 Total Loss: ${abs(self.performance['total_loss']):.2f}
📈 Net P/L: ${(self.performance['total_profit'] + self.performance['total_loss']):.2f}

Today's P/L: ${self.performance['daily_profit_loss']:.2f}
            """
            
            self.send_telegram(report)
            return report
            
        except Exception as e:
            print(f"❌ Error generating report: {e}")

    def setup_telegram_commands(self):
        """
        Setup command handler untuk Telegram
        """
        try:
            bot = self.notifications['telegram']['bot']
            
            @bot.message_handler(commands=['start', 'help'])
            def send_welcome(message):
                if str(message.chat.id) != self.notifications['telegram']['chat_id']:
                    bot.reply_to(message, "❌ Anda tidak memiliki akses ke bot ini.")
                    return
                    
                welcome_text = """
🤖 Selamat datang di Bot Trading!

Perintah yang tersedia:
/login - Login ke MT5
/run - Mulai auto trading
/stop - Hentikan auto trading
/status - Cek status bot
/balance - Cek balance
/positions - Cek posisi terbuka
/history - Lihat history trading
/report - Lihat laporan performa
/settings - Lihat pengaturan bot
/help - Bantuan
                """
                bot.reply_to(message, welcome_text)

            @bot.message_handler(commands=['run'])
            def start_bot(message):
                if str(message.chat.id) != self.notifications['telegram']['chat_id']:
                    bot.reply_to(message, "❌ Anda tidak memiliki akses.")
                    return
                
                if not self.login_status['is_logged_in']:
                    bot.reply_to(message, "❌ Belum login ke MT5! Gunakan /login dulu.")
                    return
                
                if self.bot_status['is_running']:
                    bot.reply_to(message, "⚠️ Bot sudah berjalan!")
                    return
                
                try:
                    # Start trading dalam thread baru
                    import threading
                    self.bot_status['is_running'] = True
                    self.bot_status['start_time'] = datetime.now()
                    
                    trading_thread = threading.Thread(target=self.run_auto_trading)
                    trading_thread.daemon = True
                    trading_thread.start()
                    
                    bot.reply_to(message, """
✅ Bot trading berhasil dijalankan!

Gunakan /status untuk memonitor bot
Gunakan /stop untuk menghentikan bot
                    """)
                    
                except Exception as e:
                    error_msg = f"❌ Error starting bot: {e}"
                    bot.reply_to(message, error_msg)
                    self.bot_status['is_running'] = False

            @bot.message_handler(commands=['login'])
            def start_login(message):
                if str(message.chat.id) != self.notifications['telegram']['chat_id']:
                    bot.reply_to(message, "❌ Anda tidak memiliki akses.")
                    return
                
                if self.login_status['is_logged_in']:
                    bot.reply_to(message, "⚠️ Sudah login ke MT5!")
                    return
                
                # Reset temporary credentials
                self.temp_credentials = {}
                
                # Minta login ID
                msg = bot.reply_to(message, """
🔐 Proses Login MT5

Silakan kirim Login ID MT5 Anda:
(Ketik 'cancel' untuk membatalkan)
                """)
                bot.register_next_step_handler(msg, process_login_id)

            def process_login_id(message):
                try:
                    if message.text.lower() == 'cancel':
                        bot.reply_to(message, "✅ Proses login dibatalkan.")
                        return
                        
                    login_id = int(message.text.strip())
                    self.temp_credentials['login'] = login_id
                    
                    # Minta password
                    msg = bot.reply_to(message, """
🔑 Masukkan Password MT5:
(Pesan akan dihapus setelah diproses)
(Ketik 'cancel' untuk membatalkan)
                    """)
                    bot.register_next_step_handler(msg, process_password)
                    
                except ValueError:
                    bot.reply_to(message, """
❌ Login ID harus berupa angka!
Gunakan /login untuk mencoba lagi.
                    """)
                    return

            def process_password(message):
                try:
                    if message.text.lower() == 'cancel':
                        bot.reply_to(message, "✅ Proses login dibatalkan.")
                        # Hapus pesan untuk keamanan
                        bot.delete_message(message.chat.id, message.message_id)
                        return
                        
                    # Simpan password
                    self.temp_credentials['password'] = message.text.strip()
                    
                    # Hapus pesan password untuk keamanan
                    bot.delete_message(message.chat.id, message.message_id)
                    
                    # Minta nama server
                    msg = bot.reply_to(message, """
🏢 Masukkan Nama Server MT5:
(Contoh: XMTrading-Demo, ICMarkets-Live)
(Ketik 'cancel' untuk membatalkan)
                    """)
                    bot.register_next_step_handler(msg, process_server)
                    
                except Exception as e:
                    bot.reply_to(message, f"❌ Error: {e}")
                    return

            def process_server(message):
                try:
                    if message.text.lower() == 'cancel':
                        bot.reply_to(message, "✅ Proses login dibatalkan.")
                        return
                        
                    # Simpan server
                    self.temp_credentials['server'] = message.text.strip()
                    
                    # Update MT5 config
                    self.mt5_config.update(self.temp_credentials)
                    
                    # Coba login
                    login_result = self.initialize_mt5()
                    
                    if login_result:
                        self.login_status['is_logged_in'] = True
                        self.login_status['last_login'] = datetime.now()
                        self.login_status['login_attempts'] = 0
                        
                        account_info = mt5.account_info()
                        success_message = f"""
✅ LOGIN MT5 BERHASIL!

👤 Account: {account_info.login}
💰 Balance: ${account_info.balance:.2f}
💵 Equity: ${account_info.equity:.2f}
🏢 Broker: {account_info.company}
⚡️ Server: {self.mt5_config['server']}

Bot siap digunakan!
Kirim /help untuk melihat menu perintah.
                        """
                        bot.reply_to(message, success_message)
                        
                    else:
                        self.login_status['login_attempts'] += 1
                        bot.reply_to(message, """
❌ Login gagal! 
Silakan cek kembali kredensial Anda.
Gunakan /login untuk mencoba lagi.
                        """)
                    
                    # Hapus kredensial temporary
                    self.temp_credentials = {}
                    # Hapus password dari config
                    self.mt5_config.pop('password', None)
                    
                except Exception as e:
                    bot.reply_to(message, f"❌ Error: {e}")
                    return

            @bot.message_handler(commands=['logout'])
            def logout_mt5(message):
                if str(message.chat.id) != self.notifications['telegram']['chat_id']:
                    return
                
                if not self.login_status['is_logged_in']:
                    bot.reply_to(message, "⚠️ Belum login ke MT5!")
                    return
                
                try:
                    mt5.shutdown()
                    self.login_status['is_logged_in'] = False
                    self.login_status['last_login'] = None
                    self.mt5_config = {'path': self.mt5_config['path']}
                    bot.reply_to(message, "✅ Berhasil logout dari MT5!")
                    
                except Exception as e:
                    bot.reply_to(message, f"❌ Error logout: {e}")

            @bot.message_handler(commands=['status', 'balance', 'positions'])
            def check_info(message):
                if str(message.chat.id) != self.notifications['telegram']['chat_id']:
                    return
                
                command = message.text[1:]  # Hapus '/' dari command
                
                if command == 'status':
                    status = "🟢 Running" if self.bot_status['is_running'] else "🔴 Stopped"
                    login_status = "🟢 Connected" if self.login_status['is_logged_in'] else "🔴 Disconnected"
                    runtime = datetime.now() - self.bot_status['start_time'] if self.bot_status['start_time'] else "N/A"
                    
                    status_text = f"""
📊 STATUS BOT TRADING

Bot Status: {status}
MT5 Connection: {login_status}
Running Time: {runtime}
Total Signals: {self.bot_status['total_signals']}
Last Update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                    """
                    bot.send_message(message.chat.id, status_text)
                    
                elif command == 'balance':
                    account = mt5.account_info()
                    if account is None:
                        bot.send_message(message.chat.id, "❌ Error mendapatkan info balance")
                        return
                        
                    balance_text = f"""
💰 ACCOUNT BALANCE

Balance: ${account.balance:.2f}
Equity: ${account.equity:.2f}
Profit: ${account.profit:.2f}
Margin Level: {account.margin_level:.2f}%
                    """
                    bot.send_message(message.chat.id, balance_text)
                    
                elif command == 'positions':
                    positions = mt5.positions_get()
                    if positions is None or len(positions) == 0:
                        bot.send_message(message.chat.id, "📊 Tidak ada posisi terbuka")
                        return
                        
                    positions_text = "📊 POSISI TERBUKA\n\n"
                    for pos in positions:
                        positions_text += f"""
Symbol: {pos.symbol}
Type: {'BUY' if pos.type == 0 else 'SELL'}
Volume: {pos.volume}
Open Price: {pos.price_open:.5f}
Current Price: {pos.price_current:.5f}
SL: {pos.sl:.5f}
TP: {pos.tp:.5f}
Profit: ${pos.profit:.2f}
                        """
                    bot.send_message(message.chat.id, positions_text)

            @bot.message_handler(commands=['settings'])
            def show_settings(message):
                if str(message.chat.id) != self.notifications['telegram']['chat_id']:
                    return
                    
                settings_text = f"""
⚙️ BOT SETTINGS

Risk per Trade: {self.risk_params['risk_percent']}%
Max Daily Loss: {self.risk_params['max_daily_loss']}%
Max Trades: {self.risk_params['max_trades']}
Trading Hours: {self.market_filters['trading_hours']['start']} - {self.market_filters['trading_hours']['end']}
Max Spread: {self.market_filters['max_spread']} pips
Trailing Stop: {'Enabled' if self.trailing_params['enabled'] else 'Disabled'}
                """
                bot.reply_to(message, settings_text)

            @bot.message_handler(commands=['stop'])
            def stop_trading(message):
                if str(message.chat.id) != self.notifications['telegram']['chat_id']:
                    bot.send_message(message.chat.id, "❌ Anda tidak memiliki akses.")
                    return
                
                try:
                    # Hentikan trading
                    self.bot_status['is_running'] = False
                    
                    # Hitung runtime
                    runtime = datetime.now() - self.bot_status['start_time'] if self.bot_status['start_time'] else "N/A"
                    
                    # Tutup semua posisi terbuka
                    positions_closed = self.close_all_positions()
                    
                    stop_message = f"""
🛑 BOT TRADING DIHENTIKAN!

Runtime: {runtime}
Total Signals: {self.bot_status['total_signals']}
Posisi Ditutup: {positions_closed}

Status: Stopped
                    """
                    bot.send_message(message.chat.id, stop_message)
                    
                    print("Bot trading dihentikan via Telegram command")
                    
                except Exception as e:
                    error_msg = f"❌ Error menghentikan bot: {e}"
                    print(error_msg)
                    bot.send_message(message.chat.id, error_msg)

            print("✅ Telegram commands berhasil disetup")
            
        except Exception as e:
            print(f"❌ Error setup telegram commands: {e}")

    def initialize_mt5(self):
        """
        Inisialisasi dan login ke MT5
        """
        try:
            print("\n=== MULAI PROSES LOGIN MT5 ===")
            
            # Shutdown MT5 jika sudah berjalan
            if mt5.initialize():
                print("Menutup koneksi MT5 yang ada...")
                mt5.shutdown()
                time.sleep(2)
            
            # Inisialisasi MT5
            print("\nMencoba inisialisasi MT5...")
            init_result = mt5.initialize(
                path=self.mt5_config['path'],
                login=self.mt5_config['login'],
                password=self.mt5_config['password'],
                server=self.mt5_config['server'],
                timeout=60000
            )
            
            if not init_result:
                error_code = mt5.last_error()
                raise Exception(f"MT5 initialize failed. Error code: {error_code}")
            
            print("✅ MT5 initialized successfully")
            
            # Verifikasi login
            account_info = mt5.account_info()
            if account_info is None:
                raise Exception("Failed to get account info")
            
            # Update status login
            self.login_status.update({
                'is_logged_in': True,
                'last_login': datetime.now(),
                'login_attempts': 0
            })
            
            print("\n=== INFORMASI AKUN ===")
            print(f"Login: {account_info.login}")
            print(f"Server: {account_info.server}")
            print(f"Balance: ${account_info.balance:.2f}")
            print(f"Equity: ${account_info.equity:.2f}")
            print(f"Company: {account_info.company}")
            
            # Kirim notifikasi Telegram
            if hasattr(self, 'notifications') and self.notifications['telegram']['enabled']:
                self.send_telegram(f"""
✅ LOGIN MT5 BERHASIL!

👤 Account: {account_info.login}
💰 Balance: ${account_info.balance:.2f}
💵 Equity: ${account_info.equity:.2f}
🏢 Broker: {account_info.company}
⚡️ Server: {self.mt5_config['server']}

Bot siap digunakan!
Gunakan /help untuk melihat menu perintah.
                """)
            
            return True
            
        except Exception as e:
            print(f"\n❌ MT5 ERROR: {str(e)}")
            print(f"Last MT5 Error: {mt5.last_error()}")
            
            # Update status login
            self.login_status.update({
                'is_logged_in': False,
                'login_attempts': self.login_status['login_attempts'] + 1
            })
            
            # Kirim notifikasi error ke Telegram
            if hasattr(self, 'notifications') and self.notifications['telegram']['enabled']:
                self.send_telegram(f"""
❌ LOGIN MT5 GAGAL!

Error: {str(e)}
Attempts: {self.login_status['login_attempts']}

Gunakan /login untuk mencoba lagi.
                """)
            
            return False
            
        finally:
            print("\n=== SELESAI PROSES LOGIN ===")

    def check_login_status(self):
        """
        Cek status login dan reconnect jika perlu
        """
        try:
            if not self.login_status['is_logged_in']:
                print("⚠️ Not logged in, attempting to reconnect...")
                return self.initialize_mt5()
            
            # Cek koneksi MT5
            if not mt5.terminal_info():
                print("⚠️ MT5 connection lost, attempting to reconnect...")
                return self.initialize_mt5()
            
            return True
            
        except Exception as e:
            print(f"❌ Error checking login status: {e}")
            return False

    def start_telegram_polling(self):
        """
        Mulai polling Telegram dalam thread terpisah
        """
        try:
            if not self.bot_status['is_polling']:
                import threading
                
                bot = self.notifications['telegram']['bot']
                
                def polling_worker():
                    print("Starting Telegram polling...")
                    self.bot_status['is_polling'] = True
                    bot.infinity_polling(timeout=60, long_polling_timeout=30)
                
                polling_thread = threading.Thread(target=polling_worker)
                polling_thread.daemon = True
                polling_thread.start()
                
                print("✅ Telegram polling started!")
                return True
            
            return False
            
        except Exception as e:
            print(f"❌ Error starting Telegram polling: {e}")
            return False

    def run_auto_trading(self):
        """
        Jalankan auto trading dengan pengecekan status yang lebih baik
        """
        try:
            if self.bot_status['is_running']:
                self.send_telegram("⚠️ Bot trading sudah berjalan!")
                return
            
            print("\n=== AUTO TRADING STARTED ===")
            self.bot_status.update({
                'is_running': True,
                'start_time': datetime.now(),
                'total_signals': 0
            })
            
            self.send_telegram("🚀 Auto trading dimulai!")
            
            while self.bot_status['is_running']:
                try:
                    # Cek koneksi MT5
                    if not self.check_mt5_connection():
                        self.send_telegram("⚠️ MT5 connection lost! Mencoba reconnect...")
                        if not self.initialize_mt5():
                            time.sleep(60)
                            continue
                    
                    # Cek kondisi market
                    market_ok, market_message = self.check_market_conditions()
                    if not market_ok:
                        print(f"⚠️ {market_message}")
                        time.sleep(300)  # tunggu 5 menit
                        continue
                    
                    # Analisa setiap pair
                    for instrument_type, symbols in self.trading_pairs.items():
                        for symbol in symbols:
                            print(f"\nAnalyzing {symbol}...")
                            
                            signal = self.analyze_market(symbol)
                            if signal:
                                self.bot_status['total_signals'] += 1
                                
                                # Notifikasi sinyal
                                signal_msg = f"""
🎯 SINYAL TRADING

Symbol: {signal['symbol']}
Type: {instrument_type}
Action: {signal['action']}
Confidence: {signal['confidence']*100:.1f}%
Trend: {signal['trend']}
Momentum: {signal['momentum']}
Volume: {signal['volume']}
                                """
                                self.send_telegram(signal_msg)
                                
                                # Eksekusi trade
                                if self.execute_trade(signal):
                                    self.send_telegram("✅ Order berhasil dieksekusi!")
                                else:
                                    self.send_telegram("❌ Order gagal dieksekusi!")
                            
                            # Jeda antar analisa
                            time.sleep(2)
                    
                    # Monitor posisi terbuka
                    self.monitor_positions()
                    
                    print("\nWaiting for next analysis...")
                    time.sleep(300)  # Analisa setiap 5 menit
                    
                    # Cek status setiap iterasi
                    if not self.bot_status['is_running']:
                        print("Bot status changed to stopped, ending trading loop")
                        break
                    
                except Exception as e:
                    error_msg = f"❌ Error dalam trading loop: {e}"
                    print(error_msg)
                    self.send_telegram(error_msg)
                    time.sleep(60)
            
            print("Trading loop ended")
            self.send_telegram("🛑 Auto trading telah dihentikan!")
            
        except Exception as e:
            error_msg = f"❌ Fatal error dalam auto trading: {e}"
            print(error_msg)
            self.send_telegram(error_msg)
            self.bot_status['is_running'] = False

    def analyze_market(self, symbol):
        """
        Analisa pasar dengan parameter yang disesuaikan per instrument
        """
        try:
            # Tentukan tipe instrument
            instrument_type = self.get_instrument_type(symbol)
            if not instrument_type:
                raise Exception(f"Unknown instrument type for {symbol}")
            
            settings = self.analysis_settings[instrument_type]
            timeframes = settings['timeframes']
            
            signals = {tf: None for tf in timeframes}
            total_score = 0
            
            for tf in timeframes:
                rates = mt5.copy_rates_from_pos(symbol, tf, 0, 100)
                if rates is None:
                    continue
                
                df = pd.DataFrame(rates)
                df['time'] = pd.to_datetime(df['time'], unit='s')
                
                # Hitung indikator
                df['EMA20'] = df['close'].ewm(span=20).mean()
                df['EMA50'] = df['close'].ewm(span=50).mean()
                df['RSI'] = self.calculate_rsi(df['close'])
                bb_upper, bb_middle, bb_lower = self.calculate_bollinger_bands(df['close'])
                macd, signal = self.calculate_macd(df['close'])
                
                # Analisa momentum
                momentum_score = 0
                
                # 1. Trend Direction (EMA)
                if df['EMA20'].iloc[-1] > df['EMA50'].iloc[-1]:
                    momentum_score += 1
                elif df['EMA20'].iloc[-1] < df['EMA50'].iloc[-1]:
                    momentum_score -= 1
                
                # 2. RSI
                rsi = df['RSI'].iloc[-1]
                if 30 <= rsi <= 70:  # Range normal
                    if rsi > 50:
                        momentum_score += 1
                    else:
                        momentum_score -= 1
                
                # 3. Bollinger Bands
                current_price = df['close'].iloc[-1]
                if current_price > bb_upper[-1]:
                    momentum_score -= 1
                elif current_price < bb_lower[-1]:
                    momentum_score += 1
                
                # 4. MACD
                if macd[-1] > signal[-1] and macd[-2] <= signal[-2]:
                    momentum_score += 2
                elif macd[-1] < signal[-1] and macd[-2] >= signal[-2]:
                    momentum_score -= 2
                
                # 5. Volume Analysis
                if df['tick_volume'].iloc[-1] > df['tick_volume'].iloc[-2]:
                    momentum_score += 1
                
                total_score += momentum_score
                
                # Determine signal for this timeframe
                if momentum_score >= 2:
                    signals[tf] = 'BUY'
                elif momentum_score <= -2:
                    signals[tf] = 'SELL'
            
            # Final decision based on all timeframes
            buy_signals = sum(1 for s in signals.values() if s == 'BUY')
            sell_signals = sum(1 for s in signals.values() if s == 'SELL')
            
            # Calculate confidence level
            confidence = max(buy_signals, sell_signals) / len(timeframes)
            
            if confidence >= 0.5:  # Minimal 50% timeframes setuju
                action = 'BUY' if buy_signals > sell_signals else 'SELL'
                
                return {
                    'symbol': symbol,
                    'action': action,
                    'confidence': confidence,
                    'total_score': total_score,
                    'type': instrument_type,
                    'signals': signals
                }
            
            return None
            
        except Exception as e:
            print(f"❌ Error analyzing {symbol}: {e}")
            return None

    def get_instrument_type(self, symbol):
        """
        Tentukan tipe instrument dari symbol
        """
        for type_, symbols in self.trading_pairs.items():
            if symbol in symbols:
                return type_
        return None

    def execute_trade(self, signal):
        """
        Eksekusi trading dengan parameter yang disesuaikan
        """
        try:
            symbol = signal['symbol']
            action = signal['action']
            instrument_type = signal['type']
            
            # Get symbol info
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is None:
                raise Exception(f"Failed to get symbol info for {symbol}")
            
            # Cek spread
            current_spread = (symbol_info.ask - symbol_info.bid) / symbol_info.point
            max_allowed_spread = self.trading_pairs[instrument_type][symbol]['max_spread']
            
            if current_spread > max_allowed_spread:
                self.send_telegram(f"""
⚠️ Spread terlalu tinggi untuk {symbol}
Current: {current_spread:.1f} pips
Max allowed: {max_allowed_spread} pips
                """)
                return False
            
            # Setup order parameters
            volume = self.calculate_position_size(symbol, instrument_type)
            price = symbol_info.ask if action == 'BUY' else symbol_info.bid
            
            # Calculate SL/TP
            if instrument_type == 'crypto':
                sl_distance = price * (self.risk_settings[instrument_type]['sl_percent'] / 100)
                tp_distance = price * (self.risk_settings[instrument_type]['tp_percent'] / 100)
            else:
                sl_distance = self.risk_settings[instrument_type]['sl_pips'] * symbol_info.point
                tp_distance = self.risk_settings[instrument_type]['tp_pips'] * symbol_info.point
            
            sl = price - sl_distance if action == 'BUY' else price + sl_distance
            tp = price + tp_distance if action == 'BUY' else price - tp_distance
            
            # Prepare order request
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": mt5.ORDER_TYPE_BUY if action == 'BUY' else mt5.ORDER_TYPE_SELL,
                "price": price,
                "sl": sl,
                "tp": tp,
                "deviation": 20,
                "magic": 234000,
                "comment": f"signal_{signal['confidence']:.2f}",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            # Execute order
            result = mt5.order_send(request)
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                raise Exception(f"Order failed: {result.comment}")
            
            # Send notification
            self.send_telegram(f"""
✅ ORDER EXECUTED

Symbol: {symbol}
Type: {action}
Price: {price:.5f}
Volume: {volume:.2f}
SL: {sl:.5f}
TP: {tp:.5f}
Spread: {current_spread:.1f} pips
Confidence: {signal['confidence']*100:.1f}%
            """)
            
            return True
            
        except Exception as e:
            error_msg = f"❌ Error executing trade: {e}"
            print(error_msg)
            self.send_telegram(error_msg)
            return False

    def calculate_ma(self, close, period):
        """
        Menghitung Moving Average
        """
        import numpy as np
        return np.convolve(close, np.ones(period), 'valid') / period

    def calculate_rsi(self, close, period=14):
        """
        Menghitung RSI (Relative Strength Index)
        """
        import numpy as np
        
        # Hitung perubahan harga
        delta = np.diff(close)
        
        # Pisahkan gain dan loss
        gain = np.where(delta > 0, delta, 0)
        loss = np.where(delta < 0, -delta, 0)
        
        # Hitung average gain dan loss
        avg_gain = np.convolve(gain, np.ones(period), 'valid') / period
        avg_loss = np.convolve(loss, np.ones(period), 'valid') / period
        
        # Hitung RS dan RSI
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi

    def calculate_bollinger_bands(self, close, period=20, std_dev=2):
        """
        Menghitung Bollinger Bands
        """
        import numpy as np
        
        # Hitung MA dan Standard Deviation
        ma = self.calculate_ma(close, period)
        std = np.std(close[-period:])
        
        # Hitung bands
        upper_band = ma + (std_dev * std)
        lower_band = ma - (std_dev * std)
        
        return upper_band, ma, lower_band

    def calculate_macd(self, close, fast=12, slow=26, signal=9):
        """
        Menghitung MACD (Moving Average Convergence Divergence)
        """
        import numpy as np
        
        # Hitung EMA
        ema_fast = self.calculate_ema(close, fast)
        ema_slow = self.calculate_ema(close, slow)
        
        # Hitung MACD line
        macd_line = ema_fast - ema_slow
        
        # Hitung signal line
        signal_line = self.calculate_ema(macd_line, signal)
        
        return macd_line, signal_line

    def calculate_ema(self, data, period):
        """
        Menghitung Exponential Moving Average
        """
        import numpy as np
        
        multiplier = 2 / (period + 1)
        ema = [data[0]]
        
        for price in data[1:]:
            ema.append((price * multiplier) + (ema[-1] * (1 - multiplier)))
            
        return np.array(ema)

    def check_market_conditions(self):
        """
        Cek kondisi pasar sebelum trading
        """
        try:
            current_time = datetime.now().time()
            
            # Cek jam trading menggunakan datetime.time()
            if not (self.market_filters['trading_hours']['start'] <= 
                   current_time <= 
                   self.market_filters['trading_hours']['end']):
                return False, "Di luar jam trading"
            
            # Cek high impact news
            if self.check_economic_calendar():
                return False, "Ada high impact news"
            
            # Cek spread
            for symbol in self.forex_pairs:
                tick = mt5.symbol_info_tick(symbol)
                spread = (tick.ask - tick.bid) / tick.bid * 10000
                
                if spread > self.market_filters['max_spread']:
                    return False, f"Spread terlalu tinggi pada {symbol}"
            
            return True, "Market conditions OK"
            
        except Exception as e:
            return False, f"Error checking market conditions: {e}"

    def check_economic_calendar(self):
        """
        Cek economic calendar untuk high impact news
        """
        # Implementasi cek kalender ekonomi
        # Bisa menggunakan API dari forexfactory atau investing.com
        return False

    def trailing_stop(self, position):
        """
        Update trailing stop untuk posisi yang profit
        """
        try:
            if not self.trailing_params['enabled']:
                return
            
            symbol_info = mt5.symbol_info(position.symbol)
            point = symbol_info.point
            
            # Hitung profit dalam pips
            profit_pips = position.profit / (symbol_info.trade_tick_value * position.volume)
            
            if profit_pips >= self.trailing_params['start_pips']:
                new_sl = None
                
                if position.type == mt5.ORDER_TYPE_BUY:
                    potential_sl = position.price_current - (self.trailing_params['step_pips'] * point)
                    if potential_sl > position.sl + (self.trailing_params['min_step'] * point):
                        new_sl = potential_sl
                else:
                    potential_sl = position.price_current + (self.trailing_params['step_pips'] * point)
                    if potential_sl < position.sl - (self.trailing_params['min_step'] * point):
                        new_sl = potential_sl
                
                if new_sl:
                    request = {
                        "action": mt5.TRADE_ACTION_SLTP,
                        "symbol": position.symbol,
                        "position": position.ticket,
                        "sl": new_sl,
                        "tp": position.tp
                    }
                    
                    result = mt5.order_send(request)
                    if result.retcode == mt5.TRADE_RETCODE_DONE:
                        self.send_telegram(f"""
🔄 TRAILING STOP UPDATE
Ticket: {position.ticket}
Symbol: {position.symbol}
New SL: {new_sl:.5f}
                        """)
                        
        except Exception as e:
            print(f"❌ Error updating trailing stop: {e}")

    def monitor_positions(self):
        """
        Monitor posisi terbuka dan update trailing stop
        """
        try:
            positions = mt5.positions_get()
            if positions:
                for position in positions:
                    # Update trailing stop
                    self.trailing_stop(position)
                    
                    # Cek drawdown
                    if position.profit < 0:
                        drawdown = abs(position.profit) / mt5.account_info().balance * 100
                        if drawdown >= self.risk_params['max_drawdown']:
                            self.close_position(position)
                            self.send_telegram(f"""
⚠️ POSISI DITUTUP - MAX DRAWDOWN
Ticket: {position.ticket}
Symbol: {position.symbol}
Loss: ${position.profit:.2f}
Drawdown: {drawdown:.2f}%
                            """)
                            
        except Exception as e:
            print(f"❌ Error monitoring positions: {e}")

    def close_position(self, position):
        """
        Tutup posisi trading spesifik
        """
        try:
            # Tentukan tipe order (kebalikan dari posisi)
            close_type = mt5.ORDER_TYPE_SELL if position.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
            
            # Siapkan request
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": position.symbol,
                "volume": position.volume,
                "type": close_type,
                "position": position.ticket,
                "price": mt5.symbol_info_tick(position.symbol).bid if position.type == mt5.ORDER_TYPE_BUY else mt5.symbol_info_tick(position.symbol).ask,
                "deviation": 20,
                "magic": 234000,
                "comment": "close_by_bot",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            # Kirim request
            result = mt5.order_send(request)
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                print(f"❌ Error closing position {position.ticket}: {result.comment}")
                return False
            
            # Kirim notifikasi
            close_msg = f"""
📤 POSISI DITUTUP

Ticket: {position.ticket}
Symbol: {position.symbol}
Volume: {position.volume}
Profit: ${position.profit:.2f}
            """
            self.send_telegram(close_msg)
            
            return True
            
        except Exception as e:
            print(f"❌ Error closing position {position.ticket}: {e}")
            return False

    def check_mt5_connection(self):
        """
        Cek koneksi MT5 dan status login
        """
        try:
            # Cek apakah MT5 terkoneksi
            if not mt5.terminal_info():
                print("❌ MT5 tidak terkoneksi")
                return False
                
            # Cek apakah sudah login
            account_info = mt5.account_info()
            if account_info is None:
                print("❌ Belum login ke MT5")
                return False
                
            # Cek apakah login ID sesuai
            if account_info.login != self.mt5_config['login']:
                print("❌ Login ID tidak sesuai")
                return False
                
            return True
            
        except Exception as e:
            print(f"❌ Error checking MT5 connection: {e}")
            return False

    def close_all_positions(self):
        """
        Tutup semua posisi yang terbuka
        """
        try:
            positions = mt5.positions_get()
            if positions is None or len(positions) == 0:
                return "Tidak ada posisi terbuka"
            
            closed_count = 0
            for position in positions:
                if self.close_position(position):
                    closed_count += 1
            
            return f"{closed_count}/{len(positions)} posisi ditutup"
            
        except Exception as e:
            print(f"❌ Error closing positions: {e}")
            return "Error menutup posisi"

def main():
    # Initialize analyzer
    analyzer = ForexGoldAnalyzer()
    
    # Test Telegram connection only
    if analyzer.test_telegram_connection():
        print("✅ Telegram connection successful!")
        
        # Start Telegram polling
        if analyzer.start_telegram_polling():
            print("\n🤖 Bot siap menerima perintah!")
            print("Kirim /start atau /help untuk melihat menu")
            print("Gunakan /login untuk login ke MT5")
            
            # Keep main thread running
            while True:
                time.sleep(1)
                
    else:
        print("❌ Telegram connection failed!")

if __name__ == "__main__":
    try:
        # Initialize analyzer
        analyzer = ForexGoldAnalyzer()
        
        # Test Telegram connection only
        if analyzer.test_telegram_connection():
            print("✅ Telegram connection successful!")
            
            # Start Telegram polling
            if analyzer.start_telegram_polling():
                print("\n🤖 Bot siap menerima perintah!")
                print("Kirim /start atau /help untuk melihat menu")
                print("Gunakan /login untuk login ke MT5")
                
                # Keep main thread running
                while True:
                    time.sleep(1)
                    
        else:
            print("❌ Telegram connection failed!")

    except KeyboardInterrupt:
        print("\n⚠️ Program dihentikan oleh user")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
    finally:
        if mt5.initialize():
            mt5.shutdown()