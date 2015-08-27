param
(
    [string]$cloudbaseinitdir
)

$patch_code = @'
import os
from cloudbaseinit.original_shell import main
try:
    main()
finally:
    user_path = os.path.expanduser("~")
    finish_file = os.path.join(user_path, "cloudbaseinit_finished")
    with open(finish_file, "w") as stream:
        pass
'@

mv $cloudbaseinitdir\shell.py $cloudbaseinitdir\original_shell.py -ErrorAction ignore
rm $cloudbaseinitdir\shell.pyc -ErrorAction ignore
echo $patch_code | Out-File -Encoding utf8 $cloudbaseinitdir\shell.py
