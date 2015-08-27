param
(
    [string]$cloudbaseinitdir
)

$patch_code = @'
import os
from cloudbaseinit.original_shell import main

with open("C:\\cloudbaseinit_started", "w") as stream:
    pass
main()
'@

mv $cloudbaseinitdir\shell.py $cloudbaseinitdir\original_shell.py -ErrorAction ignore
rm $cloudbaseinitdir\shell.pyc -ErrorAction ignore
echo $patch_code | Out-File -Encoding utf8 $cloudbaseinitdir\shell.py
