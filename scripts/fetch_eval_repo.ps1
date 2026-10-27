param([string]$Destination = "data/eval_repo")
$ErrorActionPreference = "Stop"
$commit = "f4bcfaba7c85be3c6332cc74a20819f586dcdbc6"
if (Test-Path -LiteralPath $Destination) { throw "Destination already exists: $Destination" }
git clone --filter=blob:none https://github.com/fastapi/full-stack-fastapi-template.git $Destination
git -C $Destination checkout --detach $commit
Write-Output "Pinned evaluation repository at $commit"
