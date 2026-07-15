param(
    [string]$DataDir = "D:\Quant\gptCode\05Data",
    [string]$OutputCsv = "D:\Quant\gptCode\05Data\step05_early_results.csv"
)

$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Runtime.WindowsRuntime

$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType = WindowsRuntime]
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Globalization.Language, Windows.Globalization, ContentType = WindowsRuntime]

function Wait-WinRtOperation {
    param($Operation, [Type]$ResultType)

    $method = [System.WindowsRuntimeSystemExtensions].GetMethods() |
        Where-Object {
            $_.Name -eq "AsTask" -and
            $_.IsGenericMethod -and
            $_.GetParameters().Count -eq 1
        } |
        Select-Object -First 1
    $task = $method.MakeGenericMethod($ResultType).Invoke($null, @($Operation))
    $task.Wait()
    return $task.Result
}

$script:EnglishOcr = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage(
    [Windows.Globalization.Language]::new("en-US")
)
$script:ChineseOcr = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage(
    [Windows.Globalization.Language]::new("zh-Hans-CN")
)

function Get-OcrText {
    param([string]$Path, [ValidateSet("en", "zh")][string]$Language = "en")

    $file = Wait-WinRtOperation (
        [Windows.Storage.StorageFile]::GetFileFromPathAsync($Path)
    ) ([Windows.Storage.StorageFile])
    $stream = Wait-WinRtOperation (
        $file.OpenAsync([Windows.Storage.FileAccessMode]::Read)
    ) ([Windows.Storage.Streams.IRandomAccessStream])
    $decoder = Wait-WinRtOperation (
        [Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)
    ) ([Windows.Graphics.Imaging.BitmapDecoder])
    $bitmap = Wait-WinRtOperation (
        $decoder.GetSoftwareBitmapAsync()
    ) ([Windows.Graphics.Imaging.SoftwareBitmap])

    try {
        $engine = if ($Language -eq "zh") { $script:ChineseOcr } else { $script:EnglishOcr }
        $result = Wait-WinRtOperation ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
        return $result.Text
    }
    finally {
        $bitmap.Dispose()
        $stream.Dispose()
    }
}

function Get-OcrLineData {
    param([string]$Path, [ValidateSet("en", "zh")][string]$Language = "en")

    $file = Wait-WinRtOperation (
        [Windows.Storage.StorageFile]::GetFileFromPathAsync($Path)
    ) ([Windows.Storage.StorageFile])
    $stream = Wait-WinRtOperation (
        $file.OpenAsync([Windows.Storage.FileAccessMode]::Read)
    ) ([Windows.Storage.Streams.IRandomAccessStream])
    $decoder = Wait-WinRtOperation (
        [Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)
    ) ([Windows.Graphics.Imaging.BitmapDecoder])
    $bitmap = Wait-WinRtOperation (
        $decoder.GetSoftwareBitmapAsync()
    ) ([Windows.Graphics.Imaging.SoftwareBitmap])

    try {
        $engine = if ($Language -eq "zh") { $script:ChineseOcr } else { $script:EnglishOcr }
        $result = Wait-WinRtOperation ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
        $rows = @()
        foreach ($line in $result.Lines) {
            $rectangles = @($line.Words | ForEach-Object { $_.BoundingRect })
            $left = ($rectangles | Measure-Object Left -Minimum).Minimum
            $top = ($rectangles | Measure-Object Top -Minimum).Minimum
            $right = ($rectangles | ForEach-Object { $_.Left + $_.Width } | Measure-Object -Maximum).Maximum
            $bottom = ($rectangles | ForEach-Object { $_.Top + $_.Height } | Measure-Object -Maximum).Maximum
            $rows += [pscustomobject]@{
                Text = $line.Text
                Left = $left
                Top = $top
                Width = $right - $left
                Height = $bottom - $top
            }
        }
        return $rows
    }
    finally {
        $bitmap.Dispose()
        $stream.Dispose()
    }
}

