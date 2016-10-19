function Get-ProgramDir([string]$dirname="Cloudbase Solutions") {
    $osArch = (Get-WmiObject Win32_OperatingSystem).OSArchitecture
    $programDirs = @($ENV:ProgramFiles)

    if($osArch -eq "64-bit")
    {
        $programDirs += ${ENV:ProgramFiles(x86)}
    }


    $ProgramFilesDir = 0
    foreach ($programDir in $programDirs)
    {
        if (Test-Path "$programDir\$dirname")
        {
            $ProgramFilesDir = $programDir
        }
    }
    if (!$ProgramFilesDir)
    {
        throw "$dirname not found."
    }

    return $ProgramFilesDir
}
