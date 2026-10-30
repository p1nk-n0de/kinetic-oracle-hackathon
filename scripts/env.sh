# source scripts/env.sh — exports MODEL_API_KEY from the private key file. Never echo it.
if [ -z "${MODEL_API_KEY:-}" ] && [ -s "$HOME/.config/meta/model_api_key" ]; then
  export MODEL_API_KEY="$(cat "$HOME/.config/meta/model_api_key")"
fi
export GODOT_STUDIO_EXTRA_ROOT="${GODOT_STUDIO_EXTRA_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)/runs}"
