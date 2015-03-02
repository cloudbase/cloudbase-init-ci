function Get-ProgramDir() {
    $osArch = (Get-WmiObject Win32_OperatingSystem).OSArchitecture
    $programDirs = @($ENV:ProgramFiles)

    if($osArch -eq "64-bit")
    {
        $programDirs += ${ENV:ProgramFiles(x86)}
    }


    $ProgramFilesDir = 0
    foreach ($programDir in $programDirs)
    {
        if (Test-Path "$programDir\Cloudbase Solutions")
        {
            $ProgramFilesDir = $programDir
        }
    }
    if (!$ProgramFilesDir)
    {
        throw "Cloudbase-init installed files not found in $programDirs"
    }

    return $ProgramFilesDir
}
