# Agno Framework Template

This template provides a foundation for building AI agents using the [Agno framework](https://github.com/xpander-ai/agno) integrated with the xpander.ai platform.

## Features

- **Agno Framework Integration**: Built on the powerful Agno AI agent framework
- **Thinking Tools**: Includes step-by-step reasoning capabilities
- **Dual Mode Support**: Works both standalone and with Xpander backend
- **State Management**: Maintains conversation history and state
- **Async Operations**: Built for high-performance async execution

## Files Structure

- `xpander_handler.py` - WebSocket event handler for Xpander platform
- `requirements.txt` - Python dependencies
- `Dockerfile` - Container deployment configuration
- `.env.example` - Template for environment variables
- `.dockerignore` - Docker ignore file

## Getting Started

### Local Development

1. **Install Dependencies**:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   make install
   ```

### Xpander Platform Integration

1. **Initialize in your project**:

   ```bash
   npm install -g xpander-cli
   xpander login
   xpander agent new
   xpander agent init
   ```

2. **Run the agent**

   ```bash
   python xpander_handler.py
   ```

3. **Test it locally**

   ```bash
   docker build . -t my-agent && docker run my-agent
   # add --env-file .env to load the secrets
   # use the cli to sync the .env file to xpander.ai with xpander secrets-sync
   ```

4. **Deploy to Xpander**:

   ```bash
   xpander deploy
   ```

### Environment Variables

Create a `.env` file for local development based on `.env.example`:

```env
XPANDER_API_KEY="{YOUR_API_KEY}"
XPANDER_ORGANIZATION_ID="{YOUR_ORGANIZATION_ID}"
XPANDER_AGENT_ID="{YOUR_XPANDER_AGENT_ID}"
ANTHROPIC_API_KEY="{YOUR_ANTHROPIC_API_KEY_IF_USING_ANTHROPIC}"
OPENAI_API_KEY="{YOUR_OPENAI_API_KEY_IF_USING_OPENAI}"
```

## Dependencies

- **agno[all]**: Core AI agent framework with all features
- **xpander-sdk[agno]**: Xpander platform SDK with Agno integration
- **openai**: OpenAI API integration
- **anthropic**: Anthropic API integration
- **mcp**: Model Context Protocol support
- **python-dotenv**: Environment variable management

## Notes

- Ensure you have Python 3.12+ installed
- The template supports multiple AI providers (OpenAI, Anthropic)
- Uses Alpine-based Docker image for lightweight deployment
- Includes MCP (Model Context Protocol) support
