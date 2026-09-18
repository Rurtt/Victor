$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$synth = $null
$speechStream = $null
$reader = $null
$audio = $null
$player = $null
try {
    $text = [Console]::In.ReadToEnd()
    if ([string]::IsNullOrWhiteSpace($text)) { exit 0 }
    if ($text.Length -gt 8000) { throw 'Speech text exceeds the local limit.' }
    Add-Type -AssemblyName System.Speech
    $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
    $thai = $synth.GetInstalledVoices() | Where-Object { $_.Enabled -and $_.VoiceInfo.Culture.TwoLetterISOLanguageName -eq 'th' } | Select-Object -First 1
    if ($thai) {
        $synth.SelectVoice($thai.VoiceInfo.Name)
        $synth.Speak($text)
    } else {
        $synth.Dispose()
        $synth = $null
        Add-Type -AssemblyName System.Runtime.WindowsRuntime
        $null = [Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media.SpeechSynthesis, ContentType = WindowsRuntime]
        $null = [Windows.Media.SpeechSynthesis.SpeechSynthesisStream, Windows.Media.SpeechSynthesis, ContentType = WindowsRuntime]
        $null = [Windows.Storage.Streams.DataReader, Windows.Storage.Streams, ContentType = WindowsRuntime]
        $voice = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices | Where-Object { $_.Language -like 'th-*' } | Select-Object -First 1
        if (-not $voice) { throw 'ไม่พบเสียงภาษาไทยใน Windows กรุณาติดตั้งเสียงภาษาไทยที่ Settings > Time & language > Speech (ms-settings:speech)' }
        $asTask = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetGenericArguments().Count -eq 1 -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' } | Select-Object -First 1
        function Wait-LocalOperation($operation, [Type]$resultType) {
            $task = $asTask.MakeGenericMethod($resultType).Invoke($null, @($operation))
            $task.Wait()
            return $task.Result
        }
        $synth = New-Object Windows.Media.SpeechSynthesis.SpeechSynthesizer
        $synth.Voice = $voice
        $speechStream = Wait-LocalOperation ($synth.SynthesizeTextToStreamAsync($text)) ([Windows.Media.SpeechSynthesis.SpeechSynthesisStream])
        if ($speechStream.Size -gt 134217728) { throw 'Local speech output exceeds the limit.' }
        $reader = New-Object Windows.Storage.Streams.DataReader($speechStream)
        $loaded = Wait-LocalOperation ($reader.LoadAsync([uint32]$speechStream.Size)) ([uint32])
        $bytes = New-Object byte[] $loaded
        $reader.ReadBytes($bytes)
        $audio = New-Object System.IO.MemoryStream(,$bytes)
        $player = New-Object System.Media.SoundPlayer($audio)
        $player.PlaySync()
    }
} catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
} finally {
    if ($player) { $player.Dispose() }
    if ($audio) { $audio.Dispose() }
    if ($reader) { $reader.Dispose() }
    if ($speechStream) { $speechStream.Dispose() }
    if ($synth) { $synth.Dispose() }
}
