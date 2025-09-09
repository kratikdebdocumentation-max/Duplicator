# 🚀 Duplicator Trading Bot - Web Interface Startup Guide

## Quick Start (3 Steps)

### Step 1: Install Dependencies
```bash
# Install web server dependencies
pip install -r web_requirements.txt
```

### Step 2: Start the Web Server
```bash
# Option A: Use the launcher (recommended)
python run_web_server.py --optimized

# Option B: Use startup scripts
# Windows
start_web.bat

# Linux/Mac
./start_web.sh

# Option C: Direct execution
python web_server_optimized.py
```

### Step 3: Access the Interface
Open your browser and go to: **http://localhost:8000**

---

## 🎯 Configuration Options

### Basic Usage
```bash
# Standard server (good for development)
python run_web_server.py

# Optimized server (recommended for trading)
python run_web_server.py --optimized

# Allow network access (for remote access)
python run_web_server.py --optimized --network

# Development mode with auto-reload
python run_web_server.py --optimized --reload
```

### Advanced Configuration
```bash
# Custom host and port
python run_web_server.py --optimized --host 0.0.0.0 --port 8080

# Debug mode
python run_web_server.py --optimized --log-level debug

# Network access with custom port
python run_web_server.py --optimized --network --port 9000
```

---

## 🔧 Troubleshooting

### Common Issues

#### 1. Port Already in Use
```bash
# Find process using port 8000
netstat -ano | findstr :8000

# Kill the process (Windows)
taskkill /PID <PID> /F

# Kill the process (Linux/Mac)
kill -9 <PID>
```

#### 2. Dependencies Not Installed
```bash
# Install all dependencies
pip install -r web_requirements.txt

# If you get permission errors
pip install --user -r web_requirements.txt
```

#### 3. Broker Connection Issues
- Check your `credentials1.json` and `credentials2.json` files
- Verify broker credentials are correct
- Ensure brokers are enabled in `config/config.yaml`

#### 4. WebSocket Connection Failed
- Check firewall settings
- Try accessing via `http://127.0.0.1:8000` instead of `localhost`
- Clear browser cache and cookies

---

## 📊 Performance Tips

### For Best Performance
1. **Use Optimized Server**: Always use `--optimized` flag
2. **Close Unused Tabs**: Reduce memory usage
3. **Use Wired Connection**: Better stability than WiFi
4. **Regular Restarts**: Restart server daily for optimal performance

### For Development
1. **Use Auto-reload**: `--reload` flag for development
2. **Debug Mode**: `--log-level debug` for detailed logs
3. **Check Logs**: Monitor `logs/` directory for issues

---

## 🌐 Network Access

### Local Access Only (Default)
```bash
python run_web_server.py --optimized
# Access: http://localhost:8000
```

### Network Access (Remote Access)
```bash
python run_web_server.py --optimized --network
# Access: http://your-ip:8000
```

### Custom Network Configuration
```bash
python run_web_server.py --optimized --host 192.168.1.100 --port 8000
# Access: http://192.168.1.100:8000
```

---

## 🧪 Testing the Installation

### Run Tests
```bash
# Test basic functionality
python test_web_server.py

# Test with custom URL
python test_web_server.py --url http://localhost:8000

# Test with timeout
python test_web_server.py --timeout 30
```

### Manual Testing
1. Open browser to `http://localhost:8000`
2. Check if the dashboard loads
3. Try placing a test order
4. Verify real-time updates work

---

## 📱 Mobile Access

### From Mobile Device
1. Find your computer's IP address
2. Start server with network access: `python run_web_server.py --optimized --network`
3. Access from mobile: `http://your-ip:8000`

### Example
```bash
# Your computer IP is 192.168.1.100
python run_web_server.py --optimized --network

# Access from mobile: http://192.168.1.100:8000
```

---

## 🔒 Security Considerations

### Local Access Only (Recommended)
- Default configuration only allows local access
- Most secure for trading applications
- No external network exposure

### Network Access
- Only enable if you need remote access
- Consider firewall rules
- Use strong network security

---

## 📈 Monitoring

### Check Server Status
```bash
# Test health endpoint
curl http://localhost:8000/api/health

# Check if server is running
netstat -ano | findstr :8000
```

### View Logs
```bash
# Check application logs
tail -f logs/trading_web_app_*.log

# Check all logs
tail -f logs/*.log
```

---

## 🚀 Production Deployment

### For Production Use
```bash
# Use optimized server
python run_web_server.py --optimized --host 0.0.0.0 --port 8000

# Or use uvicorn directly for more control
uvicorn web_server_optimized:TradingWebApp --host 0.0.0.0 --port 8000 --workers 1
```

### Process Management
```bash
# Using nohup for background execution
nohup python run_web_server.py --optimized > web_server.log 2>&1 &

# Using screen for session management
screen -S trading_web
python run_web_server.py --optimized
# Ctrl+A, D to detach
```

---

## 🎯 Quick Commands Reference

### Start Server
```bash
# Basic start
python run_web_server.py --optimized

# Development mode
python run_web_server.py --optimized --reload

# Network access
python run_web_server.py --optimized --network

# Custom port
python run_web_server.py --optimized --port 9000
```

### Test Server
```bash
# Basic test
python test_web_server.py

# Test with custom URL
python test_web_server.py --url http://localhost:8000
```

### Check Status
```bash
# Health check
curl http://localhost:8000/api/health

# Check processes
netstat -ano | findstr :8000
```

---

## 🆘 Getting Help

### If Something Goes Wrong
1. **Check Logs**: Look in `logs/` directory
2. **Test Installation**: Run `python test_web_server.py`
3. **Verify Dependencies**: Ensure all packages are installed
4. **Check Configuration**: Verify broker credentials and config

### Common Solutions
- **Restart Server**: Stop and start again
- **Clear Cache**: Delete browser cache
- **Check Ports**: Ensure port 8000 is available
- **Verify Files**: Ensure all web files are present

---

**🎉 You're Ready to Trade!**

Once the web server is running, you'll have access to a fast, modern trading interface with all the same functionality as the Telegram bot, plus real-time updates and a responsive design that works on any device.

**Happy Trading! 🚀**
