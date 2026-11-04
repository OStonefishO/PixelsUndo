# Build the PixelsUndo Android WebView wrapper.
# Requires: JDK 17 and Android SDK build-tools + platform 34.
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
# aapt2 cannot open non-ASCII directories, so stage the project under %TEMP%.
$Root = Join-Path $env:TEMP "PixelsUndoAndroidBuild"
$AndroidDir = Join-Path $Root "android"
$Sdk = if ($env:ANDROID_SDK_ROOT) { $env:ANDROID_SDK_ROOT } else { "D:\Android\sdk" }
$Out = Join-Path $AndroidDir "build"
$Keystore = Join-Path $AndroidDir "pixelsundo-release.jks"
$RealKeystore = Join-Path $ProjectRoot "android\pixelsundo-release.jks"
$KeyPass = "pixelsundo"
$VersionName = "1.4.0"
$VersionCode = 140

if (Test-Path $Root) { Remove-Item $Root -Recurse -Force }
New-Item -ItemType Directory -Force -Path $Root | Out-Null
Copy-Item (Join-Path $ProjectRoot "android") $Root -Recurse
if (Test-Path $RealKeystore) { Copy-Item $RealKeystore $Keystore -Force }

function Find-Jdk {
    $candidates = @(
        $env:JAVA_HOME,
        "D:\Android\jdk-17",
        "C:\Program Files\Microsoft\jdk-17*",
        "C:\Program Files\Eclipse Adoptium\jdk-17*"
    )
    foreach ($candidate in $candidates) {
        if (-not $candidate) { continue }
        if (Test-Path (Join-Path $candidate "bin\javac.exe")) { return $candidate }
        $resolved = Get-ChildItem $candidate -ErrorAction SilentlyContinue -Directory | Select-Object -First 1
        if ($resolved -and (Test-Path (Join-Path $resolved.FullName "bin\javac.exe"))) { return $resolved.FullName }
    }
    throw "JDK 17 not found. Set JAVA_HOME or extract it to D:\Android\jdk-17."
}

function Assert-LastExit([string]$Step) {
    if ($LASTEXITCODE -ne 0) { throw "$Step failed with exit code $LASTEXITCODE" }
}

$Jdk = Find-Jdk
$BuildTools = Get-ChildItem (Join-Path $Sdk "build-tools") -Directory |
    Sort-Object { [version]$_.Name } -Descending | Select-Object -First 1
if (-not $BuildTools) { throw "Android build-tools not installed under $Sdk" }
$Platform = Join-Path $Sdk "platforms\android-34\android.jar"
if (-not (Test-Path $Platform)) { throw "android-34 platform not installed under $Sdk" }

$Aapt2 = Join-Path $BuildTools.FullName "aapt2.exe"
$D8 = Join-Path $BuildTools.FullName "d8.bat"
$Zipalign = Join-Path $BuildTools.FullName "zipalign.exe"
$Apksigner = Join-Path $BuildTools.FullName "apksigner.bat"
$Jar = Join-Path $Jdk "bin\jar.exe"
$Javac = Join-Path $Jdk "bin\javac.exe"
$Keytool = Join-Path $Jdk "bin\keytool.exe"

if (Test-Path $Out) { Remove-Item $Out -Recurse -Force }
New-Item -ItemType Directory -Force -Path $Out, (Join-Path $Out "classes"), (Join-Path $Out "dex"), (Join-Path $Out "gen") | Out-Null

Write-Host "1/7 compiling resources"
& $Aapt2 compile --dir (Join-Path $AndroidDir "res") -o (Join-Path $Out "compiled.zip")
Assert-LastExit "aapt2 compile"

Write-Host "2/7 linking manifest and resources"
& $Aapt2 link -o (Join-Path $Out "unsigned.apk") `
    -I $Platform `
    --manifest (Join-Path $AndroidDir "AndroidManifest.xml") `
    --java (Join-Path $Out "gen") `
    --min-sdk-version 29 --target-sdk-version 34 `
    --version-code $VersionCode --version-name $VersionName `
    (Join-Path $Out "compiled.zip")
Assert-LastExit "aapt2 link"

Write-Host "3/7 compiling Java"
$Sources = @(Get-ChildItem (Join-Path $AndroidDir "src") -Recurse -Filter *.java |
    ForEach-Object { $_.FullName })
$Sources += @(Get-ChildItem (Join-Path $Out "gen") -Recurse -Filter *.java |
    ForEach-Object { $_.FullName })
& $Javac -source 8 -target 8 -bootclasspath $Platform -encoding UTF-8 `
    -classpath $Platform -d (Join-Path $Out "classes") $Sources
Assert-LastExit "javac"

Write-Host "4/7 dexing"
$Classes = @(Get-ChildItem (Join-Path $Out "classes") -Recurse -Filter *.class |
    ForEach-Object { $_.FullName })
& $D8 --lib $Platform --min-api 29 --output (Join-Path $Out "dex") $Classes
Assert-LastExit "d8"

Write-Host "5/7 packaging"
& $Jar --update --file (Join-Path $Out "unsigned.apk") -C (Join-Path $Out "dex") classes.dex
Assert-LastExit "jar update"
& $Zipalign -f -p 4 (Join-Path $Out "unsigned.apk") (Join-Path $Out "aligned.apk")
Assert-LastExit "zipalign"

Write-Host "6/7 signing"
if (-not (Test-Path $Keystore)) {
    & $Keytool -genkeypair -v -keystore $Keystore -storepass $KeyPass -keypass $KeyPass `
        -alias pixelsundo -keyalg RSA -keysize 2048 -validity 10000 `
        -dname "CN=StoneFish8, O=PixelsUndo, C=CN"
    Assert-LastExit "keytool"
}
$Apk = Join-Path $Root "PixelsUndo-Android.apk"
& $Apksigner sign --ks $Keystore --ks-pass "pass:$KeyPass" --key-pass "pass:$KeyPass" `
    --out $Apk (Join-Path $Out "aligned.apk")
Assert-LastExit "apksigner sign"
& $Apksigner verify --print-certs $Apk
Assert-LastExit "apksigner verify"

Copy-Item $Apk (Join-Path $ProjectRoot "PixelsUndo-Android.apk") -Force
Copy-Item $Keystore $RealKeystore -Force
Write-Host "7/7 done: $ProjectRoot\PixelsUndo-Android.apk"




