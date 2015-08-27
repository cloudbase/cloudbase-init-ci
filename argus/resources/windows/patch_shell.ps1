param
(
    [string]$cloudbaseinitdir
)

$patch_code = @'
import os
from cloudbaseinit.original_shell import main

if __name__ == "__main__":
    try:
        main()
    finally:
        with open("C:\\cloudbaseinit_finished", "w") as stream:
           pass
'@

mv $cloudbaseinitdir\shell.py $cloudbaseinitdir\original_shell.py -ErrorAction ignore
rm $cloudbaseinitdir\shell.pyc -ErrorAction ignore
echo $patch_code | Out-File -Encoding utf8 $cloudbaseinitdir\shell.py
