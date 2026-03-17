# telemetry/indicators/definitions.py
from .registry import registry

class BaseIndicator:
    name = ""
    dependencies = []
    
    def compute(self, candle: dict, state: dict, dep_results: dict) -> tuple[any, dict]:
        """
        Returns (computed_value, new_state).
        candle: {'open': x, 'high': x, 'low': x, 'close': x, 'volume': x}
        """
        raise NotImplementedError

@registry.register
class EMA20(BaseIndicator):
    name = "EMA_20"
    period = 20

    def compute(self, candle, state, dep_results):
        close = candle['close']
        prev_ema = state.get('prev_ema')
        
        if prev_ema is None:
            # Seed value (requires historical backfill on first run, simplified here)
            return close, {'prev_ema': close, 'count': 1}
            
        alpha = 2.0 / (self.period + 1)
        ema = (close - prev_ema) * alpha + prev_ema
        
        return ema, {'prev_ema': ema, 'count': state.get('count', 1) + 1}

@registry.register
class SMA20(BaseIndicator):
    name = "SMA_20"
    period = 20

    def compute(self, candle, state, dep_results):
        close = candle['close']
        window = state.get('window', [])
        
        window.append(close)
        if len(window) > self.period:
            window.pop(0)
            
        sma = sum(window) / len(window)
        return sma, {'window': window}

@registry.register
class MACD(BaseIndicator):
    name = "MACD_12_26"
    dependencies = ["EMA_12", "EMA_26"] # Assumes these are registered

    def compute(self, candle, state, dep_results):
        ema_12 = dep_results.get("EMA_12")
        ema_26 = dep_results.get("EMA_26")
        
        if ema_12 is None or ema_26 is None:
            return None, state
            
        macd_line = ema_12 - ema_26
        
        # Calculate Signal Line (EMA 9 of MACD Line)
        prev_signal = state.get('prev_signal', macd_line)
        alpha = 2.0 / (9 + 1)
        signal_line = (macd_line - prev_signal) * alpha + prev_signal
        
        histogram = macd_line - signal_line
        
        result = {"macd": macd_line, "signal": signal_line, "hist": histogram}
        return result, {'prev_signal': signal_line}