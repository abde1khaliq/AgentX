# AgentX 🕵️‍♂️
> A Discord bot that turns any server into a game of deduction and deception.

Players are split into **Detectives** and one hidden **AgentX (Spy)**. Detectives must expose the spy. The spy must deduce the secret location without being caught.

---

## Table of Contents
- [How to Play](#how-to-play)
- [Commands](#commands)
- [Running Locally](#running-locally)
- [Contributing](#contributing)
- [Language Support](#language-support)

---

## How to Play

1. **Host a game** — Use `/host` to create a lobby. Players join via the **Join Game** button (5–15 players).
2. **Roles are assigned** — Each player secretly becomes either a Detective or AgentX.
3. **Questioning phase** — Detectives discuss clues about the secret location. AgentX listens, blends in, and tries to deduce it.
4. **Voting phase** — Everyone votes on who they think is AgentX.

**Detectives win** by correctly identifying the spy.  
**AgentX wins** by guessing the secret location correctly or avoiding detection entirely.

---

## Commands

| Command | Description |
|---|---|
| `/host` | Start a new game |
| `/hint` | Receive a hint during the questioning phase |
| `/stop` | Stop the current game *(host only)* |
| `/set_language` | Configure the bot's language for your server |
| `/report` | Report a bug or issue |
| `/invite` | Invite AgentX to another server |
| `/ping` | Check bot latency |

---

## Running Locally

### Prerequisites
Make sure you have Python installed, then enable the following in your [Discord Developer Portal](https://discord.com/developers/applications/):
- ✅ Presence Intent
- ✅ Server Members Intent
- ✅ Message Content Intent

### Setup

**1. Create and activate a virtual environment:**
```bash
python -m venv agentx-venv
```
```bash
# Windows (PowerShell)
agentx-venv\Scripts\Activate

# macOS / Linux
source agentx-venv/bin/activate
```

**2. Install dependencies:**
```bash
pip install -r requirements.txt
```

**3. Create .env file:
  1. Navigate to the `root_data` directory
  2. Create a new .env file within
  3. within the .env file declare a `BOT_TOKEN` variable with your token like so
     ```
     BOT_TOKEN=1230294890ASDKMAWODIJS98ZUC98AJW89AJD89JAW89DJWA9DH7H
     ```

**3. Run the bot:**
```bash
python bot.py
```

---

## Contributing

Contributions are welcome! Forking is allowed.

1. Fork the repository.
2. Create a new branch for your feature or fix.
3. Commit your changes with clear messages.
4. Open a pull request for review.

**Ideas for contributions:**
- New locations or role variations
- Improved error handling and edge cases
- Better tutorial and FAQ content
- Additional language localizations

---

## Language Support

AgentX supports multiple languages. Server admins can switch languages at any time using `/set_language`.

---

## License

AgentX is open for community contributions. Please respect the project guidelines when submitting changes.
