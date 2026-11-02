# source scripts/env.sh — exports MODEL_API_KEY from the private key file. Never echo it.
# Machine-specific settings (where the Godot studio lives, its MCP entry point; see propriosam/local_config.py)
# go in the untracked scripts/env.local.sh, which is sourced first when present.
_ko_dir="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
[ -f "$_ko_dir/env.local.sh" ] && . "$_ko_dir/env.local.sh"
if [ -z "${MODEL_API_KEY:-}" ] && [ -s "$HOME/.config/meta/model_api_key" ]; then
  export MODEL_API_KEY="$(cat "$HOME/.config/meta/model_api_key")"
fi
_ko_var="${KO_GODOT_EXTRA_ROOT_ENV:-GODOT_STUDIO_EXTRA_ROOT}"
[ -n "$(printenv "$_ko_var")" ] || export "$_ko_var=$(cd "$_ko_dir/.." && pwd)/runs"
unset _ko_dir _ko_var
