[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$RuiPath
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

function Require([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}

try {
    Require (Test-Path -LiteralPath $RuiPath -PathType Leaf) "Required Smart Skin RUI is missing."
    $Resolved = (Resolve-Path -LiteralPath $RuiPath).Path
    Require ((Get-Item -LiteralPath $Resolved).Length -le 1048576) "RUI exceeds the 1 MiB limit."

    $Settings = New-Object System.Xml.XmlReaderSettings
    $Settings.DtdProcessing = [System.Xml.DtdProcessing]::Prohibit
    $Settings.XmlResolver = $null
    $Reader = [System.Xml.XmlReader]::Create($Resolved, $Settings)
    try {
        $Xml = New-Object System.Xml.XmlDocument
        $Xml.XmlResolver = $null
        $Xml.Load($Reader)
    }
    finally { $Reader.Dispose() }

    $Rui = $Xml.DocumentElement
    Require ($Rui.Name -eq "RhinoUI") "Unexpected RUI root."
    Require ($Rui.GetAttribute("guid") -eq "66132d99-9d6c-512f-aea3-86d88fbf5eb0") "RUI identity changed."
    Require ($Rui.GetAttribute("plug_in_guid") -eq "b3f42f21-1f15-45e6-9bc2-a68b0b27c877") "Plug-in GUID mismatch."
    Require ($Rui.GetAttribute("major_ver") -eq "2") "Unexpected RUI format."

    $Groups = @($Rui.SelectNodes("tool_bar_groups/tool_bar_group"))
    $Bars = @($Rui.SelectNodes("tool_bars/tool_bar"))
    $Buttons = @($Rui.SelectNodes("tool_bars/tool_bar/tool_bar_item"))
    $Macros = @($Rui.SelectNodes("macros/macro_item"))
    Require ($Groups.Count -eq 1 -and $Bars.Count -eq 1 -and $Buttons.Count -eq 1 -and $Macros.Count -eq 4) "Expected one group, one toolbar, one product button and four preserved macros."
    Require (@($Rui.SelectNodes("menus/* | extend_rhino_menus/*")).Count -eq 0) "Smart Skin must not extend Rhino menus."

    $Group = $Groups[0]; $Bar = $Bars[0]
    $Items = @($Group.SelectNodes("tool_bar_group_item"))
    Require ($Items.Count -eq 1) "Expected one group item."
    $Item = $Items[0]
    $Identities = @{
        group = @($Group, "ebed14d4-d943-5ac3-b2bc-74cfc7eaa798")
        group_item = @($Item, "c7770a71-565a-599e-8b5a-f78a36324ecd")
        toolbar = @($Bar, "c2cb82d9-8ff1-5230-865f-af924412192d")
    }
    foreach ($Pair in $Identities.Values) {
        Require ($Pair[0].GetAttribute("guid") -eq $Pair[1]) "Stable toolbar component GUID mismatch."
    }
    Require ($Item.SelectSingleNode("tool_bar_id").InnerText -eq $Bar.GetAttribute("guid")) "Unresolved toolbar reference."
    Require ($Group.GetAttribute("active_tool_bar_group") -eq $Item.GetAttribute("guid")) "Unresolved active group item."
    Require ($Item.GetAttribute("major_version") -eq "1" -and $Item.GetAttribute("minor_version") -eq "2") "Unexpected product toolbar revision."
    Require ($Group.SelectSingleNode("dock_bar_info").GetAttribute("visible") -eq "True") "First-load toolbar must be visible."

    $CommandSpecs = @(
        [ordered]@{
            name = "SmartSurfaceBuild"
            script = "! _SmartSurfaceBuild"
            macro = "388db0d8-f25d-5e76-849f-49b913de4229"
            bitmap = "ccb35d2d-9542-5366-8f54-dd3da8cfbae0"
            index = 0
        },
        [ordered]@{
            name = "SmartSurfacePlan"
            script = "! _SmartSurfacePlan"
            macro = "aecb1052-7a96-58ec-8877-6b97e1689798"
            bitmap = "5bb6fb4b-5e8d-555a-a744-d88d184ba8fd"
            index = 1
        },
        [ordered]@{
            name = "SmartSurfacePreflight"
            script = "! _SmartSurfacePreflight"
            macro = "8330b22b-75bf-5cfd-b251-a634072397e9"
            bitmap = "2a674390-4cee-51f1-922b-742a1eaee03d"
            index = 2
        },
        [ordered]@{
            name = "SmartSurfaceVersion"
            script = "! _SmartSurfaceVersion"
            macro = "8671d92d-bb1f-5e8e-80b3-a60c34d1ddae"
            bitmap = "63fb3907-aaba-55ad-882e-819bac4aba3d"
            index = 3
        }
    )

    $Button = $Buttons[0]
    $BuildSpec = $CommandSpecs[0]
    Require ($Button.GetAttribute("guid") -eq "e8384b80-33a1-5372-837d-b2605d097033") "Product button identity changed."
    Require (@($Button.SelectNodes("right_macro_id")).Count -eq 0) "Right-click must not invoke a second toolbar action."
    Require ($Button.SelectSingleNode("left_macro_id").InnerText -eq $BuildSpec.macro) "Product button must invoke SmartSurfaceBuild."

    foreach ($Spec in $CommandSpecs) {
        $Macro = $Rui.SelectSingleNode("macros/macro_item[@guid='" + $Spec.macro + "']")
        Require ($null -ne $Macro) "Missing macro for $($Spec.name)."
        Require ($Macro.SelectSingleNode("text/locale_1033").InnerText -ceq $Spec.name) "Unexpected macro name for $($Spec.name)."
        Require ($Macro.SelectSingleNode("script").InnerText -ceq $Spec.script) "Unexpected script for $($Spec.name)."
        Require ($Macro.GetAttribute("bitmap_id") -eq $Spec.bitmap) "Macro bitmap identity mismatch for $($Spec.name)."
        foreach ($Locale in @("locale_1033", "locale_1049")) {
            $Tooltip = $Macro.SelectSingleNode("tooltip/" + $Locale)
            Require ($null -ne $Tooltip -and -not [string]::IsNullOrWhiteSpace($Tooltip.InnerText)) "Missing localized tooltip for $($Spec.name)."
        }
    }

    $BuildMacro = $Rui.SelectSingleNode("macros/macro_item[@guid='" + $BuildSpec.macro + "']")
    Require ($BuildMacro.SelectSingleNode("button_text/locale_1033").InnerText -ceq "Smart Skin") "Product button text must be Smart Skin."
    Require ($BuildMacro.SelectSingleNode("button_text/locale_1049").InnerText -ceq "Smart Skin") "Localized product button text must be Smart Skin."
    Require ($BuildMacro.SelectSingleNode("tooltip/locale_1033").InnerText -match "SmartSurfaceBuild") "Product tooltip must identify the invoked command."
    $BuildHelp = $BuildMacro.SelectSingleNode("help_text/locale_1033").InnerText
    Require ($BuildHelp -notmatch "\bAccept\b|\bCancel\b") "Product help must use normal Rhino confirmation, not extra Accept/Cancel options."

    $VisibleMacroIds = @($Buttons | ForEach-Object { $_.SelectSingleNode("left_macro_id").InnerText })
    foreach ($Spec in $CommandSpecs | Select-Object -Skip 1) {
        Require ($VisibleMacroIds -notcontains $Spec.macro) "Diagnostic command $($Spec.name) must remain command-line only."
    }

    Add-Type -AssemblyName System.Drawing
    $Sizes = @{ small_bitmap = 16; normal_bitmap = 24; large_bitmap = 32 }
    Require (@($Rui.SelectNodes("bitmaps/*")).Count -eq 3) "Expected three bitmap atlases."
    foreach ($Tag in $Sizes.Keys) {
        $Size = $Sizes[$Tag]
        $Atlas = $Rui.SelectSingleNode("bitmaps/" + $Tag)
        Require ($null -ne $Atlas) "Missing bitmap atlas."
        Require ($Atlas.GetAttribute("item_width") -eq [string]$Size -and $Atlas.GetAttribute("item_height") -eq [string]$Size) "Unexpected bitmap cell size."
        $BitmapItems = @($Atlas.SelectNodes("bitmap_item"))
        Require ($BitmapItems.Count -eq 4) "Expected four bitmap items per atlas."
        foreach ($Spec in $CommandSpecs) {
            $BitmapItem = $Atlas.SelectSingleNode("bitmap_item[@guid='" + $Spec.bitmap + "']")
            Require ($null -ne $BitmapItem) "Missing bitmap item for $($Spec.name)."
            Require ($BitmapItem.GetAttribute("index") -eq [string]$Spec.index) "Bitmap index mismatch for $($Spec.name)."
        }
        $Bytes = [Convert]::FromBase64String($Atlas.SelectSingleNode("bitmap").InnerText)
        Require ($Bytes.Length -ge 24) "Empty bitmap."
        $Magic = [BitConverter]::ToString($Bytes, 0, 8)
        Require ($Magic -eq "89-50-4E-47-0D-0A-1A-0A") "Bitmap is not a PNG."
        # Reject oversized PNG headers before invoking the image decoder.
        $ExpectedWidth = [BitConverter]::GetBytes([int](250 * $Size))
        $ExpectedHeight = [BitConverter]::GetBytes([int]$Size)
        if ([BitConverter]::IsLittleEndian) {
            [Array]::Reverse($ExpectedWidth)
            [Array]::Reverse($ExpectedHeight)
        }
        Require ([BitConverter]::ToString($Bytes, 16, 4) -eq [BitConverter]::ToString($ExpectedWidth)) "Unexpected PNG width header."
        Require ([BitConverter]::ToString($Bytes, 20, 4) -eq [BitConverter]::ToString($ExpectedHeight)) "Unexpected PNG height header."
        $Stream = New-Object System.IO.MemoryStream
        $Image = $null
        $DecodedBitmap = $null
        try {
            $Stream.Write($Bytes, 0, $Bytes.Length)
            $Stream.Position = 0
            $Image = [System.Drawing.Image]::FromStream($Stream, $true, $true)
            Require ($Image.Width -eq 250 * $Size -and $Image.Height -eq $Size) "Unexpected legacy 250-column atlas dimensions."
            $DecodedBitmap = New-Object System.Drawing.Bitmap -ArgumentList $Image
            foreach ($Spec in $CommandSpecs) {
                $OpaquePixels = 0
                $StartX = $Spec.index * $Size
                for ($X = $StartX; $X -lt $StartX + $Size; $X++) {
                    for ($Y = 0; $Y -lt $Size; $Y++) {
                        if ($DecodedBitmap.GetPixel($X, $Y).A -gt 0) { $OpaquePixels++ }
                    }
                }
                Require ($OpaquePixels -gt 0) "Bitmap cell is empty for $($Spec.name)."
            }
        }
        finally {
            if ($null -ne $DecodedBitmap) { $DecodedBitmap.Dispose() }
            if ($null -ne $Image) { $Image.Dispose() }
            $Stream.Dispose()
        }
    }
    Write-Host "SMARTSKIN_TOOLBAR PASS | groups=1 | toolbars=1 | buttons=1 | product=SmartSkin | diagnostics=command-line | icons=16,24,32"
}
catch {
    Write-Host "SMARTSKIN_TOOLBAR FAIL | error=$($_.Exception.Message)"
    throw
}
