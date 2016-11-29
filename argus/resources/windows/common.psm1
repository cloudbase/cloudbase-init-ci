function Get-ProgramDir([string]$dirname="Cloudbase Solutions") {
    $osArch = $ENV:PROCESSOR_ARCHITECTURE
    $programDirs = @($ENV:ProgramFiles)

    if($osArch -eq "AMD64")
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
