$ErrorActionPreference = "Stop"
$env:BOT_PROFILE = "dev"
python "$PSScriptRoot\..\bot.py" --profile dev
