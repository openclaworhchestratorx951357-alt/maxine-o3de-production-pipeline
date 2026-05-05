Set-StrictMode -Version Latest

function Resolve-MaxineRepoRoot {
    param([string]$ScriptRoot)
    if ([string]::IsNullOrWhiteSpace($ScriptRoot)) {
        $ScriptRoot = $PSScriptRoot
    }
    return (Resolve-Path (Join-Path $ScriptRoot "..\..")).Path
}

function Resolve-MaxinePath {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$RepoRoot
    )
    if ([System.IO.Path]::IsPathRooted($Path)) {
        return [System.IO.Path]::GetFullPath($Path)
    }
    return [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $Path))
}

function Get-MaxineUtcNow {
    return (Get-Date).ToUniversalTime().ToString("o")
}

function Set-MaxineObjectProperty {
    param(
        [Parameter(Mandatory = $true)] [object]$Object,
        [Parameter(Mandatory = $true)] [string]$Name,
        [Parameter(Mandatory = $true)] [AllowNull()] $Value
    )
    if ($Object.PSObject.Properties[$Name]) {
        $Object.$Name = $Value
    }
    else {
        $Object | Add-Member -NotePropertyName $Name -NotePropertyValue $Value
    }
}

function Ensure-MaxineChildObject {
    param(
        [Parameter(Mandatory = $true)] [object]$Parent,
        [Parameter(Mandatory = $true)] [string]$Name
    )
    if (-not $Parent.PSObject.Properties[$Name] -or $null -eq $Parent.$Name) {
        Set-MaxineObjectProperty -Object $Parent -Name $Name -Value ([pscustomobject]@{})
    }
    return $Parent.$Name
}

function Ensure-MaxineArrayProperty {
    param(
        [Parameter(Mandatory = $true)] [object]$Parent,
        [Parameter(Mandatory = $true)] [string]$Name
    )
    if (-not $Parent.PSObject.Properties[$Name] -or $null -eq $Parent.$Name) {
        Set-MaxineObjectProperty -Object $Parent -Name $Name -Value @()
    }
    return @($Parent.$Name)
}

function Write-MaxineJsonAtomic {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][object]$Data,
        [int]$Depth = 40
    )

    $targetPath = [System.IO.Path]::GetFullPath($Path)
    $parentDir = Split-Path -Parent $targetPath
    if (-not [string]::IsNullOrWhiteSpace($parentDir)) {
        New-Item -ItemType Directory -Force -Path $parentDir | Out-Null
    }

    $tempFile = Join-Path $parentDir ([System.IO.Path]::GetRandomFileName() + ".tmp")
    $json = $Data | ConvertTo-Json -Depth $Depth
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($tempFile, $json, $utf8NoBom)
    Move-Item -LiteralPath $tempFile -Destination $targetPath -Force
}

function Read-MaxineJsonObject {
    param([Parameter(Mandatory = $true)][string]$Path)
    return Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
}

function Invoke-MaxineManifestValidation {
    param(
        [Parameter(Mandatory = $true)][string]$ManifestPath,
        [Parameter(Mandatory = $true)][string]$RepoRoot
    )
    $validatorScript = Join-Path $RepoRoot "tools\manifest-validator\validate_manifest.py"
    if (Test-Path -LiteralPath $validatorScript) {
        & python $validatorScript $ManifestPath
        if ($LASTEXITCODE -ne 0) {
            throw "Manifest validation failed: $ManifestPath"
        }
    }
}

function Merge-MaxineUniqueStrings {
    param(
        [string[]]$Base = @(),
        [string[]]$Incoming = @()
    )

    $combined = New-Object System.Collections.Generic.List[string]
    foreach ($candidate in @($Base) + @($Incoming)) {
        if ([string]::IsNullOrWhiteSpace($candidate)) { continue }
        if (-not $combined.Contains($candidate)) {
            [void]$combined.Add($candidate)
        }
    }
    return $combined.ToArray()
}