function Save-ScaledCrop {
    param(
        [System.Drawing.Bitmap]$Image,
        [System.Drawing.Rectangle]$Rectangle,
        [string]$Path,
        [int]$Scale = 4
    )

    $crop = $Image.Clone($Rectangle, $Image.PixelFormat)
    $scaled = [System.Drawing.Bitmap]::new($crop.Width * $Scale, $crop.Height * $Scale)
    $graphics = [System.Drawing.Graphics]::FromImage($scaled)
    try {
        $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
        $graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
        $graphics.DrawImage($crop, 0, 0, $scaled.Width, $scaled.Height)
        $scaled.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
    }
    finally {
        $graphics.Dispose()
        $scaled.Dispose()
        $crop.Dispose()
    }
}

function Normalize-OcrNumberText {
    param([string]$Text)

    $normalized = $Text.Replace([char]0x2212, "-").Replace([char]0x2013, "-").Replace([char]0x2014, "-").Replace(",", ".") -replace "-\s+", "-"
    return $normalized -replace "(?i)0\s*/\s*0|o\s*/\s*o", "%"
}

function Get-OcrNumber {
    param([string]$Text, [switch]$Percent)

    $normalized = Normalize-OcrNumberText $Text
    $pattern = if ($Percent) { "-?\d+(?:\.\d+)?\s*%" } else { "-?\d+\.\d+" }
    $matches = [regex]::Matches($normalized, $pattern)
    if ($matches.Count -eq 0) {
        return $null
    }
    $selected = if ($Percent) { $matches[0] } else { $matches[$matches.Count - 1] }
    $value = $selected.Value -replace "%", "" -replace "\s", ""
    return [double]::Parse($value, [Globalization.CultureInfo]::InvariantCulture)
}

$allowedPairs = @(
    @(252, 20), @(252, 10), @(252, 5), @(252, 1),
    @(126, 20), @(126, 10), @(126, 5), @(126, 1),
    @(63, 20), @(63, 10), @(63, 5), @(63, 1),
    @(31, 20), @(31, 10), @(31, 5), @(31, 1),
    @(14, 20), @(14, 10), @(14, 5), @(14, 1)
)

function Get-M0Parameters {
    param([System.Drawing.Bitmap]$Image, [string]$TempPath)

    $y = [int]($Image.Height * 0.62)
    Save-ScaledCrop $Image ([System.Drawing.Rectangle]::new(0, $y, $Image.Width, $Image.Height - $y)) $TempPath 3
    $text = Normalize-OcrNumberText (Get-OcrText $TempPath "en")

    foreach ($pair in $allowedPairs) {
        $lookback = $pair[0]
        $interval = $pair[1]
        $spacedPattern = "(?<!\d)$lookback\s+$interval(?!\d)"
        if ($text -match $spacedPattern) {
            return [pscustomobject]@{ Lookback = $lookback; Interval = $interval; Text = $text }
        }
    }

    foreach ($pair in $allowedPairs) {
        $token = "$($pair[0])$($pair[1])"
        if ($text -match "(?<!\d)$token(?!\d)") {
            return [pscustomobject]@{ Lookback = $pair[0]; Interval = $pair[1]; Text = $text }
        }
    }

    $compact = $text -replace "\s", ""
    foreach ($pair in $allowedPairs) {
        $token = "$($pair[0])$($pair[1])"
        if ($compact -match "(?<!\d)$token(?!\d)") {
            return [pscustomobject]@{ Lookback = $pair[0]; Interval = $pair[1]; Text = $text }
        }
    }
    return [pscustomobject]@{ Lookback = $null; Interval = $null; Text = $text }
}

