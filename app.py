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
                'token': 'isi token telegram',
                'chat_id': 'isi chat id telegram',
                'bot': None
            }
        }
        
        # Inisialisasi MT5 tanpa login
        self.mt5_config = {
            'path': r'C:\Program Files\MetaTrader 5\terminal64.exe'
        }
        
        # Status login
        self.login_status = {
            'is_logged_in': False,
            'login_attempts': 0,
            'last_login': None
        }
        
        # Temporary storage untuk proses login
        self.temp_credentials = {}
        
        # Inisialisasi bot Telegram
        if self.notifications['telegram']['enabled']:
            self.initialize_telegram_bot()
        
        # Tambahan parameter untuk indikator
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
        
        # Parameter manajemen risiko
        self.risk_params = {
            'risk_percent': 1.0,  # Risiko 1% per trade
            'max_daily_loss': 3.0,  # Maksimum loss harian 3%
            'max_trades': 5,  # Maksimum trade per hari
            'correlation_threshold': 0.7  # Batas korelasi antar pair
        }
        
        # Tambahan parameter untuk filter market
        self.market_filters = {
            'min_volatility': 0.1,      # Minimum volatilitas untuk trading
            'max_spread': 20,           # Maximum spread dalam pips
            'trading_hours': {
                'start': '07:00',       # Jam mulai (GMT+0)
                'end': '21:00'          # Jam selesai (GMT+0)
            },
            'excluded_days': [5, 6]     # Tidak trading Sabtu-Minggu
        }
        
        # Parameter untuk trailing stop
        self.trailing_params = {
            'enabled': True,
            'activation_pips': 20,      # Aktifkan setelah profit 20 pips
            'trailing_distance': 15      # Jarak trailing stop dalam pips
        }
        
        # Performance tracking
        self.performance = {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'total_profit': 0,
            'total_loss': 0,
            'daily_profit_loss': 0,
            'win_rate': 0
        }
        
        # Status bot
        self.bot_status = {
            'is_running': False,
            'start_time': None,
            'total_signals': 0,
            'is_polling': False  # Tambahan status untuk polling
        }
        
        # Command handler untuk Telegram
        if self.notifications['telegram']['enabled']:
            self.setup_telegram_commands()

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
        Menghitung ukuran posisi berdasarkan risiko
        """
        try:
            account_info = mt5.account_info()
            if account_info is None:
                raise Exception("Tidak dapat mendapatkan informasi akun")
                
            balance = account_info.balance
            risk_amount = balance * (self.risk_params['risk_percent'] / 100)
            
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is None:
                raise Exception(f"Tidak dapat mendapatkan informasi symbol {symbol}")
                
            pip_value = symbol_info.trade_tick_value
            pip_risk = stop_loss_pips * pip_value
            
            lot_size = risk_amount / pip_risk
            lot_size = round(lot_size, 2)  # Round to 2 decimal places
            
            # Pastikan lot size dalam batas yang diizinkan
            if lot_size < symbol_info.volume_min:
                lot_size = symbol_info.volume_min
            elif lot_size > symbol_info.volume_max:
                lot_size = symbol_info.volume_max
                
            return lot_size
            
        except Exception as e:
            print(f"❌ Error menghitung position size: {e}")
            return 0.01  # Default minimal lot size

    def execute_trade(self, symbol, trade_type, lot_size, sl_price, tp_price):
        """
        Eksekusi order trading
        """
        try:
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": lot_size,
                "type": mt5.ORDER_TYPE_BUY if trade_type == "BUY" else mt5.ORDER_TYPE_SELL,
                "price": mt5.symbol_info_tick(symbol).ask if trade_type == "BUY" else mt5.symbol_info_tick(symbol).bid,
                "sl": sl_price,
                "tp": tp_price,
                "deviation": 20,
                "magic": 234000,
                "comment": "python script open",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            result = mt5.order_send(request)
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                raise Exception(f"Order gagal dengan error code: {result.retcode}")
                
            # Tambahkan ke history
            trade_info = {
                'datetime': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'symbol': symbol,
                'type': trade_type,
                'lot_size': lot_size,
                'entry': request['price'],
                'sl': sl_price,
                'tp': tp_price,
                'ticket': result.order
            }
            self.trade_history.append(trade_info)
            
            # Kirim notifikasi
            self.send_telegram(f"""
🔵 TRADE EXECUTED
Symbol: {symbol}
Type: {trade_type}
Lot: {lot_size}
Entry: {request['price']}
SL: {sl_price}
TP: {tp_price}
Ticket: {result.order}
            """)
            
            return True
            
        except Exception as e:
            print(f"❌ Error eksekusi trade: {e}")
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
        Update setup_telegram_commands dengan sistem login yang lebih aman
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

            @bot.message_handler(commands=['status'])
            def check_status(message):
                if str(message.chat.id) != self.notifications['telegram']['chat_id']:
                    return
                
                # Update status untuk menampilkan info login
                status = "🟢 Running" if self.bot_status['is_running'] else "🔴 Stopped"
                login_status = "🟢 Connected" if self.login_status['is_logged_in'] else "🔴 Disconnected"
                last_login = self.login_status['last_login'].strftime('%Y-%m-%d %H:%M:%S') if self.login_status['last_login'] else "Never"
                
                status_text = f"""
