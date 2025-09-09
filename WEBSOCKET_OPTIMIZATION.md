# WebSocket Optimization for Dual Broker Setup

## Overview

This document describes the optimized WebSocket implementation that reduces bandwidth usage and improves efficiency for the dual broker trading system.

## Optimization Strategy

### Price/Quote Updates (SL)
- **Source**: Broker 1 only
- **Reason**: Price data is market-wide and identical across all brokers
- **Benefit**: Reduces duplicate data and bandwidth usage

### Order Updates
- **Source**: Both brokers individually
- **Reason**: Each broker has its own order status and execution details
- **Benefit**: Ensures complete order tracking across all brokers

## Implementation Details

### WebSocket Manager Changes

#### 1. Optimized Startup (`_start_optimized_websockets`)
```python
def _start_optimized_websockets(self, connected_brokers: Dict[str, Any]) -> None:
    # Primary broker (Broker 1) gets both callbacks
    primary_broker.start_websocket(
        order_callback=self._handle_order_update,
        quote_callback=self._handle_quote_update
    )
    
    # Secondary brokers get only order callbacks
    for broker_name in broker_names[1:]:
        broker.start_websocket(
            order_callback=self._handle_order_update,
            quote_callback=None  # No price updates
        )
```

#### 2. Symbol Subscription (Broker 1 Only)
```python
def subscribe_symbol(self, symbol: str, exchange: str = "NFO") -> bool:
    # Only subscribe to primary broker for price updates
    primary_broker = connected_brokers[broker_names[0]]
    return primary_broker.subscribe(ws_symbol)
```

#### 3. Broker Identification
- Each broker adds its name to websocket data
- Order and quote updates are tagged with broker source
- Enables proper tracking and logging

### ShoonyaBroker Changes

#### Enhanced Callback Handling
```python
def _on_order_update(self, order_data: Dict[str, Any]) -> None:
    # Add broker identification
    order_data['broker_name'] = self.name
    self._notify_order_update(order_data)

def _on_quote_update(self, quote_data: Dict[str, Any]) -> None:
    # Add broker identification
    quote_data['broker_name'] = self.name
    self._notify_quote_update(quote_data)
```

## Benefits

### 1. Bandwidth Optimization
- **Before**: Price data from both brokers (duplicate)
- **After**: Price data from Broker 1 only
- **Savings**: ~50% reduction in price update traffic

### 2. Resource Efficiency
- Reduced CPU usage for processing duplicate price data
- Lower memory footprint for websocket connections
- Improved overall system performance

### 3. Maintained Functionality
- Complete order tracking across all brokers
- Real-time price updates for trading decisions
- No loss of critical trading information

## Usage

### Starting the System
```bash
python start_dual_broker_web.py
```

### Testing the Optimization
```bash
python test_optimized_websockets.py
```

### Web Interface
- Access: `http://127.0.0.1:8000`
- View real-time broker status and performance
- Monitor both price and order updates

## Monitoring

### Log Messages
- **Price Updates**: `"Price update from broker1: NIFTY24123400CE = ₹12345.50"`
- **Order Updates**: `"Order update from broker1: ORD123 status: COMPLETE"`
- **WebSocket Setup**: `"Price/Quote updates: broker1 only"`

### Web Interface Indicators
- Broker status cards show individual connection health
- Real-time order tracking per broker
- Performance metrics for each broker

## Configuration

The optimization is automatically applied when:
1. Multiple brokers are configured in `config.yaml`
2. Both brokers are enabled (`enabled: true`)
3. WebSocket manager starts successfully

## Troubleshooting

### Common Issues

1. **No Price Updates**
   - Check if Broker 1 is connected
   - Verify symbol subscription on primary broker

2. **Missing Order Updates**
   - Ensure both brokers are connected
   - Check websocket connection status

3. **Broker Identification Issues**
   - Verify broker names in configuration
   - Check websocket callback implementation

### Debug Commands
```bash
# Check broker status
curl http://127.0.0.1:8000/api/brokers

# Check detailed broker info
curl http://127.0.0.1:8000/api/brokers/details

# Test websocket optimization
python test_optimized_websockets.py
```

## Future Enhancements

1. **Dynamic Primary Broker Selection**
   - Automatically select most stable broker for price updates
   - Failover mechanism if primary broker disconnects

2. **Load Balancing**
   - Distribute order updates across multiple brokers
   - Optimize based on broker performance

3. **Advanced Monitoring**
   - Real-time bandwidth usage metrics
   - Performance analytics per broker
   - Automated optimization recommendations
