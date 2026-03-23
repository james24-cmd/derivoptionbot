import logging

class RecoverySystem:
    def __init__(self, payout_rate=0.92, max_trades=5):
        self.S = 0.0          # Total accumulated loss
        self.n = 0            # Trade number in sequence (0 means no active sequence)
        self.p = payout_rate
        self.max_trades = max_trades
        self.active_direction = None
        
    def reset(self):
        self.S = 0.0
        self.n = 0
        self.active_direction = None
        logging.info("Recovery sequence reset.")
        
    def get_next_stake(self, base_stake=0.50):
        if self.n == 0:
            return base_stake
            
        # Stake must cover total accumulated loss (self.S) 
        # plus the typical profit of the base stake (base_stake * self.p)
        # Formula: stake * p = S + base_stake * p -> stake = (S / p) + base_stake
        stake = (self.S / self.p) + base_stake
        return round(stake, 2)
        
    def record_loss(self, lost_stake):
        self.S += lost_stake
        self.n += 1
        logging.warning(f"[LOST] Trade sequence {self.n} lost. Accumulated loss (S): ${self.S:.2f}")
        
    def record_win(self):
        logging.info(f"[WON] Trade sequence {self.n+1} won! Resetting...")
        self.reset()
        
    def should_stop(self):
        if self.n >= self.max_trades:
            logging.error(f"[HARD STOP] Maximum consecutive losses ({self.max_trades}) reached.")
            return True
        return False
