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
    Require ($Groups.Count -eq 1 -and $Bars.Count -eq 1 -and $Buttons.Count -eq 1 -and $Macros.Count -eq 1) "Expected exactly one group, toolbar, button and macro."
    Require (@($Rui.SelectNodes("menus/* | extend_rhino_menus/*")).Count -eq 0) "P04 must not extend Rhino menus."

    $Group = $Groups[0]; $Bar = $Bars[0]; $Button = $Buttons[0]; $Macro = $Macros[0]
    $Items = @($Group.SelectNodes("tool_bar_group_item"))
    Require ($Items.Count -eq 1) "Expected one group item."
    $Item = $Items[0]
    $Identities = @{
        group = @($Group, "ebed14d4-d943-5ac3-b2bc-74cfc7eaa798")
        group_item = @($Item, "c7770a71-565a-599e-8b5a-f78a36324ecd")
        toolbar = @($Bar, "c2cb82d9-8ff1-5230-865f-af924412192d")
        button = @($Button, "e8384b80-33a1-5372-837d-b2605d097033")
        macro = @($Macro, "388db0d8-f25d-5e76-849f-49b913de4229")
    }
    foreach ($Pair in $Identities.Values) {
        Require ($Pair[0].GetAttribute("guid") -eq $Pair[1]) "Stable toolbar component GUID mismatch."
    }
    Require ($Item.SelectSingleNode("tool_bar_id").InnerText -eq $Bar.GetAttribute("guid")) "Unresolved toolbar reference."
    Require ($Group.GetAttribute("active_tool_bar_group") -eq $Item.GetAttribute("guid")) "Unresolved active group item."
    Require ($Group.SelectSingleNode("dock_bar_info").GetAttribute("visible") -eq "True") "First-load toolbar must be visible."
    Require ($Button.SelectSingleNode("left_macro_id").InnerText -eq $Macro.GetAttribute("guid")) "Unresolved button macro."
    Require (@($Button.SelectNodes("right_macro_id")).Count -eq 0) "Right-click must not invoke a second action."
    Require ($Macro.SelectSingleNode("script").InnerText -ceq "! _SmartSurfaceBuild") "Unexpected macro, selection reset, or automatic acceptance."
    foreach ($Locale in @("locale_1033", "locale_1049")) {
        $Tooltip = $Macro.SelectSingleNode("tooltip/" + $Locale)
        Require ($null -ne $Tooltip -and -not [string]::IsNullOrWhiteSpace($Tooltip.InnerText)) "Missing localized tooltip."
    }

    Add-Type -AssemblyName System.Drawing
    $BitmapGuid = "ccb35d2d-9542-5366-8f54-dd3da8cfbae0"
    Require ($Macro.GetAttribute("bitmap_id") -eq $BitmapGuid) "Macro bitmap identity mismatch."
    $Sizes = @{ small_bitmap = 16; normal_bitmap = 24; large_bitmap = 32 }
    Require (@($Rui.SelectNodes("bitmaps/*")).Count -eq 3) "Expected three bitmap atlases."
    foreach ($Tag in $Sizes.Keys) {
        $Size = $Sizes[$Tag]
        $Atlas = $Rui.SelectSingleNode("bitmaps/" + $Tag)
        Require ($null -ne $Atlas) "Missing bitmap atlas."
        Require ($Atlas.GetAttribute("item_width") -eq [string]$Size -and $Atlas.GetAttribute("item_height") -eq [string]$Size) "Unexpected bitmap cell size."
        $BitmapItems = @($Atlas.SelectNodes("bitmap_item"))
        Require ($BitmapItems.Count -eq 1) "Expected one bitmap item per atlas."
        Require ($BitmapItems[0].GetAttribute("guid") -eq $BitmapGuid -and $BitmapItems[0].GetAttribute("index") -eq "0") "Bitmap GUID or index mismatch."
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
        try {
            $Stream.Write($Bytes, 0, $Bytes.Length)
            $Stream.Position = 0
            $Image = [System.Drawing.Image]::FromStream($Stream, $true, $true)
            Require ($Image.Width -eq 250 * $Size -and $Image.Height -eq $Size) "Unexpected legacy 250-column atlas dimensions."
        }
        finally {
            if ($null -ne $Image) { $Image.Dispose() }
            $Stream.Dispose()
        }
    }
    Write-Host "SMARTSKIN_TOOLBAR PASS | groups=1 | toolbars=1 | buttons=1 | macro=SmartSurfaceBuild | icons=16,24,32"
}
catch {
    Write-Host "SMARTSKIN_TOOLBAR FAIL | error=$($_.Exception.Message)"
    throw
}