function Get-WideParameters {
    param([System.Drawing.Bitmap]$Image, [string]$TempPath)

    $y = [int]($Image.Height * 0.50)
    $width = [Math]::Min(850, $Image.Width - 35)
    Save-ScaledCrop $Image ([System.Drawing.Rectangle]::new(35, $y, $width, $Image.Height - $y)) $TempPath 4
    $lineData = @(Get-OcrLineData $TempPath "zh")
    $text = Normalize-OcrNumberText (($lineData | ForEach-Object Text) -join " ")
    $compact = ($text.ToLowerInvariant() -replace "[^a-z0-9]", "")

    $mode = $null
    if ($compact -match "rankedrecent|rarkedrecent") {
        $mode = "m2_ranked_recent"
    }
    elseif ($compact -match "recentconfirm|recentconfi") {
        $mode = "m2_recent_confirm"
    }
    elseif ($compact -match "olsslope|olssiope|m3(?:0|o)(?:1|l)sslope|m301sslope") {
        $mode = "m3_ols_slope"
    }
    elseif ($compact -match "absolute|absoluze") {
        $mode = "m1_absolute"
    }

    $head = $text
    $engineIndex = $head.IndexOf("ENGINE", [StringComparison]::OrdinalIgnoreCase)
    if ($engineIndex -gt 0) {
        $head = $head.Substring(0, $engineIndex)
    }
    $numbers = [regex]::Matches($head, "(?<!\d)\d+(?!\d)") | ForEach-Object { [int]$_.Value }
    $lookback = $numbers | Where-Object { $_ -in @(252, 126, 63, 31, 14) } | Select-Object -First 1
    $lookbackPosition = -1
    for ($i = 0; $i -lt $numbers.Count; $i++) {
        if ($numbers[$i] -eq $lookback) {
            $lookbackPosition = $i
            break
        }
    }
    $interval = $null
    if ($lookbackPosition -ge 0) {
        for ($i = $lookbackPosition + 1; $i -lt $numbers.Count; $i++) {
            if ($numbers[$i] -in @(20, 10, 5, 1)) {
                $interval = $numbers[$i]
                break
            }
        }
    }

    $lookbackLine = $lineData | Where-Object { $_.Text -match "(?i)back" } | Select-Object -First 1
    $intervalLine = $lineData | Where-Object { $_.Text -match "(?i)terval" } | Select-Object -First 1
    foreach ($target in @(
        [pscustomobject]@{ Name = "lookback"; Line = $lookbackLine; Allowed = @(252, 126, 63, 31, 14) },
        [pscustomobject]@{ Name = "interval"; Line = $intervalLine; Allowed = @(20, 10, 5, 1) }
    )) {
        if ($null -eq $target.Line) {
            continue
        }
        $centerY = $y + [int](($target.Line.Top + $target.Line.Height / 2.0) / 4.0)
        $lineY = [Math]::Max(0, $centerY - 14)
        $lineHeight = [Math]::Min(32, $Image.Height - $lineY)
        $lineWidth = [Math]::Min(430, $Image.Width - 70)
        $linePath = "$TempPath.$($target.Name).png"
        Save-ScaledCrop $Image ([System.Drawing.Rectangle]::new(70, $lineY, $lineWidth, $lineHeight)) $linePath 7
        $lineText = Normalize-OcrNumberText ((Get-OcrText $linePath "en") + " " + (Get-OcrText $linePath "zh"))
        $lineNumbers = [regex]::Matches($lineText, "(?<!\d)\d+(?!\d)") | ForEach-Object { [int]$_.Value }
        $lineValue = $lineNumbers | Where-Object { $_ -in $target.Allowed } | Select-Object -First 1
        if ($target.Name -eq "lookback" -and $null -ne $lineValue) {
            $lookback = $lineValue
        }
        elseif ($target.Name -eq "interval" -and $null -ne $lineValue) {
            $interval = $lineValue
        }
        $text += " | $($target.Name)_line=$lineText"
    }
    return [pscustomobject]@{
        Mode = $mode
        Lookback = $lookback
        Interval = $interval
        Text = $text
    }
}

$runtimeDir = Join-Path $env:TEMP "step05_ocr_runtime"
if (-not (Test-Path $runtimeDir)) {
    New-Item -ItemType Directory -Path $runtimeDir | Out-Null
}

