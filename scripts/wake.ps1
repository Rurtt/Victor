$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$recognizer = $null
try {
    Add-Type -AssemblyName System.Speech
    $available = [System.Speech.Recognition.SpeechRecognitionEngine]::InstalledRecognizers()
    $english = $available | Where-Object { $_.Culture.Name -eq 'en-US' } | Select-Object -First 1
    if (-not $english) { $english = $available | Where-Object { $_.Culture.TwoLetterISOLanguageName -eq 'en' } | Select-Object -First 1 }
    if (-not $english) { throw 'Windows English speech recognition is not installed. Install English speech in Windows language settings.' }
    $recognizer = New-Object System.Speech.Recognition.SpeechRecognitionEngine($english)
    $choices = New-Object System.Speech.Recognition.Choices
    $choices.Add([string[]]@('Jarvis', 'Hey Jarvis'))
    $builder = New-Object System.Speech.Recognition.GrammarBuilder
    $builder.Culture = $english.Culture
    $builder.Append($choices)
    $recognizer.LoadGrammar((New-Object System.Speech.Recognition.Grammar($builder)))
    $recognizer.SetInputToDefaultAudioDevice()
    while ($true) {
        $result = $recognizer.Recognize([TimeSpan]::FromSeconds(3))
        if ($result -and $result.Confidence -ge 0.65) {
            [Console]::WriteLine('wake')
            [Console]::Out.Flush()
        }
    }
} catch {
    [Console]::WriteLine('error:' + $_.Exception.Message)
    [Console]::Out.Flush()
    exit 1
} finally {
    if ($recognizer) { $recognizer.Dispose() }
}
