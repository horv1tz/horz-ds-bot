# Simple Discord Bot - "Hello World" Bot

A basic Discord bot that responds with "Hello World" when triggered by a specific command. This project serves as an introductory example for Discord bot development.

## Features

- Responds to `/hello` command with "Hello World" message
- Simple `/ping` command for testing bot responsiveness
- Clean, well-documented code structure
- Easy setup and deployment

## Requirements

- Python 3.8 or higher
- Discord account with server administrator permissions
- Access to [Discord Developer Portal](https://discord.com/developers/applications)

## Installation

1. **Clone or download this repository**
   ```bash
   git clone <repository-url>
   cd horz-ds-bot
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up your Discord bot**
   - Go to [Discord Developer Portal](https://discord.com/developers/applications)
   - Create a new application
   - Go to the "Bot" section and click "Add Bot"
   - Copy the bot token

4. **Configure the bot**
   - Copy `.env.example` to `.env`
   - Edit `.env` and replace `your_bot_token_here` with your actual bot token
   ```
   DISCORD_BOT_TOKEN=your_actual_bot_token_here
   ```

5. **Invite the bot to your server**
   - In the Discord Developer Portal, go to "OAuth2" > "URL Generator"
   - Select the "bot" scope
   - Select necessary permissions (at minimum: Send Messages)
   - Copy the generated URL and open it in your browser
   - Select your server and authorize the bot

## Usage

1. **Start the bot**
   ```bash
   python bot.py
   ```

2. **Use the bot commands**
   - `/hello` - Bot responds with "Hello World"
   - `/ping` - Bot responds with "Pong! The bot is working correctly."

## Commands

### `/hello`
Responds with "Hello World" message.

**Usage:** `/hello`

### `/ping`
Simple ping command to test bot responsiveness.

**Usage:** `/ping`

## Troubleshooting

### Bot won't start
- Ensure you have Python 3.8+ installed
- Check that all dependencies are installed: `pip install -r requirements.txt`
- Verify your bot token is correct in the `.env` file

### Bot doesn't respond to commands
- Make sure the bot has been invited to your server with proper permissions
- Check that the bot is online in your server's member list
- Verify the command prefix is `/` (you can change this in `bot.py`)

### Common errors
- **"CommandNotFound"**: Bot didn't recognize the command. Try `/hello` or `/ping`
- **"Token not found"**: Check your `.env` file contains the correct bot token

## Development

This bot is built using:
- [discord.py](https://discordpy.readthedocs.io/) - Discord API wrapper for Python
- [python-dotenv](https://pypi.org/project/python-dotenv/) - Environment variable management

## Future Enhancements

This basic bot can be extended with additional features such as:
- More commands and responses
- Database integration for persistent data
- Web dashboard for bot management
- Advanced moderation features

## License

This project is for educational purposes and can be used as a foundation for more complex Discord bot implementations.

## Docker Deployment

The bot can also be deployed using Docker for easier containerization and deployment.

### Prerequisites
- Docker installed on your system
- Docker Compose (if using docker-compose)

### Using Docker Compose (Recommended)

1. **Build and run the container**
   ```bash
   docker-compose up -d
   ```

2. **View logs**
   ```bash
   docker-compose logs -f
   ```

3. **Stop the container**
   ```bash
   docker-compose down
   ```

### Proxy Configuration

If you need to use a proxy to connect to Discord (required in some networks):

1. **Configure proxy in `.env` file**:
   ```bash
   # Basic HTTP proxy URL
   PROXY_URL=http://proxy_host:proxy_port

   # SOCKS5 proxy (often used by local proxy apps)
   PROXY_URL=socks5://127.0.0.1:1080

   # Option A: credentials in URL
   PROXY_URL=http://username:password@proxy_host:proxy_port

   # Option B (recommended): credentials in separate variables
   PROXY_URL=http://proxy_host:proxy_port
   PROXY_USERNAME=your_proxy_username
   PROXY_PASSWORD=your_proxy_password
   ```

   You can also use standard proxy env vars instead of `PROXY_URL`:
   `HTTPS_PROXY`, `HTTP_PROXY`, or `ALL_PROXY`.

   If you see an error like `Unsupported method ('CONNECT')`, you likely configured
   an HTTP proxy URL for a SOCKS port. In that case, use `socks5://...` in `PROXY_URL`.

2. **Restart the bot**:
   ```bash
   docker-compose down
   docker-compose up -d
   ```

3. **Verify proxy usage**:
   Check the logs to confirm the bot is using the proxy:
   ```bash
   docker-compose logs -f
   # Should show: "Using proxy: http://your_proxy_url:port"
   ```

### Using Docker Directly

1. **Build the image**
   ```bash
   docker build -t horz-ds-bot .
   ```

2. **Run the container**
   ```bash
   docker run -d \
     --name horz-ds-bot \
     --restart unless-stopped \
     -e DISCORD_BOT_TOKEN=your_bot_token_here \
     horz-ds-bot
   ```

3. **View logs**
   ```bash
   docker logs -f horz-ds-bot
   ```

4. **Stop the container**
   ```bash
   docker stop horz-ds-bot
   docker rm horz-ds-bot
   ```

### Docker Configuration Notes

- The bot token can be provided via `.env` file or environment variable
- Logs are stored in the `/app/logs` directory inside the container
- The container will automatically restart unless manually stopped
- Health checks are configured to monitor bot status

## Support

For setup and configuration issues, refer to the troubleshooting section above. For additional Discord bot development resources, see the [discord.py documentation](https://discordpy.readthedocs.io/).
