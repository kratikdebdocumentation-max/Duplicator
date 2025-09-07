# Duplicator Trading Bot

A modular Telegram-based trading tool that duplicates orders across multiple brokers. Built as a modern, scalable alternative to the original MasterChildGUI application.

## 🚀 Features

- **Multi-Broker Support**: Place orders simultaneously across multiple brokers (Shoonya)
- **Telegram Integration**: Interactive commands for order placement and management
- **Real-time Updates**: WebSocket feeds for live order status and price updates
- **Order Management**: Place, modify, cancel, and track orders across all brokers
- **Modular Architecture**: Clean, maintainable codebase with separate modules
- **Configuration Management**: YAML-based configuration for easy setup
- **Comprehensive Logging**: Detailed logging for all trading activities
- **Error Handling**: Robust error handling and recovery mechanisms

## 📋 Prerequisites

- Python 3.8 or higher
- Telegram Bot Token
- Broker API credentials (Shoonya)
- Active internet connection

## 🛠️ Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd Duplicator
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Install the package** (optional):
   ```bash
   pip install -e .
   ```

## ⚙️ Configuration

### 1. Telegram Bot Setup

1. Create a new bot with [@BotFather](https://t.me/botfather)
2. Get your bot token and chat ID
3. Update `config/config.yaml` with your credentials

### 2. Broker Credentials

1. Copy your broker credential files to the project root:
   - `credentials1.json` (Broker 1)
   - `credentials2.json` (Broker 2)

2. Ensure the credential files have the following structure:
   ```json
   {
     "username": "your_username",
     "pwd": "your_password",
     "factor2": "your_totp_secret",
     "vc": "your_vendor_code",
     "app_key": "your_api_key",
     "imei": "your_imei"
   }
   ```

### 3. Configuration File

Edit `config/config.yaml` to match your setup:

```yaml
# Telegram Bot Configuration
telegram:
  bot_token: "YOUR_TELEGRAM_BOT_TOKEN"
  chat_id: "YOUR_CHAT_ID"
  sos_chat_id: "YOUR_SOS_CHAT_ID"

# Trading Configuration
trading:
  default_exchange: "NFO"
  default_price_type: "LMT"
  default_retention: "DAY"
  default_order_type: "MIS"  # MIS or CNC
  lot_multipliers:
    NIFTY: 25
    BANKNIFTY: 15
    SENSEX: 10

# Broker Configuration
brokers:
  broker1:
    name: "Shoonya Broker 1"
    enabled: true
    credentials_file: "credentials1.json"
    api_type: "shoonya"
    
  broker2:
    name: "Shoonya Broker 2"
    enabled: true
    credentials_file: "credentials2.json"
    api_type: "shoonya"
```

## 🚀 Usage

### Starting the Bot

```bash
python main.py
```

### Telegram Commands

Once the bot is running, you can use these commands in Telegram:

#### Basic Commands
- `/start` - Welcome message and help
- `/help` - Show available commands
- `/status` - Check system and broker status
- `/brokers` - Check individual broker status

#### Order Commands
- `/buy SYMBOL QTY PRICE` - Place buy order
- `/sell SYMBOL QTY PRICE` - Place sell order
- `/cancel ORDER_ID` - Cancel specific order
- `/modify ORDER_ID QTY PRICE` - Modify order

#### Status Commands
- `/orders` - List all active orders
- `/positions` - View current positions summary

#### Quick Order Format
You can also send orders in a simple text format:
```
NIFTY25DEC24CE25000 25 150.50
```

### Example Usage

1. **Place a buy order**:
   ```
   /buy NIFTY25DEC24CE25000 25 150.50
   ```

2. **Check order status**:
   ```
   /orders
   ```

3. **Cancel an order**:
   ```
   /cancel ORD_1234567890
   ```

4. **View positions**:
   ```
   /positions
   ```

## 🏗️ Architecture

The application follows a modular architecture:

```
Duplicator/
├── src/
│   ├── brokers/          # Broker interface and implementations
│   ├── orders/           # Order management system
│   ├── telegram/         # Telegram bot implementation
│   ├── websocket/        # WebSocket feed handlers
│   └── utils/            # Utilities and configuration
├── config/               # Configuration files
├── logs/                 # Log files
├── data/                 # Data storage
└── main.py              # Main application entry point
```

### Key Components

1. **BrokerManager**: Manages multiple broker connections
2. **OrderManager**: Handles order placement, modification, and tracking
3. **TelegramBot**: Provides interactive Telegram interface
4. **WebSocketManager**: Manages real-time data feeds
5. **ConfigManager**: Handles configuration management

## 📊 Order Flow

1. **Order Placement**: User sends command via Telegram
2. **Validation**: Order parameters are validated
3. **Duplication**: Order is placed on all connected brokers
4. **Tracking**: Order status is tracked across all brokers
5. **Updates**: Real-time updates are sent via Telegram
6. **Management**: Orders can be modified or cancelled

## 🔧 Configuration Options

### Trading Parameters
- `default_exchange`: Default exchange (NFO, BSE, etc.)
- `default_price_type`: Price type (LMT, MKT, etc.)
- `default_retention`: Order retention (DAY, IOC, etc.)
- `default_order_type`: Order type (MIS, CNC)
- `lot_multipliers`: Lot sizes for different indices

### Broker Settings
- `enabled`: Enable/disable specific brokers
- `credentials_file`: Path to broker credentials
- `api_type`: Broker API type (shoonya, etc.)

### Logging
- `level`: Logging level (DEBUG, INFO, WARNING, ERROR)
- `log_dir`: Directory for log files
- `max_file_size`: Maximum log file size
- `backup_count`: Number of backup log files

## 📝 Logging

The application provides comprehensive logging:

- **Application Logs**: Main application events
- **Broker Logs**: Broker-specific operations
- **Order Logs**: Order placement and updates
- **Telegram Logs**: Bot interactions
- **WebSocket Logs**: Real-time data feeds

Logs are stored in the `logs/` directory with daily rotation.

## 🛡️ Security

- Credentials are stored in separate JSON files
- Configuration files use YAML format
- All sensitive data is excluded from logs
- Telegram bot token should be kept secure

## 🚨 Error Handling

The application includes robust error handling:

- **Connection Recovery**: Automatic broker reconnection
- **Order Retry**: Retry failed order operations
- **WebSocket Recovery**: Automatic WebSocket reconnection
- **Graceful Shutdown**: Clean shutdown on signals

## 📈 Monitoring

- Real-time status monitoring
- Health checks for all components
- Telegram notifications for critical events
- Comprehensive logging for debugging

## 🔄 Updates and Maintenance

### Order Cleanup
Old orders are automatically cleaned up after 7 days by default.

### Log Rotation
Log files are automatically rotated based on size and age.

### Configuration Reload
Configuration can be reloaded without restarting the application.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## ⚠️ Disclaimer

This software is for educational and personal use only. Trading involves risk, and you should never trade with money you cannot afford to lose. The authors are not responsible for any financial losses.

## 🆘 Support

For support and questions:

1. Check the logs in the `logs/` directory
2. Review the configuration in `config/config.yaml`
3. Ensure all credentials are correct
4. Verify broker API connectivity

## 🔮 Future Enhancements

- Support for additional brokers
- Advanced order types (bracket orders, etc.)
- Portfolio management features
- Risk management tools
- Web dashboard interface
- Mobile app integration

---

**Happy Trading! 🚀**