📊 STATUS BOT TRADING

Bot Status: {status}
MT5 Connection: {login_status}
Last Login: {last_login}
Running Time: {datetime.now() - self.bot_status['start_time'] if self.bot_status['start_time'] else 'N/A'}
Total Signals: {self.bot_status['total_signals']}
Last Update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                """
                bot.reply_to(message, status_text)

            @bot.message_handler(commands=['balance'])
            def check_balance(message):
                if str(message.chat.id) != self.notifications['telegram']['chat_id']:
                    return
                    
                account = mt5.account_info()
                if account is None:
                    bot.reply_to(message, "❌ Error mendapatkan info balance")
                    return
                    
                balance_text = f"""
💰 ACCOUNT BALANCE

Balance: ${account.balance:.2f}
Equity: ${account.equity:.2f}
Profit: ${account.profit:.2f}
Margin Level: {account.margin_level:.2f}%
                """
                bot.reply_to(message, balance_text)

            @bot.message_handler(commands=['positions'])
            def check_positions(message):
                if str(message.chat.id) != self.notifications['telegram']['chat_id']:
                    return
                    
                positions = mt5.positions_get()
                if positions is None or len(positions) == 0:
                    bot.reply_to(message, "📊 Tidak ada posisi terbuka")
                    return
                    
                positions_text = "📊 POSISI TERBUKA\n\n"
                for pos in positions:
                    positions_text += f"""
Symbol: {pos.symbol}
Type: {'BUY' if pos.type == 0 else 'SELL'}
Volume: {pos.volume}
Open Price: {pos.price_open}
Current Price: {pos.price_current}
SL: {pos.sl}
TP: {pos.tp}
Profit: ${pos.profit}
                    """
                
                bot.reply_to(message, positions_text)

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

            print("✅ Telegram commands berhasil disetup")
            
        except Exception as e:
            print(f"❌ Error setup telegram commands: {e}")

    def initialize_mt5(self):
        """
        Inisialisasi dan login ke MT5
        """
        try:
            if not mt5.initialize(path=self.mt5_config['path']):
                raise Exception("MT5 initialize() failed")
                
            # Login hanya jika ada kredensial
            if all(k in self.mt5_config for k in ['login', 'password', 'server']):
                if not mt5.login(
                    login=self.mt5_config['login'],
                    password=self.mt5_config['password'],
                    server=self.mt5_config['server']
                ):
                    raise Exception("MT5 login failed")
                
                # Cek koneksi
                account_info = mt5.account_info()
                if account_info is None:
                    raise Exception("Failed to get account info")
                    
                return True
                
            return False
            
        except Exception as e:
            print(f"❌ MT5 initialization error: {e}")
            return False

    def check_mt5_connection(self):
        """
        Cek koneksi MT5 dan reconnect jika terputus
        """
        try:
            if not mt5.terminal_info():
                print("⚠️ MT5 connection lost. Attempting to reconnect...")
                if not self.initialize_mt5():
                    raise Exception("Failed to reconnect to MT5")
                print("✅ MT5 reconnected successfully")
                
            return True
        except Exception as e:
            print(f"❌ MT5 connection error: {e}")
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
        Update fungsi trading
        """
        try:
            print("\n=== AUTO TRADING STARTED ===")
            self.send_telegram("🚀 Auto trading dimulai!")
            
            while self.bot_status['is_running']:
                try:
                    # Cek koneksi MT5
                    if not self.check_mt5_connection():
                        self.send_telegram("⚠️ MT5 connection lost! Trying to reconnect...")
                        time.sleep(60)
                        continue
                    
                    # Trading logic
                    for symbol in self.forex_pairs:
                        print(f"\nAnalyzing {symbol}...")
                        # ... (kode trading Anda) ...
                    
                    print("\nWaiting for next analysis...")
                    time.sleep(300)  # 5 menit delay
                    
                except Exception as e:
                    error_msg = f"❌ Error dalam trading loop: {e}"
                    print(error_msg)
                    self.send_telegram(error_msg)
                    time.sleep(60)  # Delay sebelum retry
            
            self.send_telegram("🛑 Auto trading dihentikan!")
            
        except Exception as e:
            error_msg = f"❌ Fatal error dalam auto trading: {e}"
            print(error_msg)
            self.send_telegram(error_msg)
            self.bot_status['is_running'] = False

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