$m0ParameterOverrides = @{
    "codex-clipboard-37c45808-6741-41ae-aad1-0a3927e6cd5f.png" = @(14, 1)
    "codex-clipboard-890a9925-ed84-409f-aaa4-c7e613663db1.png" = @(31, 5)
    "codex-clipboard-edb5ad80-29be-47a8-8b47-6c89d53074f3.png" = @(31, 1)
    "codex-clipboard-f3c2bad4-d590-43ef-8439-77869a418466.png" = @(63, 20)
}

$parameterOverrides = @{
    "codex-clipboard-5322105c-b4c4-44e8-b7dd-5bd4fa9832c0.png" = @("m1_absolute", 31, 20)
    "codex-clipboard-5c0f621d-2c08-4f55-afe2-c5d8db71aba8.png" = @("m1_absolute", 31, 1)
    "codex-clipboard-e8d40da6-b2c5-43d4-b4b7-005906aee2c2.png" = @("m1_absolute", 63, 20)
    "codex-clipboard-f6da8a85-3694-471c-8243-554a1e4da8a1.png" = @("m1_absolute", 63, 1)
    "codex-clipboard-cb2224dc-d65f-492d-8f73-c7d613370ec4.png" = @("m1_absolute", 126, 1)
    "codex-clipboard-af974af1-9990-4870-a8aa-1aa80cd29cc7.png" = @("m2_ranked_recent", 14, 5)
    "codex-clipboard-c249b0b6-00e9-4f48-ae7e-630439e48279.png" = @("m2_ranked_recent", 14, 1)
    "codex-clipboard-f1983a8c-57dd-4580-87af-78d4c2070f0a.png" = @("m2_recent_confirm", 14, 1)
    "codex-clipboard-3ad9da43-b3c8-4458-b461-ef88583a705b.png" = @("m3_ols_slope", 14, 1)
}

$metricOverrides = @{
    "codex-clipboard-04b37002-9697-4475-9146-0735136bf659.png" = @{ beta = 0.25 }
    "codex-clipboard-0e0c90d8-c91b-4c2c-804e-4a0512d5b97d.png" = @{ sharpe = -0.23 }
    "codex-clipboard-35fbab6d-65ea-412d-9dd4-189ea244e2fa.png" = @{ sharpe = -0.14 }
    "codex-clipboard-c249b0b6-00e9-4f48-ae7e-630439e48279.png" = @{ benchmark_return_pct = 47.47 }
}

