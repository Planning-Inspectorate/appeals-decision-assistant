# Instructions

## Set environment variables for Azure OpenAI
Get your Azure OpenAI API key and endpoint from the [Azure Portal](https://ai.azure.com/foundryResource/overview?wsid=/subscriptions/962e477c-0f3b-4372-97fc-a198a58e259e/resourceGroups/pins-rg-ada-dev/providers/Microsoft.CognitiveServices/accounts/pins-ais-ada-dev&tid=5878df98-6f88-48ab-9322-998ce557088d).

```
export AZURE_OPENAI_API_KEY=[YOUR-AZURE-OPENAI-API-KEY]
export AZURE_OPENAI_ENDPOINT=https://westeurope.api.cognitive.microsoft.com/
export OPENAI_API_VERSION="2024-12-01-preview"
```

## Install dependencies
If you don't have brew, install it
```
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

If you don't have uv, install it
```
brew install uv
```

Sync dependencies from the pyproject.toml file into the uv virtual environment (in parent directory)
```
uv sync
```

## Run the script in the uv environment
```
uv run weather.py new york
```
