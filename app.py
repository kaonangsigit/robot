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

    def run_auto_trading(self):
        """
        Menjalankan auto trading dengan fitur tambahan
        """
        try:
            print("\n=== AUTO TRADING STARTED ===")
            last_report_time = datetime.now()
            
            while True:
                # Generate laporan harian
                now = datetime.now()
                if now.hour == 0 and (now - last_report_time).seconds > 3600:
                    self.generate_report()
                    last_report_time = now
                    self.performance['daily_profit_loss'] = 0  # Reset daily P/L
                
                for symbol in self.forex_pairs:
                    # Cek kondisi market
                    market_ok, market_message = self.check_market_conditions(symbol)
                    if not market_ok:
                        print(f"\n⚠️ {symbol}: {market_message}")
                        continue
                        
                    print(f"\nAnalyzing {symbol}...")
                    
                    # Update trailing stops untuk posisi yang ada
                    positions = mt5.positions_get(symbol=symbol)
                    if positions:
                        for position in positions:
                            self.manage_trailing_stop(position)
                    
                    # Analisis multi-timeframe
                    signals = {}
                    for tf_name, tf in self.timeframes.items():
                        df = self.get_price_data(symbol, tf)
                        if df is not None:
                            df = self.calculate_indicators(df)
                            signals[tf_name] = self.analyze_signals(df)
                    
                    # Hitung total strength
                    total_strength = sum([s['strength'] for s in signals.values()])
                    
                    # Execute trade jika sinyal kuat
                    if abs(total_strength) >= 3:
                        trade_type = "BUY" if total_strength > 0 else "SELL"
                        
                        # Hitung SL dan TP berdasarkan ATR
                        df = self.get_price_data(symbol, mt5.TIMEFRAME_H1)
                        df = self.calculate_indicators(df)
                        atr = df['ATR'].iloc[-1]
                        
                        current_price = mt5.symbol_info_tick(symbol).ask if trade_type == "BUY" else mt5.symbol_info_tick(symbol).bid
                        sl_distance = atr * 1.5
                        tp_distance = atr * 2
                        
                        sl_price = current_price - sl_distance if trade_type == "BUY" else current_price + sl_distance
                        tp_price = current_price + tp_distance if trade_type == "BUY" else current_price - tp_distance
                        
                        # Hitung lot size
                        lot_size = self.calculate_position_size(symbol, sl_distance)
                        
                        # Execute trade
                        if self.execute_trade(symbol, trade_type, lot_size, sl_price, tp_price):
                            print(f"✅ Trade executed for {symbol}")
                        
                print("\nWaiting for next analysis...")
                time.sleep(300)  # Wait 5 minutes
                
        except Exception as e:
            error_msg = f"❌ Error dalam auto trading: {e}"
            print(error_msg)
            self.send_telegram(error_msg)

def main():
    # Initialize MT5
    if not mt5.initialize():
        print("❌ Initialize MT5 failed")
        quit()

    # Create analyzer instance
    analyzer = ForexGoldAnalyzer()
    
    # Test Telegram connection
    print("\nTesting Telegram connection...")
    if analyzer.test_telegram_connection():
        print("✅ Telegram connection successful!")
        
        # Start auto trading
        print("\nStarting auto trading...")
        analyzer.run_auto_trading()
    else:
        print("❌ Telegram connection failed!")

    # Shutdown MT5
    mt5.shutdown()

if __name__ == "__main__":
    main()