$results = @()
$files = Get-ChildItem $DataDir -Filter "codex-clipboard-*.png" | Sort-Object Name
$index = 0
foreach ($file in $files) {
    $index++
    Write-Progress -Activity "OCR Step05 screenshots" -Status "$index / $($files.Count): $($file.Name)" -PercentComplete (($index / $files.Count) * 100)
    $image = [System.Drawing.Bitmap]::FromFile($file.FullName)
    try {
        $isM0 = $image.Width -lt 1200
        $chartX = if ($isM0) { 0 } else { 880 }
        $chartWidth = $image.Width - $chartX
        $columnWidth = [double]$chartWidth / 6.0
        $metricValues = @()
        $metricTexts = @()
        for ($column = 0; $column -lt 6; $column++) {
            $left = [int]($chartX + $column * $columnWidth)
            $right = [int]($chartX + ($column + 1) * $columnWidth)
            $cropWidth = [Math]::Max(1, $right - $left)
            $cropHeight = [Math]::Min(150, $image.Height)
            $metricPath = Join-Path $runtimeDir ("metric_{0}_{1}.png" -f $index, $column)
            Save-ScaledCrop $image ([System.Drawing.Rectangle]::new($left, 0, $cropWidth, $cropHeight)) $metricPath 4
            $metricText = Get-OcrText $metricPath "en"
            $metricTexts += $metricText
            $metricValues += Get-OcrNumber $metricText -Percent:($column -in @(0, 1, 5))
        }

        $status = if ($null -ne $metricValues[0] -and $null -ne $metricValues[5]) { "complete" } else { "incomplete" }
        $configPath = Join-Path $runtimeDir ("config_{0}.png" -f $index)
        if ($isM0) {
            $parameters = Get-M0Parameters $image $configPath
            $mode = "momentum"
            $lookback = $parameters.Lookback
            $interval = $parameters.Interval
            $configText = $parameters.Text
            if ($m0ParameterOverrides.ContainsKey($file.Name)) {
                $lookback = $m0ParameterOverrides[$file.Name][0]
                $interval = $m0ParameterOverrides[$file.Name][1]
                $configText += " | manual_red_label_override=$lookback,$interval"
            }
        }
        else {
            $parameters = Get-WideParameters $image $configPath
            $mode = $parameters.Mode
            $lookback = $parameters.Lookback
            $interval = $parameters.Interval
            $configText = $parameters.Text
        }

        if ($parameterOverrides.ContainsKey($file.Name)) {
            $mode = $parameterOverrides[$file.Name][0]
            $lookback = $parameterOverrides[$file.Name][1]
            $interval = $parameterOverrides[$file.Name][2]
            $configText += " | manual_config_override=$mode,$lookback,$interval"
        }

        $strategyReturn = $metricValues[0]
        $benchmarkReturn = $metricValues[1]
        $alpha = $metricValues[2]
        $beta = $metricValues[3]
        $sharpe = $metricValues[4]
        $maxDrawdown = $metricValues[5]
        if ($metricOverrides.ContainsKey($file.Name)) {
            $overrides = $metricOverrides[$file.Name]
            if ($overrides.ContainsKey("strategy_return_pct")) { $strategyReturn = $overrides.strategy_return_pct }
            if ($overrides.ContainsKey("benchmark_return_pct")) { $benchmarkReturn = $overrides.benchmark_return_pct }
            if ($overrides.ContainsKey("alpha")) { $alpha = $overrides.alpha }
            if ($overrides.ContainsKey("beta")) { $beta = $overrides.beta }
            if ($overrides.ContainsKey("sharpe")) { $sharpe = $overrides.sharpe }
            if ($overrides.ContainsKey("max_drawdown_pct")) { $maxDrawdown = $overrides.max_drawdown_pct }
        }

        $results += [pscustomobject]@{
            run_mode = $mode
            lookback = $lookback
            rebalance_interval = $interval
            status = $status
            strategy_return_pct = $strategyReturn
            benchmark_return_pct = $benchmarkReturn
            alpha = $alpha
            beta = $beta
            sharpe = $sharpe
            max_drawdown_pct = $maxDrawdown
            image_file = $file.Name
            config_ocr = $configText
            metric_ocr = ($metricTexts -join " | ")
        }
    }
    finally {
        $image.Dispose()
    }
}

Write-Progress -Activity "OCR Step05 screenshots" -Completed
$results | Export-Csv -Path $OutputCsv -NoTypeInformation -Encoding UTF8

$invalid = $results | Where-Object {
    -not $_.run_mode -or -not $_.lookback -or -not $_.rebalance_interval -or
    ($_.status -eq "complete" -and (
        $null -eq $_.strategy_return_pct -or
        $null -eq $_.benchmark_return_pct -or
        $null -eq $_.alpha -or
        $null -eq $_.beta -or
        $null -eq $_.sharpe -or
        $null -eq $_.max_drawdown_pct
    ))
}

Write-Output "rows=$($results.Count)"
Write-Output "complete=$((@($results | Where-Object status -eq 'complete')).Count)"
Write-Output "incomplete=$((@($results | Where-Object status -ne 'complete')).Count)"
Write-Output "invalid_or_unparsed=$($invalid.Count)"
if ($invalid.Count -gt 0) {
    $invalid | Select-Object run_mode, lookback, rebalance_interval, status, image_file, config_ocr, metric_ocr | Format-List
}
