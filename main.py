import asyncio
import websockets
import json
import logging
import pandas as pd
from strategy import analyze_candles
from recovery_system import RecoverySystem

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# --- CONFIGURATION ---
API_TOKEN = "cDub9aTPsvu3ttc"  # Your token
SYMBOL = "R_100"  # Volatility 100 Index. Can be updated.
PAYOUT_RATE = 0.92
BASE_STAKE = 1.00

recovery = RecoverySystem(payout_rate=PAYOUT_RATE, max_trades=5)

async def authenticate(ws):
    await ws.send(json.dumps({"authorize": API_TOKEN}))
    res = json.loads(await ws.recv())
    if "error" in res:
        logging.error(f"Auth Failed: {res['error']['message']}")
        return False
    logging.info("Successfully authenticated.")
    return True

async def buy_contract(ws, direction, stake):
    logging.info(f"==> EXECUTING {direction} | Stake: ${stake}")
    
    buy_req = {
        "buy": 1,
        "price": stake,
        "parameters": {
            "amount": stake,
            "basis": "stake",
            "contract_type": direction,
            "currency": "USD",
            "duration": 1,
            "duration_unit": "m",
            "symbol": SYMBOL
        },
        "req_id": 999
    }
    await ws.send(json.dumps(buy_req))

async def main():
    uri = "wss://ws.binaryws.com/websockets/v3?app_id=1089"
    pending_contract_id = None
    
    while True:
        try:
            async with websockets.connect(uri, ping_interval=30, ping_timeout=10) as ws:
                if API_TOKEN != "YOUR_API_TOKEN_HERE":
                    if not await authenticate(ws):
                        return
                else:
                    logging.warning("API_TOKEN not set. Running in dry-mode (no execution).")

                # Restore previous contract subscription if reconnected
                if pending_contract_id is not None:
                    logging.info(f"Re-subscribing to lost pending contract: {pending_contract_id}")
                    await ws.send(json.dumps({
                        "proposal_open_contract": 1, 
                        "contract_id": pending_contract_id,
                        "subscribe": 1
                    }))

                # Subscribe to history
                req = {
                    "ticks_history": SYMBOL,
                    "end": "latest",
                    "count": 5,
                    "style": "candles",
                    "granularity": 60,
                    "subscribe": 1
                }
                await ws.send(json.dumps(req))
                
                last_epoch = 0
                df = pd.DataFrame(columns=['epoch', 'open', 'high', 'low', 'close'])

                while True:
                    response = json.loads(await ws.recv())
                    
                    if 'error' in response:
                        err_msg = response['error']['message']
                        req_type = response.get('msg_type', '')
                        req_id = response.get('req_id')
                        logging.error(f"API Error ({req_type}): {err_msg}")
                        if req_id == 999:
                            pending_contract_id = None
                        if req_type == 'proposal_open_contract' and pending_contract_id is not None:
                            # Usually means contract is already closed/invalid
                            # We might have missed the end. Let's force reset if needed.
                            logging.warning("Failed to resubscribe to contract. Resetting.")
                            pending_contract_id = None

                    if 'proposal_open_contract' in response:
                        contract = response['proposal_open_contract']
                        # `is_sold` is 1 when finished.
                        if contract and contract.get('is_sold'):
                            profit = contract.get('profit', 0)
                            status = contract.get('status')
                            logging.info(f"Contract Closed. Status: {status}, Profit: {profit}")
                            if status == 'won' or profit > 0:
                                recovery.record_win()
                            else:
                                recovery.record_loss(abs(float(contract.get('buy_price', 0))))
                            pending_contract_id = None
                    
                    if 'buy' in response:
                        pending_contract_id = response['buy']['contract_id']
                        await ws.send(json.dumps({
                            "proposal_open_contract": 1, 
                            "contract_id": pending_contract_id,
                            "subscribe": 1
                        }))

                    if 'candles' in response:
                        df = pd.DataFrame(response['candles'])
                        df[['open', 'high', 'low', 'close']] = df[['open', 'high', 'low', 'close']].astype(float)
                        df['epoch'] = df['epoch'].astype(int)
                        last_epoch = df.iloc[-1]['epoch']
                        logging.info(f"Loaded {len(df)} historical candles.")

                    if 'ohlc' in response:
                        candle = response['ohlc']
                        epoch = int(candle['open_time'])
                        
                        if last_epoch != 0 and epoch > last_epoch:
                            logging.info(f"Candle closed. Analyzing...")
                            df = df.tail(5).copy()
                            
                            if pending_contract_id is not None:
                                logging.info("Contract is currently open. Waiting for result before analyzing new setups.")
                            elif recovery.should_stop():
                                logging.error("Bot HALTED: Hard Stop Limit reached.")
                            else:
                                if recovery.n > 0:
                                    direction = recovery.active_direction
                                    stake = recovery.get_next_stake(BASE_STAKE)
                                    logging.info(f"[RECOVERY MODE (n={recovery.n})] Re-entering {direction} with Stake: ${stake:.2f}")
                                    await buy_contract(ws, direction, stake)
                                else:
                                    direction = analyze_candles(df)
                                    if direction:
                                        stake = recovery.get_next_stake(BASE_STAKE)
                                        recovery.active_direction = direction
                                        logging.info(f"Setup Approved. Expected direction: {direction}. Stake: ${stake:.2f}")
                                        await buy_contract(ws, direction, stake)

                        last_epoch = epoch
                        
                        row_data = {
                            'epoch': epoch,
                            'open': float(candle['open']),
                            'high': float(candle['high']),
                            'low': float(candle['low']),
                            'close': float(candle['close'])
                        }
                        
                        if not df.empty and df.iloc[-1]['epoch'] == epoch:
                            df.iloc[-1] = row_data
                        else:
                            df.loc[len(df)] = row_data

        except (websockets.exceptions.ConnectionClosed, OSError) as e:
            logging.error(f"Connection lost: {e}. Reconnecting in 5 seconds...")
            await asyncio.sleep(5)
        except Exception as e:
            logging.error(f"Unexpected error: {e}. Reconnecting in 5 seconds...")
            await asyncio.sleep(5)

from keep_alive import keep_alive

if __name__ == "__main__":
    keep_alive()
    asyncio.run(main())
