param(
    [string]$Model = "gpt-4o-mini"
)

$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $ProjectDir
$Python = Join-Path $ProjectDir ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Missing .venv. Create it and install requirements first."
}

& $Python "scripts/preflight_provider.py" --provider openai --model $Model

& $Python "run_eval.py" --provider openai --model $Model --version v2 --suite base `
    --system-prompt "artifacts/versions/v2_system_prompt.md" `
    --tools "artifacts/tools.yaml" `
    --eval-cases "data/eval_base.json"

& $Python "run_eval.py" --provider openai --model $Model --version v2 --suite group `
    --system-prompt "artifacts/versions/v2_system_prompt.md" `
    --tools "artifacts/tools.yaml" `
    --eval-cases "data/eval_group.json"

& $Python "run_eval.py" --provider openai --model $Model --version v3 --suite base `
    --system-prompt "artifacts/system_prompt.md" `
    --tools "artifacts/tools.yaml" `
    --eval-cases "data/eval_base.json"

& $Python "run_eval.py" --provider openai --model $Model --version v3 --suite group `
    --system-prompt "artifacts/system_prompt.md" `
    --tools "artifacts/tools.yaml" `
    --eval-cases "data/eval_group.json"

Write-Host "Completed v2/v3 base and Company Policy group evals."
